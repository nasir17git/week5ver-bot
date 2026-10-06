import os
from datetime import date
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
from utils import WEEK_NAMES, classify_week, get_today_kst, get_week_option_id


class SlackListClient:
    def __init__(self, client):
        self.client = client
        self.list_id = os.environ["SLACK_LIST_ID"]
        if isinstance(getattr(client, "retry_handlers", None), list) and not any(
            isinstance(handler, RateLimitErrorRetryHandler) for handler in client.retry_handlers
        ):
            client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=2))

    # ── 조회 ────────────────────────────────────────────────────────────────

    def _fetch_items(self) -> list:
        """내부용: List 전체 아이템 반환 (페이지네이션 포함)."""
        items = []
        cursor = None

        while True:
            kwargs = {"list_id": self.list_id, "limit": 100}
            if cursor:
                kwargs["cursor"] = cursor

            try:
                response = self.client.slackLists_items_list(**kwargs)
            except SlackApiError as e:
                print(f"[SlackList] _fetch_items 실패: {e.response.get('error')}")
                raise

            items.extend(response.get("items", []))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return items

    def list_items(self) -> list:
        """전체 아이템 조회."""
        items = self._fetch_items()
        print(f"[SlackList] 전체 아이템 수: {len(items)}")
        return items

    def get_items_by_user(self, user_id: str) -> list:
        """담당자(user 타입 필드)에 user_id가 포함된 아이템만 반환."""
        return [
            item for item in self._fetch_items()
            if _is_goal(item) and _is_assigned_to(item, user_id)
        ]

    def get_incomplete_items_by_user(self, user_id: str, week: str) -> list:
        """담당자가 user_id이고 todo_completed가 False인 아이템만 반환. 마감일 오름차순.
        week 지정 시 해당 주차 아이템만 반환."""
        col_todo = _required_env("SLACK_LIST_COL_TODO_COMPLETED")
        week_option_id = _required_week_option(week)
        items = [
            item for item in self._fetch_items()
            if _is_goal(item)
            and _is_assigned_to(item, user_id)
            and not _is_completed(item, col_todo)
            and _is_week_match(item, week_option_id)
        ]
        items.sort(key=_get_deadline)
        return items

    def get_all_incomplete_items(self, week: str) -> list:
        """현재 주차에서 오늘까지 완료 예정인 미완료 목표를 반환."""
        col_todo = _required_env("SLACK_LIST_COL_TODO_COMPLETED")
        week_option_id = _required_week_option(week)
        today = get_today_kst()
        return [
            item for item in self._fetch_items()
            if _is_goal(item)
            and not _is_completed(item, col_todo)
            and _is_week_match(item, week_option_id)
            and _is_due_by(item, today)
        ]

    def get_valid_goal(self, item_id: str, user_id: str, week: str) -> dict | None:
        """현재 주차의 본인 소유 미완료 목표만 반환."""
        col_todo = _required_env("SLACK_LIST_COL_TODO_COMPLETED")
        week_option_id = _required_week_option(week)
        return next((
            item for item in self._fetch_items()
            if item.get("id") == item_id
            and _is_goal(item)
            and _is_assigned_to(item, user_id)
            and not _is_completed(item, col_todo)
            and _is_week_match(item, week_option_id)
        ), None)

    def get_participation_status(self, user_id: str, week: str) -> str | None:
        """참여현황 행의 상태를 active/rest로 반환. 신청 행이 없으면 None."""
        week_option = _required_week_option(week)
        rows = [
            item for item in self._fetch_items()
            if _is_participation(item)
            and _is_assigned_to(item, user_id)
            and _is_week_match(item, week_option)
        ]
        if len(rows) > 1:
            raise RuntimeError(f"중복 참여현황입니다: {user_id} / {week}")
        if not rows:
            return None
        row = rows[0]
        if _has_select(row, "SLACK_LIST_COL_PARTICIPATION_STATUS", "SLACK_LIST_OPT_STATUS_REST"):
            return "rest"
        if _has_select(row, "SLACK_LIST_COL_PARTICIPATION_STATUS", "SLACK_LIST_OPT_STATUS_ACTIVE"):
            return "active"
        return None

    # ── 생성 ────────────────────────────────────────────────────────────────

    def create_item(
        self,
        title: str,
        user_id: str,
        deadline: str | None = None,
        week: str | None = None,
    ) -> dict:
        """Slack List에 목표 아이템을 생성합니다.

        필요한 환경 변수 (column ID):
          SLACK_LIST_COL_TITLE      목표 제목
          SLACK_LIST_COL_ASSIGNEE   담당자
          SLACK_LIST_COL_DEADLINE   기한
          SLACK_LIST_COL_WEEK       주차 (select option ID와 값이 일치해야 함)
        """
        initial_fields = _build_create_fields(
            title=title,
            user_id=user_id,
            deadline=deadline,
            week=_required_week_option(week) if week else None,
        )

        try:
            response = self.client.slackLists_items_create(
                list_id=self.list_id,
                initial_fields=initial_fields,
            )
        except SlackApiError as e:
            print(f"[SlackList] create_item 실패: {e.response.get('error')}")
            return {}

        item = response.get("item", {})
        print(f"[SlackList] create_item 성공: id={item.get('id')}")
        return item

    def sync_participation(self, user_id: str, week: str, status: str = "active", *, items: list | None = None) -> tuple[dict, bool]:
        """사용자·주차 참여현황 행을 없을 때만 생성. (item, created)"""
        if items is None:
            items = self._fetch_items()
        existing = next((
            item for item in items
            if _is_participation(item)
            and _is_assigned_to(item, user_id)
            and _is_week_match(item, _required_week_option(week))
        ), None)
        status_value = _required_env(
            "SLACK_LIST_OPT_STATUS_REST" if status == "rest" else "SLACK_LIST_OPT_STATUS_ACTIVE"
        )
        if existing:
            # 운영자가 List에서 지정한 휴식 상태를 재동기화로 덮어쓰지 않습니다.
            return existing, False

        fields = [
            {"column_id": _required_env("SLACK_LIST_COL_TITLE"), "rich_text": _rich_text_block("참여현황")},
            {"column_id": _required_env("SLACK_LIST_COL_ASSIGNEE"), "user": [user_id]},
            {"column_id": _required_env("SLACK_LIST_COL_WEEK"), "select": [_required_week_option(week)]},
            {"column_id": _required_env("SLACK_LIST_COL_ROW_TYPE"), "select": [_required_env("SLACK_LIST_OPT_ROW_PARTICIPATION")]},
            {"column_id": _required_env("SLACK_LIST_COL_PARTICIPATION_STATUS"), "select": [status_value]},
            {"column_id": _required_env("SLACK_LIST_COL_REGISTERED_COUNT"), "number": [0]},
            {"column_id": _required_env("SLACK_LIST_COL_COMPLETED_COUNT"), "number": [0]},
        ]
        response = self.client.slackLists_items_create(list_id=self.list_id, initial_fields=fields)
        created = response.get("item", {})
        if not created.get("id"):
            raise RuntimeError("참여현황 생성 응답에 ID가 없습니다. List를 확인한 뒤 재시도하세요.")
        items.append(created)
        return created, True

    def refresh_participation_stats(self) -> list[dict]:
        """현재 List 상태로 참여현황 행의 등록/완료 수와 판정을 다시 기록."""
        items = self._fetch_items()
        goals = [item for item in items if _is_goal(item)]
        results = []
        seen = set()
        for row in (item for item in items if _is_participation(item)):
            users = extract_assignees(row)
            weeks = _field_values(row, _required_env("SLACK_LIST_COL_WEEK"), "select")
            states = _field_values(row, _required_env("SLACK_LIST_COL_PARTICIPATION_STATUS"), "select")
            valid_states = {_required_env("SLACK_LIST_OPT_STATUS_ACTIVE"), _required_env("SLACK_LIST_OPT_STATUS_REST")}
            if len(users) != 1 or len(weeks) != 1 or len(states) != 1 or states[0] not in valid_states:
                raise RuntimeError(f"참여현황 {row.get('id')}의 담당자·주차·참여 상태를 확인하세요.")
            if weeks[0] not in {_required_week_option(week) for week in WEEK_NAMES}:
                raise RuntimeError(f"참여현황 {row.get('id')}의 주차를 확인하세요.")
            key = (users[0], weeks[0])
            if key in seen:
                raise RuntimeError(f"중복 참여현황입니다: {users[0]} / {weeks[0]}")
            seen.add(key)
        for row in (item for item in items if _is_participation(item)):
            users = extract_assignees(row)
            week_value = _field_values(row, _required_env("SLACK_LIST_COL_WEEK"), "select")
            if not users or not week_value:
                continue
            user_id, week_option = users[0], week_value[0]
            user_goals = [
                item for item in goals
                if _is_assigned_to(item, user_id) and _is_week_match(item, week_option)
            ]
            registered = len(user_goals)
            completed_col = _required_env("SLACK_LIST_COL_TODO_COMPLETED")
            completed = sum(_is_completed(item, completed_col) for item in user_goals)
            is_rest = _has_select(row, "SLACK_LIST_COL_PARTICIPATION_STATUS", "SLACK_LIST_OPT_STATUS_REST")
            week = next((name for name in WEEK_NAMES if get_week_option_id(name) == week_option), None)
            if not week:
                raise RuntimeError(f"참여현황 행의 주차 옵션을 해석할 수 없습니다: {week_option}")
            judgment = classify_week(week, "rest" if is_rest else "active", registered, completed)
            cells = []
            registered_col = _required_env("SLACK_LIST_COL_REGISTERED_COUNT")
            completed_col = _required_env("SLACK_LIST_COL_COMPLETED_COUNT")
            judgment_col = _required_env("SLACK_LIST_COL_JUDGMENT")
            if _field_values(row, registered_col, "number") != [registered]:
                cells.append({"row_id": row["id"], "column_id": registered_col, "number": [registered]})
            if _field_values(row, completed_col, "number") != [completed]:
                cells.append({"row_id": row["id"], "column_id": completed_col, "number": [completed]})
            if _field_text(row, judgment_col) != judgment:
                cells.append({"row_id": row["id"], "column_id": judgment_col, "rich_text": _rich_text_block(judgment)})
            if cells:
                self.client.slackLists_items_update(list_id=self.list_id, cells=cells)
            results.append({"user_id": user_id, "week_option": week_option, "registered": registered, "completed": completed, "judgment": judgment})
        return results

    # ── 수정 ────────────────────────────────────────────────────────────────

    def update_item(
        self,
        item_id: str,
        title: str | None = None,
        retro: str | None = None,
        proof_file_ids: list | None = None,
        mark_done: bool = False,
    ) -> bool:
        """Slack List 아이템을 수정합니다 (일간 인증).

        필요한 환경 변수 (column ID):
          SLACK_LIST_COL_TITLE            목표 제목
          SLACK_LIST_COL_RETRO            한 줄 회고
          SLACK_LIST_COL_PROOF            인증자료
          SLACK_LIST_COL_TODO_COMPLETED   todo_completed 불리언 컬럼 (todo_mode 활성화 필요)
        """
        cells = _build_update_cells(
            row_id=item_id,
            title=title,
            retro=retro,
            proof_file_ids=proof_file_ids,
            mark_done=mark_done,
        )

        if not cells:
            return True  # 업데이트할 내용 없음

        try:
            self.client.slackLists_items_update(
                list_id=self.list_id,
                cells=cells,
            )
        except SlackApiError as e:
            print(f"[SlackList] update_item 실패 (error={e.response.get('error')}): {e.response.data}")
            return False

        print(f"[SlackList] update_item 성공: row_id={item_id}")
        return True


# ── 헬퍼 함수 ────────────────────────────────────────────────────────────────

def _rich_text_block(text: str) -> list:
    """텍스트 문자열을 Slack rich_text 블록 형식으로 변환."""
    return [
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": text}],
                }
            ],
        }
    ]


def _build_create_fields(
    title: str,
    user_id: str,
    deadline: str | None,
    week: str | None,
) -> list:
    """create_item용 initial_fields 배열 구성."""
    fields: list = []

    col_title    = _required_env("SLACK_LIST_COL_TITLE")
    col_assignee = _required_env("SLACK_LIST_COL_ASSIGNEE")
    col_deadline = _required_env("SLACK_LIST_COL_DEADLINE")
    col_week     = _required_env("SLACK_LIST_COL_WEEK")

    if col_title and title:
        fields.append({"column_id": col_title, "rich_text": _rich_text_block(title)})
    if col_assignee and user_id:
        fields.append({"column_id": col_assignee, "user": [user_id]})
    if col_deadline and deadline:
        fields.append({"column_id": col_deadline, "date": [deadline]})
    if col_week and week:
        fields.append({"column_id": col_week, "select": [week]})
    row_type_col = _required_env("SLACK_LIST_COL_ROW_TYPE")
    row_goal = _required_env("SLACK_LIST_OPT_ROW_GOAL")
    fields.append({"column_id": row_type_col, "select": [row_goal]})

    return fields


def _build_update_cells(
    row_id: str,
    title: str | None,
    retro: str | None,
    proof_file_ids: list | None,
    mark_done: bool = False,
) -> list:
    """update_item용 cells 배열 구성. 각 셀에 row_id 포함."""
    cells: list = []

    col_title          = _required_env("SLACK_LIST_COL_TITLE") if title else ""
    col_retro          = _required_env("SLACK_LIST_COL_RETRO") if retro else ""
    col_proof          = _required_env("SLACK_LIST_COL_PROOF") if proof_file_ids else ""
    col_todo_completed = _required_env("SLACK_LIST_COL_TODO_COMPLETED") if mark_done else ""

    if col_title and title:
        cells.append({
            "row_id": row_id,
            "column_id": col_title,
            "rich_text": _rich_text_block(title),
        })
    if col_retro and retro:
        cells.append({
            "row_id": row_id,
            "column_id": col_retro,
            "rich_text": [retro] if isinstance(retro, dict) else _rich_text_block(retro),
        })
    if col_proof and proof_file_ids:
        cells.append({
            "row_id": row_id,
            "column_id": col_proof,
            "attachment": proof_file_ids,
        })
    if mark_done and col_todo_completed:
        cells.append({
            "row_id": row_id,
            "column_id": col_todo_completed,
            "checkbox": True,
        })

    return cells


def _get_deadline(item: dict) -> str:
    """마감일(date 타입) 컬럼 값을 'YYYY-MM-DD' 문자열로 반환. 없으면 '9999-12-31' (뒤로 정렬)."""
    col_deadline = os.environ.get("SLACK_LIST_COL_DEADLINE")
    if not col_deadline:
        return "9999-12-31"
    for field in item.get("fields", []):
        if field.get("column_id") == col_deadline:
            date_values = field.get("date", [])
            if date_values:
                return date_values[0]
    return "9999-12-31"


def _is_week_match(item: dict, week_option_id: str | None) -> bool:
    """주차가 일치하는 아이템만 통과. 미설정은 통과하지 않음."""
    if not week_option_id:
        return False
    col_week = os.environ.get("SLACK_LIST_COL_WEEK")
    if not col_week:
        return False
    for field in item.get("fields", []):
        if field.get("column_id") == col_week:
            return week_option_id in field.get("select", [])
    return False


def _required_env(key: str) -> str:
    value = os.environ.get(key, "")
    if not value or value.endswith("XXXXXXXXX"):
        raise RuntimeError(f"필수 환경 변수 {key}가 설정되지 않았습니다.")
    return value


def _required_week_option(week: str) -> str:
    if week not in WEEK_NAMES:
        raise RuntimeError(f"알 수 없는 주차: {week}")
    return _required_env(f"SLACK_LIST_OPT_{week.upper()}")


def _field_values(item: dict, column_id: str, field_name: str) -> list:
    for field in item.get("fields", []):
        if field.get("column_id") == column_id:
            return field.get(field_name, []) or []
    return []


def _field_text(item: dict, column_id: str) -> str:
    """Slack text/rich_text 필드의 평문 값을 반환."""
    for field in item.get("fields", []):
        if field.get("column_id") == column_id:
            return field.get("text") or field.get("value") or ""
    return ""


def _has_select(item: dict, column_env: str, option_env: str) -> bool:
    column_id = os.environ.get(column_env, "")
    option = os.environ.get(option_env, "")
    return bool(column_id and option and option in _field_values(item, column_id, "select"))


def _is_participation(item: dict) -> bool:
    _required_env("SLACK_LIST_COL_ROW_TYPE")
    _required_env("SLACK_LIST_OPT_ROW_PARTICIPATION")
    return _has_select(item, "SLACK_LIST_COL_ROW_TYPE", "SLACK_LIST_OPT_ROW_PARTICIPATION")


def _is_goal(item: dict) -> bool:
    # 기존 행은 행 구분 값이 없어도 목표로 취급합니다.
    return not _is_participation(item)


def _is_due_by(item: dict, cutoff: date) -> bool:
    """기한이 cutoff 이전 또는 당일이면 True. 기한 없는 기존 목표도 포함."""
    col_deadline = os.environ.get("SLACK_LIST_COL_DEADLINE")
    if not col_deadline:
        return True
    for field in item.get("fields", []):
        if field.get("column_id") == col_deadline:
            date_values = field.get("date", [])
            if not date_values:
                return True
            try:
                return date.fromisoformat(date_values[0]) <= cutoff
            except (ValueError, TypeError):
                return True
    return True


def _is_completed(item: dict, col_todo: str | None) -> bool:
    """todo_completed 컬럼의 checkbox 값이 True이면 완료로 판단."""
    if not col_todo:
        return False
    for field in item.get("fields", []):
        if field.get("column_id") == col_todo:
            return field.get("checkbox", False)
    return False


def _is_assigned_to(item: dict, user_id: str) -> bool:
    """설정된 담당자 컬럼만 소유권 판정에 사용합니다."""
    return user_id in extract_assignees(item)


def extract_title(item: dict) -> str:
    """아이템에서 제목 텍스트 추출. SLACK_LIST_COL_TITLE 컬럼 ID로 정확히 찾음."""
    col_title = os.environ.get("SLACK_LIST_COL_TITLE")
    for field in item.get("fields", []):
        if col_title and field.get("column_id") == col_title:
            return field.get("text") or "(제목 없음)"
    # fallback: text 키가 있는 첫 번째 필드
    for field in item.get("fields", []):
        if field.get("text"):
            return field["text"]
    return "(제목 없음)"


def extract_assignees(item: dict) -> list:
    """아이템에서 담당자 user_id 목록 추출."""
    col_assignee = os.environ.get("SLACK_LIST_COL_ASSIGNEE")
    for field in item.get("fields", []):
        if col_assignee and field.get("column_id") == col_assignee:
            return field.get("user", [])
    return []
