"""월별 참가 신청 파일을 기존 Slack List의 참여현황 행으로 동기화합니다."""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk import WebClient

from slack_list.client import SlackListClient
from utils import MONTH_WEEKS


def read_participants(path: Path) -> list[dict]:
    rows: dict[tuple[str, str], dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != ["user_id", "month"]:
            raise ValueError("CSV 헤더는 정확히 user_id,month 이어야 합니다.")
        for line_no, raw in enumerate(reader, start=2):
            if None in raw:
                raise ValueError(f"{line_no}행에 불필요한 열이 있습니다.")
            user_id = (raw.get("user_id") or "").strip()
            month = (raw.get("month") or "").strip()
            if not re.fullmatch(r"[UW][A-Z0-9]{8,}", user_id):
                raise ValueError(f"{line_no}행 user_id가 올바르지 않습니다: {user_id!r}")
            if month not in MONTH_WEEKS:
                raise ValueError(f"{line_no}행 month는 {', '.join(MONTH_WEEKS)} 중 하나여야 합니다.")
            rows[(user_id, month)] = {"user_id": user_id, "month": month}
    return list(rows.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="week5ver 월별 참가자 추가 동기화. 파일에서 삭제한 신청자는 List에서 제거되지 않습니다. 신청 취소/휴식은 운영자가 List에서 변경하세요.")
    parser.add_argument("file", nargs="?", default="participants.csv")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--report-only", action="store_true", help="참가자 행 생성 없이 현재 상태만 재집계")
    args = parser.parse_args()

    load_dotenv(args.env_file, override=True)
    client = SlackListClient(WebClient(token=os.environ["SLACK_BOT_TOKEN"]))

    created = updated = 0
    if not args.report_only:
        participants = read_participants(Path(args.file))
        existing_items = client.list_items()
        for participant in participants:
            for week in MONTH_WEEKS[participant["month"]]:
                _, was_created = client.sync_participation(participant["user_id"], week, items=existing_items)
                created += int(was_created)
                updated += int(not was_created)

    stats = []
    if args.report_only:
        stats = client.refresh_participation_stats()
        totals: dict[str, int] = defaultdict(int)
        for row in stats:
            totals[row["user_id"]] += row["completed"]
            print(
                f'{row["user_id"]}\t{row["week_option"]}\t'
                f'{row["registered"]}/{row["completed"]}\t{row["judgment"]}'
            )
        for user_id, completed in sorted(totals.items()):
            print(f"누적\t{user_id}\t완료 목표 {completed}개")
    print(f"처리 완료: 참여현황 생성={created}, 기존={updated}, 집계={len(stats)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
