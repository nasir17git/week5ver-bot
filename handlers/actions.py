"""버튼 클릭, 이모지 반응, Modal 제출(view_submission) 핸들러."""

import json
import os
from templates import messages
from handlers.views import goal_register_modal, goal_update_modal
from utils import collector_kwargs, updater_kwargs, get_certification_week

# 이모지 트리거 설정
EMOJI_GOAL_REGISTER = os.environ.get("SLACK_EMOJI_GOAL_REGISTER", "pencil2")
EMOJI_GOAL_UPDATE   = os.environ.get("SLACK_EMOJI_GOAL_UPDATE",   "white_check_mark")


def register_actions(app, list_client):
    channel_id = os.environ["SLACK_CHANNEL_ID"]

    # ── 버튼 핸들러 ──────────────────────────────────────────────────────────

    @app.action("open_goal_register_modal")
    def handle_open_register_modal(ack, body, client):
        ack()
        meta = json.dumps({
            "channel_id": body.get("channel", {}).get("id", channel_id),
            "message_ts": body.get("message", {}).get("ts", ""),
        })
        client.views_open(
            trigger_id=body["trigger_id"],
            view=goal_register_modal(private_metadata=meta),
        )

    @app.action("open_goal_update_modal")
    def handle_open_update_modal(ack, body, client):
        ack()
        user_id = body["user"]["id"]
        items = list_client.get_incomplete_items_by_user(user_id, week=get_certification_week())
        meta = json.dumps({
            "channel_id": body.get("channel", {}).get("id", channel_id),
            "message_ts": body.get("message", {}).get("ts", ""),
        })
        client.views_open(
            trigger_id=body["trigger_id"],
            view=goal_update_modal(items, private_metadata=meta),
        )

    # ── 이모지 반응 핸들러 ───────────────────────────────────────────────────

    @app.event("reaction_added")
    def handle_reaction_added(event, client):
        reaction = event.get("reaction", "")
        user_id  = event.get("user")
        ch       = event.get("item", {}).get("channel")

        if ch != channel_id:
            return

        if reaction == EMOJI_GOAL_REGISTER:
            # trigger_id가 없으므로 채널 DM으로 안내
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="목표 등록은 `/목표등록` 슬래시 명령어 또는 안내 메시지의 버튼을 이용해주세요.",
            )

        elif reaction == EMOJI_GOAL_UPDATE:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="인증은 `/목표인증` 슬래시 명령어 또는 안내 메시지의 버튼을 이용해주세요.",
            )

    # ── Modal 제출 핸들러 ────────────────────────────────────────────────────

    @app.view("goal_register_modal")
    def handle_goal_register_submit(ack, view, client, body):
        ack()

        user_id = body["user"]["id"]
        values  = view["state"]["values"]
        week    = values["week_block"]["week_input"].get("selected_option", {}).get("value")

        # 5개 강의 수집 (빈 값 제외)
        lectures = []
        for i in range(1, 6):
            title    = (values.get(f"lecture_{i}_block", {})
                              .get(f"lecture_{i}_input", {})
                              .get("value") or "").strip()
            deadline = (values.get(f"deadline_{i}_block", {})
                              .get(f"deadline_{i}_input", {})
                              .get("selected_date"))
            if title:
                lectures.append({"title": title, "deadline": deadline})

        if not lectures:
            return

        # Slack List 아이템 생성
        created_goals = []
        for lec in lectures:
            item = list_client.create_item(
                title=lec["title"],
                user_id=user_id,
                deadline=lec["deadline"],
                week=week,
            )
            if item or not os.environ.get("SLACK_LIST_COL_TITLE"):
                # column ID 미설정 시에도 메시지는 전송
                created_goals.append(lec)

        msg = messages.goal_registered(user_id=user_id, goals=created_goals)
        meta = _parse_meta(view.get("private_metadata", ""))
        if meta.get("message_ts"):
            # 버튼 클릭: 원본 메시지에 스레드 댓글만
            client.chat_postMessage(
                channel=meta.get("channel_id", channel_id),
                thread_ts=meta["message_ts"],
                **collector_kwargs(),
                **msg,
            )
        else:
            # 슬래시 명령어: 채널에 직접 전송
            client.chat_postMessage(channel=channel_id, **collector_kwargs(), **msg)

    @app.view("goal_update_modal")
    def handle_goal_update_submit(ack, view, client, body):
        ack()

        user_id  = body["user"]["id"]
        values   = view["state"]["values"]

        item_id  = (values["goal_select_block"]["goal_select_input"]
                         .get("selected_option", {}).get("value"))
        retro    = (values.get("retro_block", {})
                         .get("retro_input", {})
                         .get("value") or "").strip()
        # file_input 결과는 files 키에 파일 ID 배열로 전달됨
        proof_files = (values.get("proof_block", {})
                             .get("proof_input", {})
                             .get("files") or [])
        proof_ids = [f["id"] for f in proof_files]

        if item_id:
            list_client.update_item(
                item_id=item_id,
                retro=retro or None,
                proof_file_ids=proof_ids or None,
                mark_done=True,
            )

        # 인증자료 퍼머링크 조회 (메시지 미리보기용)
        file_permalinks = []
        for fid in proof_ids:
            try:
                info = client.files_info(file=fid)
                pl = info.get("file", {}).get("permalink")
                if pl:
                    file_permalinks.append(pl)
            except Exception as e:
                print(f"[files.info] 파일 정보 조회 실패 fid={fid}: {e}")

        # 인증된 강의명 조회
        items = list_client.get_items_by_user(user_id)
        title = next(
            (f["text"] for item in items if item["id"] == item_id
             for f in item.get("fields", []) if f.get("text")),
            "(강의)"
        )

        msg = messages.goal_certified(
            user_id=user_id,
            title=title,
            retro=retro or None,
            file_permalinks=file_permalinks or None,
        )
        meta = _parse_meta(view.get("private_metadata", ""))
        if meta.get("message_ts"):
            # 버튼 클릭: 원본 메시지에 스레드 댓글 + 채널에도 전송
            client.chat_postMessage(
                channel=meta.get("channel_id", channel_id),
                thread_ts=meta["message_ts"],
                reply_broadcast=True,  # 스레드 댓글이 채널에도 노출
                **updater_kwargs(),
                **msg,
            )
        else:
            # 슬래시 명령어: 채널에 직접 전송
            client.chat_postMessage(channel=channel_id, **updater_kwargs(), **msg)


def _parse_meta(raw: str) -> dict:
    """private_metadata JSON 파싱. 실패 시 빈 dict 반환."""
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}
