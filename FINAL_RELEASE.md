# MindGuard AI — Final College Prototype Release

**Release:** 1.0 (consolidated from development increments 2–6)  
**Stack:** HTML, CSS, JavaScript, Flask, MySQL, pandas, scikit-learn, Chart.js

## Included modules

- Student registration, password hashing, login and role checks
- Versioned consent notice and CSRF protection
- Daily mood, stress, sleep and academic-pressure check-ins
- Student-only longitudinal trend summaries and non-clinical suggestions
- Student appointment requests
- Counsellor request workflow with controlled status transitions and minimal audit history
- Cohort summaries suppressed below five distinct contributors
- Student consent withdrawal and account deletion
- HMAC-fingerprinted login throttling
- Urgent-support page with India emergency and Tele-MANAS contact routes

## Fresh installation

1. Install Python 3.10+ and MySQL 8+.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   python -m venv .venv
   # Windows PowerShell: .venv\\Scripts\\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

4. In MySQL Workbench, execute `schema.sql` using a database administrator account. For deployment, create a dedicated MySQL application user with only the permissions needed on the `mindguard` schema; do not run Flask as MySQL root.
5. Copy `.env.example` to `.env` and configure `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, and a long random `SECRET_KEY`.
6. Start the app:

   ```bash
   python app.py
   ```

7. Visit `http://127.0.0.1:5000`, register a student, and review consent. Create the counsellor account from a terminal:

   ```bash
   flask --app app create-counsellor
   ```

## Upgrade from Increment 6

No schema change is needed for this consolidated release. Keep the existing database and `.env`; extract this release into a new folder, install requirements, and start the app. Do not execute `schema.sql` as a substitute for a backup. `CREATE TABLE IF NOT EXISTS` preserves existing tables, but always back up first.

## Tests and verification

Run from this directory:

```bash
python -m pytest -q
python -m compileall -q .
```

The automated unit tests cover analytics, privacy helper operations, appointment transitions, and login-throttling helpers. They do **not** replace live MySQL integration tests. Before demonstration, verify registration, login, consent, check-ins, student-to-student access denial, counsellor-only routes, appointment status changes, withdrawal and account deletion against a disposable test database.

## Important deployment boundary

This is a college-level demonstration prototype, not a clinical product or production-ready student information system. Do not upload real student mental-health data or deploy campus-wide without institutional approval, a qualified counsellor-led safety protocol, a documented privacy notice, access reviews, HTTPS, secure secrets, backups, retention/deletion procedures, incident response, and legal/privacy review. Trend indicators are descriptive and non-diagnostic. No machine-learning output establishes clinical accuracy or predicts self-harm.
