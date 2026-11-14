import unittest
from workflow import can_transition, available_transitions, apply_status_transition


class FakeCursor:
    def __init__(self, update_rowcount=1):
        self.calls = []
        self.rowcount = update_rowcount

    def execute(self, sql, params):
        self.calls.append((" ".join(sql.split()), params))


class AppointmentWorkflowTests(unittest.TestCase):
    def test_pending_can_be_accepted_or_declined(self):
        self.assertTrue(can_transition("pending", "accepted"))
        self.assertTrue(can_transition("pending", "declined"))
        self.assertEqual(available_transitions("pending"), ["accepted", "declined"])

    def test_accepted_can_be_completed_or_declined(self):
        self.assertTrue(can_transition("accepted", "completed"))
        self.assertTrue(can_transition("accepted", "declined"))
        self.assertFalse(can_transition("accepted", "pending"))

    def test_terminal_statuses_cannot_be_reopened(self):
        for status in ("declined", "completed"):
            self.assertEqual(available_transitions(status), [])
            self.assertFalse(can_transition(status, "accepted"))

    def test_unknown_status_is_rejected(self):
        self.assertFalse(can_transition("unknown", "completed"))

    def test_valid_transition_updates_and_writes_minimal_audit_event(self):
        cur = FakeCursor(update_rowcount=1)
        result = apply_status_transition(cur, 81, "pending", "accepted", 12)
        self.assertEqual(result, "updated")
        self.assertEqual(len(cur.calls), 2)
        self.assertIn("UPDATE support_requests", cur.calls[0][0])
        self.assertIn("INSERT INTO appointment_status_events", cur.calls[1][0])
        self.assertEqual(cur.calls[1][1], (81, 12, "pending", "accepted"))

    def test_invalid_transition_does_not_write(self):
        cur = FakeCursor()
        self.assertEqual(apply_status_transition(cur, 81, "completed", "accepted", 12), "invalid")
        self.assertEqual(cur.calls, [])

    def test_concurrent_stale_transition_does_not_write_audit(self):
        cur = FakeCursor(update_rowcount=0)
        self.assertEqual(apply_status_transition(cur, 81, "pending", "accepted", 12), "stale")
        self.assertEqual(len(cur.calls), 1)
        self.assertIn("UPDATE support_requests", cur.calls[0][0])


if __name__ == "__main__":
    unittest.main()
