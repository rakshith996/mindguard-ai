# MindGuard AI — Increment 5 notes

## Added
- Minimal audit history for successful counsellor appointment status transitions.
- Status update and audit insert share one database transaction.
- Counsellor dashboard shows up to 25 recent status changes without student names, login IDs, messages, or wellness values in the history section.
- New MySQL migration: `migrations/005_appointment_status_events.sql`.
- Unit tests cover successful audit writes, invalid transitions, and stale compare-and-set updates.

## Database upgrade
- Existing Increment 4 installations must execute `migrations/005_appointment_status_events.sql` once.
- Fresh installations can use the updated `schema.sql`.

## Privacy behavior
- Audit events are tied to the support request and cascade-delete when that request is erased.
- Counsellor actor references become NULL if the counsellor account is deleted.
- No student wellness or appointment message content is copied into the audit event.

## Verification boundary
- Unit tests and static checks should be run with the README command.
- A live MySQL migration, transaction rollback, foreign-key cascade, and full Flask route test still require a configured MySQL server and installed Flask dependencies.
