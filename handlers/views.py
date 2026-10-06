"""Modal(팝업) UI 정의 — Block Kit JSON 반환 함수 모음."""

import json

from slack_list.client import extract_title
from utils import MONTH_WEEKS, get_current_week, get_week_dates


def monthly_registration_modal(month: str, private_metadata: str | None = None) -> dict:
    """해당 월의 참가 신청 여부를 확인하는 Modal."""
    if private_metadata is None:
        private_metadata = json.dumps({"month": month})
    year, month_number = month.split("-", 1)
    month_label = f"{year}년 {int(month_number)}월"
    return {
        "type": "modal",
        "callback_id": "monthly_registration_modal",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "월간 활동 등록"},
        "submit": {"type": "plain_text", "text": "예"},
        "close": {"type": "plain_text", "text": "아니오"},
        "blocks": [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{month_label}* 활동을 등록하시겠습니까?\n등록하면 이 달에 배정된 모든 주차에 참가자로 추가됩니다.",
            },
        }],
    }


def monthly_already_registered_modal(month: str) -> dict:
    """해당 월의 모든 주차에 이미 참여현황이 있는 사용자에게 보여주는 Modal."""
    month_number = int(month.split("-", 1)[1])
    weeks = " · ".join(
        f"{week}({get_week_dates(week)[0].month}/{get_week_dates(week)[0].day}~)"
        for week in MONTH_WEEKS[month]
    )
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "월간 활동 등록"},
        "close": {"type": "plain_text", "text": "닫기"},
        "blocks": [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{month_number}월* 활동에 이미 등록되어 있습니다.\n{weeks}\n_월 구분은 주차의 월요일 기준입니다._",
            },
        }],
    }


def goal_register_modal(private_metadata: str = "") -> dict:
    """주간 목표 등록 Modal (목표 최대 5개 + 목표일)."""
    current_week = get_current_week()

    if not current_week:
        return season_closed_modal()

    available_weeks = [current_week]
    week_options = [
        {"text": {"type": "plain_text", "text": w}, "value": w}
        for w in available_weeks
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
                "initial_option": {"text": {"type": "plain_text", "text": current_week}, "value": current_week},
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "공부·독서·코딩 등 이번 주 목표를 한 번에 최대 5개까지 입력하세요. 목표 하나를 한 번 인증하면 완료됩니다."},
        },
    ]

    for i in range(1, 6):
        required = i == 1
        blocks.append(
            {
                "type": "input",
                "block_id": f"lecture_{i}_block",
                "label": {"type": "plain_text", "text": f"목표 {i}"},
                "optional": not required,
                "element": {
                    "type": "plain_text_input",
                    "action_id": f"lecture_{i}_input",
                    "placeholder": {"type": "plain_text", "text": "공부할 내용 또는 완료할 목표"},
                    "max_length": 200,
                },
            }
        )
        blocks.append(
            {
                "type": "input",
                "block_id": f"deadline_{i}_block",
                "label": {"type": "plain_text", "text": f"목표 {i} 완료 예정일"},
                "optional": not required,
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


def season_closed_modal(message: str = "현재는 Season 4 등록·인증 기간이 아닙니다.") -> dict:
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "week5ver"},
        "close": {"type": "plain_text", "text": "닫기"},
        "blocks": [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": message},
        }],
    }


def goal_update_modal(items: list, private_metadata: str = "") -> dict:
    """목표 인증 Modal (목표 선택 + 제목 변경 + 인증자료 + 한 줄 회고)."""
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
                        "text": "이번 주 인증할 미완료 목표가 없습니다.\n모두 완료했거나 아직 등록하지 않은 상태입니다.",
                    },
                }
            ],
        }

    options = [
        {
            "text": {"type": "plain_text", "text": (extract_title(item).strip() or "제목 없는 목표")[:75]},
            "value": item["id"],
        }
        for item in items[:100]
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
                "label": {"type": "plain_text", "text": "인증할 목표 선택"},
                "hint": {"type": "plain_text", "text": "미완료 목표를 최대 100개 표시합니다. 완료 후 다시 열면 다음 목표가 표시됩니다."},
                "element": {
                    "type": "static_select",
                    "action_id": "goal_select_input",
                    "placeholder": {"type": "plain_text", "text": "목표를 선택하세요"},
                    "options": options,
                    "initial_option": options[0],
                },
            },
            {
                "type": "input",
                "block_id": "title_edit_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "목표 제목 변경"},
                "hint": {"type": "plain_text", "text": "비워두면 기존 제목을 유지합니다."},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title_edit_input",
                    "placeholder": {"type": "plain_text", "text": "변경할 목표 제목 입력"},
                    "max_length": 200,
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
                    "type": "rich_text_input",
                    "action_id": "retro_input",
                    "placeholder": {"type": "plain_text", "text": "오늘의 한 줄 회고를 남겨주세요"},
                },
            },
        ],
    }
