import logging
import os
from collections import defaultdict
from templates import messages
from utils import get_current_week, collector_kwargs, updater_kwargs

logger = logging.getLogger(__name__)

_COLLECTOR_NAME     = "week5ver-collector"
_COLLECTOR_ICON_URL = os.environ.get("SLACK_COLLECTOR_ICON_URL", "")

_UPDATOR_NAME       = "week5ver-updator"
_UPDATOR_ICON_URL   = os.environ.get("SLACK_UPDATOR_ICON_URL", "")

_NOTIFIER_NAME      = "week5ver-notifier"
_NOTIFIER_ICON_URL  = os.environ.get("SLACK_NOTIFIER_ICON_URL", "")


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
        **collector_kwargs(),
        **msg,
    )
    logger.info(f"[Scheduler] 주간 목표 등록 안내 발송 ok={result['ok']} week={week}")


def post_daily_update_request(client) -> tuple[str, str] | tuple[None, None]:
    """일간 인증 안내 메시지 발송. 성공 시 (ts, channel_id) 반환."""
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    msg = messages.daily_update_request()
    result = client.chat_postMessage(
        channel=channel_id,
        **updater_kwargs(),
        **msg,
    )
    logger.info(f"[Scheduler] 일간 인증 안내 발송 ok={result['ok']}")
    if result["ok"]:
        return result["ts"], channel_id
    return None, None


def expire_daily_update_message(client, channel_id: str, ts: str) -> None:
    """일간 인증 안내 메시지를 만료 상태로 업데이트 (버튼 제거)."""
    msg = messages.daily_update_expired()
    try:
        client.chat_update(channel=channel_id, ts=ts, **msg)
        logger.info(f"[Scheduler] 일간 인증 안내 만료 처리 ts={ts}")
    except Exception as e:
        logger.warning(f"[Scheduler] 일간 인증 안내 만료 처리 실패: {e}")


def send_daily_notifications(client) -> None:
    """미완료 항목 담당자에게 DM 발송 (매일 오후 9시 KST)."""
    from slack_list.client import SlackListClient, extract_title, extract_assignees

    list_client = SlackListClient(client)
    incomplete_items = list_client.get_all_incomplete_items()

    if not incomplete_items:
        logger.info("[Notifier] 미완료 항목 없음 — DM 발송 생략")
        return

    # user_id → [title, ...] 그룹핑
    user_items: dict[str, list[str]] = defaultdict(list)
    for item in incomplete_items:
        title = extract_title(item)
        for user_id in extract_assignees(item):
            user_items[user_id].append(title)

    bot_kwargs = _bot_kwargs(_NOTIFIER_NAME, _NOTIFIER_ICON_URL)
    sent, skipped = 0, 0

    for user_id, titles in user_items.items():
        try:
            dm = client.conversations_open(users=user_id)
            dm_channel = dm["channel"]["id"]
            bullet_list = "\n".join(f"• {t}" for t in titles)
            text = (
                f"안녕하세요 <@{user_id}>! :wave:\n"
                f"오늘 아직 인증하지 않은 강의가 {len(titles)}개 있어요:\n"
                f"{bullet_list}"
            )
            client.chat_postMessage(channel=dm_channel, text=text, **bot_kwargs)
            sent += 1
            logger.info(f"[Notifier] DM 발송 → {user_id} ({len(titles)}개)")
        except Exception as e:
            skipped += 1
            logger.warning(f"[Notifier] DM 발송 실패 user={user_id}: {e}")

    logger.info(f"[Notifier] 완료 — 발송={sent} 실패={skipped} 총={len(user_items)}")
