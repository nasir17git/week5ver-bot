import logging
import os
from templates import messages
from utils import get_current_week

logger = logging.getLogger(__name__)

_COLLECTOR_NAME     = "week5ver-collector"
_COLLECTOR_ICON_URL = os.environ.get("SLACK_COLLECTOR_ICON_URL", "")

_UPDATOR_NAME       = "week5ver-updator"
_UPDATOR_ICON_URL   = os.environ.get("SLACK_UPDATOR_ICON_URL", "")


def _bot_kwargs(username: str, icon_url: str) -> dict:
    kwargs = {"username": username}
    if icon_url:
        kwargs["icon_url"] = icon_url
    return kwargs


def post_weekly_goal_request(client) -> None:
    """주간 목표 등록 안내 메시지 발송."""
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    week = get_current_week()
    msg = messages.weekly_goal_request(week=week)
    result = client.chat_postMessage(
        channel=channel_id,
        **_bot_kwargs(_COLLECTOR_NAME, _COLLECTOR_ICON_URL),
        **msg,
    )
    logger.info(f"[Scheduler] 주간 목표 등록 안내 발송 ok={result['ok']} week={week}")


def post_daily_update_request(client) -> None:
    """일간 인증 안내 메시지 발송."""
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    msg = messages.daily_update_request()
    result = client.chat_postMessage(
        channel=channel_id,
        **_bot_kwargs(_UPDATOR_NAME, _UPDATOR_ICON_URL),
        **msg,
    )
    logger.info(f"[Scheduler] 일간 인증 안내 발송 ok={result['ok']}")
