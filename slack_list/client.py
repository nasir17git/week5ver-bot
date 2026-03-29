import os
from slack_sdk.errors import SlackApiError
from utils import get_week_option_id


class SlackListClient:
    def __init__(self, client):
        self.client = client
        self.list_id = os.environ["SLACK_LIST_ID"]

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
                break

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
        return [item for item in self._fetch_items() if _is_assigned_to(item, user_id)]

    def get_incomplete_items_by_user(self, user_id: str) -> list:
        """담당자가 user_id이고 todo_completed가 False인 아이템만 반환. updated_at 내림차순."""
        col_todo = os.environ.get("SLACK_LIST_COL_TODO_COMPLETED")
        items = [
            item for item in self._fetch_items()
            if _is_assigned_to(item, user_id) and not _is_completed(item, col_todo)
        ]
        items.sort(key=_get_updated_at, reverse=True)
        return items

    def get_all_incomplete_items(self) -> list:
        """todo_completed가 False인 전체 아이템 반환."""
        col_todo = os.environ.get("SLACK_LIST_COL_TODO_COMPLETED")
        return [
            item for item in self._fetch_items()
            if not _is_completed(item, col_todo)
        ]

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
          SLACK_LIST_COL_TITLE      수강예정 강의이름
          SLACK_LIST_COL_ASSIGNEE   담당자
          SLACK_LIST_COL_DEADLINE   기한
          SLACK_LIST_COL_WEEK       주차 (select option ID와 값이 일치해야 함)
        """
        initial_fields = _build_create_fields(
            title=title,
            user_id=user_id,
            deadline=deadline,
            week=get_week_option_id(week) if week else None,
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

    # ── 수정 ────────────────────────────────────────────────────────────────

    def update_item(
        self,
        item_id: str,
        retro: str | None = None,
        proof_file_ids: list | None = None,
        mark_done: bool = False,
    ) -> bool:
        """Slack List 아이템을 수정합니다 (일간 인증).

        필요한 환경 변수 (column ID):
          SLACK_LIST_COL_RETRO            한 줄 회고
          SLACK_LIST_COL_PROOF            인증자료
          SLACK_LIST_COL_TODO_COMPLETED   todo_completed 불리언 컬럼 (todo_mode 활성화 필요)
        """
        cells = _build_update_cells(
            row_id=item_id,
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

    col_title    = os.environ.get("SLACK_LIST_COL_TITLE")
    col_assignee = os.environ.get("SLACK_LIST_COL_ASSIGNEE")
    col_deadline = os.environ.get("SLACK_LIST_COL_DEADLINE")
    col_week     = os.environ.get("SLACK_LIST_COL_WEEK")

    if col_title and title:
        fields.append({"column_id": col_title, "rich_text": _rich_text_block(title)})
    if col_assignee and user_id:
        fields.append({"column_id": col_assignee, "user": [user_id]})
    if col_deadline and deadline:
        fields.append({"column_id": col_deadline, "date": [deadline]})
    if col_week and week:
        fields.append({"column_id": col_week, "select": [week]})

    return fields


def _build_update_cells(
    row_id: str,
    retro: str | None,
    proof_file_ids: list | None,
    mark_done: bool = False,
) -> list:
    """update_item용 cells 배열 구성. 각 셀에 row_id 포함."""
    cells: list = []

    col_retro          = os.environ.get("SLACK_LIST_COL_RETRO")
    col_proof          = os.environ.get("SLACK_LIST_COL_PROOF")
    col_todo_completed = os.environ.get("SLACK_LIST_COL_TODO_COMPLETED")

    if col_retro and retro:
        cells.append({
            "row_id": row_id,
            "column_id": col_retro,
            "rich_text": _rich_text_block(retro),
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


def _get_updated_at(item: dict) -> float:
    """updated_at 컬럼의 타임스탬프를 float로 반환. 없으면 0.0."""
    col = os.environ.get("SLACK_LIST_COL_UPDATED_AT")
    if not col:
        return 0.0
    for field in item.get("fields", []):
        if field.get("column_id") == col:
            ts = field.get("timestamp") or field.get("value")
            try:
                return float(ts)
            except (ValueError, TypeError):
                return 0.0
    return 0.0


def _is_completed(item: dict, col_todo: str | None) -> bool:
    """todo_completed 컬럼의 checkbox 값이 True이면 완료로 판단."""
    if not col_todo:
        return False
    for field in item.get("fields", []):
        if field.get("column_id") == col_todo:
            return field.get("checkbox", False)
    return False


def _is_assigned_to(item: dict, user_id: str) -> bool:
    """fields 중 user 타입 필드에 user_id가 있으면 True."""
    for field in item.get("fields", []):
        if user_id in field.get("user", []):
            return True
    return False


def extract_title(item: dict) -> str:
    """아이템에서 제목 텍스트 추출. text 필드가 있는 첫 번째 필드 사용."""
    for field in item.get("fields", []):
        text = field.get("text")
        if text:
            return text
    return "(제목 없음)"


def extract_assignees(item: dict) -> list:
    """아이템에서 담당자 user_id 목록 추출."""
    col_assignee = os.environ.get("SLACK_LIST_COL_ASSIGNEE")
    for field in item.get("fields", []):
        if col_assignee and field.get("column_id") == col_assignee:
            return field.get("user", [])
        # column_id 없이도 user 필드 있으면 반환
        if field.get("user"):
            return field["user"]
    return []
