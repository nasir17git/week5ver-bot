from scheduler.jobs import post_weekly_goal_request, post_daily_update_request, send_daily_notifications


def register_commands(app):
    @app.command("/등록발송")
    def handle_send_weekly_notice(ack, respond, client):
        """주간 목표 등록 안내 메시지 수동 발송."""
        ack()
        post_weekly_goal_request(client)
        respond(response_type="ephemeral", text="주간 목표 등록 안내 메시지를 발송했습니다.")

    @app.command("/인증발송")
    def handle_send_daily_notice(ack, respond, client):
        """일간 인증 안내 메시지 수동 발송."""
        ack()
        post_daily_update_request(client)
        respond(response_type="ephemeral", text="일간 인증 안내 메시지를 발송했습니다.")

    @app.command("/알림발송")
    def handle_send_daily_notifications(ack, respond, client):
        """미완료 항목 담당자 DM 알림 수동 발송."""
        ack()
        send_daily_notifications(client)
        respond(response_type="ephemeral", text="미완료 항목 담당자에게 DM 알림을 발송했습니다.")
