# MindGuard AI — Increment 4 notes

## Added
- Calendar-time personal stress trend direction, only after at least five entries spanning 14 days.
- Repeated self-reported pattern observations in a 14-day window ending at the latest entry.
- Student chart with mood category display order, stress, academic pressure and sleep.
- Weekly counsellor aggregation that averages each student once per week, suppresses groups below five distinct students, rounds averages to half-points, and omits contributor counts.
- Appointment status state machine with compare-and-set SQL updates.

## Database migration
No schema change is required for increment 4. Existing `schema.sql` remains valid.

## Verification performed in this build environment
- 15 Python unit tests passed.
- Python syntax compilation passed for `app.py`, `analytics.py`, `privacy_ops.py`, `workflow.py`, and tests.
- All 9 Jinja templates parsed successfully.
- Flask/MySQL end-to-end routes were not run here because Flask and the MySQL connector are not installed in this build environment. Install `requirements.txt`, configure MySQL, then complete the manual checklist in `README.md`.

## Safety note
All patterns are descriptive prompts based on voluntary self-reports. They are not diagnoses, forecasts, clinical risk scores, or automatic alerts. The urgent-support route remains a separate human-support pathway.
