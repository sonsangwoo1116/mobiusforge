# MobiusForge - Autonomous Agent Harness PRD

> **Version**: 2.0
> **Created**: 2026-03-16
> **Updated**: 2026-03-16 (digging 분석 반영)
> **Status**: Draft
> **Project**: Ralphthon @Seoul 2026 출전용
> **Author**: Team (TBD)

---

## 1. Overview

### 1.1 Problem Statement

현재 Ralph Loop 기반 에이전트 하네스들은 다음과 같은 한계를 가진다:

| 문제 | 설명 |
|------|------|
| **Oscillating Loop** | 에이전트가 두 오류 상태를 왔다갔다하며 무한 루프에 빠짐 |
| **Context Amnesia** | 매 루프마다 컨텍스트 리셋으로 이전 실패 교훈을 잃음 |
| **단일 에이전트 병목** | 하나의 에이전트가 모든 작업을 순차 처리 → 느림 |
| **Premature Exit** | 에이전트가 "충분히 좋다"고 판단하고 조기 종료 |
| **비용 폭발** | 50회 반복 시 $50~100+ API 크레딧 소모, 제어 불가 |
| **Drift 감지 부재** | 에이전트가 원래 목표에서 벗어나도 자동 감지 못함 |

**MobiusForge**는 이 문제들을 해결하는 차세대 자율 에이전트 하네스다.

### 1.2 Goals

- **G1**: 100% 자율 실행 달성 (Ralphthon "가재옷 룰" 통과)
- **G2**: Ralph Loop의 6대 한계를 구조적으로 해결
- **G3**: "Humans On the Loop" 패턴 구현 — 에이전트가 실행하되 하네스가 품질을 보장
- **G4**: Agentic Flywheel — 실행할수록 하네스 자체가 개선되는 자가 진화 구조
- **G5**: Ralphthon @Seoul 대회 우승

### 1.3 Non-Goals (Out of Scope)

- 범용 SaaS 플랫폼 (대회 전용 도구)
- GUI 기반 에디터/IDE 통합
- 멀티 유저 동시 접속
- 클라우드 배포 (로컬 실행 전용)

### 1.4 Scope

| 포함 | 제외 |
|------|------|
| Claude Code SDK/Subagent 기반 에이전트 실행 루프 | 모델 파인튜닝 |
| 파일 기반 상태 관리 + Claude Code persistent memory | 외부 데이터베이스 |
| Claude Code Hooks 기반 자동 테스트/린트/커밋 | CI/CD 서비스 연동 |
| 실시간 모니터링 TUI 대시보드 | 웹 기반 대시보드 |
| Git worktree 기반 병렬 격리 실행 | 쿠버네티스 오케스트레이션 |
| 멀티 에이전트 오케스트레이션 (Subagent System) | 3개 이상 LLM 동시 사용 |
| SDK 기반 토큰/비용 추적 | 결제 시스템 |

### 1.5 Security Policy

- API 키는 환경변수(`ANTHROPIC_API_KEY`)로만 전달. config.yaml에 시크릿 포함 금지
- `.gitignore`에 `.env`, `.mobiusforge/logs/`, `.mobiusforge/raw/` 포함
- 로그에서 API 키 패턴(`sk-ant-*`, `sk-proj-*`) 자동 마스킹
- 에이전트에 `permissionMode: dontAsk` + 명시적 `allowedTools`로 권한 최소화

---

## 2. User Stories

### 2.1 Primary User

**해커톤 참가자** — Ralphthon @Seoul에 출전하여 자율 에이전트로 12시간 내에 프로젝트를 완성해야 하는 개발자.

### 2.2 User Stories & Acceptance Criteria

#### US-001: 원커맨드 자율 실행

> As a 해커톤 참가자, I want to 하나의 명령어로 에이전트를 시작하고 자율 실행시킬 수 있게 so that 수동 개입 없이 12시간 동안 코딩이 진행된다.

```gherkin
Scenario: 원커맨드 시작
  Given PRD(specs)와 프로젝트 초기 코드가 준비됨
  When `mobiusforge start` 명령어 실행
  Then 에이전트가 자율적으로 태스크를 선택하고 구현을 시작한다
  And 각 태스크 완료 시 자동으로 테스트/커밋이 실행된다
  And 모든 태스크 완료 또는 타임아웃까지 반복한다
```

#### US-002: Oscillation 자동 탈출

> As a 참가자, I want to 에이전트가 두 오류 상태를 왕복하는 것을 자동 감지하고 탈출하게 so that 무한 루프에 시간을 낭비하지 않는다.

```gherkin
Scenario: Oscillation 감지 및 탈출
  Given 에이전트가 같은 파일을 3회 이상 되돌리기/재수정
  When Oscillation Detector가 패턴을 감지
  Then 현재 접근법을 중단한다
  And 실패 원인을 lessons.md에 기록한다
  And 대안 전략(다른 접근법/태스크 스킵)으로 전환한다
```

#### US-003: 크로스루프 학습

> As a 참가자, I want to 이전 루프의 실패/성공 패턴이 다음 루프에 반영되게 so that 같은 실수를 반복하지 않는다.

```gherkin
Scenario: 실패 패턴 학습
  Given Loop N에서 특정 접근법이 실패하여 기록됨
  When Loop N+1이 시작되고 유사한 태스크를 만남
  Then 에이전트 프롬프트에 이전 실패 교훈이 포함된다
  And 동일한 실패 접근법을 피한다
```

#### US-004: 실시간 모니터링

> As a 참가자, I want to 에이전트의 진행 상황을 실시간으로 볼 수 있게 so that 문제 발생 시 빠르게 파악할 수 있다.

```gherkin
Scenario: TUI 대시보드 모니터링
  Given MobiusForge가 실행 중
  When `mobiusforge dashboard` 실행
  Then 현재 태스크, 진행률, 토큰 사용량, 비용이 표시된다
  And 최근 커밋 로그와 테스트 결과가 실시간 갱신된다
```

#### US-005: 멀티 에이전트 병렬 실행

> As a 참가자, I want to 독립적인 태스크를 여러 에이전트가 동시에 처리하게 so that 12시간을 최대한 효율적으로 사용한다.

```gherkin
Scenario: 병렬 태스크 실행
  Given PRD에 독립적인 태스크 A, B, C가 있음
  When Orchestrator가 의존성 그래프를 분석
  Then 독립 태스크 A, B를 별도 worktree에서 동시 실행
  And C는 A 완료 후 순차 실행
  And 병합 시 충돌 자동 해결
```

#### US-006: 태스크 완료 재검증

> As a 참가자, I want to 에이전트가 "완료"를 선언해도 실제 완료 여부를 재검증하게 so that 미완성 코드가 커밋되지 않는다.

```gherkin
Scenario: 완료 재검증
  Given 에이전트가 태스크 완료를 선언
  When Completion Verifier가 specs의 acceptance criteria와 비교
  Then criteria를 충족하면 DONE 처리
  And criteria 미충족 시 에이전트에게 부족한 부분을 명시하여 재작업 지시
```

#### US-007: 목표 이탈 감지

> As a 참가자, I want to 에이전트가 원래 목표에서 벗어나는 것을 자동 감지하게 so that 시간을 낭비하지 않는다.

```gherkin
Scenario: Drift 감지
  Given 에이전트가 현재 태스크와 무관한 파일을 수정
  When Drift Detector가 변경 diff와 태스크 명세를 비교
  Then drift 점수가 임계값 초과 시 에이전트를 중단
  And 원래 태스크로 리다이렉트
```

---

## 3. Functional Requirements

### 3.1 Core Engine

| ID | Requirement | Priority | Dependencies |
|----|------------|----------|--------------|
| FR-001 | **Mobius Loop Engine**: Claude Code SDK 기반 반복 실행 루프. 매 루프마다 새 세션 시작, 파일 기반 상태 읽기. `--output-format json`으로 토큰 사용량 포함 응답 수신 | P0 (Must) | - |
| FR-002 | **Plan Reader**: task_plan.md에서 현재 태스크 상태를 읽고 다음 작업을 결정 | P0 (Must) | FR-001 |
| FR-003 | **Spec Loader**: specs/ 디렉토리에서 태스크별 명세를 선택적으로 로드 (컨텍스트 효율화) | P0 (Must) | FR-002 |
| FR-004 | **Auto Validator**: Claude Code `PostToolUse` 훅으로 테스트/린트 자동 실행. 실패 시 task_plan에 기록 | P0 (Must) | FR-001 |
| FR-005 | **Auto Committer**: 검증 통과 시 자동 git add + commit (의미 있는 커밋 메시지 생성) | P0 (Must) | FR-004 |

### 3.2 Anti-Oscillation System

| ID | Requirement | Priority | Dependencies |
|----|------------|----------|--------------|
| FR-006 | **Oscillation Detector**: 동일 파일의 반복 수정 패턴 감지 (diff 해시 비교, 최근 5루프 윈도우) | P0 (Must) | FR-001 |
| FR-007 | **Strategy Rotator**: oscillation 감지 시 대안 접근법으로 전환 (최대 3회). 메커니즘: (1) 실패 접근법을 lessons.md에 기록 (2) "이전 접근법 X 실패. 완전히 다른 방법 시도" 프롬프트 주입 (3) 3회 모두 실패 시 태스크를 더 작은 서브태스크로 분해 시도 | P0 (Must) | FR-006 |
| FR-008 | **Dead-end Skipper**: 모든 전략 실패 시 태스크를 BLOCKED 처리하고 다음으로 이동 | P1 (Should) | FR-007 |

### 3.3 Cross-Loop Memory (뫼비우스 메모리)

| ID | Requirement | Priority | Dependencies |
|----|------------|----------|--------------|
| FR-009 | **Lessons Writer**: 매 루프 종료 시 성공/실패 교훈을 `.mobiusforge/lessons.md`에 append. Claude Code Subagent `memory: project` 기능과 연계 | P0 (Must) | FR-001 |
| FR-010 | **Lesson Injector**: 루프 시작 시 관련 교훈을 에이전트 프롬프트에 주입. `APPLIES_TO` 태그 기반 관련도 필터링으로 현재 태스크 관련 교훈만 선택 | P0 (Must) | FR-009 |
| FR-011 | **Guardrails File**: `.mobiusforge/guardrails.md`에 프로젝트 규칙/제약 누적 관리 | P1 (Should) | - |
| FR-012 | **Lesson Pruner**: lessons.md가 30항목 초과 시 오래되고 관련도 낮은 항목 자동 제거. APPLIES_TO 태그 기반 관련도 + 시간 decay 알고리즘 | P1 (Should) | FR-009 |

### 3.4 Completion & Drift Verification

| ID | Requirement | Priority | Dependencies |
|----|------------|----------|--------------|
| FR-013 | **Completion Verifier**: 에이전트가 태스크 완료 선언 시 specs의 acceptance criteria와 실제 구현을 비교. 미충족 항목이 있으면 에이전트에게 구체적 부족 사항을 명시하여 재작업 지시. `PreToolUse` 훅으로 커밋 전 자동 실행 | P0 (Must) | FR-003, FR-004 |
| FR-014 | **Goal Drift Detector**: 5루프마다 현재 코드 변경 diff와 현재 태스크 명세를 비교하여 drift 점수 산출. LLM 기반 의미적 비교 (변경이 목표에 기여하는지) | P1 (Should) | FR-002, FR-003 |
| FR-015 | **Drift Auto Corrector**: drift 점수가 임계값(0.7) 초과 시 에이전트를 중단하고 원래 태스크로 리다이렉트. drift 원인을 lessons.md에 기록 | P1 (Should) | FR-014 |

### 3.5 Multi-Agent Orchestration

| ID | Requirement | Priority | Dependencies |
|----|------------|----------|--------------|
| FR-016 | **Dependency Graph Builder**: PRD/specs에서 태스크 의존성 DAG 자동 생성 | P1 (Should) | FR-003 |
| FR-017 | **Parallel Executor**: Claude Code `--agents` + `isolation: worktree`로 독립 태스크를 별도 git worktree에서 동시 실행. 에이전트별 개별 상태 파일 관리 (race condition 방지) | P1 (Should) | FR-016 |
| FR-018 | **Worktree Merger**: 병렬 워크트리 완료 시 메인 브랜치로 순차 머지. 충돌 발생 시 에이전트에게 머지 해결 태스크 위임 | P1 (Should) | FR-017 |
| FR-019 | **Agent Pool Manager**: 동시 실행 에이전트 수 제한 및 리소스 관리 | P1 (Should) | FR-017 |

### 3.6 Monitoring & Control

| ID | Requirement | Priority | Dependencies |
|----|------------|----------|--------------|
| FR-020 | **TUI Dashboard**: Rich/Textual 기반 터미널 대시보드 (진행률, 로그, 비용) | P1 (Should) | FR-001 |
| FR-021 | **Token/Cost Tracker**: `--output-format json` 응답에서 `usage` 필드 파싱하여 루프별 토큰 사용량 및 누적 비용 추적 | P0 (Must) | FR-001 |
| FR-022 | **Budget Guard**: 설정된 예산 한도 초과 시 자동 일시정지 | P0 (Must) | FR-021 |
| FR-023 | **Activity Logger**: 모든 에이전트 활동을 `.mobiusforge/logs/`에 구조화 기록. API 키 패턴 자동 마스킹 | P0 (Must) | FR-001 |

### 3.7 Agentic Flywheel (자가 진화)

| ID | Requirement | Priority | Dependencies |
|----|------------|----------|--------------|
| FR-024 | **Harness Self-Analyzer**: N 루프마다 전체 실행 패턴을 분석하여 비효율 감지 | P2 (Could) | FR-023 |
| FR-025 | **Prompt Auto-Tuner**: 실행 결과 기반으로 PROMPT.md 자동 개선 제안 | P2 (Could) | FR-024 |
| FR-026 | **Spec Refiner**: 반복 실패하는 태스크의 specs를 자동 구체화 | P2 (Could) | FR-024 |

### 3.8 Safety & Control

| ID | Requirement | Priority | Dependencies |
|----|------------|----------|--------------|
| FR-027 | **Rollback Guard**: 검증 실패 시 자동 git rollback (마지막 성공 커밋으로) | P0 (Must) | FR-004 |
| FR-028 | **Max Loop Limiter**: 최대 루프 횟수 제한 (기본: 100) | P0 (Must) | FR-001 |
| FR-029 | **Timeout Guard**: 단일 루프 최대 실행 시간 제한 (기본: 10분) | P0 (Must) | FR-001 |
| FR-030 | **Absolute Time Guard**: 대회 종료 시간 기반 제어. `end_time` 설정 시 해당 시각 도달하면 새 태스크 시작 금지. `wind_down_minutes`(기본 30분) 전부터 정리 모드 진입 | P0 (Must) | FR-001 |
| FR-031 | **Graceful Shutdown**: abort 시 안전한 중단 프로토콜. (1) SIGTERM → 30초 대기 (2) 미종료 시 SIGKILL (3) uncommitted 변경 자동 git stash (4) IN_PROGRESS 태스크를 INTERRUPTED로 변경 (5) 재개 시 INTERRUPTED부터 시작 | P0 (Must) | FR-001 |
| FR-032 | **Docker Sandbox**: 에이전트 실행을 Docker 컨테이너 내부로 격리 (사전 빌드된 이미지 사용) | P2 (Could) | - |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Metric | Target |
|--------|--------|
| 루프 시작 오버헤드 | < 3초 (상태 로딩 + 프롬프트 조립) |
| 동시 에이전트 수 | 최대 4개 병렬 worktree |
| 모니터링 갱신 주기 | < 2초 (TUI 대시보드) |
| 12시간 연속 실행 | 안정적 동작 (메모리 누수 없음) |

### 4.2 Reliability

| Metric | Target |
|--------|--------|
| Oscillation 탈출 성공률 | > 90% |
| 자동 복구율 (에이전트 크래시) | > 95% (자동 재시작) |
| 데이터 무손실 | 어떤 실패에서도 .mobiusforge/ 상태 보존 |
| Graceful Shutdown 성공률 | 100% (uncommitted 변경 보존) |

### 4.3 Cost Efficiency

| Metric | Target |
|--------|--------|
| 루프당 평균 토큰 사용 | < 50K tokens |
| 12시간 총 비용 | < $50 (Claude API) |
| 불필요한 반복 비율 | < 10% (oscillation + drift + premature exit) |

### 4.4 Developer Experience

| Metric | Target |
|--------|--------|
| 초기 설정 시간 | < 5분 (config.yaml + specs 작성) |
| 러닝 커브 | README만으로 시작 가능 |
| 디버깅 | 모든 루프의 input/output 재현 가능 |
| dry-run | 실제 API 호출 없이 루프 흐름 시뮬레이션 가능 |

---

## 5. Technical Design

### 5.1 Architecture Overview (하이브리드 아키텍처)

Claude Code 내장 기능 위에 MobiusForge 차별화 레이어를 얹는 구조:

```
┌─────────────────────────────────────────────────────────────────┐
│                        MobiusForge CLI                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          Orchestrator (MobiusForge 핵심 — 직접 구현)       │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │  │
│  │  │ Loop Mgr │ │ Planner  │ │ Prompt   │ │ State Mgr  │  │  │
│  │  │          │ │ (태스크   │ │ Assembler│ │ (task_plan │  │  │
│  │  │          │ │  선택/DAG)│ │          │ │  파서)     │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────────────────┐  │
│  │          Claude Code Layer (내장 기능 활용)                 │  │
│  │                                                           │  │
│  │  • --agents JSON 플래그로 서브에이전트 정의                  │  │
│  │  • --output-format json으로 토큰 사용량 수신                │  │
│  │  • isolation: worktree로 병렬 에이전트 격리                 │  │
│  │  • hooks (PreToolUse/PostToolUse)로 검증 자동화             │  │
│  │  • memory: project로 크로스세션 학습 보조                   │  │
│  │  • permissionMode: dontAsk로 무중단 실행                   │  │
│  │  • allowedTools로 에이전트 권한 최소화                      │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────────────────┐  │
│  │       MobiusForge Intelligence (차별화 — 직접 구현)        │  │
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐ │  │
│  │  │ Oscillation │ │ Drift        │ │ Completion       │ │  │
│  │  │ Detector    │ │ Detector     │ │ Verifier         │ │  │
│  │  └─────────────┘ └──────────────┘ └───────────────────┘ │  │
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐ │  │
│  │  │ Strategy    │ │ Budget Guard │ │ Agentic Flywheel │ │  │
│  │  │ Rotator     │ │ & Tracker    │ │ (Self-Improve)   │ │  │
│  │  └─────────────┘ └──────────────┘ └───────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    TUI Dashboard (Textual)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Claude Code 내장 기능 활용 매핑

| MobiusForge 요구사항 | Claude Code 내장 기능 | 추가 구현 필요 |
|---|---|---|
| 에이전트 실행 | `claude -p --output-format json --allowedTools ...` | 프롬프트 조립, 루프 관리 |
| 토큰/비용 추적 (FR-021) | `--output-format json` → `usage` 필드 | 누적 합산, 예산 비교 |
| 크로스루프 학습 (FR-009/010) | `memory: project` (서브에이전트) | lessons.md 구조화, 태그 기반 필터링 |
| 병렬 실행 격리 (FR-017) | `isolation: worktree` | DAG 스케줄링, 머지 관리 |
| 테스트/린트 자동화 (FR-004) | `hooks.PostToolUse` | Oscillation 감지, Completion 검증 |
| 에이전트 권한 제어 | `permissionMode`, `allowedTools` | - |

### 5.3 Core Loop Flow (뫼비우스 루프 v2)

```
                    ┌─── Loop Start ───┐
                    │                  │
                    ▼                  │
            ┌──────────────┐           │
            │ Guard Check  │           │
            │ • Budget OK? │           │
            │ • Max Loop?  │           │
            │ • Time Left? │ ← FR-030 Absolute Time Guard
            │ • Wind Down? │           │
            └──────┬───────┘           │
                   │ OK                │
                   ▼                   │
            ┌──────────────┐           │
            │ Load State   │           │
            │ task_plan.md │           │
            │ lessons.md   │           │
            │ guardrails   │           │
            └──────┬───────┘           │
                   │                   │
                   ▼                   │
            ┌──────────────┐           │
            │ Select Task  │           │
            │ (priority +  │           │
            │  dependency  │           │
            │  + DAG)      │           │
            └──────┬───────┘           │
                   │                   │
                   ▼                   │
            ┌──────────────┐           │
            │ Assemble     │           │
            │ Prompt       │           │  뫼비우스 띠:
            │ (PROMPT.md + │           │  안과 밖이 없는
            │  spec + task │           │  무한 연결
            │  + lessons   │           │
            │  + guardrails│           │
            │  + failed    │           │
            │  approaches) │           │
            └──────┬───────┘           │
                   │                   │
                   ▼                   │
            ┌──────────────┐           │
            │ Run Agent    │           │
            │ (Claude Code │           │
            │  SDK/CLI     │           │
            │  --agents    │           │
            │  --json out) │           │
            └──────┬───────┘           │
                   │                   │
                   ▼                   │
            ┌──────────────┐           │
            │ Track Tokens │ ← FR-021 JSON usage 파싱
            │ Update Cost  │           │
            └──────┬───────┘           │
                   │                   │
                   ▼                   │
            ┌──────────────┐           │
            │ Completion   │ ← FR-013 Acceptance Criteria 검증
            │ Verifier     │           │
            └──────┬───────┘           │
                   │                   │
                   ▼                   │
            ┌──────────────┐           │
            │ Validate     │◄── Oscillation Check (FR-006)
            │ (test/lint)  │◄── Drift Check (FR-014, 매 5루프)
            └──────┬───────┘           │
                   │                   │
              ┌────┴────┐              │
              │         │              │
           PASS      FAIL              │
              │         │              │
              ▼         ▼              │
         ┌────────┐ ┌────────┐        │
         │ Commit │ │Rollback│        │
         │ + Log  │ │+ Learn │        │
         │+ Lesson│ │+ Rotate│ ← FR-007 Strategy Rotator
         └───┬────┘ └───┬────┘        │
             │          │              │
             └────┬─────┘              │
                  │                    │
                  ▼                    │
            ┌──────────────┐           │
            │ Update State │           │
            │ task_plan.md │           │
            │ lessons.md   │           │
            │ prune if >30 │ ← FR-012 Lesson Pruner
            └──────┬───────┘           │
                   │                   │
                   ▼                   │
            ┌──────────────┐           │
            │ All Done?    │── No ─────┘
            └──────┬───────┘
                   │ Yes
                   ▼
              ┌─────────┐
              │  Done   │
              └─────────┘
```

### 5.4 Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Language | **Python 3.12+** | 에코시스템, 빠른 개발 |
| CLI | **Click** | 직관적 CLI 프레임워크 |
| Agent Runtime | **Claude Code CLI** (`--agents`, `--output-format json`) | SDK 레벨 토큰 추적, 서브에이전트, 훅 시스템 내장 |
| Agent Isolation | **Git Worktree** (`isolation: worktree`) | Docker 없이 병렬 격리. Claude Code 내장 |
| TUI | **Textual** | 모던 터미널 UI |
| Config | **YAML (PyYAML)** | 사람이 읽기 쉬운 설정 |
| State | **Markdown + JSON** | 파일 기반, git 친화적 |
| Test Runner | **subprocess** (pytest/jest 등) | 프로젝트 독립적 |
| Container | **Docker** (선택적) | P2. 사전 빌드 이미지만 사용 |

### 5.5 Directory Structure

```
ralphthon-harness/
├── mobiusforge/                     # 패키지 코드
│   ├── __init__.py
│   ├── cli.py                       # CLI 엔트리포인트 (click)
│   ├── core/
│   │   ├── loop.py                  # 뫼비우스 루프 엔진
│   │   ├── planner.py               # 태스크 선택 & DAG
│   │   ├── runner.py                # 에이전트 실행기 (claude CLI 래퍼)
│   │   ├── prompt_assembler.py      # 프롬프트 조립기
│   │   └── validator.py             # 테스트/린트 검증기
│   ├── memory/
│   │   ├── state.py                 # task_plan.md 파서/업데이터
│   │   ├── lessons.py               # 교훈 관리 (읽기/쓰기/주입/정리)
│   │   └── guardrails.py            # 가드레일 관리
│   ├── intelligence/
│   │   ├── oscillation.py           # 진동 감지기
│   │   ├── strategy_rotator.py      # 대안 전략 생성기
│   │   ├── completion_verifier.py   # 태스크 완료 재검증
│   │   └── drift_detector.py        # 목표 이탈 감지기
│   ├── orchestration/
│   │   ├── dag.py                   # 태스크 의존성 DAG
│   │   ├── parallel.py              # Worktree 기반 병렬 실행
│   │   └── merger.py                # Worktree 머지 관리
│   ├── safety/
│   │   ├── budget.py                # 비용/토큰 추적 & 제한
│   │   ├── rollback.py              # 자동 롤백
│   │   ├── timeout.py               # 타임아웃 + 절대시간 가드
│   │   └── shutdown.py              # Graceful shutdown 프로토콜
│   ├── monitor/
│   │   ├── dashboard.py             # TUI 대시보드 (Textual)
│   │   ├── logger.py                # 구조화 로거 (API 키 마스킹)
│   │   └── tracker.py               # 진행률 트래커
│   └── flywheel/
│       ├── analyzer.py              # 실행 패턴 분석
│       └── tuner.py                 # 프롬프트/스펙 자동 개선
│
├── agents/                          # Claude Code 서브에이전트 정의
│   ├── worker.md                    # 코딩 워커 에이전트
│   ├── reviewer.md                  # 코드 리뷰 에이전트
│   └── merger.md                    # 머지 충돌 해결 에이전트
│
├── hooks/                           # Claude Code 훅 스크립트
│   ├── pre_commit_validate.sh       # 커밋 전 테스트/린트
│   └── post_edit_check.sh           # 파일 편집 후 drift 체크
│
├── templates/                       # 프로젝트 초기화 템플릿
│   ├── PROMPT.md.tmpl
│   ├── AGENTS.md.tmpl
│   ├── task_plan.md.tmpl
│   ├── config.yaml.tmpl
│   └── .gitignore.tmpl
│
├── tests/
│   ├── test_loop.py
│   ├── test_planner.py
│   ├── test_oscillation.py
│   ├── test_completion_verifier.py
│   ├── test_drift_detector.py
│   └── ...
│
├── docs/
│   └── prd/
│       ├── mobiusforge-harness.md   # 이 문서
│       └── digging-report.md        # 분석 리포트
│
├── pyproject.toml
└── README.md
```

### 5.6 Configuration (config.yaml)

```yaml
# MobiusForge Configuration
project:
  name: "my-project"
  path: "./workspace"

agent:
  type: "claude-code"                    # claude-code | custom
  model: "claude-sonnet-4-6"             # 모델 선택
  timeout_per_loop: 600                  # 루프당 타임아웃 (초)
  permission_mode: "dontAsk"             # dontAsk | acceptEdits
  allowed_tools:                         # 에이전트 허용 도구
    - Read
    - Write
    - Edit
    - Bash
    - Glob
    - Grep

loop:
  max_iterations: 100                    # 최대 루프 횟수
  max_parallel_agents: 2                 # 동시 에이전트 수 (worktree)
  cooldown_seconds: 5                    # 루프 간 쿨다운
  max_total_time: 43200                  # 총 실행 시간 제한 (초, 12시간)
  end_time: ""                           # 절대 종료 시간 (ISO 8601, 예: "2026-03-29T21:00:00+09:00")
  wind_down_minutes: 30                  # 종료 N분 전 새 태스크 시작 금지

budget:
  max_total_cost: 50.0                   # 총 예산 ($)
  warn_at_percent: 80                    # 경고 임계값 (%)
  cost_per_1k_input: 0.003               # 입력 토큰 단가
  cost_per_1k_output: 0.015              # 출력 토큰 단가

validation:
  test_command: "pytest"                 # 테스트 명령어
  lint_command: "ruff check ."           # 린트 명령어
  auto_commit: true                      # 검증 통과 시 자동 커밋
  auto_rollback: true                    # 검증 실패 시 자동 롤백
  completion_verify: true                # 태스크 완료 재검증 활성화

safety:
  oscillation_threshold: 3              # 진동 감지 횟수
  oscillation_window: 5                 # 최근 N 루프 감시 윈도우
  max_strategy_retries: 3               # 전략 변경 최대 횟수
  dead_end_action: "skip"               # skip | pause | abort
  drift_check_interval: 5              # N 루프마다 drift 체크
  drift_threshold: 0.7                  # drift 점수 임계값 (0~1)

memory:
  max_lessons: 30                       # lessons.md 최대 항목 수
  prune_strategy: "relevance_decay"     # relevance_decay | fifo
  use_claude_memory: true               # Claude Code memory: project 연계

monitoring:
  dashboard: true                       # TUI 대시보드 활성화
  log_level: "INFO"                     # 로그 레벨
  save_raw_output: true                 # 에이전트 원시 출력 저장
  mask_secrets: true                    # 로그에서 API 키 패턴 마스킹
```

### 5.7 Agent Definition (agents/worker.md)

```markdown
---
name: mobius-worker
description: MobiusForge 코딩 워커. 태스크를 받아 구현하고 테스트하는 자율 에이전트.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
permissionMode: dontAsk
isolation: worktree
memory: project
---

당신은 MobiusForge의 자율 코딩 에이전트입니다.

## 작업 규칙
1. task_plan.md에서 할당된 태스크만 수행
2. specs/에서 해당 태스크의 명세를 읽고 정확히 구현
3. 구현 후 반드시 테스트 작성 및 실행
4. 하나의 태스크에만 집중. 다른 파일은 건드리지 않음
5. 완료 시 task_plan.md의 해당 태스크를 DONE으로 변경

## 금지 사항
- 테스트 없이 코드 커밋 금지
- specs에 없는 기능 추가 금지
- 기존 테스트를 삭제하거나 비활성화 금지
- node_modules, __pycache__ 등 생성 파일 커밋 금지

## 크로스루프 학습
- .mobiusforge/lessons.md의 교훈을 참고
- 이전에 실패한 접근법은 반복하지 않음
- 새로운 교훈 발견 시 lessons.md에 기록

## 에러 발생 시
- 테스트 실패: 에러 메시지를 분석하고 수정 시도 (최대 3회)
- 해결 불가: task_plan.md에 BLOCKED 기록하고 다음 태스크로
```

### 5.8 PROMPT.md 템플릿 명세

MobiusForge가 생성하는 PROMPT.md에 반드시 포함될 내용:

```markdown
# [Project Name]

## 프로젝트 개요
[1~2줄 프로젝트 설명]

## 기술 스택
- Language: [Python 3.12 / TypeScript 5.x / etc.]
- Framework: [FastAPI / Next.js / etc.]
- Database: [PostgreSQL / SQLite / etc.]
- Test: [pytest / jest / etc.]

## 코딩 컨벤션
- 네이밍: [snake_case / camelCase]
- 파일 구조: [기능별 / 레이어별]
- 최대 파일 크기: 300줄
- 함수 최대 크기: 50줄

## 의존성 레이어 규칙
Types → Config → Repository → Service → Runtime → UI
(역방향 의존 금지)

## 에러 핸들링
- 모든 외부 호출은 try/except로 감싸기
- 커스텀 예외 클래스 사용
- 에러 로깅 필수

## 커밋 메시지 형식
feat: [기능 설명]
fix: [버그 설명]
refactor: [리팩토링 설명]

## 절대 하지 말 것
- print() 디버깅 (logger 사용)
- 하드코딩된 시크릿/패스워드
- TODO 주석 남기고 넘어가기
- 테스트 없는 코드
```

### 5.9 Key State Files

#### task_plan.md (태스크 상태 관리 — 구 fix_plan.md)

```markdown
# Task Plan

## Current Sprint

### [DONE] T-001: 프로젝트 초기 구조 설정
- completed_at: 2026-03-29T09:30:00
- loops_taken: 2

### [IN_PROGRESS] T-002: 사용자 인증 API
- started_at: 2026-03-29T09:35:00
- approach: JWT + refresh token
- loops_taken: 3
- blockers: none

### [OPEN] T-003: 대시보드 UI
- depends_on: T-002
- priority: P1

### [BLOCKED] T-004: 결제 연동
- blocked_reason: "Oscillation detected - 3 strategies failed"
- failed_approaches:
  - "Stripe SDK direct integration → TypeError in webhook handler"
  - "Custom webhook handler → CORS issue"
  - "Adapter pattern → circular dependency"

### [INTERRUPTED] T-005: 알림 시스템
- interrupted_at: 2026-03-29T15:00:00
- reason: "mobiusforge abort by user"
- resume_hint: "푸시 알림 SDK 연동 중 중단. Firebase 초기화까지 완료"
```

#### lessons.md (크로스루프 학습)

```markdown
# Lessons Learned

## Loop 5 - 2026-03-29T10:15:00
- **FAIL**: pytest fixture scope 문제로 DB 연결 풀 고갈
- **LESSON**: 테스트에서 `scope="function"` 대신 `scope="session"` 사용
- **APPLIES_TO**: database, testing

## Loop 8 - 2026-03-29T11:00:00
- **SUCCESS**: API 엔드포인트 일괄 생성 시 spec 파일 분리가 효과적
- **LESSON**: 하나의 spec에 3개 이상의 엔드포인트를 넣지 말 것
- **APPLIES_TO**: api, specs
```

### 5.10 dry-run 모드 명세

`mobiusforge start --dry-run` 실행 시:
1. specs 파싱 및 유효성 검사
2. 태스크 DAG 생성 및 시각화
3. 프롬프트 조립 (실제 전송 안함)
4. 예상 루프 수, 토큰 소비, 비용 추정 출력
5. 병렬 실행 계획 (어떤 태스크가 동시 실행 가능한지)
6. 대회 전 리허설 용도

---

## 6. Implementation Phases

### Phase 1: MVP Core (대회 전 필수 완성) — D-13

- [ ] 프로젝트 구조 설정 (pyproject.toml, 패키지)
- [ ] FR-001: Mobius Loop Engine (Claude Code CLI 래퍼 + JSON 출력 파싱)
- [ ] FR-002: Plan Reader (task_plan.md 파서)
- [ ] FR-003: Spec Loader
- [ ] FR-004: Auto Validator (hooks 기반)
- [ ] FR-005: Auto Committer
- [ ] FR-009: Lessons Writer
- [ ] FR-010: Lesson Injector (태그 기반 필터링)
- [ ] FR-013: Completion Verifier
- [ ] FR-021: Token/Cost Tracker (JSON usage 파싱)
- [ ] FR-027: Rollback Guard
- [ ] FR-028: Max Loop Limiter
- [ ] FR-029: Timeout Guard
- [ ] FR-030: Absolute Time Guard
- [ ] FR-031: Graceful Shutdown

**Deliverable**: `mobiusforge start`로 단일 에이전트 자율 루프 + 완료 검증 + 안전 제어

### Phase 2: Safety & Intelligence (대회 전 완성 목표) — D-10

- [ ] FR-006: Oscillation Detector
- [ ] FR-007: Strategy Rotator (프롬프트 기반 대안 생성)
- [ ] FR-008: Dead-end Skipper
- [ ] FR-011: Guardrails File
- [ ] FR-012: Lesson Pruner
- [ ] FR-014: Goal Drift Detector
- [ ] FR-015: Drift Auto Corrector
- [ ] FR-022: Budget Guard
- [ ] FR-023: Activity Logger (API 키 마스킹)
- [ ] agents/worker.md 서브에이전트 정의
- [ ] hooks/ 스크립트 작성

**Deliverable**: 안정적 장시간 자율 실행 (oscillation 탈출 + drift 감지 + 완료 검증)

### Phase 3: Multi-Agent & Monitoring (대회 전 목표) — D-5

- [ ] FR-016: Dependency Graph Builder
- [ ] FR-017: Parallel Executor (worktree 기반)
- [ ] FR-018: Worktree Merger
- [ ] FR-019: Agent Pool Manager
- [ ] FR-020: TUI Dashboard
- [ ] agents/reviewer.md, agents/merger.md 정의
- [ ] dry-run 모드 구현

**Deliverable**: 병렬 에이전트 + 실시간 모니터링 + 리허설

### Phase 4: Flywheel + 대회 준비 (보너스) — D-2

- [ ] FR-024: Harness Self-Analyzer
- [ ] FR-025: Prompt Auto-Tuner
- [ ] FR-026: Spec Refiner
- [ ] 대회용 데모 프로젝트 템플릿 준비 (2~3개)
- [ ] 데모 프로젝트 specs 사전 작성
- [ ] 전체 시스템 리허설 (dry-run + 실행)

**Deliverable**: 자가 진화 하네스 + 대회 준비 완료

---

## 7. Differentiation: MobiusForge vs Existing Harnesses

### 7.1 기존 하네스 대비 차별점

| Feature | Ralph Loop | agent-harness | **MobiusForge** |
|---------|-----------|---------------|-----------------|
| 기본 루프 | While-true bash | 문서 기반 | **뫼비우스 루프 (학습 연결)** |
| 에이전트 런타임 | 단순 subprocess | 단순 subprocess | **Claude Code SDK/Subagent 시스템** |
| Oscillation 감지 | 없음 | 없음 | **자동 감지 + 3단계 전략 전환** |
| 크로스루프 학습 | 없음 (컨텍스트 리셋) | 수동 | **태그 기반 자동 교훈 주입 + 정리** |
| 완료 검증 | 없음 | 없음 | **Acceptance Criteria 자동 재검증** |
| 멀티 에이전트 | 없음 | 없음 | **Worktree 격리 + DAG 병렬 실행** |
| 비용 제어 | 수동 모니터링 | 없음 | **JSON 파싱 실시간 추적 + 예산 가드** |
| Drift 감지 | 수동 | 없음 | **LLM 기반 의미적 Drift 분석** |
| 시간 제어 | 없음 | 없음 | **절대시간 가드 + Wind-down 모드** |
| 자가 진화 | 없음 | 없음 | **Agentic Flywheel** |

### 7.2 핵심 혁신: "뫼비우스 메모리"

기존 Ralph Loop의 가장 큰 약점은 **컨텍스트 리셋 시 모든 것을 잃는 것**이다.

MobiusForge의 뫼비우스 메모리는:
1. **매 루프 종료 시** 교훈/패턴을 파일에 기록 (태그 분류)
2. **매 루프 시작 시** 현재 태스크 관련 교훈만 선택적 주입
3. **30항목 초과 시** 자동 정리 (relevance + time decay)
4. 컨텍스트는 리셋되지만 **지식은 연결된다** — 뫼비우스 띠처럼

```
Loop N ──교훈 기록──▶ lessons.md ──관련 교훈 필터──▶ Loop N+1
         (끝)          (태그 기반)                    (시작)
              ↑            │                            │
              │       [30항목 초과 시                    │
              │        자동 정리]                        │
              └────── 뫼비우스 연결 ─────────────────────┘
```

### 7.3 "Humans On the Loop" 구현

Martin Fowler의 프레임워크에 따라:
- **에이전트**: 코드 작성, 테스트, 커밋 (실행자)
- **하네스**: 품질 검증, 안전 제어, 비용 관리, drift/oscillation 감지 (가드레일)
- **인간**: 스펙 작성, 모니터링, 전략적 개입만 (감독자)

---

## 8. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| 자율 실행 비율 | > 95% | (자동 커밋 수) / (전체 루프 수) |
| Oscillation 탈출률 | > 90% | (자동 탈출 수) / (감지 수) |
| 태스크 완료율 | > 80% | (완료 태스크) / (전체 태스크) |
| Completion Verifier 정확도 | > 85% | (정확한 판정) / (전체 판정) |
| 12시간 안정성 | 0 크래시 | 크래시 없이 완주 |
| 평균 루프 시간 | < 5분 | 루프 시작~종료 평균 |
| 비용 효율 | < $50/12h | 총 API 비용 |
| 수동 개입 횟수 | 0회 | 가재옷 착용 횟수 |
| Drift 발생 시 복구 | > 80% | (자동 복구) / (drift 감지) |

---

## 9. Risk & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| API rate limit | High | Medium | 지수 백오프 + 쿨다운 조절 |
| 에이전트 환각 (잘못된 코드) | High | High | Completion Verifier + 테스트 게이트 + 자동 롤백 |
| 12시간 중 메모리 누수 | High | Low | 프로세스 격리 + 루프별 새 프로세스 |
| lessons.md 비대화 | Medium | Medium | Lesson Pruner (30항목 제한 + relevance decay) |
| 병렬 에이전트 머지 충돌 | Medium | High | Worktree 격리 + 파일 단위 태스크 분리 + 순차 머지 |
| 대회 당일 네트워크 불안정 | High | Low | 재시도 로직 + 쿨다운 |
| 에이전트 목표 이탈 (Drift) | Medium | High | Drift Detector (5루프 간격) + Auto Corrector |
| 에이전트 조기 종료 (Premature Exit) | High | High | Completion Verifier + acceptance criteria 재검증 |
| 대회 시간 초과 | High | Medium | Absolute Time Guard + Wind-down 모드 (30분 전 정리) |
| API 키 유출 | Critical | Low | 환경변수 전용 + 로그 마스킹 + .gitignore |
| 중단 시 코드 손실 | High | Medium | Graceful Shutdown (stash + INTERRUPTED 상태) |

---

## 10. CLI Interface

```bash
# 초기화
mobiusforge init                    # 프로젝트 초기화 (templates 복사)
mobiusforge init --from-prd prd.md  # PRD에서 specs 자동 생성

# 실행
mobiusforge start                   # 자율 실행 시작
mobiusforge start --parallel 2      # 2개 에이전트 병렬 (worktree)
mobiusforge start --budget 30       # 예산 $30 제한
mobiusforge start --end-time "2026-03-29T21:00:00+09:00"  # 절대 종료 시간
mobiusforge start --dry-run         # 실제 API 없이 루프 시뮬레이션 (specs 파싱, DAG, 비용 추정)

# 모니터링
mobiusforge dashboard               # TUI 대시보드
mobiusforge status                  # 현재 상태 요약
mobiusforge logs                    # 최근 로그 출력
mobiusforge cost                    # 비용 리포트

# 제어
mobiusforge pause                   # 현재 루프 완료 후 일시정지
mobiusforge resume                  # 재개 (INTERRUPTED 태스크부터)
mobiusforge skip [task-id]          # 특정 태스크 스킵
mobiusforge abort                   # Graceful shutdown (stash + INTERRUPTED)

# 분석
mobiusforge report                  # 실행 리포트 생성
mobiusforge lessons                 # 학습된 교훈 출력
mobiusforge dag                     # 태스크 의존성 DAG 시각화
```

---

## 11. 대회 준비 체크리스트

### D-13 ~ D-10: 하네스 MVP 개발
- [ ] Phase 1 완성
- [ ] 기본 루프 동작 확인

### D-10 ~ D-5: 안정성 확보
- [ ] Phase 2 완성
- [ ] 8시간 연속 실행 테스트

### D-5 ~ D-2: 병렬 + 모니터링
- [ ] Phase 3 완성
- [ ] dry-run으로 전체 흐름 검증

### D-2 ~ D-day: 최종 준비
- [ ] 데모 프로젝트 템플릿 2~3개 준비
- [ ] 각 프로젝트 specs/ 사전 작성
- [ ] 테스트 프레임워크 사전 설정
- [ ] 전체 리허설 (dry-run + 2시간 실행)
- [ ] config.yaml 최종 튜닝

### 데모 프로젝트 선정 기준
- 명확하고 테스트 가능한 요구사항
- 독립적 모듈 구조 (병렬 에이전트 친화)
- 외부 API 의존성 최소화
- 12시간 내 완성 가능한 규모

---

> **Next Steps**
> 1. `/implement`로 Phase 1 MVP 구현 시작
> 2. 대회 전 단계별 리허설 계획 수립
