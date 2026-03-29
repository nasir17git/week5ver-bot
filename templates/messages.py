"""채널 전송용 봇 메시지 템플릿 모음."""

from datetime import date, timedelta
from utils import WEEK_SCHEDULE

_WEEK_EMOJIS = {
    "demo":  ":hammer:",
    "week1": ":seedling:",
    "week2": ":herb:",
    "week3": ":ear_of_rice:",
    "week4": ":sunflower:",
    "week5": ":deciduous_tree:",
    "week6": ":four_leaf_clover:",
    "week7": ":cherry_blossom:",
    "week8": ":fire:",
    "week9": ":sports_medal:",
}

_NUMBER_EMOJIS = [":one:", ":two:", ":three:", ":four:", ":five:"]
_NUMBER_LABELS = ["첫번째", "두번째", "세번째", "네번째", "다섯번째"]

_DAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def _fmt_day(d: date) -> str:
    """date → YYMMDD(요일)"""
    return d.strftime("%y%m%d") + f"({_DAY_KO[d.weekday()]})"


def weekly_goal_request(week: str | None = None) -> dict:
    """주간 목표 등록 안내 메시지 (버튼 포함)."""
    reg_start: date | None = None
    for name, start, _ in WEEK_SCHEDULE:
        if name == week:
            reg_start = start
            break

    header_date = reg_start.strftime("%Y-%m-%d") if reg_start else ""
    prog_start  = _fmt_day(date(2026, 3, 23))
    prog_end    = _fmt_day(date(2026, 5, 31))

    header = (
        f":calendar:  {header_date}  에 시작되는 주간 목표 등록\n"
        f"{prog_start}~{prog_end} 간 수강할 목표를 등록해주세요!\n"
        f"---\n:pushpin: 타임라인\n"
    )

    timeline_lines = []
    for name, start, _ in WEEK_SCHEDULE:
        emoji   = _WEEK_EMOJIS.get(name, ":calendar:")
        sat     = start.strftime("%y%m%d")
        sun     = (start + timedelta(days=1)).strftime("%d")
        timeline_lines.append(f"{emoji} {sat}~{sun} - {name} 주간 목표 등록")

    return {
        "text": "이번 주 수강 목표를 등록해주세요!",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": header},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(timeline_lines)},
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "주간 목표 등록"},
                        "action_id": "open_goal_register_modal",
                        "style": "primary",
                    }
                ],
            },
        ],
    }


def goal_registered(user_id: str, goals: list[dict]) -> dict:
    """주간 목표 등록 완료 메시지.

    goals: [{"title": str, "deadline": str | None}, ...]
    """
    lines = [f":rocket: <@{user_id}> 님이 다음의 주간 목표를 입력했습니다\n---\n:dart: 주간 수강 목표\n"]
    for i, goal in enumerate(goals):
        num   = _NUMBER_EMOJIS[i] if i < len(_NUMBER_EMOJIS) else f"{i+1}."
        label = _NUMBER_LABELS[i] if i < len(_NUMBER_LABELS) else f"{i+1}번째"
        date_str = f" / {goal['deadline']}" if goal.get("deadline") else ""
        lines.append(f"{num}{label} 수강 목표\n{goal['title']}{date_str}\n")

    return {
        "text": f"<@{user_id}> 님이 주간 목표를 등록했습니다.",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines)},
            }
        ],
    }


def goal_certified(
    user_id: str,
    title: str,
    retro: str | None = None,
    file_permalinks: list[str] | None = None,
) -> dict:
    """일간 인증 완료 메시지."""
    text = f":tada: <@{user_id}> 님이\n{title}\n\n강의 인증을 완료했습니다! :mortar_board::sparkles:"
    if retro:
        text += f"\n\n:memo: 한 줄 회고\n{retro}"

    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
    ]
    for permalink in (file_permalinks or []):
        blocks.append({
            "type": "image",
            "image_url": permalink,
            "alt_text": "인증자료",
        })

    return {
        "text": f"<@{user_id}> 님이 강의 인증을 완료했습니다.",
        "blocks": blocks,
    }


def daily_update_request() -> dict:
    """일간 인증 안내 메시지 (버튼 포함)."""
    today = date.today().strftime("%Y-%m-%d")
    return {
        "text": "오늘의 강의 인증을 해주세요!",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":calendar: *{today}*\n:white_check_mark: *오늘의 강의 인증을 해주세요!*\n수강 완료한 강의의 인증자료와 한 줄 회고를 남겨주세요.",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "일간 목표 인증"},
                        "action_id": "open_goal_update_modal",
                        "style": "primary",
                    }
                ],
            },
        ],
    }


def daily_update_expired() -> dict:
    """일간 인증 안내 메시지 만료 버전 (버튼 없음)."""
    today = date.today().strftime("%Y-%m-%d")
    return {
        "text": "인증 시간이 마감되었습니다.",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":calendar: *{today}*\n:lock: *인증 시간이 마감되었습니다.*",
                },
            },
        ],
    }


def error_message(text: str) -> dict:
    """에러 안내 메시지 (ephemeral용)."""
    return {
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f":warning: {text}"},
            }
        ],
    }
