import json
import os
import unittest
from unittest.mock import Mock, patch

from handlers.actions import register_actions, _handle_certification
from handlers.views import goal_update_modal
from handlers.commands import register_commands
from templates.messages import goal_certified


class HandlerTests(unittest.TestCase):
    @patch.dict(os.environ, {"SLACK_CHANNEL_ID": "C1"})
    @patch("handlers.actions.get_current_week", return_value="week1")
    def test_registration_requires_due_date_inside_current_week(self, _week):
        handlers = {}
        app = Mock()
        app.action.side_effect = lambda name: lambda fn: fn
        app.event.side_effect = lambda name: lambda fn: fn
        app.view.side_effect = lambda name: lambda fn: handlers.setdefault(name, fn)
        lists = Mock()
        register_actions(app, lists)
        submit = handlers["goal_register_modal"]

        for deadline in (None, "2026-09-21"):
            ack = Mock()
            values = {
                "week_block": {"week_input": {"selected_option": {"value": "week1"}}},
                "lecture_1_block": {"lecture_1_input": {"value": "독서"}},
                "deadline_1_block": {"deadline_1_input": {"selected_date": deadline}},
            }
            submit(ack, {"state": {"values": values}}, Mock(), {"user": {"id": "U1"}})
            self.assertEqual(ack.call_args.kwargs["response_action"], "errors")
        lists.create_item.assert_not_called()

    @patch.dict(os.environ, {"SLACK_CHANNEL_ID": "C1", "SLACK_ADMIN_USER_IDS": "UADMIN"})
    @patch("handlers.commands.post_weekly_goal_request")
    @patch("handlers.commands.get_current_week", return_value="week1")
    def test_operator_command_rejects_wrong_user_channel_and_offseason(self, week, send):
        handlers = {}
        app = Mock()
        app.command.side_effect = lambda name: lambda fn: handlers.setdefault(name, fn)
        register_commands(app)
        command = handlers["/등록발송"]
        for body in ({"user_id": "UOTHER", "channel_id": "C1"},
                     {"user_id": "UADMIN", "channel_id": "COTHER"}):
            command(Mock(), Mock(), Mock(), body)
        send.assert_not_called()
        week.return_value = None
        respond = Mock()
        command(Mock(), respond, Mock(), {"user_id": "UADMIN", "channel_id": "C1"})
        send.assert_not_called()
        self.assertIn("발송하지 않았습니다", respond.call_args.kwargs["text"])

    @patch("handlers.actions.get_certification_week", return_value="week1")
    def test_missing_and_malformed_proof_cannot_complete_goal(self, _week):
        for files in (None, [], ["F1"], [{}], [{"id": ""}]):
            ack, client, lists = Mock(), Mock(), Mock()
            view = {"private_metadata": json.dumps({"week": "week1"}),
                    "state": {"values": {"proof_block": {"proof_input": {"files": files}}}}}
            _handle_certification(ack, view, client, {"user": {"id": "U1"}}, lists, "C1")
            self.assertEqual(ack.call_args.kwargs["response_action"], "errors")
            lists.update_item.assert_not_called()

    @patch.dict(os.environ, {"SLACK_CHANNEL_ID": "C1"})
    @patch("handlers.actions.get_current_week", return_value="week1")
    def test_loading_modal_opens_before_list_lookup_and_lookup_error_is_visible(self, _week):
        handlers = {}
        app = Mock()
        app.action.side_effect = lambda name: lambda fn: handlers.setdefault(name, fn)
        app.event.side_effect = lambda name: lambda fn: fn
        app.view.side_effect = lambda name: lambda fn: fn
        lists, client = Mock(), Mock()
        client.views_open.return_value = {"view": {"id": "V1"}}

        def lookup(*_args):
            client.views_open.assert_called_once()
            raise RuntimeError("upstream unavailable")

        lists.get_participation_status.side_effect = lookup
        register_actions(app, lists)
        handlers["open_goal_register_modal"](Mock(), {"user": {"id": "U1"}, "trigger_id": "trigger"}, client)
        self.assertIn("불러오지 못했습니다", client.views_update.call_args.kwargs["view"]["blocks"][0]["text"]["text"])

    def test_pdf_permalink_is_link_not_image(self):
        message = goal_certified("U1", "독서", file_permalinks=["https://workspace.slack.com/files/U1/F1/report.pdf"])
        self.assertFalse(any(block["type"] == "image" for block in message["blocks"]))
        self.assertIn("인증자료 보기", message["blocks"][-1]["text"]["text"])

    @patch("handlers.views.extract_title", return_value="")
    def test_goal_selector_handles_large_list_and_empty_title(self, _title):
        modal = goal_update_modal([{"id": f"I{i}"} for i in range(101)])
        options = modal["blocks"][0]["element"]["options"]
        self.assertEqual(len(options), 100)
        self.assertTrue(all(option["text"]["text"] for option in options))

    @patch("handlers.actions.get_certification_week", return_value="week1")
    @patch("handlers.actions.extract_title", return_value="목표")
    def test_announcement_failure_does_not_undo_certification(self, _title, _week):
        ack, client, lists = Mock(), Mock(), Mock()
        lists.get_participation_status.return_value = "active"
        lists.get_valid_goal.return_value = {"id": "I1"}
        lists.update_item.return_value = True
        client.files_info.return_value = {"file": {}}
        client.chat_postMessage.side_effect = RuntimeError("posting failed")
        view = {"private_metadata": json.dumps({"week": "week1"}), "state": {"values": {
            "goal_select_block": {"goal_select_input": {"selected_option": {"value": "I1"}}},
            "proof_block": {"proof_input": {"files": [{"id": "F1"}]}}
        }}}
        _handle_certification(ack, view, client, {"user": {"id": "U1"}}, lists, "C1")
        lists.update_item.assert_called_once()
        self.assertIn("인증은 저장됐지만", client.chat_postEphemeral.call_args.kwargs["text"])


if __name__ == "__main__":
    unittest.main()
