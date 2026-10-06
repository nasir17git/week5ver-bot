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

_WEEKLY_MESSAGE_TEXT = "이번 주 공부 목표를 등록해주세요!"
_WEEKLY_EVENT_TYPE = "week5ver_weekly_goal_request"


def _bot_kwargs(username: str, icon_url: str) -> dict:
    kwargs = {"username": username}
    if icon_url:
        kwargs["icon_url"] = icon_url
    return kwargs


def post_weekly_goal_request(client) -> None:
    """주간 목표 등록 안내 메시지를 발송하고 채널에 고정."""
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    week = get_current_week()
    if not week:
        logger.info("[Scheduler] 운영 기간 밖 — 주간 등록 안내 생략")
        return
    msg = messages.weekly_goal_request(week=week)
    result = client.chat_postMessage(
        channel=channel_id,
        metadata={
            "event_type": _WEEKLY_EVENT_TYPE,
            "event_payload": {"week": week or ""},
        },
        **collector_kwargs(),
        **msg,
    )
    logger.info(f"[Scheduler] 주간 목표 등록 안내 발송 ok={result['ok']} week={week}")
    if result["ok"]:
        try:
            client.pins_add(channel=channel_id, timestamp=result["ts"])
            logger.info(f"[Scheduler] 주간 목표 등록 안내 고정 완료 ts={result['ts']}")
            _unpin_previous_weekly_goal_requests(
                client,
                channel_id=channel_id,
                current_ts=result["ts"],
                bot_id=result.get("message", {}).get("bot_id"),
            )
        except Exception as e:
            # pins:read/pins:write가 없더라도 안내 메시지 발송 자체는 유지합니다.
            logger.warning(f"[Scheduler] 주간 목표 등록 안내 고정 처리 실패: {e}")


def _unpin_previous_weekly_goal_requests(
    client,
    channel_id: str,
    current_ts: str,
    bot_id: str | None = None,
) -> None:
    """현재 글을 제외한 이 봇의 이전 주간 등록 안내 고정을 해제."""
    response = client.pins_list(channel=channel_id)
    for item in response.get("items", []):
        message = item.get("message", {})
        ts = message.get("ts")
        if not ts or ts == current_ts:
            continue

        is_weekly = (
            message.get("metadata", {}).get("event_type") == _WEEKLY_EVENT_TYPE
            or message.get("text") in {_WEEKLY_MESSAGE_TEXT, "이번 주 수강 목표를 등록해주세요!"}
        )
        is_same_bot = bool(bot_id) and message.get("bot_id") == bot_id
        if is_weekly and is_same_bot:
            client.pins_remove(channel=channel_id, timestamp=ts)
            logger.info(f"[Scheduler] 이전 주간 등록 안내 고정 해제 ts={ts}")


def post_daily_update_request(client) -> tuple[str, str] | tuple[None, None]:
    """일간 인증 안내 메시지 발송. 성공 시 (ts, channel_id) 반환."""
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    if not get_current_week():
        logger.info("[Scheduler] 운영 기간 밖 — 일간 인증 안내 생략")
        return None, None
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


def send_daily_notifications(client) -> None:
    """미완료 항목 담당자에게 DM 발송 (매일 오후 9시 KST)."""
    from slack_list.client import SlackListClient, extract_title, extract_assignees

    list_client = SlackListClient(client)
    week = get_current_week()
    if not week:
        logger.info("[Notifier] 운영 기간 밖 — DM 생략")
        return
    incomplete_items = list_client.get_all_incomplete_items(week)

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
                f"이번 주 아직 인증하지 않은 목표가 {len(titles)}개 있어요:\n"
                f"{bullet_list}"
            )
            client.chat_postMessage(channel=dm_channel, text=text, **bot_kwargs)
            sent += 1
            logger.info(f"[Notifier] DM 발송 → {user_id} ({len(titles)}개)")
        except Exception as e:
            skipped += 1
            logger.warning(f"[Notifier] DM 발송 실패 user={user_id}: {e}")

    logger.info(f"[Notifier] 완료 — 발송={sent} 실패={skipped} 총={len(user_items)}")
