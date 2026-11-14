"""Privacy-conscious database-backed login throttling.

Only HMAC fingerprints are persisted; raw login IDs and IP addresses are not.
The account/IP bucket reduces repeated guessing against one account from one
source, while the IP bucket slows broad password spraying from one address.
"""

import hashlib
import hmac

WINDOW_MINUTES = 15
ACCOUNT_IP_MAX_FAILURES = 5
IP_MAX_FAILURES = 60


def _fingerprint(secret_key, scope, value):
    key = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
    message = f"{scope}\0{value}".encode("utf-8", errors="replace")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def build_login_buckets(secret_key, login_id, remote_addr):
    """Return (opaque digest, max failures) buckets for one login attempt."""
    normalized_login = (login_id or "").strip().lower()[:60]
    address = (remote_addr or "unknown")[:100]
    return (
        (_fingerprint(secret_key, "account-ip", normalized_login + "\0" + address), ACCOUNT_IP_MAX_FAILURES),
        (_fingerprint(secret_key, "ip", address), IP_MAX_FAILURES),
    )


def evaluate_bucket(failure_count, window_expired, currently_blocked, limit):
    """Pure decision helper; returns (should_block, should_reset_window)."""
    if currently_blocked:
        return True, False
    if window_expired:
        return False, True
    return int(failure_count) >= int(limit), False


def _ensure_bucket(cur, bucket_hash):
    cur.execute(
        "INSERT IGNORE INTO auth_rate_limit_buckets "
        "(bucket_hash, failure_count, window_started_at, updated_at) "
        "VALUES (%s,0,NOW(),NOW())",
        (bucket_hash,),
    )


def bucket_is_blocked(cur, bucket_hash, limit):
    """Lock/read one bucket and reset it when its 15-minute window expires."""
    _ensure_bucket(cur, bucket_hash)
    cur.execute(
        "SELECT failure_count, "
        f"(window_started_at <= NOW() - INTERVAL {WINDOW_MINUTES} MINUTE) AS window_expired, "
        "(blocked_until IS NOT NULL AND blocked_until > NOW()) AS currently_blocked "
        "FROM auth_rate_limit_buckets WHERE bucket_hash=%s FOR UPDATE",
        (bucket_hash,),
    )
    row = cur.fetchone()
    blocked, reset = evaluate_bucket(
        row["failure_count"], bool(row["window_expired"]),
        bool(row["currently_blocked"]), limit,
    )
    if reset:
        cur.execute(
            "UPDATE auth_rate_limit_buckets SET failure_count=0, "
            "window_started_at=NOW(), blocked_until=NULL, updated_at=NOW() "
            "WHERE bucket_hash=%s",
            (bucket_hash,),
        )
    return blocked


def record_failed_login(cur, bucket_hash, limit):
    """Atomically add a failed attempt and temporarily block at the threshold."""
    _ensure_bucket(cur, bucket_hash)
    cur.execute(
        "SELECT failure_count, "
        f"(window_started_at <= NOW() - INTERVAL {WINDOW_MINUTES} MINUTE) AS window_expired "
        "FROM auth_rate_limit_buckets WHERE bucket_hash=%s FOR UPDATE",
        (bucket_hash,),
    )
    row = cur.fetchone()
    count = 0 if row["window_expired"] else int(row["failure_count"])
    count += 1
    reset_window = bool(row["window_expired"])
    if reset_window:
        cur.execute(
            "UPDATE auth_rate_limit_buckets SET failure_count=%s, window_started_at=NOW(), "
            f"blocked_until=IF(%s >= %s, DATE_ADD(NOW(), INTERVAL {WINDOW_MINUTES} MINUTE), NULL), "
            "updated_at=NOW() WHERE bucket_hash=%s",
            (count, count, limit, bucket_hash),
        )
    else:
        cur.execute(
            "UPDATE auth_rate_limit_buckets SET failure_count=%s, "
            f"blocked_until=IF(%s >= %s, DATE_ADD(NOW(), INTERVAL {WINDOW_MINUTES} MINUTE), NULL), "
            "updated_at=NOW() WHERE bucket_hash=%s",
            (count, count, limit, bucket_hash),
        )


def clear_successful_account_bucket(cur, bucket_hash):
    """Clear only the account/IP bucket after successful authentication."""
    cur.execute(
        "DELETE FROM auth_rate_limit_buckets WHERE bucket_hash=%s",
        (bucket_hash,),
    )


def clear_empty_bucket(cur, bucket_hash):
    """Remove a zero-failure bucket created by a successful sign-in check."""
    cur.execute(
        "DELETE FROM auth_rate_limit_buckets WHERE bucket_hash=%s AND failure_count=0",
        (bucket_hash,),
    )
