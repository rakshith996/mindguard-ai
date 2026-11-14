# MindGuard AI — Flask + MySQL prototype (increment 6)

This increment adds **database-backed login throttling and additional web-security defaults** to the student/counsellor workflows, privacy controls, analytics, and appointment audit history.

## What is included

- Student registration and sign-in with Werkzeug password hashing.
- A separate consent screen before any wellness check-in is accepted.
- Daily self-report fields: mood, stress, sleep hours, academic pressure.
- A safety question that is **not stored**. If the student selects immediate danger, the app opens a human-support page rather than calculating a score or claiming to alert anyone.
- Personal trend summaries using pandas and scikit-learn linear regression against elapsed calendar days. They require at least three entries for a summary and five entries spanning at least two weeks for a simple direction label. Repeated high self-reported patterns are described to the student only; no score or diagnosis is produced.
- Rule-based, non-clinical suggestions based on the student's own latest check-in.
- Appointment requests. The counsellor sees the identity and optional message only for requests the student intentionally submitted.
- A counsellor dashboard that shows no individual check-ins. Weekly groups are suppressed unless at least five distinct students contributed. Each student is averaged once per week, cohort values are rounded to half-points, and contributor counts are not displayed.
- Counsellor request statuses follow a controlled workflow: pending → accepted/declined; accepted → completed/declined. Compare-and-set SQL updates guard against stale concurrent changes.
- CSRF tokens on HTML POST forms, parameterized SQL, role checks, password hashing, and HTTP-only session cookies.
- Database-backed sign-in throttling: five failures per login/IP pair or 60 failures per source IP within a 15-minute window. Only HMAC fingerprints are stored; raw login IDs and IP addresses are not written to the throttle table.
- Session cookies expire after eight hours of inactivity; successful login rotates the session and marks it permanent. HTML responses are sent with `Cache-Control: no-store`; additional browser security headers are set.

## Project structure

```text
mindguard_fullstack/
├── app.py
├── analytics.py
├── privacy_ops.py
├── workflow.py
├── rate_limit.py
├── migrations/
│   ├── 005_appointment_status_events.sql
│   └── 006_login_rate_limits.sql
├── schema.sql
├── requirements.txt
├── .env.example
├── README.md
├── INCREMENT_6_NOTES.md
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── consent.html
│   ├── privacy.html
│   ├── student_dashboard.html
│   ├── appointments.html
│   ├── urgent_support.html
│   └── counsellor_dashboard.html
├── static/style.css
└── tests/
    ├── test_analytics.py
    ├── test_privacy_ops.py
    ├── test_workflow.py
    └── test_rate_limit.py
```

## 1. Requirements

- Python 3.10 or 3.11
- MySQL Server 8.0+
- VS Code (recommended)

Open a terminal in this folder.

### Windows PowerShell

```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation for this terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`. Set a long random `SECRET_KEY`, and the MySQL username/password you will create next. Keep `.env` private; do not commit it to GitHub.

## 2. Create the MySQL database and restricted application user

Open MySQL Workbench or the MySQL command line as a database administrator and run `schema.sql` first. Then create a dedicated app user (replace the password):

```sql
CREATE USER 'mindguard_app'@'localhost' IDENTIFIED BY 'use-a-strong-unique-password';
GRANT SELECT, INSERT, UPDATE, DELETE ON mindguard.* TO 'mindguard_app'@'localhost';
FLUSH PRIVILEGES;
```

Put the same username and password in `.env` (`MYSQL_USER`, `MYSQL_PASSWORD`). If Flask connects over TCP using `127.0.0.1` and MySQL account host matching differs on your setup, create the account for the matching host as well or change `MYSQL_HOST` to `localhost`.

## 3. Start the application

```powershell
python app.py
```

Open **http://127.0.0.1:5000**. Register a student account, sign in, and review the consent screen. A student account cannot submit a check-in before consent.

For local development only, Flask's built-in server is used. Do not expose it to the public internet.

## 4. Create a counsellor account

In a second terminal, activate the same virtual environment and run:

```powershell
flask --app app create-counsellor
```

Enter a staff login ID, display name, and a temporary password when prompted. The password is hidden while typing. Then sign out of the student account and sign in with the counsellor account. Counsellor accounts are created by this CLI command, not by public registration.

## 5. Upgrade an existing Increment 5 database

If you already have the Increment 5 database, execute `migrations/006_login_rate_limits.sql` once in MySQL Workbench against the `mindguard` database. A fresh installation gets the table from `schema.sql`. Do not drop or recreate the existing database.

The login throttle uses two temporary buckets: five failed attempts for the same login ID and source IP, and 60 failed attempts from one source IP, each within a 15-minute window. A blocked attempt receives a generic wait message. The table stores HMAC-SHA256 fingerprints keyed with `SECRET_KEY`, not raw login IDs or IP addresses. Keep `SECRET_KEY` stable; changing it invalidates existing throttle fingerprints. Requests behind a shared college NAT can contribute to the IP-wide threshold, so review/tune the limit before campus-wide use. The app does not trust `X-Forwarded-For`; if deployed behind a reverse proxy, configure trusted proxy handling explicitly before relying on client IP throttling.

To clean up old opaque buckets periodically, run:

```powershell
flask --app app purge-expired-login-limits --days 2
```

The command removes only old, no-longer-blocked throttle records. It does not touch student accounts, check-ins, appointments, or audit history.

For production-like configuration, set `APP_ENV=production`, use a random `SECRET_KEY` of at least 32 characters, serve the app over HTTPS, and set `COOKIE_SECURE=1`. The app refuses to start in production mode if those minimum settings are missing. This is still not a production deployment recipe: use a production WSGI server, TLS termination, secret management, monitoring, and a security review.

## 6. Quick verification checklist

1. Register two student accounts and sign in separately.
2. Confirm a new student sees the consent page and cannot open the dashboard before accepting.
3. Submit a check-in and verify it appears in that student's dashboard only.
4. Open Privacy settings, enter the correct password and type `WITHDRAW`; verify check-ins and appointment requests are removed and the student is returned to the consent screen. Sign in again and test that student features require consent.
5. Create a fresh test student, then use Privacy settings with the correct password and type `DELETE`; verify the account no longer authenticates and linked rows are removed by the foreign-key cascades.
6. Submit an appointment request; confirm it appears for that student and in the counsellor request list.
7. As counsellor, confirm there is no route or table showing individual check-in history.
8. Add check-ins from fewer than five distinct students in a week: that week should be suppressed. With five or more students, only rounded weekly averages should appear; contributor counts are intentionally not displayed.
9. Select the immediate-danger option in the safety question. It should navigate to urgent support; that answer is not written to the database and no automated alert is claimed.
10. As counsellor, verify a pending request can move to accepted or declined, an accepted request can move to completed or declined, and terminal statuses cannot be reopened.
11. Run the unit tests:

```powershell
python -m unittest discover -s tests -v
```

## 7. Safety, privacy and project limitations

- This is an educational prototype, not a clinical product. It does not diagnose, predict, treat, or assign mental-health risk scores.
- A pattern such as repeated high stress is only a descriptive indicator that may help a student reflect or voluntarily seek support.
- The urgent-support page does not contact a counsellor, emergency service, or trusted person. The student must connect with a qualified human. In India, emergency services: **112**; Tele-MANAS: **14416**.
- Check-ins are visible to the student. Counsellors see appointment requests voluntarily sent to them and cohort aggregates with a minimum group size of five. No general-admin role is implemented. Students can withdraw consent (which erases live check-ins and appointment requests) or permanently delete their account after password re-authentication.
- The app does not provide email verification, password reset, automated student-data retention, a general-purpose security audit log, HTTPS hosting, or institutional SSO. It does record the minimal appointment status transitions described below. Account deletion and consent withdrawal remove records from the live database, but do not automatically purge database backups or information already copied outside the app. Add backup-retention procedures and complete a security/privacy/ethics review before any real student deployment.
- Use TLS and set `COOKIE_SECURE=1` behind HTTPS in production. Replace the development server with a production WSGI server. Use secrets management for credentials.
- MySQL stores mood/stress/sleep/pressure values. Do not add free-text diary content or face photos to this database. Restrict database backups and access.
- Chart.js and Google Fonts are loaded from CDNs; an offline deployment should vendor these assets locally.

## 8. Student privacy controls (increment 3)

- Open **Privacy settings** from the student sidebar, including before accepting consent.
- **Withdraw consent** requires the current password and the exact confirmation word `WITHDRAW`. In one MySQL transaction it deletes that student's check-ins and appointment requests, then clears `consent_at` and `consent_version`. The account remains and must consent again before using student features.
- **Delete account** requires the current password and exact confirmation word `DELETE`. It deletes the student row; the schema's `ON DELETE CASCADE` foreign keys delete linked check-ins and support requests.
- Both actions affect the live prototype database only. They cannot recall information already viewed/copied by a counsellor or automatically erase database backups. For a real deployment, define and enforce a backup-retention/deletion process.
- Authenticated responses use `Cache-Control: no-store`; basic `nosniff`, frame-denial and referrer-policy headers are also added. These are defense-in-depth, not a complete production security review.

The `test_privacy_ops.py` checks the SQL operation sequence using a fake cursor. It does **not** prove MySQL cascade behavior; complete the manual MySQL verification above. The analytics and appointment workflow tests are pure unit tests; the full Flask/MySQL routes still need local integration testing.

## SDG alignment

- **SDG 3 — Good Health and Well-being:** encourages reflection and connection to qualified support.
- **SDG 4 — Quality Education:** recognises that academic pressure and student wellbeing can affect learning.
- **SDG 10 — Reduced Inequalities:** supports an accessible, low-barrier route to request support; production work should include language and accessibility testing.
- **SDG 16 — Peace, Justice and Strong Institutions:** supports privacy-conscious processes and controlled access to sensitive information.


## 9. Trend and counsellor workflow improvements (increment 4)

- Student trend direction is fitted against elapsed calendar days, not just row order. A direction label is shown only with at least five entries spanning at least 14 days.
- Repeated high self-reported stress, academic pressure, or short-sleep entries are described to the student when at least three relevant entries occur in the 14-day window ending with their latest check-in. This is a reflection prompt, not an alert, diagnosis, forecast, or clinical risk score.
- The student chart now plots their own mood category display order, stress, academic pressure, and sleep hours. The mood category is ordinal only for visualization and is not a validated psychological scale.
- Counsellor cohort summaries first average each student's entries within each week, so a student who checks in more often does not get extra weight. A week must contain at least five distinct students. Values are rounded to half-points and contributor counts are omitted.
- Appointment statuses use a finite workflow. Pending requests can be accepted or declined; accepted requests can be completed or declined; completed and declined requests are terminal. SQL compare-and-set updates prevent stale status submissions from overwriting a newer state.
- A group-size threshold is only a small-cohort safeguard. It does not provide formal anonymity or prevent every possible inference. For real deployment, use a privacy review, suppress more granular slices, restrict exports, and consider formal statistical disclosure controls.

### Increment 4 verification

The new unit tests cover time-span requirements for personal trends, repeated-pattern descriptions, per-week cohort suppression, per-student weighting, the minimum k=5 threshold, and allowed appointment transitions. Run them with the command in section 5.


## 10. Appointment audit history (increment 5)

The counsellor appointment workflow now records each successful status transition in `appointment_status_events`. The status update and audit insert run in the same MySQL transaction: if the audit insert fails, the status update is rolled back. The event contains only the support-request reference, counsellor account reference, previous status, new status, and timestamp. It does not copy the student's appointment message or any check-in/wellness values.

### Existing database upgrade

If you already installed Increment 4, open MySQL Workbench and execute:

```sql
SOURCE /full/path/to/mindguard_fullstack/migrations/005_appointment_status_events.sql;
```

Replace the path with the actual path on your computer. Alternatively, open the migration file in Workbench and execute its contents. For a brand-new database, the updated `schema.sql` creates this table automatically.

The counsellor dashboard shows the latest 25 status changes without showing the student's name, login ID, appointment message, or wellness history in that history table. Events are removed automatically when the associated support request is erased (for example, on consent withdrawal or account deletion). If a counsellor account is deleted, its actor reference becomes NULL while the event remains for the still-existing request.

Run the unit tests after updating:

```powershell
python -m unittest discover -s tests -v
```

### Increment 5 verification boundary

Unit tests verify the transition helper's SQL sequence and that invalid/stale transitions do not create audit events. They do not replace a live MySQL integration test. After applying the migration, create a test appointment, change its status as a counsellor, and verify one corresponding row appears in `appointment_status_events`. Then withdraw the test student's consent and verify the linked support request and its audit events are deleted.


## 11. Login throttling and security hardening (increment 6)

- Login attempts are throttled using MySQL rows in `auth_rate_limit_buckets`. The first bucket allows at most five failures for a login-ID/source-IP pair per 15-minute window; the second allows at most 60 failures per source IP per 15-minute window.
- Bucket keys are HMAC-SHA256 fingerprints made with the application `SECRET_KEY`. Raw login IDs and source IP addresses are not stored in this table. The account/IP bucket is cleared after successful sign-in; the IP-wide counter is not cleared by one successful user.
- Unknown IDs use a precomputed dummy password hash check to reduce obvious account-enumeration timing differences. This is a mitigation, not a formal constant-time guarantee.
- Successful sign-in rotates the session, marks it permanent, and uses an eight-hour lifetime. HTML responses use `Cache-Control: no-store`; additional browser security headers are set. HSTS is emitted only when secure cookies are enabled.
- `purge-expired-login-limits` removes old, inactive throttle rows. It is a maintenance command and should be scheduled by the operator if desired.
- Existing Increment 5 databases must execute `migrations/006_login_rate_limits.sql` once. Fresh databases use the updated `schema.sql`.

### Increment 6 verification boundary

The new unit tests cover deterministic and non-reversible fingerprint behavior, separation by source IP/secret, thresholds, active blocks, and window reset decisions. They do not prove MySQL row-lock behavior or Flask login-route behavior. Verify those locally with a dedicated test database: make five invalid attempts for one login/IP pair, confirm the sixth is throttled, wait for the 15-minute window to expire (or use a disposable test environment with a shorter test-only window), then confirm a correct login succeeds. Also verify that the rate-limit table contains only 64-character hexadecimal digests and no raw login IDs or IP addresses.
