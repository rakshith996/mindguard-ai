"""Allowed appointment-request status transitions."""

ALLOWED_TRANSITIONS = {
    "pending": {"accepted", "declined"},
    "accepted": {"completed", "declined"},
    "declined": set(),
    "completed": set(),
}


def can_transition(current_status, requested_status):
    """Return True only for an explicitly allowed counsellor workflow step."""
    return requested_status in ALLOWED_TRANSITIONS.get(current_status, set())


def available_transitions(current_status):
    """Stable, sorted list for the counsellor form."""
    return sorted(ALLOWED_TRANSITIONS.get(current_status, set()))


def apply_status_transition(cur, request_id, current_status, requested_status, actor_user_id):
    """Apply a compare-and-set transition and append a minimal audit event.

    The caller must run this inside one database transaction. The event stores
    only the request reference, counsellor account reference, and status change;
    it never copies the student's message or check-in information.

    Returns one of: "invalid", "stale", or "updated".
    """
    if not can_transition(current_status, requested_status):
        return "invalid"

    cur.execute(
        "UPDATE support_requests SET status=%s WHERE id=%s AND status=%s",
        (requested_status, request_id, current_status),
    )
    if cur.rowcount != 1:
        return "stale"

    cur.execute(
        "INSERT INTO appointment_status_events "
        "(support_request_id, actor_user_id, previous_status, new_status) "
        "VALUES (%s,%s,%s,%s)",
        (request_id, actor_user_id, current_status, requested_status),
    )
    return "updated"
