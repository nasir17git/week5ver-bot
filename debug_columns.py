"""Slack List의 column ID 및 select option ID를 조회하는 디버그 스크립트.

실행:
    source .venv/bin/activate
    python debug_columns.py
"""

import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

client  = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
list_id = os.environ["SLACK_LIST_ID"]

# ── 아이템 수집 ───────────────────────────────────────────────────────────────

response = client.slackLists_items_list(list_id=list_id, limit=50)
items    = response.get("items", [])

if not items:
    print("리스트에 아이템이 없습니다. Slack에서 아이템을 하나 직접 추가한 후 다시 실행하세요.")
    exit(1)

# ── 컬럼 수집 ─────────────────────────────────────────────────────────────────

columns: dict[str, dict] = {}
for item in items:
    for field in item.get("fields", []):
        col_id = field.get("column_id")
        if not col_id:
            continue

        if field.get("user"):         col_type = "person"
        elif field.get("date"):       col_type = "date"
        elif field.get("select"):     col_type = "select"
        elif field.get("timestamp"):  col_type = "timestamp"
        elif field.get("attachment"): col_type = "attachment"
        else:                         col_type = "text"

        if col_id not in columns:
            columns[col_id] = {
                "key":     field.get("key", ""),
                "type":    col_type,
                "sample":  field.get("text") or str(
                    field.get("user") or field.get("select") or
                    field.get("date") or field.get("attachment") or ""
                ),
                "options": {},  # select 전용: {option_id: label}
            }

        # select 옵션 ID 수집 (아이템에서)
        if col_type == "select":
            for opt_id in field.get("select", []):
                columns[col_id]["options"].setdefault(opt_id, "")

# ── select 옵션 라벨 보완: slackLists.items.info 로 schema 조회 ───────────────

import json as _json

first_item_id = items[0].get("id", "")
try:
    info_resp = client.slackLists_items_info(list_id=list_id, id=first_item_id)
    print("# ── slackLists.items.info raw 응답 (list.list_metadata.schema) ──")
    schema = info_resp.get("list", {}).get("list_metadata", {}).get("schema", [])
    print(_json.dumps(schema, indent=2, ensure_ascii=False))
    print()

    # schema 에서 컬럼 정의 및 select 옵션 보완
    for col_def in schema:
        col_id   = col_def.get("id")
        col_key  = col_def.get("key", "")
        col_type = col_def.get("type", "text")

        if col_id not in columns:
            columns[col_id] = {"key": col_key, "type": col_type, "sample": "", "options": {}}

        # select / multi_select 옵션
        if col_type in ("select", "multi_select"):
            columns[col_id]["type"] = "select"
            for choice in col_def.get("options", {}).get("choices", []):
                opt_val   = choice.get("value", "")
                opt_label = choice.get("label", "")
                columns[col_id]["options"][opt_val] = opt_label

except SlackApiError as e:
    print("# ── slackLists.items.info 오류 응답 ──")
    print(_json.dumps(e.response.data, indent=2, ensure_ascii=False))
    print()

# ── 자동 env 매핑 ─────────────────────────────────────────────────────────────

SKIP_KEYS = {"todo_completed"}

def guess_env_key(key: str, col_type: str) -> str | None:
    k = key.lower()
    if k in SKIP_KEYS:                          return None
    if k == "name":                             return "SLACK_LIST_COL_TITLE"
    if "assignee" in k or col_type == "person": return "SLACK_LIST_COL_ASSIGNEE"
    if "due" in k or col_type == "date":        return "SLACK_LIST_COL_DEADLINE"
    if col_type == "select":                    return "SLACK_LIST_COL_WEEK"
    if col_type == "attachment":                return "SLACK_LIST_COL_PROOF"
    if col_type == "timestamp":                 return "SLACK_LIST_COL_UPDATED_AT"
    if col_type == "text":                      return "SLACK_LIST_COL_RETRO"
    return None

# ── 출력 ─────────────────────────────────────────────────────────────────────

print("# .env에 복붙하세요\n")

seen_env: set[str] = set()
for col_id, info in columns.items():
    env_key = guess_env_key(info["key"], info["type"])
    if not env_key or env_key in seen_env:
        continue
    seen_env.add(env_key)

    print(f"# {info['key']} ({info['type']})")
    print(f"{env_key}={col_id}")
    print()

# ── select 옵션 ID 상세 출력 ──────────────────────────────────────────────────

select_cols = {cid: info for cid, info in columns.items() if info["type"] == "select"}
if select_cols:
    col_week_id = os.environ.get("SLACK_LIST_COL_WEEK", "")

    # 아이템별 제목 + option ID 매핑 수집 (multi-select 지원)
    item_option_map: list[dict] = []
    for item in items:
        title = ""
        for f in item.get("fields", []):
            if f.get("text") and not title:
                title = f["text"]
        for f in item.get("fields", []):
            if f.get("column_id") == col_week_id and f.get("select"):
                for opt_id in f["select"]:
                    item_option_map.append({"title": title or "(제목없음)", "option_id": opt_id})

    # 주차 select 컬럼 특정
    week_col_info = select_cols.get(col_week_id) or (next(iter(select_cols.values())) if select_cols else None)

    print("=" * 60)
    print("# 주차 SELECT 옵션 ID")
    print("# 아래 option_id를 보고 utils.py의 WEEK_OPTION_IDS를 채우세요")
    print("=" * 60)

    # 아이템에서 수집한 옵션 ID (slackLists.columns.list로 못 가져온 경우 대비)
    seen_opts: dict[str, list] = {}
    for row in item_option_map:
        seen_opts.setdefault(row["option_id"], []).append(row["title"])

    all_opts = week_col_info["options"] if week_col_info else {}
    # columns.list로 못 가져왔어도 아이템에서 수집한 옵션 포함
    for opt_id in seen_opts:
        all_opts.setdefault(opt_id, "")

    if all_opts:
        print(f"\n  {'option_id':<20} {'label':<12} 연결된 아이템 제목")
        print(f"  {'-'*60}")
        for opt_id, label in all_opts.items():
            titles = ", ".join(seen_opts.get(opt_id, ["(아이템 없음)"]))
            print(f"  {opt_id:<20} {label:<12} {titles[:30]}")
    else:
        print("  (아이템에서 옵션을 찾지 못했습니다)")

    # label → opt_id 역매핑 (schema에서 가져온 값 우선)
    label_to_opt: dict[str, str] = {label: opt_id for opt_id, label in all_opts.items() if label}

    print()
    print("# utils.py WEEK_OPTION_IDS 템플릿:")
    print("WEEK_OPTION_IDS = {")
    weeks = ["demo", "week1", "week2", "week3", "week4", "week5", "week6", "week7", "week8", "week9"]
    for w in weeks:
        opt_id = label_to_opt.get(w, "")
        suffix = "" if opt_id else "  # ← 확인 필요"
        print(f'    "{w}": "{opt_id}",{suffix}')
    print("}")
