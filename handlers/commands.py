import json
import os
import threading

from handlers.views import monthly_already_registered_modal, monthly_registration_modal, season_closed_modal
from scheduler.jobs import post_weekly_goal_request, post_daily_update_request, send_daily_notifications
from slack_list.client import SlackListClient
from utils import MONTH_WEEKS, get_current_week, get_registration_month


_monthly_registration_lock = threading.Lock()


def register_commands(app, list_client=None):
    def run(ack, respond, client, body, operation):
        ack()
        admins = {value.strip() for value in os.environ.get("SLACK_ADMIN_USER_IDS", "").split(",") if value.strip()}
        if body.get("user_id") not in admins:
            respond(response_type="ephemeral", text="운영자 전용 명령입니다. SLACK_ADMIN_USER_IDS 설정을 확인해주세요.")
            return
        if body.get("channel_id") != os.environ.get("SLACK_CHANNEL_ID"):
            respond(response_type="ephemeral", text="설정된 운영 채널에서만 실행할 수 있습니다.")
            return
        if not get_current_week():
            respond(response_type="ephemeral", text="운영 기간 밖이므로 안내·DM을 발송하지 않았습니다.")
            return
        try:
            operation(client)
        except Exception:
            respond(response_type="ephemeral", text="처리 중 오류가 발생했습니다. 일부 작업은 완료됐을 수 있으므로 재실행 전에 채널과 서버 로그를 확인해주세요.")
            return
        respond(response_type="ephemeral", text="명령 처리가 끝났습니다. 발송·고정의 일부 실패 여부는 서버 로그에서 확인해주세요.")

    @app.command("/등록발송")
    def handle_send_weekly_notice(ack, respond, client, body):
        """주간 목표 등록 안내 메시지 수동 발송."""
        run(ack, respond, client, body, post_weekly_goal_request)

    @app.command("/인증발송")
    def handle_send_daily_notice(ack, respond, client, body):
        """일간 인증 안내 메시지 수동 발송."""
        run(ack, respond, client, body, post_daily_update_request)

    @app.command("/알림발송")
    def handle_send_daily_notifications(ack, respond, client, body):
        """미완료 항목 담당자 DM 알림 수동 발송."""
        run(ack, respond, client, body, send_daily_notifications)

    @app.command("/월간등록")
    def handle_monthly_registration(ack, respond, client, body):
        """명령을 실행한 사용자를 현재 주차 월요일 기준 달의 참가자로 등록하기 전 확인 Modal을 엽니다.
        이미 그 달의 모든 주차에 참여현황이 있으면 안내 Modal만 보여줍니다."""
        ack()
        month = get_registration_month()
        if month not in MONTH_WEEKS:
            respond(response_type="ephemeral", text="현재는 월간 활동 등록 기간이 아닙니다.")
            return
        metadata = json.dumps({
            "month": month,
            "channel_id": body.get("channel_id", ""),
        })
        try:
            # List 조회가 trigger_id 만료(3초)보다 길 수 있어 로딩 Modal을 먼저 엽니다.
            loading = client.views_open(
                trigger_id=body["trigger_id"],
                view=season_closed_modal("참가 정보를 확인하고 있습니다…"),
            )
        except Exception:
            respond(response_type="ephemeral", text="등록 확인 창을 열지 못했습니다. 잠시 후 다시 시도해주세요.")
            return
        view_id = loading["view"]["id"]
        try:
            target = list_client or SlackListClient(client)
            weeks = MONTH_WEEKS[month]
            registered = target.get_registered_weeks(body["user_id"], weeks)
        except Exception:
            client.views_update(view_id=view_id, view=season_closed_modal("참가 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요."))
            return
        if set(weeks) <= registered:
            client.views_update(view_id=view_id, view=monthly_already_registered_modal(month))
            return
        client.views_update(view_id=view_id, view=monthly_registration_modal(month, private_metadata=metadata))

    @app.view("monthly_registration_modal")
    def handle_monthly_registration_submit(ack, view, client, body):
        ack()
        user_id = body["user"]["id"]
        try:
            metadata = json.loads(view.get("private_metadata", ""))
        except (json.JSONDecodeError, TypeError):
            metadata = {}
        month = metadata.get("month")
        channel_id = metadata.get("channel_id")

        # 오래 열어 둔 Modal로 다른 달을 등록하지 못하게 제출 시점에도 검증합니다.
        if month != get_registration_month() or month not in MONTH_WEEKS:
            _notify_monthly_result(client, channel_id, user_id, "등록 기간이 지났습니다. /월간등록을 다시 실행해주세요.")
            return

        try:
            target = list_client or SlackListClient(client)
            created = 0
            existing = 0
            # 한 프로세스 안의 동시 제출은 조회-생성 전체를 직렬화합니다.
            with _monthly_registration_lock:
                items = target.list_items()
                for week in MONTH_WEEKS[month]:
                    _, was_created = target.sync_participation(user_id, week, items=items)
                    created += int(was_created)
                    existing += int(not was_created)
        except Exception:
            _notify_monthly_result(
                client,
                channel_id,
                user_id,
                "월간 활동 등록 중 오류가 발생했습니다. 일부 주차는 등록됐을 수 있으며, 다시 실행해도 중복 생성되지 않습니다.",
            )
            return

        if created:
            text = f"{month} 활동 등록을 완료했습니다. 새로 등록된 주차 {created}개, 기존 등록 {existing}개입니다."
        else:
            text = f"{month} 활동은 이미 등록되어 있습니다. 기존 참가 상태(휴식 포함)를 유지했습니다."
        _notify_monthly_result(client, channel_id, user_id, text)


def _notify_monthly_result(client, channel_id: str | None, user_id: str, text: str) -> None:
    """원래 채널에 사용자만 볼 수 있는 처리 결과를 알립니다."""
    if channel_id:
        client.chat_postEphemeral(channel=channel_id, user=user_id, text=text)
    else:
        client.chat_postMessage(channel=user_id, text=text)
