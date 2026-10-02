import unittest
from datetime import date

from app import build_reminder_email_body, build_reminder_items, calculate_grade_letter, get_next_due_date


class PlannerHelperTests(unittest.TestCase):
    def test_recurring_due_date_advances_weekly(self):
        self.assertEqual(get_next_due_date(date(2026, 10, 1), "weekly"), date(2026, 10, 8))

    def test_recurring_due_date_advances_monthly(self):
        self.assertEqual(get_next_due_date(date(2026, 10, 31), "monthly"), date(2026, 11, 30))

    def test_build_reminder_items_includes_due_and_exam_items(self):
        tasks = [{"title": "Submit report", "due_date": date(2026, 10, 5), "reminder_days_before": 2}]
        exams = [{"exam_name": "Midterm", "exam_date": date(2026, 10, 6), "reminder_days_before": 3}]

        reminders = build_reminder_items(tasks, exams, date(2026, 10, 3))

        self.assertEqual(len(reminders), 2)
        self.assertEqual(reminders[0]["title"], "Submit report")
        self.assertEqual(reminders[1]["title"], "Midterm")

    def test_build_reminder_email_body_formats_summary(self):
        reminders = [
            {"title": "Submit report", "kind": "task", "reminder_date": date(2026, 10, 5), "detail": "Task due on 2026-10-05"},
            {"title": "Midterm", "kind": "exam", "reminder_date": date(2026, 10, 6), "detail": "Exam on 2026-10-06"},
        ]

        body = build_reminder_email_body(reminders, "Ava")

        self.assertIn("Hi Ava", body)
        self.assertIn("Submit report", body)
        self.assertIn("Midterm", body)
        self.assertIn("2 reminder(s)", body)

    def test_calculate_grade_letter_for_score(self):
        self.assertEqual(calculate_grade_letter(92), "A")
        self.assertEqual(calculate_grade_letter(75), "B")
        self.assertEqual(calculate_grade_letter(52), "C")
        self.assertEqual(calculate_grade_letter(41), "D")


if __name__ == "__main__":
    unittest.main()
