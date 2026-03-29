"""공통 유틸리티."""

import os
from datetime import date, timedelta


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


def get_week_option_id(week: str) -> str | None:
    """주차명을 Slack List select option ID로 변환. 환경변수에서 읽음. 미설정이면 None."""
    env_key = f"SLACK_LIST_OPT_{week.upper()}"
    val = os.environ.get(env_key, "")
    return val if val else None


def get_certification_week() -> str | None:
    """오늘 날짜 기준으로 인증 기간(월~일)에 해당하는 주차명 반환.
    인증 기간 = 등록 주말 다음 월요일(start+2일) ~ end."""
    today = date.today()
    for name, start, end in WEEK_SCHEDULE:
        cert_start = start + timedelta(days=2)
        if cert_start <= today <= end:
            return name
    return None


def get_current_week() -> str | None:
    """오늘 날짜 기준으로 해당 주차명 반환. 겹치는 경우 가장 최근 시작 주차 우선. 해당 없으면 None."""
    today = date.today()
    result = None
    for name, start, end in WEEK_SCHEDULE:
        if start <= today <= end:
            result = name
    return result
