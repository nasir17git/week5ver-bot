import logging
import os
from templates import messages
from utils import get_current_week, collector_kwargs, updater_kwargs

logger = logging.getLogger(__name__)


def post_weekly_goal_request(client) -> None:
    """주간 목표 등록 안내 메시지 발송."""
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    week = get_current_week()
    msg = messages.weekly_goal_request(week=week)
    result = client.chat_postMessage(
        channel=channel_id,
        **collector_kwargs(),
        **msg,
    )
    logger.info(f"[Scheduler] 주간 목표 등록 안내 발송 ok={result['ok']} week={week}")


def post_daily_update_request(client) -> None:
    """일간 인증 안내 메시지 발송."""
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    msg = messages.daily_update_request()
    result = client.chat_postMessage(
        channel=channel_id,
        **updater_kwargs(),
        **msg,
    )
    logger.info(f"[Scheduler] 일간 인증 안내 발송 ok={result['ok']}")
