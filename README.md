# MobiusForge

**Autonomous Agent Harness — AI가 코딩하는 동안, 하네스가 품질을 보장한다.**

MobiusForge는 [Ralphthon @Seoul 2026](https://luma.com/v68q8un9?locale=ko)을 위해 설계된 차세대 자율 에이전트 실행 프레임워크입니다. Ralph Loop의 한계를 구조적으로 해결하고, "Humans On the Loop" 패턴으로 100% 자율 실행을 달성합니다.

```
Loop N ──교훈 기록──▶ lessons.md ──관련 교훈 필터──▶ Loop N+1
         (끝)          (태그 기반)                    (시작)
              ↑                                        │
              └──────── 뫼비우스 연결 ──────────────────┘
```

## Why MobiusForge?

기존 Ralph Loop의 6대 한계를 해결합니다:

| 문제 | Ralph Loop | MobiusForge |
|------|-----------|-------------|
| Oscillation (무한 반복) | 수동 중단 | diff 해시 감지 → 자동 전략 전환 |
| Context Amnesia | 매 루프 리셋, 학습 없음 | 태그 기반 교훈 주입 (뫼비우스 메모리) |
| Premature Exit | 미완성 코드 커밋 | Acceptance Criteria 자동 재검증 |
| 단일 에이전트 병목 | 순차 실행만 | DAG 기반 Worktree 병렬 실행 |
| 비용 폭발 | 제어 불가 | 실시간 토큰 추적 + 예산 가드 |
| Goal Drift | 감지 없음 | 키워드 기반 Drift 분석 + 자동 롤백 |

## Quick Start

```bash
# 설치
pip install -e .

# 프로젝트 초기화
cd my-project
mobiusforge init

# 설정 편집
vim config.yaml    # 모델, 예산, 타임아웃 등
vim PROMPT.md      # 프로젝트 규칙, 코딩 컨벤션
vim task_plan.md   # 태스크 정의

# specs 작성
mkdir -p specs
vim specs/T-001.md  # 태스크별 상세 명세

# 실행
mobiusforge start

# 대회 모드 (시간 제한 + 예산)
mobiusforge start --end-time "2026-03-29T21:00:00+09:00" --budget 30
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  MobiusForge CLI                     │
├─────────────────────────────────────────────────────┤
│  Orchestrator          Claude Code Layer             │
│  ┌────────────┐        ┌──────────────────────┐     │
│  │ Loop Mgr   │───────▶│ --output-format json  │     │
│  │ Planner    │        │ --agents (subagent)   │     │
│  │ Prompt Asm │        │ isolation: worktree   │     │
│  └────────────┘        │ hooks (validation)    │     │
│                        │ memory: project       │     │
│  Intelligence          └──────────────────────┘     │
│  ┌────────────────────────────────────────────┐     │
│  │ Oscillation Detector → Strategy Rotator    │     │
│  │ Completion Verifier  → Drift Detector      │     │
│  │ Budget Guard         → Agentic Flywheel    │     │
│  └────────────────────────────────────────────┘     │
│                                                     │
│  TUI Dashboard (Rich)                               │
└─────────────────────────────────────────────────────┘
```

## Core Loop

매 루프마다:

1. **Guard Check** — 예산, 시간, 루프 수 확인
2. **Load State** — task_plan.md, lessons.md, guardrails 로딩
3. **Select Task** — 우선순위 + 의존성 기반 태스크 선택
4. **Assemble Prompt** — PROMPT.md + spec + 관련 교훈 + 실패 접근법 조합
5. **Run Agent** — Claude Code CLI 실행 (JSON 출력으로 토큰 추적)
6. **Oscillation Check** — diff 해시 비교, 핑퐁 패턴 감지
7. **Drift Check** — 변경 파일 vs 태스크 명세 비교 (매 5루프)
8. **Validate** — 테스트 + 린트 실행
9. **Completion Verify** — Acceptance Criteria 충족 여부 재검증
10. **Commit or Rollback** — 성공 시 커밋, 실패 시 롤백 + 교훈 기록
11. **Repeat** — 뫼비우스 연결

## Key Features

### Anti-Oscillation Pipeline

에이전트가 막혔을 때 자동 탈출:

```
막힘 감지 → 전략 1: "완전히 다른 방법으로"
         → 전략 2: "서브태스크로 분해"
         → 전략 3: "최소한의 변경만"
         → Dead End: BLOCKED 처리 → 다음 태스크
```

### Mobius Memory (크로스루프 학습)

컨텍스트는 리셋되지만 지식은 연결됩니다:

- `APPLIES_TO` 태그로 현재 태스크 관련 교훈만 선택 주입
- 실패 교훈은 `[AVOID]`, 성공 교훈은 `[REUSE]`로 구분
- 30항목 초과 시 자동 정리 (실패 교훈 우선 보존)

### Completion Verifier

"완료"라고 말해도 진짜 완료인지 재검증:

- spec에 명시된 파일 패턴 존재 확인
- 함수/엔드포인트 구현 여부 grep 확인
- 테스트 통과 여부 확인
- 70% 이상 criteria 충족 시 DONE 판정

### Agentic Flywheel (자가 진화)

20루프마다 자동 자가 분석:

- 실패율, 비용 스파이크, oscillation 빈도, drift 패턴 분석
- 고심각도 발견 시 guardrails.md에 규칙 자동 추가
- PROMPT.md / spec 개선 제안 생성

## CLI Commands

| Command | Description |
|---------|-------------|
| `mobiusforge init` | 프로젝트 초기화 (config, PROMPT.md, task_plan, specs/) |
| `mobiusforge start` | 자율 루프 실행 |
| `mobiusforge start --dry-run` | 시뮬레이션 (API 호출 없이 DAG, 비용 추정) |
| `mobiusforge start --parallel 2` | 2개 에이전트 Worktree 병렬 실행 |
| `mobiusforge start --end-time "..."` | 절대 종료 시간 설정 |
| `mobiusforge dashboard` | TUI 실시간 대시보드 |
| `mobiusforge dag` | 태스크 의존성 DAG 시각화 |
| `mobiusforge status` | 현재 태스크/예산 상태 |
| `mobiusforge cost` | 비용 리포트 (JSON) |
| `mobiusforge lessons` | 학습된 교훈 출력 |
| `mobiusforge analyze` | Flywheel 자가 분석 |
| `mobiusforge analyze --auto-fix` | 분석 + 가드레일 자동 적용 |
| `mobiusforge pause` / `resume` / `abort` | 실행 제어 |

## Project Structure

```
my-project/
├── config.yaml          # MobiusForge 설정
├── PROMPT.md            # 에이전트 기본 프롬프트 (코딩 컨벤션, 규칙)
├── task_plan.md         # 태스크 목록 및 상태
├── specs/               # 태스크별 상세 명세
│   ├── T-001.md
│   └── T-002.md
├── .mobiusforge/        # 런타임 상태 (자동 생성)
│   ├── lessons.md       # 크로스루프 교훈
│   ├── guardrails.md    # 프로젝트 가드레일
│   ├── budget.json      # 비용 추적
│   └── logs/            # 활동 로그
└── src/                 # 에이전트가 작성하는 코드
```

## Configuration

```yaml
# config.yaml 주요 설정
agent:
  model: "claude-sonnet-4-6"
  timeout_per_loop: 600        # 루프당 최대 10분

loop:
  max_iterations: 100
  end_time: "2026-03-29T21:00:00+09:00"  # 대회 종료 시간
  wind_down_minutes: 30        # 종료 30분 전 새 태스크 금지

budget:
  max_total_cost: 50.0         # $50 예산

safety:
  oscillation_threshold: 3     # 3회 반복 시 감지
  max_strategy_retries: 3      # 전략 전환 최대 3회
  drift_check_interval: 5      # 5루프마다 drift 체크
```

## Safety

- **Graceful Shutdown**: Ctrl+C → 현재 루프 완료 대기 → uncommitted 변경 stash → IN_PROGRESS 태스크를 INTERRUPTED로 변경
- **Auto Rollback**: 테스트/린트 실패 시 마지막 성공 커밋으로 자동 복원
- **Budget Guard**: 예산 80% 경고, 100% 자동 정지
- **Secret Masking**: 로그에서 `sk-ant-*`, `sk-proj-*`, `ghp_*` 패턴 자동 마스킹
- **Wind-down Mode**: 종료 시간 30분 전부터 새 태스크 시작 금지

## Development

```bash
# 개발 설치
pip install -e ".[dev]"

# 테스트
pytest tests/ -v

# 린트
ruff check mobiusforge/

# TUI 대시보드 (선택)
pip install -e ".[tui]"
```

## Tech Stack

- **Python 3.12+**
- **Claude Code CLI** — 에이전트 런타임
- **Click** — CLI 프레임워크
- **Rich** — TUI 대시보드 (선택)
- **Git Worktree** — 병렬 에이전트 격리

## License

MIT

---

Built for [Ralphthon @Seoul 2026](https://luma.com/v68q8un9?locale=ko) — "AI 에이전트가 코딩하는 동안, 해커들은 커뮤니티를 만듭니다."
