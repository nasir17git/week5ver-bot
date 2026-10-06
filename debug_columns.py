"""기존 Slack List의 시즌4 컬럼/옵션 ID를 조회합니다.

이 스크립트는 ``setup_slack_list.py``와 동일한 스키마 검증 및 매핑 로직을
사용합니다. 출력값을 확인하거나 기존 List를 자동 연결하려면 다음 명령을
사용하세요.

    python debug_columns.py
    python setup_slack_list.py --existing-list-id "$SLACK_LIST_ID"
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from setup_slack_list import (
    COLUMN_ENV_BY_KEY,
    OPTIONAL_COLUMN_ENVS,
    SELECT_OPTION_ENVS,
    WEEK_OPTIONS,
    _get_existing_list_schema,
    _schema_to_env,
)


COLUMN_ENV_ORDER = list(dict.fromkeys(COLUMN_ENV_BY_KEY.values()))
OPTION_ENV_ORDER = [
    *(f"SLACK_LIST_OPT_{week.upper()}" for week in WEEK_OPTIONS),
    *(env for mapping in SELECT_OPTION_ENVS.values() for env in mapping.values()),
]


def _render_env(values: dict[str, str]) -> str:
    """검증된 매핑을 .env에 붙여 넣을 수 있는 형태로 반환합니다."""
    lines = ["# Slack List Column ID"]
    for env_key in COLUMN_ENV_ORDER:
        value = values.get(env_key, "")
        if value:
            lines.append(f"{env_key}={value}")
        elif env_key in OPTIONAL_COLUMN_ENVS:
            lines.append(f"# {env_key}=  # 선택 컬럼: 현재 List에 없음")

    lines.extend(("", "# Slack List SELECT option 값"))
    lines.extend(f"{env_key}={values[env_key]}" for env_key in OPTION_ENV_ORDER)
    return "\n".join(lines)


def main() -> int:
    load_dotenv()
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    list_id = os.environ.get("SLACK_LIST_ID", "")
    if not token or token == "your-bot-token-here":
        raise SystemExit(".env에 실제 SLACK_BOT_TOKEN을 설정하세요.")
    if not list_id or list_id == "FXXXXXXXXXX":
        raise SystemExit(".env에 실제 SLACK_LIST_ID를 설정하세요.")

    client = WebClient(token=token)
    try:
        schema: list[dict[str, Any]] = _get_existing_list_schema(client, list_id)
        if not schema:
            raise RuntimeError("Slack 응답에 List schema가 없습니다.")
        values = _schema_to_env(list_id, schema)
    except SlackApiError as exc:
        error = exc.response.get("error", "unknown_error")
        raise SystemExit(f"Slack List 조회 실패: {error}") from exc
    except RuntimeError as exc:
        raise SystemExit(f"Slack List 스키마 검증 실패: {exc}") from exc

    print("# Slack List schema")
    print(json.dumps(schema, indent=2, ensure_ascii=False))
    print()
    print(_render_env(values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
