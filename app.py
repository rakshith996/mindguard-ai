import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps
from contextlib import contextmanager

import click
import mysql.connector
from dotenv import load_dotenv
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from analytics import build_student_trend, build_counsellor_aggregates, make_suggestions
from privacy_ops import withdraw_and_erase_student_data, permanently_delete_student
from workflow import can_transition, available_transitions, apply_status_transition
from rate_limit import (
    build_login_buckets, bucket_is_blocked, record_failed_login,
    clear_successful_account_bucket, clear_empty_bucket,
)

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
CONFIGURED_SECRET = os.getenv("SECRET_KEY", "").strip()
if APP_ENV == "production" and len(CONFIGURED_SECRET) < 32:
    raise RuntimeError("Production requires a SECRET_KEY containing at least 32 characters.")
if APP_ENV == "production" and os.getenv("COOKIE_SECURE", "0") != "1":
    raise RuntimeError("Production requires COOKIE_SECURE=1 and HTTPS.")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=CONFIGURED_SECRET or "development-only-change-this-secret",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_REFRESH_EACH_REQUEST=True,
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
)
CONSENT_VERSION = "1.0"
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32))


def db_connect():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "mindguard"),
        autocommit=False,
    )


@contextmanager
def db_cursor(dictionary=True):
    conn = db_connect()
    cur = conn.cursor(dictionary=dictionary)
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@app.before_request
def csrf_and_user():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    g.user = None
    if session.get("user_id"):
        try:
            with db_cursor() as (_, cur):
                cur.execute(
                    "SELECT id, display_name, login_id, role, consent_at, consent_version "
                    "FROM users WHERE id=%s AND is_active=1",
                    (session["user_id"],),
                )
                g.user = cur.fetchone()
        except mysql.connector.Error:
            # A database outage should not silently grant access.
            session.clear()
            if request.endpoint not in {"login", "register", "static", "health"}:
                flash("The database is temporarily unavailable. Please try again.", "error")
                return redirect(url_for("login"))
    if request.method == "POST":
        supplied = request.form.get("csrf_token", "")
        if not supplied or not secrets.compare_digest(supplied, session.get("csrf_token", "")):
            abort(400, description="Your form session expired. Refresh the page and try again.")


@app.after_request
def add_privacy_headers(response):
    """Reduce browser caching and add basic hardening headers."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"
    if app.config["SESSION_COOKIE_SECURE"]:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.context_processor
def inject_globals():
    return {"csrf_token": session.get("csrf_token", ""), "current_year": date.today().year, "today": date.today().isoformat()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def student_consent_required(view):
    @wraps(view)
    @role_required("student")
    def wrapped(*args, **kwargs):
        if not g.user["consent_at"]:
            return redirect(url_for("consent"))
        return view(*args, **kwargs)
    return wrapped


def safe_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@app.get("/health")
def health():
    return {"status": "ok", "service": "MindGuard AI prototype"}


@app.route("/", methods=["GET"])
def index():
    if not g.user:
        return redirect(url_for("login"))
    if g.user["role"] == "counsellor":
        return redirect(url_for("counsellor_dashboard"))
    if not g.user["consent_at"]:
        return redirect(url_for("consent"))
    return redirect(url_for("student_dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        login_id = request.form.get("login_id", "").strip().lower()
        password = request.form.get("password", "")
        if not display_name or len(display_name) > 80:
            flash("Enter a name (maximum 80 characters).", "error")
        elif not login_id or len(login_id) > 60 or not login_id.replace("_", "").replace("-", "").isalnum():
            flash("Use a student ID containing letters, numbers, hyphens or underscores.", "error")
        elif len(password) < 10:
            flash("Use a password with at least 10 characters.", "error")
        else:
            try:
                with db_cursor() as (_, cur):
                    cur.execute(
                        "INSERT INTO users (display_name, login_id, password_hash, role) "
                        "VALUES (%s,%s,%s,'student')",
                        (display_name, login_id, generate_password_hash(password)),
                    )
                flash("Account created. Please sign in and review the consent notice.", "success")
                return redirect(url_for("login"))
            except mysql.connector.IntegrityError:
                flash("That student ID is already registered.", "error")
            except mysql.connector.Error:
                flash("Could not create the account. Check the database setup and try again.", "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        raw_login_id = request.form.get("login_id", "").strip().lower()
        login_id = raw_login_id[:60]
        password = request.form.get("password", "")
        password_length_ok = len(password) <= 256
        password_for_check = password[:256]
        login_id_valid = (
            bool(raw_login_id) and len(raw_login_id) <= 60
            and raw_login_id.replace("_", "").replace("-", "").isalnum()
        )
        buckets = build_login_buckets(app.config["SECRET_KEY"], login_id, request.remote_addr)
        try:
            with db_cursor() as (_, cur):
                blocked = any(bucket_is_blocked(cur, bucket_hash, limit) for bucket_hash, limit in buckets)
                user = None
                if not blocked:
                    if login_id_valid:
                        cur.execute(
                            "SELECT id, password_hash, is_active FROM users WHERE login_id=%s",
                            (login_id,),
                        )
                        user = cur.fetchone()
                    # Perform one password-hash check even for unknown IDs to reduce
                    # account-enumeration timing differences.
                    hash_to_check = user["password_hash"] if user else DUMMY_PASSWORD_HASH
                    password_ok = check_password_hash(hash_to_check, password_for_check)
                    authenticated = bool(
                        login_id_valid and password_length_ok and user
                        and user["is_active"] and password_ok
                    )
                    if authenticated:
                        clear_successful_account_bucket(cur, buckets[0][0])
                        clear_empty_bucket(cur, buckets[1][0])
                    else:
                        for bucket_hash, limit in buckets:
                            record_failed_login(cur, bucket_hash, limit)
                else:
                    authenticated = False
            if blocked:
                flash("Too many unsuccessful sign-in attempts. Wait 15 minutes before trying again.", "error")
            elif authenticated:
                session.clear()
                session.permanent = True
                session["user_id"] = user["id"]
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("index"))
            else:
                flash("Invalid login ID or password.", "error")
        except mysql.connector.Error:
            flash("Cannot complete sign-in right now. Please try again shortly.", "error")
    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/consent", methods=["GET", "POST"])
@role_required("student")
def consent():
    if g.user["consent_at"]:
        return redirect(url_for("student_dashboard"))
    if request.method == "POST":
        if request.form.get("agree") != "yes":
            flash("You need to choose whether to agree. You can sign out if you do not wish to use the service.", "error")
        else:
            with db_cursor() as (_, cur):
                cur.execute(
                    "UPDATE users SET consent_at=NOW(), consent_version=%s WHERE id=%s",
                    (CONSENT_VERSION, g.user["id"]),
                )
            flash("Consent recorded. You can change your mind by contacting the project team to deactivate your account.", "success")
            return redirect(url_for("student_dashboard"))
    return render_template("consent.html", consent_version=CONSENT_VERSION)


@student_consent_required
def _student_home_data():
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id, mood, stress, sleep_hours, academic_pressure, created_at "
            "FROM checkins WHERE student_id=%s ORDER BY created_at DESC LIMIT 20",
            (g.user["id"],),
        )
        rows = cur.fetchall()
        cur.execute(
            "SELECT id, preferred_date, preferred_time, status, created_at "
            "FROM support_requests WHERE student_id=%s ORDER BY created_at DESC LIMIT 8",
            (g.user["id"],),
        )
        requests_list = cur.fetchall()
    trend = build_student_trend(list(reversed(rows)))
    return rows, requests_list, trend


@app.get("/student")
@student_consent_required
def student_dashboard():
    rows, requests_list, trend = _student_home_data()
    latest = rows[0] if rows else None
    suggestions = make_suggestions(latest["mood"], latest["stress"], float(latest["sleep_hours"]), latest["academic_pressure"]) if latest else []
    mood_scores = {"Great": 5, "Good": 4, "Okay": 3, "Low": 2, "Stressed": 1}
    chart_rows = [{"mood": r["mood"], "mood_score": mood_scores[r["mood"]], "stress": int(r["stress"]), "academic_pressure": int(r["academic_pressure"]), "sleep_hours": float(r["sleep_hours"]), "created_at": r["created_at"].isoformat()} for r in reversed(rows)]
    return render_template("student_dashboard.html", checkins=rows, chart_rows=chart_rows, support_requests=requests_list, trend=trend, suggestions=suggestions)


@app.post("/student/checkin")
@student_consent_required
def create_checkin():
    # Do not store the answer to the immediate-danger question. It only selects the safety page.
    if request.form.get("immediate_danger") == "yes":
        return redirect(url_for("urgent_support"))
    mood = request.form.get("mood", "")
    stress = request.form.get("stress", type=int)
    sleep = request.form.get("sleep_hours", type=float)
    pressure = request.form.get("academic_pressure", type=int)
    allowed_moods = {"Great", "Good", "Okay", "Low", "Stressed"}
    if mood not in allowed_moods or stress not in range(1, 6) or pressure not in range(1, 6):
        flash("Please complete the mood, stress and academic-pressure fields.", "error")
        return redirect(url_for("student_dashboard"))
    if sleep is None or not 0 <= sleep <= 24:
        flash("Enter sleep hours between 0 and 24.", "error")
        return redirect(url_for("student_dashboard"))
    with db_cursor() as (_, cur):
        cur.execute(
            "INSERT INTO checkins (student_id,mood,stress,sleep_hours,academic_pressure) "
            "VALUES (%s,%s,%s,%s,%s)",
            (g.user["id"], mood, stress, sleep, pressure),
        )
    flash("Your check-in was saved privately to your account.", "success")
    return redirect(url_for("student_dashboard"))


@app.get("/student/appointments")
@student_consent_required
def appointments():
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id, preferred_date, preferred_time, message, status, created_at "
            "FROM support_requests WHERE student_id=%s ORDER BY created_at DESC",
            (g.user["id"],),
        )
        items = cur.fetchall()
    return render_template("appointments.html", items=items)


@app.post("/student/appointments")
@student_consent_required
def create_appointment():
    preferred_date = safe_date(request.form.get("preferred_date"))
    preferred_time = request.form.get("preferred_time", "")
    message = request.form.get("message", "").strip()
    if not preferred_date or preferred_date < date.today():
        flash("Choose today or a future date.", "error")
    elif preferred_time not in {"Morning", "Afternoon", "Evening"}:
        flash("Choose a valid time preference.", "error")
    elif len(message) > 500:
        flash("Keep the optional message under 500 characters.", "error")
    else:
        with db_cursor() as (_, cur):
            cur.execute(
                "INSERT INTO support_requests (student_id,preferred_date,preferred_time,message) "
                "VALUES (%s,%s,%s,%s)",
                (g.user["id"], preferred_date, preferred_time, message or None),
            )
        flash("Your appointment request was sent to the counselling team.", "success")
        return redirect(url_for("appointments"))
    return redirect(url_for("appointments"))


@app.get("/student/privacy")
@role_required("student")
def student_privacy():
    """Show student-controlled privacy actions, including before consent."""
    return render_template("privacy.html")


@app.post("/student/privacy/withdraw")
@role_required("student")
def withdraw_student_consent():
    """Withdraw consent and erase this student's live prototype records."""
    if request.form.get("confirmation", "").strip() != "WITHDRAW":
        flash("Type WITHDRAW exactly to confirm this action.", "error")
        return redirect(url_for("student_privacy"))
    password = request.form.get("password", "")
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT password_hash FROM users WHERE id=%s AND role='student'", (g.user["id"],))
            account = cur.fetchone()
            if not account or not check_password_hash(account["password_hash"], password):
                flash("Password was not correct. No data was changed.", "error")
                return redirect(url_for("student_privacy"))
            withdraw_and_erase_student_data(cur, g.user["id"])
        flash("Consent withdrawn. Your check-ins and appointment requests were erased from the live prototype database. You can sign out or review consent again.", "success")
        return redirect(url_for("consent"))
    except mysql.connector.Error:
        flash("The database could not complete this request. No success was recorded; please try again.", "error")
        return redirect(url_for("student_privacy"))


@app.post("/student/privacy/delete-account")
@role_required("student")
def delete_student_account():
    """Re-authenticate and permanently delete the student's account and linked rows."""
    if request.form.get("confirmation", "").strip() != "DELETE":
        flash("Type DELETE exactly to confirm permanent account deletion.", "error")
        return redirect(url_for("student_privacy"))
    password = request.form.get("password", "")
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT password_hash FROM users WHERE id=%s AND role='student'", (g.user["id"],))
            account = cur.fetchone()
            if not account or not check_password_hash(account["password_hash"], password):
                flash("Password was not correct. No data was changed.", "error")
                return redirect(url_for("student_privacy"))
            deleted = permanently_delete_student(cur, g.user["id"])
            if deleted != 1:
                abort(404)
        session.clear()
        flash("Your account and linked records were deleted from the live prototype database.", "success")
        return redirect(url_for("login"))
    except mysql.connector.Error:
        flash("The database could not complete account deletion. Please try again.", "error")
        return redirect(url_for("student_privacy"))


@app.get("/urgent-support")
@role_required("student")
def urgent_support():
    return render_template("urgent_support.html")


@app.get("/counsellor")
@role_required("counsellor")
def counsellor_dashboard():
    with db_cursor() as (_, cur):
        # Identifiable information is limited to requests students intentionally sent for contact.
        cur.execute(
            "SELECT r.id, r.preferred_date, r.preferred_time, r.message, r.status, r.created_at, "
            "u.display_name, u.login_id "
            "FROM support_requests r JOIN users u ON u.id=r.student_id "
            "WHERE r.status IN ('pending','accepted') ORDER BY r.created_at ASC LIMIT 100"
        )
        requests_list = cur.fetchall()
        for item in requests_list:
            item["allowed_transitions"] = available_transitions(item["status"])
        # Minimal audit history: request reference and status transition only.
        # No student name, login ID, message, or check-in fields are selected.
        cur.execute(
            "SELECT e.support_request_id, e.previous_status, e.new_status, e.created_at, "
            "u.display_name AS counsellor_name "
            "FROM appointment_status_events e "
            "LEFT JOIN users u ON u.id=e.actor_user_id "
            "ORDER BY e.created_at DESC LIMIT 25"
        )
        status_history = cur.fetchall()
        # Fetch only fields needed for aggregate analysis; no names or login IDs are selected.
        cur.execute(
            "SELECT student_id, created_at, stress, sleep_hours, academic_pressure "
            "FROM checkins WHERE created_at >= NOW() - INTERVAL 30 DAY"
        )
        aggregate_source = cur.fetchall()
    aggregates = build_counsellor_aggregates(aggregate_source, minimum_students=5)
    return render_template(
        "counsellor_dashboard.html", requests_list=requests_list,
        aggregates=aggregates, status_history=status_history,
    )


@app.post("/counsellor/request/<int:request_id>/status")
@role_required("counsellor")
def update_request_status(request_id):
    requested_status = request.form.get("status", "")
    with db_cursor() as (_, cur):
        cur.execute("SELECT status FROM support_requests WHERE id=%s", (request_id,))
        current = cur.fetchone()
        if not current:
            abort(404)
        # The status update and audit insert share this transaction. If either
        # SQL operation fails, db_cursor rolls both back.
        result = apply_status_transition(
            cur, request_id, current["status"], requested_status, g.user["id"]
        )
        if result == "invalid":
            flash("That status change is not allowed. Refresh and choose an available next step.", "error")
            return redirect(url_for("counsellor_dashboard"))
        if result == "stale":
            flash("This request changed before your update was saved. Refresh and try again.", "error")
            return redirect(url_for("counsellor_dashboard"))
    flash("Request status updated and recorded in the counsellor audit history.", "success")
    return redirect(url_for("counsellor_dashboard"))


@app.cli.command("create-counsellor")
@click.option("--login-id", prompt="Counsellor login ID")
@click.option("--name", prompt="Counsellor display name")
def create_counsellor(login_id, name):
    """Create a counsellor account; the password is prompted without echoing."""
    password = click.prompt("Temporary password (at least 12 characters)", hide_input=True, confirmation_prompt=True)
    if len(password) < 12:
        raise click.ClickException("Password must contain at least 12 characters.")
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                "INSERT INTO users (display_name,login_id,password_hash,role,consent_at) "
                "VALUES (%s,%s,%s,'counsellor',NOW())",
                (name.strip(), login_id.strip().lower(), generate_password_hash(password)),
            )
        click.echo("Counsellor account created.")
    except mysql.connector.IntegrityError:
        raise click.ClickException("That login ID already exists.")


@app.cli.command("purge-expired-login-limits")
@click.option("--days", default=2, show_default=True, type=click.IntRange(min=1, max=30))
def purge_expired_login_limits(days):
    """Delete old opaque rate-limit buckets; run periodically as maintenance."""
    with db_cursor() as (_, cur):
        cur.execute(
            "DELETE FROM auth_rate_limit_buckets "
            f"WHERE updated_at < NOW() - INTERVAL {days} DAY "
            "AND (blocked_until IS NULL OR blocked_until < NOW())"
        )
        deleted = cur.rowcount
    click.echo(f"Removed {deleted} expired login-throttle records.")


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
