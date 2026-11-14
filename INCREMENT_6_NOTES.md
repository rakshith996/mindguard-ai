# MindGuard AI — Increment 6 notes

## Added
- Database-backed sign-in throttling with two 15-minute buckets: five failed attempts per login-ID/source-IP pair and 60 failed attempts per source IP.
- HMAC-SHA256 fingerprints only; raw login IDs and IP addresses are not persisted in the throttle table.
- Successful login clears the matching account/IP bucket, rotates the session, and starts an eight-hour session lifetime.
- Unknown login IDs use a precomputed dummy password-hash check to reduce account-enumeration timing differences.
- Additional browser security headers, no-store HTML responses, optional HSTS, and production-mode startup checks for a strong secret and secure cookies.
- Maintenance command `flask --app app purge-expired-login-limits --days 2`.

## Database upgrade
- Existing Increment 5 installations must execute `migrations/006_login_rate_limits.sql` once.
- New installations receive `auth_rate_limit_buckets` from the updated `schema.sql`.

## Verification boundary
- New pure unit tests cover fingerprint generation and throttle decisions.
- The actual MySQL row-lock behavior, Flask login endpoint, and shared-NAT behavior still require local integration tests with a configured MySQL database.
- The IP-wide limit can affect users sharing a college NAT; tune it after observing real traffic. Do not trust forwarded IP headers unless a trusted reverse-proxy configuration is in place.
