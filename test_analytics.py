import unittest
from datetime import datetime, timedelta

from analytics import build_student_trend, build_counsellor_aggregates, make_suggestions


class AnalyticsTests(unittest.TestCase):
    def test_student_trend_requires_three_entries_for_summary(self):
        rows = [
            {"created_at": datetime(2026, 11, 1) + timedelta(days=i), "stress": 4,
             "academic_pressure": 4, "sleep_hours": 5.5, "mood": "Stressed"}
            for i in range(2)
        ]
        result = build_student_trend(rows)
        self.assertEqual(result["count"], 2)
        self.assertNotIn("stress_avg", result)

    def test_student_trend_uses_calendar_span_and_repeated_observations(self):
        rows = [
            {"created_at": datetime(2026, 10, 20) + timedelta(days=i * 4), "stress": 4,
             "academic_pressure": 4, "sleep_hours": 5.0, "mood": "Stressed"}
            for i in range(5)
        ]
        result = build_student_trend(rows)
        self.assertEqual(result["stress_avg"], 4.0)
        self.assertEqual(result["stress_direction"], "fairly steady")
        self.assertTrue(any("at least three recent check-ins" in item for item in result["observations"]))
        self.assertNotIn("risk_score", result)

    def test_student_trend_requires_two_week_span_for_direction(self):
        rows = [
            {"created_at": datetime(2026, 11, 1) + timedelta(days=i), "stress": 4,
             "academic_pressure": 3, "sleep_hours": 7, "mood": "Okay"}
            for i in range(5)
        ]
        result = build_student_trend(rows)
        self.assertEqual(result["stress_direction"], "not enough entries across two weeks")

    def test_counsellor_aggregate_suppresses_small_cohort(self):
        rows = [{"student_id": i, "created_at": datetime(2026, 11, 3), "stress": 3,
                 "sleep_hours": 7, "academic_pressure": 3} for i in range(1, 5)]
        result = build_counsellor_aggregates(rows, minimum_students=5)
        self.assertTrue(result["suppressed"])

    def test_counsellor_aggregate_suppresses_week_even_if_period_total_is_large(self):
        rows = [{"student_id": i, "created_at": datetime(2026, 11, 3), "stress": 3,
                 "sleep_hours": 7, "academic_pressure": 3} for i in range(1, 6)]
        rows += [{"student_id": i, "created_at": datetime(2026, 11, 10), "stress": 4,
                  "sleep_hours": 6, "academic_pressure": 4} for i in range(1, 5)]
        result = build_counsellor_aggregates(rows, minimum_students=5)
        self.assertFalse(result["suppressed"])
        self.assertEqual(len(result["weeks"]), 1)
        self.assertNotIn("contributors", result["weeks"][0])
        self.assertEqual(result["weeks"][0]["avg_stress"], 3.0)

    def test_weekly_aggregate_weights_each_student_once(self):
        rows = []
        # Student 1 has several check-ins, but should count as one student average.
        for stress in (1, 1, 1, 1):
            rows.append({"student_id": 1, "created_at": datetime(2026, 11, 3), "stress": stress,
                         "sleep_hours": 8, "academic_pressure": 1})
        for student_id in range(2, 6):
            rows.append({"student_id": student_id, "created_at": datetime(2026, 11, 3), "stress": 5,
                         "sleep_hours": 6, "academic_pressure": 5})
        result = build_counsellor_aggregates(rows)
        self.assertFalse(result["suppressed"])
        self.assertEqual(result["weeks"][0]["avg_stress"], 4.0)

    def test_minimum_threshold_cannot_be_lowered_below_five(self):
        rows = [{"student_id": i, "created_at": datetime(2026, 11, 3), "stress": 3,
                 "sleep_hours": 7, "academic_pressure": 3} for i in range(1, 5)]
        self.assertTrue(build_counsellor_aggregates(rows, minimum_students=2)["suppressed"])

    def test_suggestions_are_non_clinical(self):
        suggestions = make_suggestions("Stressed", 5, 4.5, 5)
        self.assertTrue(suggestions)
        self.assertLessEqual(len(suggestions), 4)


if __name__ == "__main__":
    unittest.main()
