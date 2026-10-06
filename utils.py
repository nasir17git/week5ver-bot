"""공통 유틸리티."""

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo


_KST = ZoneInfo("Asia/Seoul")


def _today_kst() -> date:
    return datetime.now(_KST).date()


def get_today_kst() -> date:
    """현재 한국 날짜를 반환합니다."""
    return _today_kst()


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

# 진행 일정: (주차명, 월요일, 일요일)
WEEK_SCHEDULE = [
    ("week1",  date(2026, 9, 14), date(2026, 9, 20)),
    ("week2",  date(2026, 9, 21), date(2026, 9, 27)),
    ("week3",  date(2026, 9, 28), date(2026, 10, 4)),
    ("week4",  date(2026, 10, 5), date(2026, 10, 11)),
    ("week5",  date(2026, 10, 12), date(2026, 10, 18)),
    ("week6",  date(2026, 10, 19), date(2026, 10, 25)),
    ("week7",  date(2026, 10, 26), date(2026, 11, 1)),
    ("week8",  date(2026, 11, 2), date(2026, 11, 8)),
    ("week9",  date(2026, 11, 9), date(2026, 11, 15)),
    ("week10", date(2026, 11, 16), date(2026, 11, 22)),
    ("week11", date(2026, 11, 23), date(2026, 11, 29)),
]

WEEK_NAMES = [name for name, _, _ in WEEK_SCHEDULE]

MONTH_WEEKS: dict[str, list[str]] = {}
for week, monday, _ in WEEK_SCHEDULE:
    MONTH_WEEKS.setdefault(monday.strftime("%Y-%m"), []).append(week)


def get_week_dates(week: str) -> tuple[date, date]:
    """주차의 월요일과 일요일을 반환합니다."""
    for name, start, end in WEEK_SCHEDULE:
        if name == week:
            return start, end
    raise ValueError(f"알 수 없는 주차입니다: {week}")


def get_week_option_id(week: str) -> str | None:
    """주차명을 Slack List select option ID로 변환. 환경변수에서 읽음. 미설정이면 None."""
    env_key = f"SLACK_LIST_OPT_{week.upper()}"
    val = os.environ.get(env_key, "")
    return val if val else None


def get_certification_week() -> str | None:
    """오늘 날짜 기준으로 등록·인증 기간(월~일)에 해당하는 주차명 반환."""
    today = _today_kst()
    for name, start, end in WEEK_SCHEDULE:
        if start <= today <= end:
            return name
    return None


def get_current_week() -> str | None:
    """오늘 날짜 기준으로 해당 주차명 반환. 겹치는 경우 가장 최근 시작 주차 우선. 해당 없으면 None."""
    today = _today_kst()
    result = None
    for name, start, end in WEEK_SCHEDULE:
        if start <= today <= end:
            result = name
    return result


def classify_week(week: str, status: str, registered: int, completed: int) -> str:
    """현재 List 상태와 날짜를 기준으로 참여현황 판정을 반환."""
    if status == "rest":
        return "판정 제외"
    schedule = next((row for row in WEEK_SCHEDULE if row[0] == week), None)
    if not schedule:
        raise ValueError(f"알 수 없는 주차입니다: {week}")
    _, _, sunday = schedule
    ended = _today_kst() > sunday
    if registered == 0:
        return "미등록" if ended else "등록 대기"
    if completed == registered:
        return "달성"
    return "미달성" if ended else "진행 중"
