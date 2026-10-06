"""week5ver용 Slack List를 생성하고 생성된 ID를 .env에 기록합니다.

필수 Slack App scope: lists:read, lists:write

실행 예시:
    python3 setup_slack_list.py --name week5ver-2026하반기

SLACK_CHANNEL_ID가 설정되어 있으면 해당 채널 구성원에게 List 편집 권한도
부여합니다. 기존 SLACK_LIST_ID가 있으면 중복 생성을 막기 위해 종료하며,
정말 새 List가 필요할 때만 --force-new를 사용합니다.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


WEEK_OPTIONS = [f"week{i}" for i in range(1, 12)]

LIST_SCHEMA = [
    {
        "key": "name",
        "name": "목표 제목",
        "type": "text",
        "is_primary_column": True,
    },
    {
        "key": "week",
        "name": "주차",
        "type": "select",
        "options": {
            "format": "single_select",
            "choices": [
                {"value": week, "label": week, "color": _color}
                for week, _color in zip(
                    WEEK_OPTIONS,
                    [
                        "green",
                        "cyan",
                        "blue",
                        "indigo",
                        "purple",
                        "pink",
                        "red",
                        "orange",
                        "yellow",
                        "brown",
                        "gray",
                    ],
                )
            ],
        },
    },
    {"key": "proof", "name": "인증자료", "type": "attachment"},
    {"key": "retro", "name": "한 줄 회고", "type": "text"},
    {"key": "updated_at", "name": "updated_at", "type": "last_edited_time"},
    {
        "key": "row_type",
        "name": "행 구분",
        "type": "select",
        "options": {
            "format": "single_select",
            "choices": [
                {"value": "goal", "label": "목표", "color": "blue"},
                {"value": "participation", "label": "참여현황", "color": "purple"},
            ],
        },
    },
    {
        "key": "participation_status",
        "name": "참여 상태",
        "type": "select",
        "options": {
            "format": "single_select",
            "choices": [
                {"value": "active", "label": "참여", "color": "green"},
                {"value": "rest", "label": "휴식", "color": "gray"},
            ],
        },
    },
    {"key": "registered_count", "name": "등록 목표 수", "type": "number", "options": {"precision": 0}},
    {"key": "completed_count", "name": "완료 목표 수", "type": "number", "options": {"precision": 0}},
    {"key": "judgment", "name": "판정", "type": "text"},
]

COLUMN_ENV_BY_KEY = {
    "name": "SLACK_LIST_COL_TITLE",
    "week": "SLACK_LIST_COL_WEEK",
    "proof": "SLACK_LIST_COL_PROOF",
    "retro": "SLACK_LIST_COL_RETRO",
    "updated_at": "SLACK_LIST_COL_UPDATED_AT",
    "todo_completed": "SLACK_LIST_COL_TODO_COMPLETED",
    "todo_assignee": "SLACK_LIST_COL_ASSIGNEE",
    "todo_due_date": "SLACK_LIST_COL_DEADLINE",
    "row_type": "SLACK_LIST_COL_ROW_TYPE",
    "participation_status": "SLACK_LIST_COL_PARTICIPATION_STATUS",
    "registered_count": "SLACK_LIST_COL_REGISTERED_COUNT",
    "completed_count": "SLACK_LIST_COL_COMPLETED_COUNT",
    "judgment": "SLACK_LIST_COL_JUDGMENT",
}

COLUMN_ENV_BY_NAME = {
    "목표 제목": "SLACK_LIST_COL_TITLE",
    "수강예정 강의이름": "SLACK_LIST_COL_TITLE",
    "주차": "SLACK_LIST_COL_WEEK",
    "인증자료": "SLACK_LIST_COL_PROOF",
    "인증 자료": "SLACK_LIST_COL_PROOF",
    "한 줄 회고": "SLACK_LIST_COL_RETRO",
    "updated_at": "SLACK_LIST_COL_UPDATED_AT",
    **{column["name"]: COLUMN_ENV_BY_KEY[column["key"]] for column in LIST_SCHEMA},
    "행 구분": "SLACK_LIST_COL_ROW_TYPE",
    "참여 상태": "SLACK_LIST_COL_PARTICIPATION_STATUS",
    "등록 목표 수": "SLACK_LIST_COL_REGISTERED_COUNT",
    "완료 목표 수": "SLACK_LIST_COL_COMPLETED_COUNT",
    "판정": "SLACK_LIST_COL_JUDGMENT",
}

SELECT_OPTION_ENVS = {
    "row_type": {"목표": "SLACK_LIST_OPT_ROW_GOAL", "참여현황": "SLACK_LIST_OPT_ROW_PARTICIPATION"},
    "participation_status": {"참여": "SLACK_LIST_OPT_STATUS_ACTIVE", "휴식": "SLACK_LIST_OPT_STATUS_REST"},
}

# 사람 소유 List를 CSV로 만들 때 자동 편집 시각 필드는 생략할 수 있습니다.
OPTIONAL_COLUMN_ENVS = {"SLACK_LIST_COL_UPDATED_AT"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="week5ver Slack List 초기 설정")
    parser.add_argument("--name", default="week5ver-2026하반기", help="생성할 List 이름")
    parser.add_argument("--env-file", default=".env", help="읽고 갱신할 env 파일")
    parser.add_argument(
        "--existing-list-id",
        metavar="F...",
        help="이미 생성된 List를 재사용하고 컬럼/옵션 ID만 .env에 기록",
    )
    parser.add_argument(
        "--force-new",
        action="store_true",
        help="SLACK_LIST_ID가 이미 있어도 새 List 생성",
    )
    parser.add_argument(
        "--no-channel-access",
        action="store_true",
        help="SLACK_CHANNEL_ID에 편집 권한을 부여하지 않음",
    )
    return parser.parse_args()


def _schema_to_env(list_id: str, schema: list[dict[str, Any]]) -> dict[str, str]:
    values = {"SLACK_LIST_ID": list_id}

    for column in schema:
        column_key = column.get("key", "")
        env_key = COLUMN_ENV_BY_KEY.get(column_key) or COLUMN_ENV_BY_NAME.get(column.get("name", ""))
        if not env_key and column.get("type") in ("todo_completed", "todo_assignee", "todo_due_date"):
            env_key = COLUMN_ENV_BY_KEY[column["type"]]
        canonical_key = next((key for key, value in COLUMN_ENV_BY_KEY.items() if value == env_key), None)
        if canonical_key:
            expected_type = next((entry["type"] for entry in LIST_SCHEMA if entry["key"] == canonical_key), canonical_key)
            if column.get("type") != expected_type:
                raise RuntimeError(f"컬럼 {column.get('name', canonical_key)!r} 타입은 {expected_type}이어야 합니다.")
            if env_key in values:
                raise RuntimeError(f"동일 역할의 컬럼이 여러 개입니다: {env_key}")
        column_id = column.get("id")
        if env_key and column_id:
            values[env_key] = column_id

        if canonical_key == "week":
            for choice in column.get("options", {}).get("choices", []):
                label = str(choice.get("label", "")).lower()
                value = choice.get("value")
                if label in WEEK_OPTIONS and value:
                    values[f"SLACK_LIST_OPT_{label.upper()}"] = str(value)

        option_mapping = SELECT_OPTION_ENVS.get(canonical_key)
        if not option_mapping:
            if column.get("name") == "행 구분":
                option_mapping = SELECT_OPTION_ENVS["row_type"]
            elif column.get("name") == "참여 상태":
                option_mapping = SELECT_OPTION_ENVS["participation_status"]
        for choice in column.get("options", {}).get("choices", []):
            option_env = (option_mapping or {}).get(str(choice.get("label", "")))
            if option_env and choice.get("value"):
                values[option_env] = str(choice["value"])

    missing = [
        env for env in COLUMN_ENV_BY_KEY.values()
        if env not in values and env not in OPTIONAL_COLUMN_ENVS
    ]
    if missing:
        raise RuntimeError(f"Slack 응답에서 필수 컬럼 ID를 찾지 못했습니다: {', '.join(missing)}")

    missing_options = [
        f"SLACK_LIST_OPT_{week.upper()}"
        for week in WEEK_OPTIONS
        if f"SLACK_LIST_OPT_{week.upper()}" not in values
    ]
    if missing_options:
        raise RuntimeError(
            "Slack 응답에서 주차 옵션 값을 찾지 못했습니다: " + ", ".join(missing_options)
        )

    missing_control_options = [
        env_key
        for mapping in SELECT_OPTION_ENVS.values()
        for env_key in mapping.values()
        if env_key not in values
    ]
    if missing_control_options:
        raise RuntimeError(
            "Slack 응답에서 참여현황 옵션 값을 찾지 못했습니다: "
            + ", ".join(missing_control_options)
        )

    return values


def _update_env_file(path: Path, updates: dict[str, str]) -> None:
    """주석과 기존 순서를 보존하면서 지정된 키만 교체/추가합니다."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    written = set()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if key in updates:
                if key not in written:
                    output.append(f"{key}={updates[key]}")
                    written.add(key)
                    remaining.pop(key, None)
                continue
        output.append(line)

    if remaining:
        if output and output[-1] != "":
            output.append("")
        output.append("# setup_slack_list.py가 생성한 Slack List ID")
        output.extend(f"{key}={value}" for key, value in remaining.items())

    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _create_list(client: WebClient, name: str) -> dict[str, Any]:
    response = client.api_call(
        "slackLists.create",
        json={"name": name, "todo_mode": True, "schema": LIST_SCHEMA},
    )
    return response.data


def _get_existing_list_schema(client: WebClient, list_id: str) -> list[dict[str, Any]]:
    response = client.api_call(
        "slackLists.items.list",
        json={"list_id": list_id, "limit": 1, "include_list": True},
    )
    return response.data.get("list", {}).get("list_metadata", {}).get("schema", [])


def main() -> int:
    args = _parse_args()
    env_path = Path(args.env_file)
    load_dotenv(env_path, override=True)
    configured = dotenv_values(env_path)

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token or token == "your-bot-token-here":
        raise SystemExit(f"{env_path}에 실제 SLACK_BOT_TOKEN을 먼저 설정하세요.")

    existing_list_id = configured.get("SLACK_LIST_ID", "")
    if (
        not args.existing_list_id
        and existing_list_id
        and existing_list_id != "FXXXXXXXXXX"
        and not args.force_new
    ):
        raise SystemExit(
            f"SLACK_LIST_ID={existing_list_id}가 이미 설정되어 있습니다. "
            "중복 생성을 원하면 --force-new를 사용하세요."
        )

    client = WebClient(token=token)
    list_id = args.existing_list_id or ""
    try:
        if args.existing_list_id:
            list_id = args.existing_list_id
            schema = _get_existing_list_schema(client, list_id)
        else:
            response = _create_list(client, args.name)
            list_id = response.get("list_id", "")
            if list_id:
                print(f"Slack List 생성됨: {list_id} (아직 환경 설정에 연결하지 않음)", flush=True)
            schema = response.get("list_metadata", {}).get("schema", [])
        if not list_id or not schema:
            raise RuntimeError("Slack 응답에 list_id 또는 schema가 없습니다.")

        updates = _schema_to_env(list_id, schema)
        channel_id = os.environ.get("SLACK_CHANNEL_ID", "")
        if channel_id and channel_id != "CXXXXXXXXXX" and not args.no_channel_access:
            client.api_call(
                "slackLists.access.set",
                json={
                    "list_id": list_id,
                    "access_level": "write",
                    "channel_ids": [channel_id],
                },
            )

        _update_env_file(env_path, updates)
    except SlackApiError as exc:
        error = exc.response.get("error", "unknown_error")
        recovery = f" 재생성하지 말고 --existing-list-id {list_id} 로 재시도하세요." if list_id else ""
        raise SystemExit(f"Slack List 초기화 실패: {error}.{recovery}") from exc
    except (RuntimeError, OSError) as exc:
        recovery = f" 재생성하지 말고 --existing-list-id {list_id} 로 재시도하세요." if list_id else ""
        raise SystemExit(f"Slack List 초기화 실패: {exc}.{recovery}") from exc

    if args.existing_list_id:
        print(f"기존 Slack List 연결 완료: {list_id}")
    else:
        print(f"Slack List 생성 완료: {args.name} ({list_id})")
    if channel_id and channel_id != "CXXXXXXXXXX" and not args.no_channel_access:
        print(f"채널 편집 권한 부여 완료: {channel_id}")
    print(f"컬럼/주차 옵션 ID 기록 완료: {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
