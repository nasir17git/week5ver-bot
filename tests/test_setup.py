import copy
import argparse
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from dotenv import dotenv_values
from setup_slack_list import LIST_SCHEMA, _schema_to_env, _update_env_file, main
from sync_participants import read_participants


def schema():
    columns = copy.deepcopy(LIST_SCHEMA)
    columns.extend({"key": key, "name": key, "type": key} for key in (
        "todo_completed", "todo_assignee", "todo_due_date"
    ))
    for index, column in enumerate(columns):
        column["id"] = f"Col{index}"
    return columns


class SetupTests(unittest.TestCase):
    def test_failed_setup_preserves_live_env_and_reports_created_id(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            original = "SLACK_BOT_TOKEN=test\nSLACK_LIST_ID=Fold\n"
            path.write_text(original)
            args = argparse.Namespace(env_file=str(path), existing_list_id=None,
                force_new=True, name="test", no_channel_access=True)
            with patch.dict(os.environ, {}, clear=True), patch("setup_slack_list._parse_args", return_value=args), patch("setup_slack_list.WebClient"), patch("setup_slack_list._create_list", return_value={"list_id": "Fnew", "list_metadata": {"schema": []}}):
                with self.assertRaisesRegex(SystemExit, "--existing-list-id Fnew"):
                    main()
            self.assertEqual(path.read_text(), original)

    def test_ui_columns_resolve_by_name_and_todo_type(self):
        columns = schema()
        for column in columns:
            column["key"] = "generated_" + column["id"]
        result = _schema_to_env("F123", columns)
        self.assertEqual(result["SLACK_LIST_OPT_WEEK11"], "week11")
        self.assertEqual(result["SLACK_LIST_OPT_ROW_GOAL"], "goal")
        self.assertIn("SLACK_LIST_COL_ASSIGNEE", result)

    def test_user_owned_csv_list_may_omit_updated_at(self):
        columns = [column for column in schema() if column["key"] != "updated_at"]
        result = _schema_to_env("F123", columns)
        self.assertNotIn("SLACK_LIST_COL_UPDATED_AT", result)
        self.assertEqual(result["SLACK_LIST_ID"], "F123")

    def test_proof_column_name_with_space_is_supported(self):
        columns = schema()
        proof = next(column for column in columns if column["key"] == "proof")
        proof["key"] = "generated_proof"
        proof["name"] = "인증 자료"
        result = _schema_to_env("F123", columns)
        self.assertEqual(result["SLACK_LIST_COL_PROOF"], proof["id"])

    def test_wrong_column_type_rejected_before_use(self):
        columns = schema()
        next(column for column in columns if column["key"] == "registered_count")["type"] = "text"
        with self.assertRaisesRegex(RuntimeError, "number"):
            _schema_to_env("F123", columns)

    def test_duplicate_role_rejected(self):
        columns = schema()
        columns.append(copy.deepcopy(columns[-1]))
        with self.assertRaisesRegex(RuntimeError, "여러 개"):
            _schema_to_env("F123", columns)

    def test_env_duplicates_cannot_override_new_value(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("# keep\nSLACK_LIST_ID=old\nexport SLACK_LIST_ID=stale\nUNRELATED=yes\n")
            _update_env_file(path, {"SLACK_LIST_ID": "new"})
            self.assertEqual(dotenv_values(path)["SLACK_LIST_ID"], "new")
            self.assertEqual(dotenv_values(path)["UNRELATED"], "yes")

    def test_csv_rejects_invalid_empty_header_and_accepts_enterprise_id(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "participants.csv"
            path.write_text("user,month\n")
            with self.assertRaisesRegex(ValueError, "헤더"):
                read_participants(path)
            path.write_text("user_id,month\nW0123456789,2026-09\n")
            self.assertEqual(read_participants(path)[0]["user_id"], "W0123456789")
            path.write_text("user_id,month\nUinvalid!,2026-09\n")
            with self.assertRaises(ValueError):
                read_participants(path)
