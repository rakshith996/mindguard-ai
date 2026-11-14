"""Database operations for student-controlled consent withdrawal and erasure.

The caller must authenticate the student and run these statements inside the
project's transaction context manager. MySQL foreign keys cascade user deletion.
"""

def withdraw_and_erase_student_data(cursor, student_id):
    """Erase check-ins and appointment requests, then clear consent metadata."""
    cursor.execute("DELETE FROM checkins WHERE student_id=%s", (student_id,))
    cursor.execute("DELETE FROM support_requests WHERE student_id=%s", (student_id,))
    cursor.execute(
        "UPDATE users SET consent_at=NULL, consent_version=NULL WHERE id=%s AND role='student'",
        (student_id,),
    )

def permanently_delete_student(cursor, student_id):
    """Delete a student account; related rows are removed by ON DELETE CASCADE."""
    cursor.execute("DELETE FROM users WHERE id=%s AND role='student'", (student_id,))
    return cursor.rowcount
