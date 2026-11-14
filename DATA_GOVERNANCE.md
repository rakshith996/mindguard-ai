# MindGuard AI — Data governance and safety checklist

## Data minimisation

- Collect only the check-in fields required for the student reflection experience.
- The immediate-danger selection is used only to route the browser to urgent-support guidance; it is not written to the database and does not notify staff.
- Appointment messages are optional and are shared with the counselling workflow only when the student submits a request.
- Do not add facial-expression, webcam, microphone, location, social-media, attendance, or academic-record collection without a separate necessity assessment and explicit institutional approval. Such signals must not be treated as mental-health evidence.

## Access boundaries

- Students may access their own check-ins and appointment requests.
- Counsellors may access support requests intentionally submitted by students and thresholded cohort summaries.
- General administrators must not be granted access to identifiable wellness records. There is no general-admin wellness dashboard in this prototype.
- Use a dedicated database account; restrict database network access and credentials.

## Retention and deletion

This release does not silently impose an automatic retention period. Before any real deployment, the institution must approve and publish a retention schedule for check-ins, appointment requests, audit events, authentication throttling records, database backups and exported files. Provide a documented deletion process for backups and exports too. Student withdrawal/deletion actions erase the applicable live database rows through application logic and foreign-key cascades; they cannot retroactively erase copies already exported or retained in backups.

## Safety

- The application is not monitored continuously and is not an emergency response service.
- Never interpret trend summaries as diagnosis, clinical risk scoring, or self-harm prediction.
- A student indicating immediate danger is directed to qualified human/emergency support. In India the page lists 112 and Tele-MANAS 14416. The application does not call these services or alert a counsellor automatically.
- A college deployment needs a written, staffed escalation protocol approved by qualified professionals. Do not promise response times unless the service is actually staffed to meet them.

## Before any real-student pilot

- [ ] Obtain institutional ethics, legal, IT-security and counselling approvals.
- [ ] Complete a privacy impact/risk assessment and publish a plain-language notice.
- [ ] Confirm the counsellor team, coverage hours, escalation process and emergency referrals.
- [ ] Enforce HTTPS, secure production secrets, database least privilege, backups and restore testing.
- [ ] Define retention periods and verified backup/export deletion procedures.
- [ ] Test role isolation, CSRF, session expiry, rate limits, deletion and recovery using a disposable MySQL database.
- [ ] Review cohort disclosure risk; a threshold of five is a basic suppression rule, not a formal anonymity guarantee.
- [ ] Provide accessible, language-appropriate alternatives and a non-digital route to support.
