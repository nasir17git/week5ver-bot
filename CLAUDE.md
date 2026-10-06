# CLAUDE.md

이 저장소는 Slack 기반 스터디 운영 봇 `week5ver Season 4`입니다.

## 현재 운영 기준

- 운영 기간: 2026-09-14(월) ~ 2026-11-29(일)
- 주차: `week1` ~ `week11`, 각 주차는 월요일부터 일요일까지
- 매주 월요일 00:10 KST에 해당 주차 목표 등록 안내 게시
- 새 주간 안내는 채널에 고정하고 이전 주간 안내는 고정 해제
- 사용자는 해당 주차 월~일 동안 목표를 등록하고 인증
- 매일 00:10 KST에 인증 안내 게시, 인증 버튼은 만료하지 않음
- 목표 등록 시 현재 주차 안의 완료 예정일을 필수로 입력
- 매일 21:00 KST에 완료 예정일이 오늘이거나 지난 현재 주차 미완료 목표를 담당자별로 모아 DM 알림
- 목표 데이터는 `week5ver-2026하반기` Slack List에 저장
- 같은 List의 참여현황 행으로 월별 신청·휴식·주간 판정을 관리
- 목표 1개 완료를 인증 1회로 집계하며 금액 정산은 운영자가 수동 처리

상세 운영 및 기술 명세는 [Season 4 운영 문서](docs/season4-operations.md)를 참고합니다.
공유용 안내문은 [Season 4 모집글](docs/season4-recruitment.md)을 사용합니다.

## 주요 파일

```text
app.py                    Slack Bolt 앱 진입점
utils.py                  Season 4 주차 일정과 현재 주차 계산
setup_slack_list.py       Slack List·컬럼·주차 옵션 초기화
handlers/                 버튼, 모달, 슬래시 명령 처리
scheduler/                주간·일간 게시와 미완료 DM 작업
slack_list/client.py      Slack Lists API 읽기·생성·수정
templates/messages.py     Slack 메시지 Block Kit 템플릿
```

## 실행

```bash
source .venv/bin/activate
python3 app.py
```

Docker 배포:

```bash
docker build -t week5ver-bot:local .
docker run --rm --env-file .env week5ver-bot:local
```

토큰과 시크릿은 `.env`에만 저장하며 저장소에 커밋하지 않습니다.

`docker-compose.yml`도 로컬 소스를 빌드합니다. Compose로 실행할 때는 다음 명령을
사용하며, 실행 중인 기존 봇과 중복 기동하지 않습니다.

```bash
docker compose up --build -d
docker compose logs -f
```
