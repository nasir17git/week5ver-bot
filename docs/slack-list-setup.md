# Slack List 생성·연결 가이드

## 운영 방식

운영 List는 **운영자가 Slack 데스크톱에서 CSV를 가져와 직접 생성**합니다.
이렇게 만든 List의 소유자는 가져오기를 실행한 사용자이므로 Slack UI에서 컬럼을
추가·수정·삭제하고 List 자체를 관리할 수 있습니다. 봇은 완성된 List의 항목과
셀을 읽고 쓰며, List ID·컬럼 ID·선택값 ID는 `.env`에 저장합니다.

`setup_slack_list.py --name ...`으로 앱이 List를 직접 만드는 방식도 지원하지만
신규 운영 List에는 사용하지 않습니다. Slack의 공개 `slackLists.update` API는
기존 List의 이름·설명·TODO 모드만 변경할 수 있고 사용자 정의 컬럼을 나중에
추가하는 기능을 제공하지 않습니다. 공개 Lists API 목록에는 List 전체 삭제
메서드도 없습니다. 앱이 소유한 List는 사람이 Slack UI에서 소유자 전용 구조 변경과
삭제를 하기 불편하므로, 이 프로젝트에서는 장애 복구·개발 테스트 용도로만 둡니다.

- [Slack Lists 사용 및 CSV 가져오기](https://slack.com/help/articles/27452748828179-Use-lists-in-Slack)
- [Slack `slackLists.create`](https://docs.slack.dev/reference/methods/slackLists.create/)
- [Slack `slackLists.update`](https://docs.slack.dev/reference/methods/slackLists.update/)

## 현재 연결된 List

- 이름: `week5ver-2026하반기`
- URL: `https://growth-log.slack.com/lists/T074DSTH62F/F0C1HN8N066`
- List ID: `F0C1HN8N066`
- 소유 형태: 사용자가 CSV 가져오기로 생성
- 봇 접근 및 스키마 검증: 성공
- `.env` 연결: 완료

실제 확인된 구조는 다음과 같습니다.

| 컬럼 | Slack 타입 | 봇 사용 여부 | 용도 |
|---|---|---:|---|
| 목표 제목 | `text` | 필수 | 목표명 또는 참여현황 표시명 |
| 완료됨 | `todo_completed` | 필수 | 목표 완료 여부 |
| 담당자 | `todo_assignee` | 필수 | 목표 소유자·참가자 |
| 주차 | `select` | 필수 | `week1`~`week11` |
| 마감 기한 | `todo_due_date` | 필수 | 사용자 선택 목표일 |
| 행 구분 | `select` | 필수 | `목표`, `참여현황` |
| 참여 상태 | `select` | 필수 | `참여`, `휴식` |
| 등록 목표 수 | `number` | 필수 | 참여현황 집계값 |
| 완료 목표 수 | `number` | 필수 | 참여현황 집계값 |
| 판정 | `text` | 필수 | 등록 대기·진행 중·달성·미등록·미달성·판정 제외 |
| 한 줄 회고 | `text` | 필수 | 선택 입력 |
| 인증 자료 | `attachment` | 필수 | 이미지·PDF 인증자료 |
| updated_at | `last_edited_time` | 선택 | Slack 자동 편집 시각 |
| updated_by | `last_edited_by` | 미사용 | Slack 자동 편집자 |

`인증자료`와 `인증 자료` 두 이름을 모두 인식합니다. `updated_at`은 없어도 연결할
수 있으며 `updated_by`는 봇이 사용하지 않습니다.

## 처음부터 만드는 과정

### 1. CSV 가져오기

Slack 데스크톱에서 `파일 → 새로 만들기 → CSV 가져오기`를 선택하고 저장소 루트의
[`slack-list-import.csv`](../slack-list-import.csv)를 업로드합니다. List 이름은
`week5ver-2026하반기`로 지정합니다.

CSV에는 `week1`~`week11`과 상태 선택값을 생성하기 위한 임시 항목 11개가 포함돼
있습니다. 이 단계에서는 삭제하지 않습니다.

### 2. 가져온 컬럼 타입 지정

각 컬럼 이름을 눌러 `필드 편집`에서 아래처럼 지정합니다.

| 컬럼 | 타입·선택값 |
|---|---|
| 목표 제목 | 텍스트, 기본 제목 컬럼 |
| 주차 | 단일 선택: `week1`~`week11` |
| 행 구분 | 단일 선택: `목표`, `참여현황` |
| 참여 상태 | 단일 선택: `참여`, `휴식` |
| 등록 목표 수 | 숫자, 정수 |
| 완료 목표 수 | 숫자, 정수 |
| 판정 | 텍스트 |
| 한 줄 회고 | 텍스트 |

### 3. CSV로 만들 수 없는 필드 추가

컬럼 행 오른쪽 끝의 `+`를 눌러 `인증 자료`를 파일/첨부 타입으로 추가합니다.
같은 필드 메뉴에서 `작업 추적 필드`를 추가해 다음 세 컬럼을 만듭니다.

- 완료됨
- 담당자
- 마감 기한

원하면 자동 필드로 `updated_at`(`last_edited_time`)과
`updated_by`(`last_edited_by`)를 추가합니다. 봇 동작에는 필요하지 않습니다.

### 4. 봇에서 스키마 검사·연결

List URL의 마지막 `F...` 값을 사용합니다.

```bash
source .venv/bin/activate
python3 setup_slack_list.py \
  --existing-list-id F실제_LIST_ID \
  --no-channel-access
```

`--no-channel-access`는 이미 사용자가 채널에 List를 추가한 경우 적합합니다.
생략하면 스크립트가 `.env`의 `SLACK_CHANNEL_ID`에 편집 접근을 설정합니다.

성공하면 다음과 같이 출력되며 `.env`의 기존 토큰은 유지되고 List·컬럼·선택값
ID만 갱신됩니다.

```text
기존 Slack List 연결 완료: F...
컬럼/주차 옵션 ID 기록 완료: .env
```

필수 컬럼, 타입 또는 선택값이 다르면 `.env`를 새 List로 전환하지 않고 오류로
종료합니다. Slack에서 해당 필드를 수정한 뒤 같은 명령을 다시 실행합니다.

### 5. 임시 항목 삭제

연결 성공 후 아래 11개 항목을 Slack UI에서 삭제합니다.

```text
__초기설정_삭제_week1__
...
__초기설정_삭제_week11__
```

삭제 전 봇을 운영하면 임시 행이 목표 집계와 DM 대상에 섞일 수 있습니다.

### 6. 채널에 List 표시

대상 채널 상단의 `+`에서 List를 선택해 탭으로 추가합니다. List 공유 화면에서
봇과 채널 구성원이 필요한 접근 권한을 가졌는지 확인합니다.

### 7. 월별 참가자 초기화

일반 참가자는 봇 실행 후 `/월간등록`으로 현재 주차의 월요일이 속한 달을 직접 신청할 수 있습니다.
확인 모달에서 `예`를 누르면 본인의 해당 월 주차만 멱등 생성되며 기존 `휴식`
상태는 유지됩니다. 이미 모든 주차가 등록된 사용자에게는 안내 모달만 표시됩니다.
운영 기간(2026-09-14~11-29) 밖에서는 등록되지 않습니다.

초기 신청자를 일괄 등록하거나 누락을 보정하려면 임시 항목 삭제 후 월별 참가자
파일을 작성하고 동기화합니다.

```bash
cp participants.example.csv participants.csv
# participants.csv의 예시 ID를 실제 Slack 사용자 ID로 교체
python3 sync_participants.py participants.csv
```

이 단계에서 신청 월에 해당하는 사용자·주차별 참여현황 행이 생성되며 등록·완료
목표 수는 `0/0`, 판정은 빈 값으로 시작합니다. CSV 동기화는 추가 전용이므로 행을
삭제해도 기존 참여현황은 없어지지 않습니다. 실제 등록·완료 수와 판정은 다음 단계의
`--report-only` 실행 때 갱신됩니다.

### 8. 실행 전 점검

`.env`에 운영자 ID를 지정합니다. 여러 명이면 쉼표로 구분합니다.

```dotenv
SLACK_ADMIN_USER_IDS=U0123456789,U0987654321
```

집계와 테스트를 실행합니다.

```bash
python3 sync_participants.py --report-only
python3 -m unittest discover -s tests -q
```

마지막으로 봇 프로세스를 한 인스턴스만 실행합니다. `/월간등록`을 반복 실행했을 때
참여현황이 중복되지 않는지 확인하고, `/등록발송`으로 메시지 게시와 핀 교체를
확인합니다. 월간 셀프 등록의 멱등성은 단일 봇 인스턴스 운영을 전제로 합니다.

Slack App 관리 화면의 **Slash Commands**에도 `/월간등록`, `/등록발송`,
`/인증발송`, `/알림발송` 네 명령을 등록해야 합니다. Socket Mode를 사용하므로
각 명령은 이 봇 프로세스의 Bolt 핸들러로 전달됩니다.

## 앱 직접 생성 방식

개발용으로 전체 스키마를 한 번에 생성할 때만 사용합니다.

```bash
python3 setup_slack_list.py --name week5ver-2026하반기-dev --force-new
```

앱 생성 방식은 생성 순간에는 필요한 컬럼을 모두 만들 수 있습니다. 생성 후 새
사용자 정의 컬럼이 필요해지면 공개 API로 추가할 수 없으며, 사람이 소유한 새 List를
만들어 다시 연결해야 합니다. 초기화 도중 오류가 발생하면 출력된 `F...` ID로
복구하며 새 List를 다시 만들지 않습니다.

```bash
python3 setup_slack_list.py --existing-list-id F출력된_ID
```

운영 List를 바꿀 때 기존 List를 먼저 삭제할 필요는 없습니다. 새 List 검증과
`.env` 연결, 참가자 동기화, 실제 동작 확인을 마친 뒤 기존 채널 탭을 제거합니다.
