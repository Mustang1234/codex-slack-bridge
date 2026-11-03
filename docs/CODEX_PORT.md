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

open/attach/switch의 명시 `codex_thread_id`와 환경 UUID가 모두 있으면 일치해야 한다.
불일치(환경 UUID 형식 오류 포함)는 Slack 동작 전에 거부한다. 생략한 경우 MCP 프로세스의
`CODEX_THREAD_ID`를 UUID로 검증해 사용한다. `CODEX_SESSION_ID`나 PID에서 추론하지 않는다.
명시 인자가 잘못됐으면 Slack 동작 전에 거절하고, 환경 UUID가 없거나 잘못됐으면 자동 깨움
대상 없이 기존 wait 경로를 사용한다. 명시적 빈 문자열도 자동 깨움을 끈다.
각 `threads/<ts>.json`에 UUID를 지킴이 spawn 전에 기록한다. UUID 미상으로 재attach하면
옛 세션 매핑을 지워 잘못된 대상으로 전달하지 않는다. 마지막 attach가 자동 깨움 대상을 정한다.
실제 UUID 소유권은 인자만으로 증명할 수 없으므로 세션은 확인된 자기 UUID만 전달해야 한다.

### 전달·재시도·대기 경쟁 처리

- 기본 켬이며 `CODEX_SLACK_BRIDGE_WAKE_ENABLED=0` 또는 `wake_enabled=false`로 끈다.
  스레드 설정은 재attach로 갱신한다. 환경 변경 시 MCP 재시작도 필요하다.
- keeper와 wait의 Slack 조회는 inbox 적재용이다. wait와 queue 모두 같은 durable inbox에서
  메시지별 `wake_deliveries` 기록을 확인한다. 전달 최대 ts로 다른 메시지의 전달을 추론하지 않는다.
  intake는 상태 파일잠금으로 ts 중복을 막으며, wait는 keeper의 intake 커서 이하 과거 답글을
  다시 수집하지 않는다. 이미 inbox에 있는 더 이른 메시지는 이 제한 없이 전달한다.
- `.delivery.lock`은 프로세스 간 flock이다. wait lease, claim, close, bind, 결과 기록에 사용한다.
  wait 중에는 새 queue를 시작하지 않으며, 이미 claim/queued/uncertain인 ts는 wait에서 제외한다.
  wait 예외 시 lease를 해제하고 프로세스 사망 시 timeout+30초에 만료한다.
- keeper는 별도 worker를 예약한다. claim fsync와 `Popen` 시작만 짧은 잠금 안에서 수행하고
  `communicate(timeout=20)`는 잠금 밖에서 기다린다. 재시도는 저장한 시각으로 판단하여 sleep하지 않는다.
  close/bind/wait 잠금 획득은 최대 0.25초 후 명시 오류다. 새 launch는 닫힘과 마감도 재검사한다.
- queue 직전 현재 스레드/채널 listener, 소유자, 멘션, 내장 명령 필터를 다시 적용한다.
  철회된 메시지는 `revoked`로 기록한다. 본문은 외부 데이터 JSON이며 셸 없이 인자 배열로 전달한다.
- 프로세스 시작 자체가 실패한 경우만 5초·15초 백오프로 총 3회 시도한다. 이 확정 미전달은
  wait로 받을 수 있다. 실행파일/UUID가 없으면 queue하지 않는다.
- 접수 정규식은 실측 `Queued message … for thread ….` 그대로 유지했다. 접수 확인, exit 0,
  빈 stderr가 함께 있어야 성공이다. 실행 후 접수 미확인/timeout은 `uncertain`으로 남겨 재전송하지 않는다.
  접수 후 경고도 해당 ts는 재전송하지 않는다. 새 메시지는 실패를 재판정하며 다른 미전달은
  60초 cooldown 후 재판정한다. `slack_chat_list`에 wake 상태와 마지막 오류를 표시한다.
- 성공 후에도 실제 응답은 기존 `session_reply_ts` 건강 점검으로 확인한다. 실패 ⚠️ 경로는 유지한다.

### 검수 보완 재현 근거

`test_wait_must_not_skip_older_durable_inbox_message`: inbox에 101을 저장하고 Slack 조회에는
102만 남기는 경우(101이 Slack에서 삭제된 상황), 기존 wait는 102만 반환하여 max 커서가
101을 건너뛰었다. 수정 전 테스트 실패로 유실 경로를 확인했다. 수정 후 두 메시지를 모두
반환한다. 늦게 적재된 이전 ts, 재시작 claim, wait/queue 경쟁, 비동기 작업 중 close/bind,
listener 철회, UUID 불일치, 실제 argv와 상태 전이도 mock 회귀 테스트로 검증한다.

### 2차 검수: close·철회·worker 상한

close는 Slack 상태 변경 전에 전달 잠금을 확보한다. 잠금이 바쁘면 아무 변경 없이 false를
반환하고, keeper는 마감/부모 종료/폰 닫기에서 다음 주기에 다시 시도한다. switch는 기존 및
확인된 목적지 스레드 잠금을 모두 확보한 후 변경하며, 경합 시 사용자에게 재시도를 안내한다.
중첩 close/bind는 명시적으로 확보한 transaction 잠금만 재사용한다.

스레드·채널 listener 변경은 공통 `_listeners` 파일잠금을 사용한다. queue도 이 잠금을
현재 필터 확인부터 claim/프로세스 시작까지 보유하므로 철회와 launch 순서가 정해진다.
잠금 점유 중 listener 명령은 변경하지 않고 재전송 안내를 보낸다. 이미 시작한 queue는 취소하지 않는다.

`.wake-locks/`의 4개 flock 슬롯으로 동일 상태 디렉터리를 공유하는 keeper들의 queue worker를
합쳐 최대 4개로 제한한다. 슬롯이 없으면 claim하지 않고 다음 tick으로 미룬다. 슬롯은 worker
종료 시 해제한다. 프로세스 종료 후 이미 시작한 자식 queue의 생존까지 이 상한으로 통제하지는 못한다.
close/switch가 Slack을 호출하는 동안에는 해당 전달 잠금이 유지되며, 상태 파일 내부 잠금과
네트워크 호출 전체에 0.25초 실행 제한이 생긴 것은 아니다.

### 운영 한계와 복구

지킴이 프로토콜을 `inbox-gated-v4`로 올렸다. 실행 중인 옛 `inbox-v1`/`inbox-queue-v2`/`inbox-ledger-v3` 지킴이를 새
어댑터 지원 프로세스로 오인하지 않고 `STALE_KEEPER`로 알린다. 배포 시 운영자가 옛
지킴이를 정리한 뒤 재attach해야 한다. 이 변경은 프로세스를 자동 종료하지 않는다.

queue CLI에는 원자적 클라이언트 중복 키나 접수 확인 API가 없다. 로컬 상태 저장과 원격
queue 사이의 crash/timeout에는 exactly-once를 보장할 수 없다. 중복 방지를 우선하여
미확정 claim은 자동 재전송과 wait 재전달에서 제외하므로, 실제로 저장되지 않은 메시지도
자동 처리가 멈출 수 있다. inbox는 보존된다. **대상 Codex 대화와 inbox를 사람이 대조해
처리 여부를 확인해야 하며 미확정 claim을 맹목적으로 지우거나 다시 queue하지 않는다.**
새 메시지는 실패 상태에서 자동으로 재판정한다. 재attach도 실패 상태를 풀지만 이미 claim한
ts는 보존한다. 과거 high-water 상태는 최초 실행 시 기존 inbox를 legacy 기록으로 이관한다.
과거 커서가 이미 건너뛴 메시지의 처리 여부는 복원할 수 없으므로 운영자 확인이 필요하다.
공유 MCP 서버/daemon 환경 UUID는 호출자 신원을 증명하지 못한다. 명시/환경 불일치는
거부하지만, 동일한 잘못된 값이나 환경만 존재하는 오매핑은 막지 못하므로 세션별 MCP를 권한다.

64KB가 넘는 전달 본문은 자동 queue하지 않고 wait 경로로 남긴다. 여러 Slack 스레드가
동일 Codex UUID를 공유할 때 스레드 사이 전역 순서는 보장하지 않는다. 수동 monitor/watch는
이 전달 잠금·커서에 참여하지 않으므로 queue와 병행하지 않는다. 매핑 변경·닫힘과 이미
실행 중인 원격 queue는 원자적으로 취소할 수 없어 한 건의 지연 전달 가능성이 남는다. listener 재검사 이후 시작된 요청 역시 철회로 취소할 수 없다.
wait 반환 직전 프로세스가 죽으면 `waited` 기록만 남을 수 있어 정확히 한 번의 모델 수신까지
보장하지 않는다. 메시지별 기록은 inbox와 함께 누적되며 열린 장기 스레드의 용량 관리가 필요하다.

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
  커서 및 경고 상호작용은 추가 실환경 검증이 필요하다. inbox와 메시지별 전달 기록은 위와 같이 공유한다.
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
검수 보완 후: pytest 82 passed, 50 subtests passed. 홈 경로 대신 레포 내부 임시 fixture를 사용했다.
명령: `UV_CACHE_DIR=$PWD/.cache/uv TMPDIR=$PWD/tests uv run --offline --with pytest pytest -q`.
테스트는 Slack 호출과 지킴이 기동을 mock하고 임시 상태를 레포 안에 둔다.
`docs/PARITY.md`의 Claude 언급은 역사적 비교 근거로 의도적으로 보존한다.
