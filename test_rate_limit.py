import unittest

from rate_limit import (
    ACCOUNT_IP_MAX_FAILURES,
    IP_MAX_FAILURES,
    WINDOW_MINUTES,
    build_login_buckets,
    evaluate_bucket,
    bucket_is_blocked,
    record_failed_login,
    clear_empty_bucket,
)


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row


class LoginRateLimitTests(unittest.TestCase):
    def test_bucket_fingerprints_are_deterministic(self):
        first = build_login_buckets("test-secret", "Student_01", "192.0.2.10")
        second = build_login_buckets("test-secret", "student_01", "192.0.2.10")
        self.assertEqual(first, second)

    def test_raw_login_id_and_ip_are_not_stored_in_fingerprints(self):
        login_id = "rakshith_123"
        address = "203.0.113.44"
        buckets = build_login_buckets("test-secret", login_id, address)
        for fingerprint, _ in buckets:
            self.assertEqual(len(fingerprint), 64)
            self.assertNotIn(login_id, fingerprint)
            self.assertNotIn(address, fingerprint)

    def test_different_ip_gets_different_account_and_ip_buckets(self):
        first = build_login_buckets("test-secret", "student7", "192.0.2.1")
        second = build_login_buckets("test-secret", "student7", "192.0.2.2")
        self.assertNotEqual(first[0][0], second[0][0])
        self.assertNotEqual(first[1][0], second[1][0])

    def test_different_secret_changes_fingerprints(self):
        first = build_login_buckets("secret-a", "student7", "192.0.2.1")
        second = build_login_buckets("secret-b", "student7", "192.0.2.1")
        self.assertNotEqual(first, second)

    def test_limits_are_conservative_and_explicit(self):
        self.assertEqual(ACCOUNT_IP_MAX_FAILURES, 5)
        self.assertEqual(IP_MAX_FAILURES, 60)
        self.assertEqual(WINDOW_MINUTES, 15)

    def test_below_limit_does_not_block(self):
        blocked, reset = evaluate_bucket(4, False, False, 5)
        self.assertFalse(blocked)
        self.assertFalse(reset)

    def test_limit_reached_blocks(self):
        blocked, reset = evaluate_bucket(5, False, False, 5)
        self.assertTrue(blocked)
        self.assertFalse(reset)

    def test_expired_window_resets_bucket(self):
        blocked, reset = evaluate_bucket(60, True, False, 60)
        self.assertFalse(blocked)
        self.assertTrue(reset)

    def test_active_block_takes_precedence_over_window_reset(self):
        blocked, reset = evaluate_bucket(60, True, True, 60)
        self.assertTrue(blocked)
        self.assertFalse(reset)

    def test_bucket_is_blocked_uses_locked_row_and_returns_active_block(self):
        cur = FakeCursor({"failure_count": 5, "window_expired": 0, "currently_blocked": 1})
        self.assertTrue(bucket_is_blocked(cur, "a" * 64, 5))
        self.assertIn("FOR UPDATE", cur.calls[1][0])
        self.assertEqual(len(cur.calls), 2)

    def test_expired_bucket_is_reset(self):
        cur = FakeCursor({"failure_count": 9, "window_expired": 1, "currently_blocked": 0})
        self.assertFalse(bucket_is_blocked(cur, "b" * 64, 5))
        self.assertIn("failure_count=0", cur.calls[2][0])

    def test_failed_login_increments_and_sets_temporary_block_at_limit(self):
        cur = FakeCursor({"failure_count": 4, "window_expired": 0})
        record_failed_login(cur, "c" * 64, 5)
        self.assertIn("DATE_ADD(NOW(), INTERVAL 15 MINUTE)", cur.calls[2][0])
        self.assertEqual(cur.calls[2][1], (5, 5, 5, "c" * 64))

    def test_failed_login_starts_a_new_window_after_expiry(self):
        cur = FakeCursor({"failure_count": 50, "window_expired": 1})
        record_failed_login(cur, "d" * 64, 5)
        self.assertIn("window_started_at=NOW()", cur.calls[2][0])
        self.assertEqual(cur.calls[2][1], (1, 1, 5, "d" * 64))

    def test_success_cleanup_only_removes_empty_ip_bucket(self):
        cur = FakeCursor({})
        clear_empty_bucket(cur, "e" * 64)
        self.assertIn("failure_count=0", cur.calls[0][0])
        self.assertEqual(cur.calls[0][1], ("e" * 64,))


if __name__ == "__main__":
    unittest.main()
