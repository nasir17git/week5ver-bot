import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from scheduler.jobs import post_weekly_goal_request, post_daily_update_request, send_daily_notifications, expire_daily_update_message

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


def create_scheduler(client) -> BackgroundScheduler:
    """APScheduler BackgroundScheduler를 생성하고 주간·일간 job을 등록합니다."""
    scheduler = BackgroundScheduler(timezone=KST)

    # 매주 토요일 오전 12시 10분 KST — 주간 목표 등록 안내
    scheduler.add_job(
        post_weekly_goal_request,
        trigger=CronTrigger(day_of_week="sat", hour=0, minute=10, timezone=KST),
        args=[client],
        id="weekly_goal_request",
        name="주간 목표 등록 안내",
        replace_existing=True,
    )

    # 매일 오전 12시 10분 KST — 일간 인증 안내 (발송 후 24시간 뒤 만료 job 등록)
    def _post_daily_and_schedule_expire():
        ts, channel_id = post_daily_update_request(client)
        if ts and channel_id:
            expire_at = datetime.now(KST) + timedelta(hours=24)
            scheduler.add_job(
                expire_daily_update_message,
                trigger="date",
                run_date=expire_at,
                args=[client, channel_id, ts],
            )

    scheduler.add_job(
        _post_daily_and_schedule_expire,
        trigger=CronTrigger(hour=0, minute=10, timezone=KST),
        id="daily_update_request",
        name="일간 인증 안내",
        replace_existing=True,
    )

    # 매일 오후 9시 KST — 미완료 항목 담당자 DM 알림
    scheduler.add_job(
        send_daily_notifications,
        trigger=CronTrigger(hour=21, minute=0, timezone=KST),
        args=[client],
        id="daily_notifications",
        name="미완료 항목 DM 알림",
        replace_existing=True,
    )

    logger.info("[Scheduler] 주간(토 00:10) / 일간(매일 00:10) / 알림(매일 21:00) KST job 등록 완료")
    return scheduler
