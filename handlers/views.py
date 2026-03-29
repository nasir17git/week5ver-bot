"""Modal(팝업) UI 정의 — Block Kit JSON 반환 함수 모음."""

from slack_list.client import extract_title
from utils import WEEK_NAMES, get_current_week


def goal_register_modal(private_metadata: str = "") -> dict:
    """주간 목표 등록 Modal (강의 최대 5개 + 수강 예정일)."""
    current_week = get_current_week()

    week_options = [
        {"text": {"type": "plain_text", "text": w}, "value": w}
        for w in WEEK_NAMES
    ]

    blocks = [
        {
            "type": "input",
            "block_id": "week_block",
            "label": {"type": "plain_text", "text": "주차"},
            "element": {
                "type": "static_select",
                "action_id": "week_input",
                "options": week_options,
                **({"initial_option": {"text": {"type": "plain_text", "text": current_week}, "value": current_week}} if current_week else {}),
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "수강 예정 강의를 최대 5개까지 입력하세요."},
        },
    ]

    for i in range(1, 6):
        required = i == 1
        blocks.append(
            {
                "type": "input",
                "block_id": f"lecture_{i}_block",
                "label": {"type": "plain_text", "text": f"강의 {i}"},
                "optional": not required,
                "element": {
                    "type": "plain_text_input",
                    "action_id": f"lecture_{i}_input",
                    "placeholder": {"type": "plain_text", "text": "수강 예정 강의명"},
                    "max_length": 200,
                },
            }
        )
        blocks.append(
            {
                "type": "input",
                "block_id": f"deadline_{i}_block",
                "label": {"type": "plain_text", "text": f"강의 {i} 수강 예정일"},
                "optional": True,
                "element": {
                    "type": "datepicker",
                    "action_id": f"deadline_{i}_input",
                    "placeholder": {"type": "plain_text", "text": "날짜 선택"},
                },
            }
        )

    return {
        "type": "modal",
        "callback_id": "goal_register_modal",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "주간 목표 등록"},
        "submit": {"type": "plain_text", "text": "등록"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": blocks,
    }


def goal_update_modal(items: list, private_metadata: str = "") -> dict:
    """일간 인증 Modal (강의 선택 + 인증자료 + 한줄회고)."""
    if not items:
        return {
            "type": "modal",
            "title": {"type": "plain_text", "text": "일간 목표 인증"},
            "close": {"type": "plain_text", "text": "닫기"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "등록된 목표가 없습니다.\n먼저 `/목표등록`으로 이번 주 목표를 등록해주세요.",
                    },
                }
            ],
        }

    options = [
        {
            "text": {"type": "plain_text", "text": extract_title(item)[:75]},
            "value": item["id"],
        }
        for item in items
    ]

    return {
        "type": "modal",
        "callback_id": "goal_update_modal",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "일간 목표 인증"},
        "submit": {"type": "plain_text", "text": "인증"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "input",
                "block_id": "goal_select_block",
                "label": {"type": "plain_text", "text": "인증할 강의 선택"},
                "element": {
                    "type": "static_select",
                    "action_id": "goal_select_input",
                    "placeholder": {"type": "plain_text", "text": "강의를 선택하세요"},
                    "options": options,
                },
            },
            {
                "type": "input",
                "block_id": "proof_block",
                "label": {"type": "plain_text", "text": "인증자료"},
                "element": {
                    "type": "file_input",
                    "action_id": "proof_input",
                    "filetypes": ["jpg", "jpeg", "png", "gif", "pdf"],
                    "max_files": 3,
                },
            },
            {
                "type": "input",
                "block_id": "retro_block",
                "label": {"type": "plain_text", "text": "한 줄 회고"},
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "retro_input",
                    "placeholder": {"type": "plain_text", "text": "오늘의 한 줄 회고를 남겨주세요"},
                    "max_length": 500,
                },
            },
        ],
    }


def goal_view_modal(items: list) -> dict:
    """목표 조회 Modal (읽기 전용)."""
    if not items:
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "등록된 목표가 없습니다."}}
        ]
    else:
        blocks = []
        for i, item in enumerate(items, start=1):
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*{i}.* {extract_title(item)}"}}
            )
            blocks.append({"type": "divider"})

    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "내 목표 목록"},
        "close": {"type": "plain_text", "text": "닫기"},
        "blocks": blocks,
    }
