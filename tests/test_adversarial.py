import os
import unittest
from unittest.mock import Mock, patch

from test_policy import ENV, FakeClient, item
from slack_list.client import SlackListClient
from scheduler.jobs import send_daily_notifications, _unpin_previous_weekly_goal_requests


class AdversarialTests(unittest.TestCase):
    @patch.dict(os.environ, ENV, clear=True)
    def test_other_people_column_does_not_grant_goal_ownership(self):
        goal = item("g", "OWNER", "week1")
        goal["fields"].insert(0, {"column_id": "reviewer", "user": ["ATTACKER"]})
        lists = SlackListClient(FakeClient([goal]))
        self.assertIsNone(lists.get_valid_goal("g", "ATTACKER", "week1"))
        self.assertIsNotNone(lists.get_valid_goal("g", "OWNER", "week1"))

    @patch.dict(os.environ, ENV, clear=True)
    def test_duplicate_and_blank_participation_fail_before_any_stats_write(self):
        for rows in ([item("p", "U1", "week1", row_type="participation")],
                     [item("p1", "U1", "week1", row_type="participation", status="active"),
                      item("p2", "U1", "week1", row_type="participation", status="rest")]):
            fake = FakeClient(rows)
            with self.assertRaises(RuntimeError):
                SlackListClient(fake).refresh_participation_stats()
            self.assertEqual(fake.updated, [])

    @patch.dict(os.environ, ENV, clear=True)
    def test_missing_row_type_config_cannot_turn_participation_into_goal(self):
        del os.environ["SLACK_LIST_COL_ROW_TYPE"]
        with self.assertRaises(RuntimeError):
            SlackListClient(FakeClient([item("p", "U1", "week1")])).get_all_incomplete_items("week1")

    @patch("scheduler.jobs.get_current_week", return_value=None)
    @patch("slack_list.client.SlackListClient")
    def test_after_season_does_not_refresh_stats_or_send_dm(self, lists, _week):
        client = Mock()
        send_daily_notifications(client)
        lists.return_value.refresh_participation_stats.assert_not_called()
        lists.return_value.get_all_incomplete_items.assert_not_called()
        client.chat_postMessage.assert_not_called()

    def test_unknown_bot_identity_does_not_unpin_other_messages(self):
        client = Mock()
        client.pins_list.return_value = {"items": [{"message": {
            "ts": "old", "text": "이번 주 공부 목표를 등록해주세요!", "bot_id": "OTHER"}}]}
        _unpin_previous_weekly_goal_requests(client, "C1", "new", bot_id=None)
        client.pins_remove.assert_not_called()
