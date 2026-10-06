import os
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from slack_list.client import SlackListClient
from sync_participants import MONTH_WEEKS, read_participants
from utils import classify_week


ENV = {
    "SLACK_LIST_ID": "F1",
    "SLACK_LIST_COL_TITLE": "title",
    "SLACK_LIST_COL_ASSIGNEE": "assignee",
    "SLACK_LIST_COL_DEADLINE": "deadline",
    "SLACK_LIST_COL_WEEK": "week",
    "SLACK_LIST_COL_TODO_COMPLETED": "done",
    "SLACK_LIST_COL_ROW_TYPE": "row_type",
    "SLACK_LIST_COL_PARTICIPATION_STATUS": "status",
    "SLACK_LIST_COL_REGISTERED_COUNT": "registered",
    "SLACK_LIST_COL_COMPLETED_COUNT": "completed",
    "SLACK_LIST_COL_JUDGMENT": "judgment",
    "SLACK_LIST_OPT_ROW_GOAL": "goal",
    "SLACK_LIST_OPT_ROW_PARTICIPATION": "participation",
    "SLACK_LIST_OPT_STATUS_ACTIVE": "active",
    "SLACK_LIST_OPT_STATUS_REST": "rest",
    **{f"SLACK_LIST_OPT_WEEK{i}": f"week{i}" for i in range(1, 12)},
}


def item(item_id, user, week, *, row_type="goal", done=False, status=None, deadline=None):
    fields = [
        {"column_id": "assignee", "user": [user]},
        {"column_id": "week", "select": [week]},
        {"column_id": "row_type", "select": [row_type]},
        {"column_id": "done", "checkbox": done},
    ]
    if status:
        fields.append({"column_id": "status", "select": [status]})
    if deadline:
        fields.append({"column_id": "deadline", "date": [deadline]})
    return {"id": item_id, "fields": fields}


def with_stats(row, registered, completed, judgment):
    row["fields"].extend([
        {"column_id": "registered", "number": [registered]},
        {"column_id": "completed", "number": [completed]},
        {"column_id": "judgment", "text": judgment},
    ])
    return row


class FakeClient:
    def __init__(self, items):
        self.items = items
        self.created = []
        self.updated = []

    def slackLists_items_list(self, **kwargs):
        return {"items": self.items, "response_metadata": {}}

    def slackLists_items_create(self, **kwargs):
        self.created.append(kwargs)
        return {"item": {"id": "new", "fields": kwargs["initial_fields"]}}

    def slackLists_items_update(self, **kwargs):
        self.updated.append(kwargs)
        return {"ok": True}


class PolicyTests(unittest.TestCase):
    def test_months_follow_monday_month(self):
        self.assertEqual(MONTH_WEEKS["2026-09"], ["week1", "week2", "week3"])
        self.assertEqual(MONTH_WEEKS["2026-10"], ["week4", "week5", "week6", "week7"])
        self.assertEqual(MONTH_WEEKS["2026-11"], ["week8", "week9", "week10", "week11"])

    def test_participant_file_deduplicates_and_validates_before_sync(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "participants.csv"
            path.write_text("user_id,month\nU0123456789,2026-09\nU0123456789,2026-09\n", encoding="utf-8")
            self.assertEqual(read_participants(path), [{"user_id": "U0123456789", "month": "2026-09"}])

    def test_live_and_final_judgments(self):
        with patch("utils._today_kst", return_value=date(2026, 9, 16)):
            self.assertEqual(classify_week("week1", "active", 0, 0), "등록 대기")
            self.assertEqual(classify_week("week1", "active", 3, 2), "진행 중")
            self.assertEqual(classify_week("week1", "active", 3, 3), "달성")
            self.assertEqual(classify_week("week1", "rest", 3, 0), "판정 제외")
        with patch("utils._today_kst", return_value=date(2026, 9, 21)):
            self.assertEqual(classify_week("week1", "active", 0, 0), "미등록")
            self.assertEqual(classify_week("week1", "active", 3, 2), "미달성")

    @patch.dict(os.environ, ENV, clear=True)
    def test_goal_queries_exclude_participation_and_other_weeks(self):
        fake = FakeClient([
            item("goal-current", "U1", "week1"),
            item("goal-done", "U1", "week1", done=True),
            item("goal-old", "U1", "week2"),
            item("participation", "U1", "week1", row_type="participation", status="active"),
        ])
        goals = SlackListClient(fake).get_all_incomplete_items("week1")
        self.assertEqual([goal["id"] for goal in goals], ["goal-current"])

    @patch.dict(os.environ, ENV, clear=True)
    @patch("slack_list.client.get_today_kst", return_value=date(2026, 9, 15))
    def test_notifications_start_on_due_date_and_keep_overdue_goals(self, _today):
        fake = FakeClient([
            item("overdue", "U1", "week1", deadline="2026-09-14"),
            item("today", "U1", "week1", deadline="2026-09-15"),
            item("future", "U1", "week1", deadline="2026-09-17"),
            item("legacy-no-date", "U1", "week1"),
        ])
        goals = SlackListClient(fake).get_all_incomplete_items("week1")
        self.assertEqual([goal["id"] for goal in goals], ["overdue", "today", "legacy-no-date"])

    @patch.dict(os.environ, ENV, clear=True)
    def test_participation_sync_is_idempotent_and_preserves_rest(self):
        participation = item("p1", "U1", "week1", row_type="participation", status="rest")
        fake = FakeClient([participation])
        result, created = SlackListClient(fake).sync_participation("U1", "week1")
        self.assertEqual(result["id"], "p1")
        self.assertFalse(created)
        self.assertEqual(fake.created, [])
        self.assertEqual(fake.updated, [])

    @patch.dict(os.environ, ENV, clear=True)
    def test_registered_weeks_count_rest_and_ignore_goals_and_other_users(self):
        fake = FakeClient([
            item("p4", "U1", "week4", row_type="participation", status="active"),
            item("p5", "U1", "week5", row_type="participation", status="rest"),
            item("g6", "U1", "week6"),
            item("p7", "U2", "week7", row_type="participation", status="active"),
        ])
        registered = SlackListClient(fake).get_registered_weeks("U1", ["week4", "week5", "week6", "week7"])
        self.assertEqual(registered, {"week4", "week5"})

    @patch.dict(os.environ, ENV, clear=True)
    def test_new_participation_starts_with_zero_counts(self):
        fake = FakeClient([])
        SlackListClient(fake).sync_participation("U1", "week1")
        fields = fake.created[0]["initial_fields"]
        self.assertIn({"column_id": "registered", "number": [0]}, fields)
        self.assertIn({"column_id": "completed", "number": [0]}, fields)

    @patch.dict(os.environ, ENV, clear=True)
    def test_participation_counts_use_slack_number_array_format(self):
        participation = item("p1", "U1", "week1", row_type="participation", status="active")
        fake = FakeClient([participation])
        with patch("utils._today_kst", return_value=date(2026, 9, 16)):
            SlackListClient(fake).refresh_participation_stats()
        cells = fake.updated[0]["cells"]
        self.assertEqual(cells[0]["number"], [0])
        self.assertEqual(cells[1]["number"], [0])

    @patch.dict(os.environ, ENV, clear=True)
    def test_unchanged_participation_stats_do_not_mark_row_edited(self):
        participation = with_stats(
            item("p1", "U1", "week1", row_type="participation", status="active"),
            0, 0, "등록 대기",
        )
        fake = FakeClient([participation])
        with patch("utils._today_kst", return_value=date(2026, 9, 16)):
            SlackListClient(fake).refresh_participation_stats()
        self.assertEqual(fake.updated, [])


if __name__ == "__main__":
    unittest.main()
