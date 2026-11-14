"""Cautious, descriptive trend summaries. These are not clinical risk scores."""
from datetime import timedelta

import pandas as pd
from sklearn.linear_model import LinearRegression


def _frame(rows):
    df = pd.DataFrame(rows or [])
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df.sort_values("created_at")


def build_student_trend(rows):
    """Describe one student's own recent entries; never diagnose or predict."""
    df = _frame(rows)
    if df.empty:
        return {"count": 0, "message": "Complete a few check-ins to see your personal pattern."}

    result = {
        "count": int(len(df)),
        "message": "These are reflection patterns from your own entries, not a diagnosis or forecast.",
    }
    if len(df) < 3:
        result["message"] = "Add at least three check-ins to see a simple descriptive summary. This is not a diagnosis."
        return result

    # Anchor the window to the student's latest submitted entry, not to a prediction.
    latest_time = df["created_at"].max()
    recent = df[df["created_at"] >= latest_time - timedelta(days=14)].copy()
    result["window_entries"] = int(len(recent))
    result["window_label"] = "Entries in the 14 days ending with your latest check-in"

    stress_avg = float(recent["stress"].mean())
    pressure_avg = float(recent["academic_pressure"].mean())
    sleep_avg = float(recent["sleep_hours"].mean())
    result.update({
        "stress_avg": round(stress_avg, 1),
        "pressure_avg": round(pressure_avg, 1),
        "sleep_avg": round(sleep_avg, 1),
    })

    # Fit against elapsed calendar time rather than entry order. Require both
    # enough entries and a two-week span to avoid overstating sparse data.
    span_days = (df["created_at"].max() - df["created_at"].min()).total_seconds() / 86400
    if len(df) >= 5 and span_days >= 14:
        elapsed_days = (df["created_at"] - df["created_at"].min()).dt.total_seconds() / 86400
        model = LinearRegression().fit(elapsed_days.to_numpy().reshape(-1, 1), df["stress"].astype(float))
        slope_per_week = float(model.coef_[0] * 7)
        result["stress_direction"] = (
            "rising" if slope_per_week >= 0.35 else
            "easing" if slope_per_week <= -0.35 else
            "fairly steady"
        )
        result["stress_direction_note"] = "A simple line across your submitted ratings; it is not a forecast."
    else:
        result["stress_direction"] = "not enough entries across two weeks"
        result["stress_direction_note"] = "Add entries over time if you find tracking useful; there is no need to check in every day."

    observations = []
    high_stress_count = int((recent["stress"] >= 4).sum())
    high_pressure_count = int((recent["academic_pressure"] >= 4).sum())
    low_sleep_count = int((recent["sleep_hours"] < 6).sum())

    if len(recent) >= 3 and high_stress_count >= 3:
        observations.append(
            "You rated stress as high in at least three recent check-ins. If this feels difficult to manage, you could consider talking with someone you trust or requesting counsellor support."
        )
    elif stress_avg >= 4:
        observations.append("Your recent stress average is on the higher side. Consider choosing one manageable task and taking a short pause.")

    if len(recent) >= 3 and high_pressure_count >= 3:
        observations.append("You reported high academic pressure in several recent check-ins. A faculty mentor may help you prioritise or plan the workload.")
    elif pressure_avg >= 4:
        observations.append("Your recent academic-pressure average is high. It may help to break work into smaller steps or ask about priorities.")

    if len(recent) >= 3 and low_sleep_count >= 3:
        observations.append("Several recent entries recorded less than six hours of sleep. If possible, consider protecting a consistent rest window.")
    elif sleep_avg < 6:
        observations.append("Your recent sleep average is under six hours. If possible, consider a consistent wind-down routine.")

    if not observations:
        observations.append("No repeated high pattern stands out in these entries. Keep checking in only when it is useful to you.")

    result["observations"] = observations[:4]
    return result


def _round_half(value):
    """Reduce precision in cohort summaries to limit unnecessary disclosure."""
    return round(float(value) * 2) / 2


def build_counsellor_aggregates(rows, minimum_students=5):
    """Return coarse weekly cohort summaries only when each week has k students.

    The threshold is never allowed below five. Contributor counts and row-level
    values are not returned to templates. This is a small-cohort safeguard, not
    a formal anonymity or differential-privacy guarantee.
    """
    k = max(5, int(minimum_students))
    df = _frame(rows)
    if df.empty or df["student_id"].nunique() < k:
        return {
            "suppressed": True,
            "message": f"Cohort summaries are hidden until at least {k} distinct students have contributed in the reporting period.",
        }

    df["week"] = df["created_at"].dt.to_period("W-SUN").astype(str)
    # First average each student's entries within a week so frequent check-ins
    # do not give one student extra weight in the cohort average.
    student_week = (
        df.groupby(["week", "student_id"], as_index=False)
        [["stress", "sleep_hours", "academic_pressure"]]
        .mean()
    )
    output = []
    for week, group in student_week.groupby("week"):
        if group["student_id"].nunique() < k:
            continue
        output.append({
            "week": week,
            "avg_stress": _round_half(group["stress"].mean()),
            "avg_sleep": _round_half(group["sleep_hours"].mean()),
            "avg_pressure": _round_half(group["academic_pressure"].mean()),
        })

    if not output:
        return {
            "suppressed": True,
            "message": f"Weekly summaries are hidden because every displayed week must include at least {k} distinct students.",
        }
    return {
        "suppressed": False,
        "weeks": output,
        "message": "Coarse weekly cohort summaries only. No student-level entries or contributor counts are displayed.",
    }


def make_suggestions(mood, stress, sleep_hours, academic_pressure):
    """Small, non-clinical suggestions based on the student's own latest inputs."""
    suggestions = []
    if stress >= 4 and academic_pressure >= 4:
        suggestions.append("Try writing down your next three tasks, then choose just one small 20-minute step. A faculty mentor can help clarify priorities.")
    elif stress >= 4:
        suggestions.append("Try a two-minute pause, then choose one manageable next task. You do not need to solve everything at once.")
    if sleep_hours < 6:
        suggestions.append("If possible, plan a consistent wind-down time and protect a little more rest tonight.")
    if academic_pressure >= 4 and stress < 4:
        suggestions.append("Break your workload into smaller parts and consider asking a faculty member about deadlines or priorities.")
    if mood in {"Low", "Stressed"}:
        suggestions.append("Consider talking with someone you trust or requesting a campus counsellor appointment.")
    if not suggestions:
        suggestions.append("Keep doing what supports your wellbeing. A short walk, hydration or a screen break may help.")
    return suggestions[:4]
