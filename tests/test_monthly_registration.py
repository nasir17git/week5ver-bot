import json
import os
import unittest
from datetime import date
from unittest.mock import Mock, call, patch

from handlers.commands import register_commands
from handlers.views import monthly_registration_modal


class MonthlyRegistrationTests(unittest.TestCase):
    def _register(self, list_client=None):
        handlers = {}
        app = Mock()
        app.command.side_effect = lambda name: lambda fn: handlers.setdefault(name, fn)
        app.view.side_effect = lambda name: lambda fn: handlers.setdefault(name, fn)
        register_commands(app, list_client or Mock())
        return handlers

    def test_confirmation_modal_names_month_and_has_explicit_yes_no_choices(self):
        modal = monthly_registration_modal("2026-09")

        self.assertEqual(modal["type"], "modal")
        self.assertEqual(modal["callback_id"], "monthly_registration_modal")
        self.assertEqual(json.loads(modal["private_metadata"]), {"month": "2026-09"})
        rendered = json.dumps(modal, ensure_ascii=False)
        self.assertIn("2026년 9월", rendered)
        self.assertIn("등록하시겠습니까", rendered)
        self.assertIn("예", modal["submit"]["text"])
        self.assertIn("아니오", modal["close"]["text"])

    @patch("handlers.commands.get_today_kst", return_value=date(2026, 9, 30))
    def test_slash_command_opens_confirmation_for_current_kst_calendar_month(self, _today):
        command = self._register()["/월간등록"]
        ack, respond, client = Mock(), Mock(), Mock()

        command(ack, respond, client, {"user_id": "U0123456789", "trigger_id": "T1"})

        ack.assert_called_once_with()
        client.views_open.assert_called_once()
        self.assertEqual(client.views_open.call_args.kwargs["trigger_id"], "T1")
        modal = client.views_open.call_args.kwargs["view"]
        self.assertEqual(json.loads(modal["private_metadata"])["month"], "2026-09")
        respond.assert_not_called()

    @patch("handlers.commands.get_today_kst", return_value=date(2026, 12, 1))
    def test_slash_command_rejects_month_outside_september_through_november(self, _today):
        command = self._register()["/월간등록"]
        ack, respond, client = Mock(), Mock(), Mock()

        command(ack, respond, client, {"user_id": "U0123456789", "trigger_id": "T1"})

        ack.assert_called_once_with()
        client.views_open.assert_not_called()
        self.assertIn("기간", respond.call_args.kwargs["text"])

    @patch.dict(os.environ, {"SLACK_CHANNEL_ID": "C1"})
    @patch("handlers.commands.get_today_kst", return_value=date(2026, 10, 15))
    def test_yes_submission_syncs_requesting_user_for_only_that_months_weeks(self, _today):
        lists = Mock()
        existing = []
        lists.list_items.return_value = existing
        lists.sync_participation.side_effect = [({}, True)] * 4
        submit = self._register(lists)["monthly_registration_modal"]
        ack, client = Mock(), Mock()
        view = {"private_metadata": json.dumps({"month": "2026-10"})}

        submit(ack, view, client, {"user": {"id": "U0123456789"}})

        ack.assert_called_once_with()
        self.assertEqual(
            lists.sync_participation.call_args_list,
            [
                call("U0123456789", "week4", items=existing),
                call("U0123456789", "week5", items=existing),
                call("U0123456789", "week6", items=existing),
                call("U0123456789", "week7", items=existing),
            ],
        )

    @patch.dict(os.environ, {"SLACK_CHANNEL_ID": "C1"})
    @patch("handlers.commands.get_today_kst", return_value=date(2026, 10, 1))
    def test_stale_or_tampered_modal_cannot_register_a_different_month(self, _today):
        lists = Mock()
        submit = self._register(lists)["monthly_registration_modal"]

        submit(
            Mock(),
            {"private_metadata": json.dumps({"month": "2026-09", "channel_id": "C1"})},
            Mock(),
            {"user": {"id": "U0123456789"}},
        )

        lists.list_items.assert_not_called()
        lists.sync_participation.assert_not_called()

    @patch.dict(os.environ, {"SLACK_CHANNEL_ID": "C1"})
    @patch("handlers.commands.get_today_kst", return_value=date(2026, 9, 20))
    def test_repeated_submission_is_idempotent(self, _today):
        class IdempotentListClient:
            def __init__(self):
                self.keys = set()
                self.created = 0

            def list_items(self):
                return []

            def sync_participation(self, user_id, week, *, items):
                key = (user_id, week)
                if key in self.keys:
                    return {}, False
                self.keys.add(key)
                self.created += 1
                return {"id": f"row-{week}"}, True

        lists = IdempotentListClient()
        submit = self._register(lists)["monthly_registration_modal"]
        view = {"private_metadata": json.dumps({"month": "2026-09"})}
        body = {"user": {"id": "U0123456789"}}

        submit(Mock(), view, Mock(), body)
        submit(Mock(), view, Mock(), body)

        self.assertEqual(lists.created, 3)
        self.assertEqual(lists.keys, {
            ("U0123456789", "week1"),
            ("U0123456789", "week2"),
            ("U0123456789", "week3"),
        })

    @patch.dict(os.environ, {"SLACK_CHANNEL_ID": "C1"})
    @patch("handlers.commands.get_today_kst", return_value=date(2026, 9, 20))
    def test_partial_failure_can_be_safely_retried_without_duplicate_rows(self, _today):
        class FlakyListClient:
            def __init__(self):
                self.keys = set()
                self.failed_once = False

            def list_items(self):
                return []

            def sync_participation(self, user_id, week, *, items):
                key = (user_id, week)
                if week == "week2" and not self.failed_once:
                    self.failed_once = True
                    raise RuntimeError("temporary failure")
                if key in self.keys:
                    return {}, False
                self.keys.add(key)
                return {"id": f"row-{week}"}, True

        lists = FlakyListClient()
        submit = self._register(lists)["monthly_registration_modal"]
        view = {"private_metadata": json.dumps({"month": "2026-09"})}
        body = {"user": {"id": "U0123456789"}}

        submit(Mock(), view, Mock(), body)
        submit(Mock(), view, Mock(), body)

        self.assertEqual(lists.keys, {
            ("U0123456789", "week1"),
            ("U0123456789", "week2"),
            ("U0123456789", "week3"),
        })


if __name__ == "__main__":
    unittest.main()
