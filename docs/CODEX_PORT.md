# Codex CLI 포팅과 수신 방식 결정

2026-11-02, 로컬 `codex-cli 0.166.0` 기준. 이름·상태·MCP 안내 전환은 완료했지만
자동 깨움 어댑터는 구현하지 않았다. 선택은 khj 결정 대상이다.

## 확인 근거

실행한 것은 `codex --version`, `codex --help`, `codex queue --help`,
`codex exec resume --help`뿐이다. 서버·지킴이·모델 세션·Slack 연결은 실행하지 않았다.
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

## 대안 비교 (미구현)

| 방식 | 장점 | 비용·한계 |
|---|---|---|
| 기존 `slack_wait_reply(timeout_seconds=30, thread_ts=...)` | 새 프로세스 제어 없이 현재 MCP 도구 사용 가능 | 블로킹, 여러 스레드 순차 확인 지연, 턴 종료 후 자동 재개 없음. MCP timeout보다 짧게 호출해야 함 |
| 명시적 세션 ID로 `codex queue … --resume` (또는 `codex exec resume`) 어댑터 | 공식 CLI의 세션 지정 기능 사용. 향후 자동화 후보로 추천 | Slack thread와 Codex UUID 매핑, 중복 방지·재시도·처리 확인 필요. queue 재개 실패가 성공 코드일 수 있음. exec resume 동시 실행 충돌 방지 필요 |
| tmux `send-keys` 어댑터 | 기존 터미널을 이용 가능 | pane 오인, 입력 중 충돌, 인용·제어문자 문제, 터미널 상태 의존. 무인 운영용으로 비추천 |

즉시 사용은 짧은 명시적 wait 호출을 권한다. 작업 중/턴 종료 후 자동 깨움이 필요하면
khj 결정 후 queue 기반 어댑터를 먼저 검증할 것을 추천한다. 현재 지킴이에 resume를
덧붙이지 않았다. Slack 텍스트는 신뢰할 수 없는 입력으로 전달하고 기존 소유자·listener
검증을 유지해야 한다. `--last`로 세션을 추측하지 않는다.

## 남은 런타임 한계

- `_session_pid()`는 조상 실행 파일 basename이 정확히 `codex`인 경우만 채택한다.
  uvx/셸/브리지 이름을 세션으로 오인하지 않는다. 탐지 실패·ps 실패 시 MCP 서버 PID를 쓴다.
  공유 app-server 구성에서는 그 PID가 개별 대화 수명과 다를 수 있어 실환경 검증이 필요하다.
- `threads.inbox_tailed()`는 lsof로 열린 inbox만 검사한다. Codex 수신 확인이 아니며
  wait 도구는 파일을 계속 열고 있지 않아 경고가 발생할 수 있다. 자동화 결정 전 이 판정을
  세션 수신 성공으로 강화하거나 허위 heartbeat를 만들지 않았다.
- 지킴이와 wait는 서로 다른 폴링 경로다. 실 Slack에서 멘션/명령 처리와 중복 메시지,
  커서 및 경고 상호작용은 추가 검증이 필요하다. 원본 동작을 유지했다.
- 공유 daemon 수명, macOS 절전, 실제 Slack 권한/연결, 동시 브리지 운영은 미검증이다.

## 공존과 검증

패키지 `codex_slack_bridge`, 배포·CLI·MCP 서버명 `codex-slack-bridge`, 상태 루트
`~/.codex-slack-bridge`, 앱 표시명 `Codex Bridge`로 분리했다.
환경변수는 `CODEX_SLACK_BRIDGE_` 접두어만 사용하고 공용 `SLACK_*` fallback을 제거했다.
토큰/앱도 별도로 설정해야 하며 기존 브리지 설정을 자동 이관하지 않는다.
`NO_COLOR` 같은 표준 표현 설정은 공유한다. MCP 도구의 `slack_*` 이름은 서버별 namespace로 구분된다.

원본 기준: pytest 40 passed, 42 subtests passed.
전환 후: pytest 45 passed, 44 subtests passed (PID 탐지·실패 fallback·환경변수 격리 추가).
명령: `UV_CACHE_DIR=$PWD/.cache/uv TMPDIR=$PWD/tests uv run --offline --with pytest pytest -q`.
테스트는 Slack 호출과 지킴이 기동을 mock하고 임시 상태를 레포 안에 둔다.
`docs/PARITY.md`의 Claude 언급은 역사적 비교 근거로 의도적으로 보존한다.
