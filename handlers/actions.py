"""버튼 클릭, 이모지 반응, Modal 제출(view_submission) 핸들러."""

import json
import os
from datetime import date
from templates import messages
from handlers.views import goal_register_modal, goal_update_modal, season_closed_modal
from slack_list.client import extract_title
from utils import collector_kwargs, updater_kwargs, get_certification_week, get_current_week, get_week_dates

def register_actions(app, list_client):
    channel_id = os.environ["SLACK_CHANNEL_ID"]

    # ── 버튼 핸들러 ──────────────────────────────────────────────────────────

    @app.action("open_goal_register_modal")
    def handle_open_register_modal(ack, body, client):
        ack()
        week = get_current_week()
        user_id = body["user"]["id"]
        if not week:
            client.views_open(trigger_id=body["trigger_id"], view=season_closed_modal())
            return
        loading = client.views_open(trigger_id=body["trigger_id"], view=season_closed_modal("참가 정보를 확인하고 있습니다…"))
        view_id = loading["view"]["id"]
        try:
            status = list_client.get_participation_status(user_id, week)
        except Exception:
            client.views_update(view_id=view_id, view=season_closed_modal("참가 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요."))
            return
        if status != "active":
            message = "이번 주는 휴식으로 설정되어 있습니다." if status == "rest" else "이번 달 참가 신청 내역이 없습니다."
            client.views_update(view_id=view_id, view=season_closed_modal(message))
            return
        meta = json.dumps({
            "channel_id": body.get("channel", {}).get("id", channel_id),
            "message_ts": body.get("message", {}).get("ts", ""),
            "week": week,
        })
        client.views_update(
            view_id=view_id,
            view=goal_register_modal(private_metadata=meta),
        )

    @app.action("open_goal_update_modal")
    def handle_open_update_modal(ack, body, client):
        ack()
        user_id = body["user"]["id"]
        week = get_certification_week()
        if not week:
            client.views_open(trigger_id=body["trigger_id"], view=season_closed_modal())
            return
        loading = client.views_open(trigger_id=body["trigger_id"], view=season_closed_modal("인증할 목표를 불러오고 있습니다…"))
        view_id = loading["view"]["id"]
        try:
            status = list_client.get_participation_status(user_id, week)
            items = list_client.get_incomplete_items_by_user(user_id, week=week) if status == "active" else []
        except Exception:
            client.views_update(view_id=view_id, view=season_closed_modal("목표를 불러오지 못했습니다. 잠시 후 다시 시도해주세요."))
            return
        if status != "active":
            message = "이번 주는 휴식으로 설정되어 있습니다." if status == "rest" else "이번 달 참가 신청 내역이 없습니다."
            client.views_update(view_id=view_id, view=season_closed_modal(message))
            return
        meta = json.dumps({
            "channel_id": body.get("channel", {}).get("id", channel_id),
            "message_ts": body.get("message", {}).get("ts", ""),
            "week": week,
        })
        client.views_update(
            view_id=view_id,
            view=goal_update_modal(items, private_metadata=meta),
        )

    # ── Modal 제출 핸들러 ────────────────────────────────────────────────────

    @app.view("goal_register_modal")
    def handle_goal_register_submit(ack, view, client, body):
        try:
            _register_submit(ack, view, client, body)
        except Exception:
            _notify_user(client, channel_id, body["user"]["id"], "목표 등록 중 오류가 발생했습니다. 일부 목표는 저장됐을 수 있으므로 List를 확인한 뒤 다시 시도해주세요.")

    def _register_submit(ack, view, client, body):
        user_id = body["user"]["id"]
        values  = view["state"]["values"]
        week    = values["week_block"]["week_input"].get("selected_option", {}).get("value")
        current_week = get_current_week()
        if not current_week or week != current_week:
            ack(response_action="errors", errors={"week_block": "현재 진행 중인 주차에만 등록할 수 있습니다."})
            return
        # 목표 최대 5개 수집 (빈 값 제외)
        lectures = []
        errors = {}
        week_start, week_end = get_week_dates(current_week)
        for i in range(1, 6):
            title    = (values.get(f"lecture_{i}_block", {})
                              .get(f"lecture_{i}_input", {})
                              .get("value") or "").strip()
            deadline = (values.get(f"deadline_{i}_block", {})
                              .get(f"deadline_{i}_input", {})
                              .get("selected_date"))
            if title and not deadline:
                errors[f"deadline_{i}_block"] = "이 목표를 완료할 예정일을 선택해주세요."
            elif deadline and not title:
                errors[f"lecture_{i}_block"] = "예정일을 선택한 목표의 내용을 입력해주세요."
            elif title:
                try:
                    planned = date.fromisoformat(deadline)
                except (TypeError, ValueError):
                    errors[f"deadline_{i}_block"] = "올바른 날짜를 선택해주세요."
                    continue
                if not week_start <= planned <= week_end:
                    errors[f"deadline_{i}_block"] = "현재 주차의 월요일부터 일요일 사이를 선택해주세요."
                lectures.append({"title": title, "deadline": deadline})

        if errors:
            ack(response_action="errors", errors=errors)
            return
        if not lectures:
            ack(response_action="errors", errors={"lecture_1_block": "목표를 한 개 이상 입력해주세요."})
            return
        ack()
        if list_client.get_participation_status(user_id, current_week) != "active":
            _notify_user(client, channel_id, user_id, "이번 주 참가 상태가 아니어서 목표를 등록할 수 없습니다.")
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
            if item:
                created_goals.append(lec)

        failed_count = len(lectures) - len(created_goals)
        if not created_goals:
            _notify_user(client, channel_id, user_id, "목표 저장에 실패했습니다. 잠시 후 다시 시도하거나 운영자에게 알려주세요.")
            return

        msg = messages.goal_registered(user_id=user_id, goals=created_goals)
        meta = _parse_meta(view.get("private_metadata", ""))
        try:
            _post_registered(client, channel_id, meta, msg)
        except Exception:
            _notify_user(client, channel_id, user_id, "목표는 저장됐지만 채널 안내 발송에 실패했습니다. 중복 등록하지 말고 List에서 확인해주세요.")
        if failed_count:
            _notify_user(client, channel_id, user_id, f"{failed_count}개 목표는 저장되지 않았습니다. 다시 등록해주세요.")

    @app.view("goal_update_modal")
    def handle_goal_update_submit(ack, view, client, body):
        try:
            return _handle_certification(ack, view, client, body, list_client, channel_id)
        except Exception:
            _notify_user(client, channel_id, body["user"]["id"], "인증 처리 중 오류가 발생했습니다. 일부 내용은 저장됐을 수 있으므로 List를 확인한 뒤 다시 시도해주세요.")


def _post_registered(client, channel_id, meta, msg):
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


def _handle_certification(ack, view, client, body, list_client, channel_id):
        user_id  = body["user"]["id"]
        values   = view["state"]["values"]
        meta = _parse_meta(view.get("private_metadata", ""))
        current_week = get_certification_week()
        if not current_week or meta.get("week") != current_week:
            ack(response_action="errors", errors={"goal_select_block": "현재 진행 중인 주차의 목표만 인증할 수 있습니다."})
            return
        proof_files = values.get("proof_block", {}).get("proof_input", {}).get("files")
        if (not isinstance(proof_files, list) or not 1 <= len(proof_files) <= 3
                or any(not isinstance(f, dict) or not isinstance(f.get("id"), str) or not f["id"] for f in proof_files)):
            ack(response_action="errors", errors={"proof_block": "이미지 또는 PDF 인증자료를 1~3개 첨부해주세요."})
            return
        ack()
        if list_client.get_participation_status(user_id, current_week) != "active":
            _notify_user(client, channel_id, user_id, "이번 주 참가 상태가 아니어서 인증할 수 없습니다.")
            return

        item_id  = (values["goal_select_block"]["goal_select_input"]
                         .get("selected_option", {}).get("value"))
        new_title = (values.get("title_edit_block", {})
                          .get("title_edit_input", {})
                          .get("value") or "").strip()
        retro    = (values.get("retro_block", {})
                         .get("retro_input", {})
                         .get("rich_text_value"))
        # file_input 결과는 files 키에 파일 ID 배열로 전달됨
        proof_files = (values.get("proof_block", {})
                             .get("proof_input", {})
                             .get("files") or [])
        proof_ids = [f["id"] for f in proof_files]

        goal = list_client.get_valid_goal(item_id, user_id, current_week) if item_id else None
        if not goal:
            _notify_user(client, channel_id, user_id, "이 목표는 이미 완료됐거나 현재 주차에 인증할 수 없습니다.")
            return

        updated = list_client.update_item(
                item_id=item_id,
                title=new_title or None,
                retro=retro or None,
                proof_file_ids=proof_ids or None,
                mark_done=True,
            )
        if not updated:
            _notify_user(client, channel_id, user_id, "인증 내용을 Slack List에 저장하지 못했습니다. 다시 시도해주세요.")
            return

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

        # 인증된 목표명: 입력값 있으면 사용, 없으면 기존 제목 조회
        if new_title:
            title = new_title
        else:
            title = extract_title(goal)

        msg = messages.goal_certified(
            user_id=user_id,
            title=title,
            retro=retro or None,
            file_permalinks=file_permalinks or None,
        )
        try:
            client.chat_postMessage(
                channel=meta.get("channel_id", channel_id),
                **updater_kwargs(),
                **msg,
            )
        except Exception:
            _notify_user(client, channel_id, user_id, "인증은 저장됐지만 채널 안내 발송에 실패했습니다. 완료 상태는 List에서 확인해주세요.")


def _parse_meta(raw: str) -> dict:
    """private_metadata JSON 파싱. 실패 시 빈 dict 반환."""
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _notify_user(client, channel_id: str, user_id: str, text: str) -> None:
    client.chat_postEphemeral(channel=channel_id, user=user_id, text=text)
