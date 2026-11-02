# Codex CLI 포팅과 수신 방식 결정

2026-11-02, 로컬 `codex-cli 0.166.0` 기준. 이름·상태·MCP 안내 전환은 완료했지만
khj가 선택한 queue --resume 어댑터를 구현했다. 구현 전 N=1 실측과
구현 후 mock 검증은 구분해서 아래에 기록한다.

## 확인 근거

초기 문서 조사에서 실행한 것은 `codex --version`, `codex --help`, `codex queue --help`,
`codex exec resume --help`뿐이었다. 이후 일회용 모델 세션 검증을 아래와 같이 수행했다.
브리지 서버·지킴이·Slack 연결은 실행하지 않았다.
설치 CLI 도움말에서 stdout 매 줄로 현재 세션을 깨우는 persistent Monitor 동등 기능을
확인하지 못했다. 이는 모든 Codex 호스트에 그런 기능이 없다는 증명은 아니다.

로컬 도움말에는 `codex queue --thread <UUID 또는 정확한 이름> --message <TEXT> --resume`이 있다.
`--resume`은 로컬 daemon 또는 지정 remote 서버에서 재개를 시도한다. 재개 실패는 경고이며
명령 자체는 성공할 수 있다. 따라서 종료 코드만으로 메시지 처리 성공을 판단하면 안 된다.
`codex exec resume <SESSION_ID> <PROMPT>`도 제공된다. 실제 재개 동작은 미검증이다.

[공식 MCP 문서](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)는
`~/.codex/config.toml`의 `mcp_servers` 설정과 도구 호출 제한을 설명한다.
[공식 비대화형 문서](https://learn.chatgpt.com/docs/non-interactive-mode)는
`codex exec` 및 기존 세션 재개를 설명한다. 이 문서들이 MCP stdout 자체의 자동 깨움을
보장하지는 않는다. 로컬 CLI 도움말과 공개 문서의 버전 차이가 있을 수 있다.

### queue --resume 실측

2026-11-02 14:58~14:59 KST, CLI 0.166.0. **실제 응답 Y**.
기본 홈 설정을 그대로 사용했고 환경의 CODEX_HOME을 변경하지 않았다.
cwd는 `/tmp/csb-queue-test`, 각 명령 제한은 180초였다. 초기 명령:

```bash
codex exec --skip-git-repo-check --sandbox read-only --json "숫자 1만 답해. 도구 사용 및 파일 읽기/쓰기는 하지 마."
```

`thread.started`에서 받은 일회용 UUID는 `01a19ad6-8066-7ee3-b917-a48e2212efaf`.
초기 응답은 `1`이었다. 이후 이 UUID에만 아래 형태로 총 세 메시지를 넣었다.
`--last`는 사용하지 않았고 다른 세션의 기록은 읽지 않았다.

```text
codex queue --thread 01a19ad6-8066-7ee3-b917-a48e2212efaf --message <고유 식별문자열만 답하도록 하는 짧은 지시> --resume
```

근거 rollout:
`/Users/kimhyojoon/.codex/sessions/2026/11/02/rollout-2026-11-02T14-58-31-01a19ad6-8066-7ee3-b917-a48e2212efaf.jsonl`

| 요청 | user 기록 행 | assistant 응답 행 | 응답 시각 (KST) | 판정 |
|---|---:|---:|---|---|
| 단건 N1 | 24 | 27 | 14:59:13.511 | 요청한 식별문자열과 정확히 일치 |
| 연속 A | 33 | 36 | 14:59:44.261 | 정확히 일치 |
| 연속 B | 42 | 45 | 14:59:50.986 | 정확히 일치 |

A 명령은 14:59:41.324~41.621, B는 41.622~41.858에 실행했다. A 응답을 기다리지
않고 B를 제출했고, rollout은 user A → assistant A → user B → assistant B 순서였다.
`response_item`의 user/assistant 메시지로 세면 각 요청과 응답은 한 번씩이다.
동일 대화를 중복 표현하는 `event_msg`까지 합쳐 중복 수신으로 세지 않았다.
세 queue 명령 모두 exit 0, stderr 공백이었다. 재개 실패 경고는 발생하지 않았다.
단순 enqueue 성공 출력이 아니라 같은 UUID의 실제 assistant 응답으로 판정했다.
명령 로그와 추출 근거는 `/tmp/csb-queue-test/default-*.stdout`, `default-*.stderr`,
`default-pair-commands.json`, `default-final-evidence.json`에 남겼다.

**daemon:** 실행 전부터 PID 23955의 `codex app-server --listen unix:// … --managed-daemon`과
PID 89758의 `codex app-server daemon pid-update-loop`가 있었다. 초기 exec 후와 queue 후에도
동일 PID였다. 함께 관찰된 `codex-code-mode-host` PID는 55956이다.
이번 실측에서 새 daemon 생성은 관찰되지 않았고 어떤 daemon도 종료하지 않았다.
로컬 `--resume`은 help상 local daemon에서 재개를 시도하며, 이번 결과는 기존 daemon이 있는
조건의 성공이다. daemon이 없는 상태에서 자동 기동하는지는 검증하지 않았다.

**TUI가 열려 있는 경우:** 시도하지 않았다. [공식 CLI reference](https://learn.chatgpt.com/docs/cli/reference)의
queue 설명은 기존 세션 UUID/이름을 대상으로 한다. 로컬 help는 `--resume`이 daemon 또는
선택한 remote 서버에 재개를 시도한다고 설명하지만, 열린 TUI의 즉시 갱신이나 활성 턴 중
동작까지 보장하지 않는다. 따라서 기존 세션을 지정하는 인터페이스는 확인되지만 TUI에서의
동시 수신 성공은 이 실측으로 확정하지 않는다.

**반증 및 한계:** 종료 코드만 보고 성공한 것으로 오판했을 가능성을 배제하기 위해 같은
rollout의 역할·응답 본문·순서·횟수를 별도로 확인했다. 단일 일회용 세션의 관찰 결과이므로
일반적인 FIFO/exactly-once 보장, 동시 생산자, 장애 재시도, daemon 부재, 실제 Slack 연동은
검증하지 않았다. 이 실측 당시에는 어댑터를 구현하지 않았다. 기본 홈을 사용한 이번 성공에 이전 격리 홈은
필요하지 않았으며 이번 재개 작업에서 그 디렉터리는 건드리지 않았다.

## 자동 깨움 어댑터 구현

### UUID 획득과 매핑

이번 조사에서는 자기 프로세스 환경의 **키 이름만** 출력해 `CODEX_THREAD_ID`와
`CODEX_SESSION_ID`의 존재를 확인했다. 값이나 자격증명 파일은 읽거나 출력하지 않았다.
설치 CLI README와 기존 help 조사에서는 MCP 자식에 thread UUID를 주입한다는 명세를
확인하지 못했다. [공식 MCP 문서](https://learn.chatgpt.com/docs/extend/mcp)는 stdio 환경변수
설정을 설명하지만 `CODEX_THREAD_ID` 자동 전달을 보장하지 않는다.
따라서 환경 키의 존재를 MCP 전달 보장으로 간주하지 않는다.

open/attach/switch의 선택 인자 `codex_thread_id`가 우선하고, 생략한 경우만 MCP 프로세스의
`CODEX_THREAD_ID`를 UUID로 검증해 사용한다. `CODEX_SESSION_ID`나 PID에서 추론하지 않는다.
명시 인자가 잘못됐으면 Slack 동작 전에 거절하고, 환경 UUID가 없거나 잘못됐으면 자동 깨움
대상 없이 기존 wait 경로를 사용한다. 명시적 빈 문자열도 자동 깨움을 끈다.
각 `threads/<ts>.json`에 UUID를 지킴이 spawn 전에 기록한다. UUID 미상으로 재attach하면
옛 세션 매핑을 지워 잘못된 대상으로 전달하지 않는다. 마지막 attach가 자동 깨움 대상을 정한다.
실제 UUID 소유권은 인자만으로 증명할 수 없으므로 세션은 확인된 자기 UUID만 전달해야 한다.

### 전달·재시도·대기 경쟁 처리

- `wake_enabled`는 기본 true, `CODEX_SLACK_BRIDGE_WAKE_ENABLED`가 설정 파일보다 우선한다.
  false/0/off로 끈다. 값은 open/attach/switch 때 스레드에 반영되며 재attach로 갱신한다.
  실행 중 프로세스의 환경변수를 바꾸려면 MCP를 다시 시작한다.
- 기존 keeper 필터를 통과하고 내장 제어 명령이 아닌 메시지만 durable inbox에 기록한다.
  한 poll에 가장 오래된 미전달 메시지 한 건을 처리해 Slack ts 순서를 유지한다.
  프로세스 시작에는 셸 없이 인자 배열을 사용하며 timeout은 20초다.
- 본문은 thread_ts·ts·sender·text를 JSON으로 감싼 외부 데이터다. 시스템 지시나 새로운
  권한으로 취급하지 말라는 고정 안내를 앞에 둔다. 동일 Slack ts에 재답하지 않도록 안내한다.
- 접수 확인 없는 비정상 종료(출력·재개 경고 없음) 및 프로세스 시작 오류는 5초·15초
  백오프로 최대 3회 시도한다. 재시도 시각과 횟수는 디스크에 저장한다.
- CLI의 `Queued message … for thread …` 접수 확인과 빈 stderr, exit 0이 함께 있어야
  정상으로 취급한다. stderr가 있으면 보수적으로 실패로 본다. 접수 후 재개 경고는 이미
  저장된 메시지를 다시 넣지 않고 즉시 실패로 표시한다. timeout, 접수 확인 없는 exit 0,
  예상 밖 출력/재개 경고도 저장 여부가 불확실하므로 재전송하지 않는다.
- 실패 상태는 기존 세션 건강 점검의 ⚠️/복구 알림 경로에 연결한다. queue 정상 접수만으로
  실제 응답했다고 표시하지 않으며 기존 `session_reply_ts` 무응답 검사도 유지한다.
- `.delivery.lock`은 intake/상태 patch 잠금과 분리된 OS flock이다. queue 시도, 매핑 변경,
  wait 전달을 직렬화한다. wait 중에도 keeper는 inbox를 기록하되 queue 시도는 건너뛴다.
  wait는 매 poll 현재 소유자·listener·멘션 및 내장 명령 필터를 적용한다.
  반환한 ts는 잠금을 놓기 전에 `wake_wait_seen_ts`에 기록한다. queue 접수·claim 이후의
  메시지만 wait에 반환해 역방향 중복도 막는다. wait 종료·예외 시 대기 표식을 정리한다.
- queue 프로세스를 시작하기 **전에** `wake_claim_ts`를 저장/fsync한다. 접수 후에는
  `wake_last_queued_ts`를 전진시킨다. 재시작 시 미확정 claim이 있으면 재전송 대신 경고한다.
  자동 경로는 OS 잠금을 확보하지 못하면 실행하지 않는다. flock 없는 플랫폼은 매핑을
  비활성화하고 wait만 사용한다.

### 운영 한계와 복구

지킴이 프로토콜을 `inbox-queue-v2`로 올렸다. 실행 중인 옛 `inbox-v1` 지킴이를 새
어댑터 지원 프로세스로 오인하지 않고 `STALE_KEEPER`로 알린다. 배포 시 운영자가 옛
지킴이를 정리한 뒤 재attach해야 한다. 이 변경은 프로세스를 자동 종료하지 않는다.

queue CLI에는 원자적 클라이언트 중복 키나 접수 확인 API가 없다. 로컬 상태 저장과 원격
queue 사이의 crash/timeout에는 exactly-once를 보장할 수 없다. 중복 방지를 우선하여
미확정 claim은 자동 재전송과 wait 재전달에서 제외하므로, 실제로 저장되지 않은 메시지도
자동 처리가 멈출 수 있다. inbox는 보존된다. **대상 Codex 대화와 inbox를 사람이 대조해
처리 여부를 확인해야 하며 미확정 claim을 맹목적으로 지우거나 다시 queue하지 않는다.**
접수가 확인된 경고 또는 확정 실패 후에는 문제를 해결하고 재attach하여 실패 상태를
초기화할 수 있다. 이미 접수된 ts는 보존돼 재전송하지 않는다. 비정상 종료 시 CLI가
접수 사실을 전혀 출력하지 않는 경우의 중복 가능성까지 배제할 수는 없다.

64KB가 넘는 전달 본문은 자동 queue하지 않고 wait 경로로 남긴다. 여러 Slack 스레드가
동일 Codex UUID를 공유할 때 스레드 사이 전역 순서는 보장하지 않는다. 수동 monitor/watch는
이 전달 잠금·커서에 참여하지 않으므로 queue와 병행하지 않는다. 매핑 변경·닫힘과 이미
실행 중인 원격 queue는 원자적으로 취소할 수 없어 한 건의 지연 전달 가능성이 남는다.

이번 구현 검증은 subprocess/Slack/spawn mock으로만 수행했다. 실제 queue, 브리지 서버,
지킴이, Slack API는 실행하지 않았다. 기존 managed daemon 조건의 N=1은 위 실측 범위로
제한한다. MCP UUID 환경 전달, daemon 부재 시 자동 기동, 열린 TUI 동시 사용, 실제 Slack
전체 경로, 공유 daemon과 개별 세션의 수명 관계는 실환경에서 검증해야 한다.

## 검토한 대안

| 방식 | 장점 | 비용·한계 |
|---|---|---|
| 기존 `slack_wait_reply(timeout_seconds=30, thread_ts=...)` | 새 프로세스 제어 없이 현재 MCP 도구 사용 가능 | 블로킹, 여러 스레드 순차 확인 지연, 턴 종료 후 자동 재개 없음. MCP timeout보다 짧게 호출해야 함 |
| 명시적 세션 ID로 `codex queue … --resume` (또는 `codex exec resume`) 어댑터 | queue 어댑터 구현. exec resume는 미구현 대안 | Slack thread와 Codex UUID 매핑, 중복 방지·재시도·처리 확인 필요. queue 재개 실패가 성공 코드일 수 있음. exec resume 동시 실행 충돌 방지 필요 |
| tmux `send-keys` 어댑터 | 기존 터미널을 이용 가능 | pane 오인, 입력 중 충돌, 인용·제어문자 문제, 터미널 상태 의존. 무인 운영용으로 비추천 |

자동 수신은 위 queue 어댑터를 사용하고 UUID 미상·설정 off일 때 짧은 wait로 확인한다.
실 Slack 연결 전에는 별도 실환경 검증이 필요하다. `--last`로 세션을 추측하지 않는다.

## 남은 런타임 한계

- `_session_pid()`는 조상 실행 파일 basename이 정확히 `codex`인 경우만 채택한다.
  uvx/셸/브리지 이름을 세션으로 오인하지 않는다. 탐지 실패·ps 실패 시 MCP 서버 PID를 쓴다.
  공유 app-server 구성에서는 그 PID가 개별 대화 수명과 다를 수 있어 실환경 검증이 필요하다.
- `threads.inbox_tailed()`는 lsof로 열린 inbox만 검사한다. Codex 수신 확인이 아니며
  자동 경로에서는 매핑·실패 상태와 wait 대기 표식을 별도로 확인한다. 실제 응답은
  `session_reply_ts`로 계속 확인한다.
- 지킴이와 wait는 서로 다른 폴링 경로다. 실 Slack에서 멘션/명령 처리와 중복 메시지,
  커서 및 경고 상호작용은 추가 실환경 검증이 필요하다. 전달 잠금과 커서는 위와 같이 공유한다.
- 공유 daemon 수명, macOS 절전, 실제 Slack 권한/연결, 동시 브리지 운영은 미검증이다.

## 공존과 검증

패키지 `codex_slack_bridge`, 배포·CLI·MCP 서버명 `codex-slack-bridge`, 상태 루트
`~/.codex-slack-bridge`, 앱 표시명 `Codex Bridge`로 분리했다.
환경변수는 `CODEX_SLACK_BRIDGE_` 접두어만 사용하고 공용 `SLACK_*` fallback을 제거했다.
토큰/앱도 별도로 설정해야 하며 기존 브리지 설정을 자동 이관하지 않는다.
`NO_COLOR` 같은 표준 표현 설정은 공유한다. MCP 도구의 `slack_*` 이름은 서버별 namespace로 구분된다.

원본 기준: pytest 40 passed, 42 subtests passed.
전환 후: pytest 45 passed, 44 subtests passed (PID 탐지·실패 fallback·환경변수 격리 추가).
후속 A 수정 후: pytest 45 passed, 46 subtests passed (keeper CLI/모듈 토큰 검증 강화).
자동 깨움 구현 후: pytest 67 passed, 52 subtests passed. UUID 저장·실행 인자·데이터 포장,
영속 중복 방지/순서, 재시도/경고/timeout, flag off/UUID·실행파일 부재, wait 경쟁과
필터, keeper intake→queue 및 spawn 인자·건강 경고를 mock으로 검증했다.
명령: `UV_CACHE_DIR=$PWD/.cache/uv TMPDIR=$PWD/tests uv run --offline --with pytest pytest -q`.
테스트는 Slack 호출과 지킴이 기동을 mock하고 임시 상태를 레포 안에 둔다.
`docs/PARITY.md`의 Claude 언급은 역사적 비교 근거로 의도적으로 보존한다.
