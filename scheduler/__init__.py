import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from scheduler.jobs import post_weekly_goal_request, post_daily_update_request

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


def create_scheduler(client) -> BackgroundScheduler:
    """APScheduler BackgroundScheduler를 생성하고 주간·일간 job을 등록합니다."""
    scheduler = BackgroundScheduler(timezone=KST)

    # 매주 토요일 오전 12시 (00:00) KST — 주간 목표 등록 안내
    scheduler.add_job(
        post_weekly_goal_request,
        trigger=CronTrigger(day_of_week="sat", hour=0, minute=0, timezone=KST),
        args=[client],
        id="weekly_goal_request",
        name="주간 목표 등록 안내",
        replace_existing=True,
    )

    # 매일 오전 9시 KST — 일간 인증 안내
    scheduler.add_job(
        post_daily_update_request,
        trigger=CronTrigger(hour=9, minute=0, timezone=KST),
        args=[client],
        id="daily_update_request",
        name="일간 인증 안내",
        replace_existing=True,
    )

    logger.info("[Scheduler] 주간(토 00:00) / 일간(매일 09:00) KST job 등록 완료")
    return scheduler
