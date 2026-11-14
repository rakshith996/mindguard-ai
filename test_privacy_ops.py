import unittest
from privacy_ops import withdraw_and_erase_student_data, permanently_delete_student

class FakeCursor:
    def __init__(self, rowcount=1):
        self.calls = []
        self.rowcount = rowcount
    def execute(self, sql, params):
        self.calls.append((" ".join(sql.split()), params))

class PrivacyOperationTests(unittest.TestCase):
    def test_withdraw_erases_both_record_types_then_clears_consent(self):
        cur = FakeCursor()
        withdraw_and_erase_student_data(cur, 42)
        self.assertEqual(len(cur.calls), 3)
        self.assertIn("DELETE FROM checkins", cur.calls[0][0])
        self.assertIn("DELETE FROM support_requests", cur.calls[1][0])
        self.assertIn("UPDATE users SET consent_at=NULL, consent_version=NULL", cur.calls[2][0])
        self.assertTrue(all(call[1] == (42,) for call in cur.calls))

    def test_account_deletion_targets_student_role(self):
        cur = FakeCursor(rowcount=1)
        self.assertEqual(permanently_delete_student(cur, 7), 1)
        self.assertEqual(cur.calls, [("DELETE FROM users WHERE id=%s AND role='student'", (7,))])

    def test_missing_account_is_reported(self):
        cur = FakeCursor(rowcount=0)
        self.assertEqual(permanently_delete_student(cur, 999), 0)

if __name__ == "__main__":
    unittest.main()
