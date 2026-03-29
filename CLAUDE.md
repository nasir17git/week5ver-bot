# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

Slack 워크스페이스에서 동작하는 Python 기반 슬랙 봇입니다.
**week5ver (26년 상반기)** 클럽 운영을 자동화하며, 강의를 꾸준히 수강하고 인증하는 습관 형성이 목적입니다.

**핵심 기능:**
- Slack List를 저장소로 사용하여 목표 데이터 관리 (파일/DB 없음)
- 매주 **토요일 오전 12시** 채널에 메시지 게시 → 메시지 내부 버튼으로 주간 목표 등록 모달 오픈 → 최대 5개 수강 목표 등록 → 원문 댓글로 결과 전송
- 매일 채널에 메시지 게시 → 메시지 내부 버튼으로 일간 갱신 모달 오픈 → 인증자료·한줄회고 갱신 → `week5ver` 채널에 전송
- 등록/갱신 시 Slack List 아이템 생성·업데이트
- `/목표등록`, `/목표조회`, `/목표인증`, `/주간공지발송`, `/일간공지발송` 슬래시 명령어 및 이모지를 통한 목표 등록/갱신 가능

**봇 이름:**
| 봇 | 역할 |
|---|---|
| `week5ver-weekly-goals-collector` | 매주 토 오전 12시 주간 목표 등록 안내 메시지 발송 |
| `week5ver-daily-goal-updater` | 매일 일간 인증 안내 메시지 발송 및 결과 게시 |

**Slack List 컬럼 구조:**
List 이름: `week5ver-2026상반기`

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| 수강예정 강의이름 | 텍스트 | 목표 제목 |
| 담당자 | person | 목표 소유자 (user ID) |
| 기한 | 날짜 | 목표 완료 기한 |
| 주차 | 선택(select) | 해당 주차 (demo, week1~week9) |
| 인증자료 | 파일 | 완료 증빙 첨부파일 |
| 한 줄 회고 | 텍스트 | 일간 갱신 시 입력 |
| updated_at | 타임스탬프 | 마지막 편집 시간 |

## 진행 일정 (2026 상반기)

| 주차 | 목표 등록 | 강의 수강 및 인증 |
|---|---|---|
| demo | 3/21(토) ~ 3/22(일) | 3/23(월) ~ 3/29(일) |
| week1 | 3/28(토) ~ 3/29(일) | 3/30(월) ~ 4/5(일) |
| week2 | 4/4(토) ~ 4/5(일) | 4/6(월) ~ 4/12(일) |
| week3 | 4/11(토) ~ 4/12(일) | 4/13(월) ~ 4/19(일) |
| week4 | 4/18(토) ~ 4/19(일) | 4/20(월) ~ 4/26(일) |
| week5 | 4/25(토) ~ 4/26(일) | 4/27(월) ~ 5/3(일) |
| week6 | 5/2(토) ~ 5/3(일) | 5/4(월) ~ 5/10(일) |
| week7 | 5/9(토) ~ 5/10(일) | 5/11(월) ~ 5/17(일) |
| week8 | 5/16(토) ~ 5/17(일) | 5/18(월) ~ 5/24(일) |
| week9 | 5/23(토) ~ 5/24(일) | 5/25(월) ~ 5/31(일) |

## 기술 스택

- **Python 3.x**
- **Slack Bolt for Python** — 슬래시 명령어, 이모지 반응, Modal 처리
- **slack-sdk** — Slack API 직접 호출 (`slackLists_items_list` 등)
- 가상환경: `.venv`

## 환경 설정

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 실행

```bash
python app.py
```

## 환경 변수 (`.env`)

| 변수명 | 설명 |
|---|---|
| `SLACK_BOT_TOKEN` | Bot OAuth 토큰 (`xoxb-`로 시작) |
| `SLACK_SIGNING_SECRET` | 요청 검증용 서명 시크릿 |
| `SLACK_APP_TOKEN` | Socket Mode 토큰 (`xapp-`로 시작) |
| `SLACK_LIST_ID` | 목표를 저장할 Slack List ID (`F`로 시작) |
| `SLACK_CHANNEL_ID` | `week5ver` 채널 ID |

## 아키텍처

```
app.py                  # 앱 진입점, Bolt 앱 초기화 및 핸들러 등록
handlers/
  commands.py           # 슬래시 명령어 핸들러 (/목표등록, /목표조회, /목표인증)
  actions.py            # 버튼 클릭, 이모지 반응, Modal 제출(view_submission) 핸들러
  views.py              # Modal UI 정의 (Block Kit JSON 반환 함수)
slack_list/
  client.py             # Slack Lists API 래퍼 (조회 구현 / 생성·수정 TODO)
templates/
  messages.py           # 채널 전송용 봇 메시지 템플릿 (goal_registered 등)
scheduler/              # (TODO) 주간·일간 자동 메시지 발송 스케줄러
```

### Slack Lists API (Python SDK)

| SDK 메서드 | 용도 |
|---|---|
| `client.slackLists_items_list(list_id=...)` | 아이템 목록 조회 (페이지네이션 지원) — **구현됨** |
| `client.slackLists_items_create(...)` | 아이템 신규 생성 — **구현됨** |
| `client.slackLists_items_update(...)` | 아이템 수정 — **구현됨** |

> `fields`/`cells`는 리스트 형태. 각 필드에 `column_id` + 타입별 키: `rich_text`, `user`, `date`, `select`, `checkbox`, `attachment` 등.
> `todo_completed` 컬럼은 `"checkbox": true` 형식으로 업데이트. `updated_at`은 Slack 자동 관리 컬럼으로 API 쓰기 불가(`uneditable_column`).
> Slack 파일 permalink를 Block Kit `image` 블록 `image_url`로 사용하면 워크스페이스 내에서 미리보기 정상 동작 확인됨.

## 주요 흐름

### 1. 주간 목표 등록 (매주 토요일 오전 12시)
`week5ver-weekly-goals-collector` 봇이 `week5ver` 채널에 주간 목표 등록 안내 메시지 게시
→ 사용자가 메시지 내부 버튼("주간 목표 등록") 클릭 또는 이모지 반응
→ `views.goal_register_modal()` 표시
　　강의명 최대 5개 + 각 수강 예정일 + 주차 선택
→ 제출 → `actions.py`의 `goal_register_modal` view_submission 핸들러
→ `slack_list.client.create_item()`으로 Slack List에 강의당 아이템 생성
→ 원문 메시지 댓글로 등록 완료 내역 전송

### 2. 일간 갱신 (매일)
`week5ver-daily-goal-updater` 봇이 채널에 일간 갱신 안내 메시지 게시
→ 사용자가 메시지 내부 버튼("일간 목표 인증") 클릭 또는 이모지 반응
→ 해당 사용자의 목표 조회 후 `views.goal_update_modal()` 표시
　　- 수강 예정 강의 이름 (드롭다운 선택)
　　- 인증자료 (파일 업로드)
　　- 한줄회고 (선택)
→ 제출 → Slack List 아이템 갱신 (한줄회고, 인증자료, todo_completed=true)
→ 채널에 완료 메시지 전송 + 인증자료 이미지 미리보기 (permalink → image 블록)

### 3. 슬래시 명령어

| 명령어 | 동작 | 상태 |
|---|---|---|
| `/목표등록` | 목표 등록 Modal 오픈 | 구현됨 |
| `/목표조회` | 내 목표 목록 Modal 오픈 | 구현됨 |
| `/목표인증` | 일간 인증 Modal 오픈 | 구현됨 |
| `/주간공지발송` | 주간 목표 등록 안내 메시지 즉시 발송 | 구현됨 |
| `/일간공지발송` | 일간 인증 안내 메시지 즉시 발송 | 구현됨 |

## 구현 현황

### 완료
- [x] Slack Bolt 앱 초기화 + APScheduler 연동 (`app.py`)
- [x] `/목표등록` → 주간 목표 등록 모달 오픈 (강의 최대 5개 + 수강 예정일 + 주차 선택)
- [x] `/목표조회` → 조회 모달 오픈 (담당자 기준 필터)
- [x] `/목표인증` → 일간 인증 모달 오픈 (강의 선택 + 인증자료 + 한줄회고)
- [x] `goal_register_modal` view_submission → `create_item` 호출 + 채널 완료 메시지
- [x] `goal_update_modal` view_submission → `update_item` 호출 + 채널 인증 메시지
- [x] 버튼 핸들러 — `open_goal_register_modal` / `open_goal_update_modal`
- [x] 이모지 반응 핸들러 — `pencil2` / `white_check_mark` → ephemeral 안내
- [x] `SlackListClient.create_item()` — column ID 환경 변수 기반 구현
- [x] `SlackListClient.update_item()` — 한줄회고 / 인증자료 / todo_completed(checkbox) 갱신
- [x] `scheduler/` — 주간(토 00:00 KST) / 일간(매일 09:00 KST) 자동 발송
- [x] `templates/messages.py` — `goal_registered` / `goal_certified` / `weekly_goal_request` / `daily_update_request`
- [x] `utils.py` — 주차 자동 감지 (`get_current_week`)
- [x] 인증 완료 시 Slack List 아이템 `todo_completed` → `checkbox: true` 처리
- [x] 인증 메시지에 인증자료 이미지 미리보기 (`files_info` permalink → image 블록)

### TODO
- [ ] 이모지 반응 트리거 → 모달 직접 오픈 (현재: ephemeral 안내 → 슬래시 명령어 유도)
- [ ] 인증자료 Slack List attachment 컬럼 저장 (`uneditable_column` 에러 발생 중, 원인 미확인)

### column ID 환경 변수 (`.env` 설정)

Slack List column ID는 `python debug_columns.py`로 확인.

| 환경 변수 | 대응 컬럼 |
|---|---|
| `SLACK_LIST_COL_TITLE` | 수강예정 강의이름 |
| `SLACK_LIST_COL_ASSIGNEE` | 담당자 |
| `SLACK_LIST_COL_DEADLINE` | 기한 |
| `SLACK_LIST_COL_WEEK` | 주차 |
| `SLACK_LIST_COL_RETRO` | 한 줄 회고 |
| `SLACK_LIST_COL_PROOF` | 인증자료 |
| `SLACK_LIST_COL_TODO_COMPLETED` | todo_completed 불리언 컬럼 (todo_mode 활성화 후 생성) |

## 배포 (Docker)

```
Dockerfile              # python:3.12-slim, 비루트 유저(appuser) 실행
docker-compose.yml      # env_file: .env, restart: unless-stopped
.env                    # Git 제외 (.gitignore)
.env.example            # 변수 템플릿 (Git 포함)
```

```bash
docker compose up --build -d   # 빌드 및 백그라운드 실행
docker compose logs -f          # 로그 확인
docker compose down             # 중지
```

> Socket Mode 사용으로 인바운드 포트 노출 불필요. `.env`는 이미지에 포함하지 않음 (`.dockerignore` 필수).

## Slack 앱 설정 (api.slack.com)

- **Socket Mode** 활성화
- **Bot Token Scopes**:

  | Scope | 용도 |
  |---|---|
  | `chat:write` | 채널 메시지 전송·수정 |
  | `chat:write.public` | 봇 미참여 채널 메시지 전송 |
  | `commands` | 슬래시 명령어 |
  | `channels:history` | 채널 메시지 조회 |
  | `reactions:read` | 이모지 반응 이벤트 수신 |
  | `lists:read` | Slack List 아이템 조회 |
  | `lists:write` | Slack List 아이템 생성·수정·삭제 |

- **Event Subscriptions**: `reaction_added`
- **App-Level Token Scopes**: `connections:write` (Socket Mode)
- **슬래시 명령어 등록**: `/목표등록`, `/목표조회`, `/목표인증`, `/주간공지발송`, `/일간공지발송`

---

## 새로운 학기 시작시 셋팅할것
- 새로운 list 생성
- 필요한 컬럼들 생성 및 더미데이터 한줄 입력
  - 주차에 demo및 모든 week* 등록 필요
- `python debug_columns.py` 로 column_id 확인 후 .env 업데이트 
- 앱에 편집가능하게 리ㅡ트 공유