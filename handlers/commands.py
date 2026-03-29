import os
from slack_list.client import SlackListClient
from handlers.views import goal_register_modal, goal_update_modal, goal_view_modal
from scheduler.jobs import post_weekly_goal_request, post_daily_update_request


def register_commands(app):
    list_client = SlackListClient(app.client)

    @app.command("/목표등록")
    def handle_goal_register(ack, command, client):
        ack()
        client.views_open(
            trigger_id=command["trigger_id"],
            view=goal_register_modal(),
        )

    @app.command("/목표조회")
    def handle_goal_list(ack, command, client):
        ack()
        items = list_client.get_items_by_user(command["user_id"])
        client.views_open(
            trigger_id=command["trigger_id"],
            view=goal_view_modal(items),
        )

    @app.command("/목표인증")
    def handle_goal_certify(ack, command, client):
        ack()
        items = list_client.get_incomplete_items_by_user(command["user_id"])
        client.views_open(
            trigger_id=command["trigger_id"],
            view=goal_update_modal(items),
        )

    @app.command("/주간공지발송")
    def handle_send_weekly_notice(ack, respond, client):
        """주간 목표 등록 안내 메시지 수동 발송."""
        ack()
        post_weekly_goal_request(client)
        respond(response_type="ephemeral", text="주간 목표 등록 안내 메시지를 발송했습니다.")

    @app.command("/일간공지발송")
    def handle_send_daily_notice(ack, respond, client):
        """일간 인증 안내 메시지 수동 발송."""
        ack()
        post_daily_update_request(client)
        respond(response_type="ephemeral", text="일간 인증 안내 메시지를 발송했습니다.")
