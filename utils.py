"""공통 유틸리티."""

import os
from datetime import date


def collector_kwargs() -> dict:
    """week5ver-collector 봇 표시용 kwargs."""
    kwargs = {"username": "week5ver-collector"}
    icon_url = os.environ.get("SLACK_COLLECTOR_ICON_URL", "")
    if icon_url:
        kwargs["icon_url"] = icon_url
    return kwargs


def updater_kwargs() -> dict:
    """week5ver-updater 봇 표시용 kwargs."""
    kwargs = {"username": "week5ver-updater"}
    icon_url = os.environ.get("SLACK_UPDATOR_ICON_URL", "")
    if icon_url:
        kwargs["icon_url"] = icon_url
    return kwargs

# 진행 일정: (주차명, 시작일, 종료일)
WEEK_SCHEDULE = [
    ("demo",  date(2026, 3, 21),  date(2026, 3, 29)),
    ("week1", date(2026, 3, 28),  date(2026, 4,  5)),
    ("week2", date(2026, 4,  4),  date(2026, 4, 12)),
    ("week3", date(2026, 4, 11),  date(2026, 4, 19)),
    ("week4", date(2026, 4, 18),  date(2026, 4, 26)),
    ("week5", date(2026, 4, 25),  date(2026, 5,  3)),
    ("week6", date(2026, 5,  2),  date(2026, 5, 10)),
    ("week7", date(2026, 5,  9),  date(2026, 5, 17)),
    ("week8", date(2026, 5, 16),  date(2026, 5, 24)),
    ("week9", date(2026, 5, 23),  date(2026, 5, 31)),
]

WEEK_NAMES = [name for name, _, _ in WEEK_SCHEDULE]


# 주차명 → Slack List select option ID 매핑
# debug_columns.py 실행 결과를 보고 채워주세요
WEEK_OPTION_IDS: dict[str, str] = {
    "demo": "Opt2SU4DLJN",
    "week1": "OptP0EHJM8R",
    "week2": "OptVL3FAWOB",
    "week3": "OptSQCCK2TM",
    "week4": "OptZ93GPZN6",
    "week5": "Opt2AF3GT92",
    "week6": "OptHSJJAQII",
    "week7": "OptJQYZ0N2K",
    "week8": "OptACRFJHSP",
    "week9": "Opt96JD88U9",
}


def get_week_option_id(week: str) -> str | None:
    """주차명을 Slack List select option ID로 변환. 미설정이면 None."""
    val = WEEK_OPTION_IDS.get(week, "")
    return val if val else None


def get_current_week() -> str | None:
    """오늘 날짜 기준으로 해당 주차명 반환. 겹치는 경우 가장 최근 시작 주차 우선. 해당 없으면 None."""
    today = date.today()
    result = None
    for name, start, end in WEEK_SCHEDULE:
        if start <= today <= end:
            result = name
    return result
