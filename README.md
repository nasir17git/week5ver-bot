# week5ver-bot
Season 4 스터디의 주간 목표 등록과 인증을 돕는 Slack 봇입니다.
2026-09-14~11-29, `week1`~`week11`을 월~일 단위로 운영합니다.

- [Season 4 운영 및 동작 명세](docs/season4-operations.md)
- [Slack List 생성·연결 가이드](docs/slack-list-setup.md)
- [Season 4 Slack 모집글](docs/season4-recruitment.md)

## Slack List 초기 설정

운영 List는 [`slack-list-import.csv`](slack-list-import.csv)를 Slack 데스크톱에서
가져와 사용자가 직접 생성합니다. 필드 타입 설정, 봇 연결, 임시 항목 삭제까지의
전체 과정은 [Slack List 생성·연결 가이드](docs/slack-list-setup.md)를 따릅니다.

이미 완성한 List를 연결하는 명령은 다음과 같습니다.

```bash
python3 setup_slack_list.py --existing-list-id FXXXXXXXXXX --no-channel-access
```

앱 직접 생성은 개발·복구 용도입니다. 공개 API의 생성 후 컬럼 변경과 List 전체
삭제 제약 때문에 신규 운영 List에는 사용하지 않습니다.

## 월별 참가자 동기화

참가자는 Slack에서 `/월간등록`을 실행해 현재 달 참여를 직접 신청할 수 있습니다.
확인 모달에서 `예`를 누르면 실행한 사용자의 Slack user ID로 해당 월의 모든 주차
참여현황이 생성됩니다. 같은 사용자가 다시 실행해도 중복 행은 만들지 않으며, 기존
행의 `휴식` 상태는 유지합니다. Season 4 활동 월인 2026년 9~11월 밖에서는
등록할 수 없습니다.

기존 List에 `행 구분`, `참여 상태`, `등록 목표 수`, `완료 목표 수`, `판정`
컬럼이 필요합니다. 자세한 설정은 [Season 4 운영 문서](docs/season4-operations.md)를
참고하세요.

```bash
cp participants.example.csv participants.csv
python3 sync_participants.py participants.csv
python3 sync_participants.py --report-only
```

운영자가 참가자를 일괄 등록하거나 누락을 보정할 때는 복사한 CSV의 예시 ID를 실제
신청자 ID로 바꾼 뒤 동기화하세요. CSV에서 행을 지워도
기존 신청은 취소되지 않습니다. 일반 동기화는 참여현황을 0/0으로 생성할 뿐 기존
집계값을 갱신하지 않습니다. `--report-only`를 명시적으로 실행할 때만 List의
등록·완료 수와 판정을 재집계합니다.

수동 발송 명령은 `.env`의 `SLACK_ADMIN_USER_IDS`에 운영자 ID를 지정해야 사용할 수 있습니다.
