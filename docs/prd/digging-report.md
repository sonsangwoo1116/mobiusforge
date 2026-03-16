# MobiusForge PRD Analysis Report

## 분석 대상
- **문서**: `docs/prd/mobiusforge-harness.md`
- **버전**: 1.0
- **분석일**: 2026-03-16

---

## 요약

| 카테고리 | 발견 | Critical | Major | Minor |
|----------|------|----------|-------|-------|
| 완전성 | 6 | 3 | 2 | 1 |
| 실현가능성 | 5 | 1 | 3 | 1 |
| 보안 | 2 | 1 | 1 | 0 |
| 일관성 | 3 | 0 | 2 | 1 |
| **총계** | **16** | **5** | **8** | **3** |

---

## 상세 분석

### 🔴 Critical (즉시 수정 필요)

#### C-1. Claude Code 호출 방식이 구식 — SDK/Subagent 미활용

- **위치**: Section 5.3 Technology Stack, FR-001
- **문제**: `claude -p` subprocess 호출만 정의. 그러나 2026년 현재 Claude Code는 **Agent SDK (Python)**, **Subagent System**, **`--agents` CLI 플래그**를 공식 지원한다. 특히:
  - **Claude Agent SDK**: Python에서 양방향 대화, 커스텀 도구, 훅 시스템, 권한 제어, async 지원
  - **Subagent System**: `--agents` JSON으로 세션 단위 에이전트 정의, 도구 제한, 모델 선택, MCP 서버 스코핑
  - **Persistent Memory**: 서브에이전트에 `memory: project` 설정 시 크로스세션 학습 내장
  - **Hooks**: `PreToolUse`, `PostToolUse`, `SubagentStart/Stop` 훅으로 검증 자동화
  - **Git Worktree 격리**: `isolation: worktree`로 병렬 에이전트 충돌 방지 내장
- **영향**: subprocess로 직접 호출하면 토큰 추적, 에러 핸들링, 프로세스 관리를 **모두 직접 구현**해야 함. SDK를 쓰면 이 중 상당수가 이미 해결됨
- **개선안**:
  ```
  [기존] Python subprocess → claude -p "prompt"
  [개선] Claude Agent SDK 또는 --agents 플래그 기반 아키텍처로 전환

  핵심 변경:
  1. Agent SDK로 에이전트 실행 (토큰 추적 내장)
  2. Subagent 시스템으로 멀티에이전트 구현 (병렬 실행 내장)
  3. Hooks로 PreToolUse 검증 (린트/테스트 자동화)
  4. isolation: worktree로 병렬 작업 충돌 방지
  5. memory: project로 크로스루프 학습 (lessons.md 대체 가능)
  ```

#### C-2. Drift 감지 — FR 누락

- **위치**: Section 7.1 차별점 테이블
- **문제**: 차별점 테이블에 "Drift 감지: 자동 (목표 대비 진행 비교)"로 명시되어 있으나, **해당 기능의 FR이 존재하지 않음**. 어떤 FR에도 drift 감지 로직이 정의되지 않았다.
- **영향**: 대회 시연 시 "차별점"으로 내세울 수 없음. 에이전트가 목표를 벗어나도 방치됨
- **개선안**:
  ```markdown
  ### 3.8 Drift Detection

  | ID | Requirement | Priority | Dependencies |
  |----|------------|----------|--------------|
  | FR-027 | **Goal Drift Detector**: N 루프마다 현재 작업이 원래 specs/fix_plan 목표와 정렬되는지 검증. 코드 변경 diff와 태스크 명세를 비교하여 drift 점수 산출 | P1 (Should) | FR-002, FR-003 |
  | FR-028 | **Auto Corrector**: drift 점수가 임계값 초과 시 에이전트를 중단하고 원래 태스크로 리다이렉트 | P1 (Should) | FR-027 |
  ```

#### C-3. Premature Exit 해결책 누락

- **위치**: Section 1.1 Problem Statement, Section 3
- **문제**: 문제점 6가지 중 "Premature Exit"이 명시되어 있으나, 이를 해결하는 FR이 없음. Auto Validator(FR-004)는 테스트/린트만 검사하고, **"에이전트가 태스크를 실제로 완료했는지"는 검증하지 않음**
- **영향**: LangChain의 사례에서 이미 검증됨 — 에이전트는 "완료"라고 말하지만 실제로 미완인 경우가 빈번
- **개선안**:
  ```markdown
  | FR-029 | **Completion Verifier**: 에이전트가 "완료"를 선언할 때 PreCompletionChecklist를 실행. specs의 acceptance criteria와 실제 구현을 비교하여 완료 여부 재검증 | P0 (Must) | FR-003, FR-004 |
  ```
  > 참고: LangChain은 이 하나의 기능 추가로 벤치마크 성능이 52.8% → 66.5%로 향상됨

#### C-4. 토큰/비용 추적 방법 미정의

- **위치**: FR-017, Section 4.3
- **문제**: "토큰 사용량 및 누적 비용 추적"이 P0인데, **Claude Code CLI subprocess 출력에서 토큰 수를 어떻게 파싱하는지 방법이 없음**. `claude -p`의 stdout은 텍스트 응답이지 토큰 메타데이터가 아님
- **영향**: 비용 추적 불가 → Budget Guard(FR-018) 무용지물
- **개선안**:
  ```
  방법 1: Claude Agent SDK 사용 → SDK가 토큰 사용량 반환
  방법 2: --output-format json 플래그 사용 → JSON 응답에서 usage 파싱
  방법 3: tiktoken 등으로 프롬프트 토큰 수 추정 (부정확)

  → 방법 1 (SDK) 권장. C-1 개선과 연계
  ```

#### C-5. API Key/시크릿 보안

- **위치**: 전체 (누락)
- **문제**: config.yaml에 API 키 관리 방법이 없음. 대회에서 API 키가 git에 커밋되거나 로그에 노출될 위험
- **영향**: API 키 노출 시 크레딧 도용 가능
- **개선안**:
  ```markdown
  - API 키는 환경변수(ANTHROPIC_API_KEY)로만 전달
  - config.yaml에 시크릿 절대 포함 금지
  - .gitignore에 .env, .mobiusforge/logs/ 포함
  - 로그에서 API 키 패턴 자동 마스킹
  ```

---

### 🟡 Major (구현 전 수정 권장)

#### M-1. Strategy Rotator 메커니즘 미정의

- **위치**: FR-007
- **문제**: "대안 접근법으로 전환"이라고만 되어있지, **어떻게 대안을 생성하는지** 정의 안됨. 코드 레벨에서 "다른 접근법"을 어떻게 만들어내나?
- **개선안**:
  ```
  전략 전환 메커니즘:
  1. 실패한 접근법을 lessons.md에 기록
  2. 에이전트에게 "이전 접근법 X가 실패함. 완전히 다른 방법으로 시도하라"는 프롬프트 주입
  3. 프롬프트에 구체적 대안 힌트 포함 (예: "라이브러리 대신 직접 구현", "다른 패키지 사용" 등)
  4. 3회 모두 실패 시 → 태스크를 더 작은 서브태스크로 분해 시도
  ```

#### M-2. 병렬 에이전트 충돌 해결 전략이 비현실적

- **위치**: FR-014, Risk Section
- **문제**: "자동 리베이스"로 머지 충돌 해결이라고 되어있으나, **코드 수준 충돌의 자동 해결은 매우 어려움**. 두 에이전트가 같은 파일을 수정하면 자동 해결 불가
- **개선안**:
  ```
  [기존] 자동 리베이스로 충돌 해결
  [개선] 충돌 방지 우선 전략:
  1. isolation: worktree로 에이전트별 독립 워크트리 (Claude Code 내장 기능)
  2. 태스크 할당 시 파일 단위 잠금 (같은 파일 수정 금지)
  3. 충돌 발생 시 → 두 번째 에이전트의 변경을 별도 브랜치에 보관
  4. 오케스트레이터가 순차적으로 머지 시도
  5. 자동 해결 불가 시 → 에이전트에게 머지 해결 태스크 위임
  ```

#### M-3. lessons.md 무한 증가 + 관련도 필터링 미정의

- **위치**: FR-009, FR-010, Risk Section
- **문제**: "최대 50항목 유지 + 관련도 필터링"이 Risk에 언급되었으나 FR에는 없음. 100루프 실행 시 lessons.md가 거대해지면 프롬프트 토큰 낭비
- **개선안**:
  ```markdown
  | FR-030 | **Lesson Pruner**: lessons.md가 30항목 초과 시 오래되고 관련도 낮은 항목 자동 제거. 태그 기반 관련도 매칭 (APPLIES_TO 필드) | P1 (Should) | FR-009 |

  또는 Claude Code Subagent의 memory: project 기능 활용 시
  → 내장 MEMORY.md 200줄 제한 + 자동 큐레이션이 이미 구현되어 있음
  ```

#### M-4. 대회 당일 "무엇을 만들 것인가" 전략 부재

- **위치**: 전체 (누락)
- **문제**: 하네스 자체는 완벽하지만, **대회에서 어떤 프로젝트를 자율 에이전트로 만들 것인지** 전략이 없음. 하네스의 성능은 타깃 프로젝트의 복잡도에 크게 의존
- **개선안**:
  ```
  사전 준비 필요:
  1. 데모용 프로젝트 템플릿 2~3개 준비 (웹앱, API, CLI 도구 등)
  2. 각 프로젝트의 specs/ 사전 작성
  3. 테스트 프레임워크 사전 설정
  4. "자율 실행 친화적" 프로젝트 선정 기준 정의:
     - 명확한 테스트 가능 요구사항
     - 독립적 모듈 구조
     - 외부 의존성 최소화
  ```

#### M-5. PROMPT.md / AGENTS.md 내용 미정의

- **위치**: Section 5.6, templates/
- **문제**: 템플릿 파일이 언급되었으나 **실제 내용이 전혀 정의되지 않음**. OpenAI의 핵심 교훈: "AGENTS.md가 모호하면 에이전트 출력도 모호하다"
- **개선안**:
  ```markdown
  PROMPT.md 필수 포함 내용:
  - 프로젝트 개요 (1줄)
  - 기술 스택 명시
  - 코딩 컨벤션 (네이밍, 파일 구조)
  - 금지 사항 (하면 안 되는 것 목록)
  - 커밋 메시지 형식
  - 테스트 작성 규칙

  AGENTS.md 필수 포함 내용:
  - 의존성 레이어 규칙 (Types → Config → Service → UI)
  - 파일 크기 제한
  - 에러 핸들링 패턴
  - 로깅 규칙
  ```

#### M-6. Graceful Shutdown / 상태 복구 미정의

- **위치**: FR-001, CLI (mobiusforge abort)
- **문제**: `mobiusforge abort` "즉시 중단 (안전하게)"라고만 되어있고, **에이전트가 코드 수정 중간에 죽으면 어떻게 되는지** 정의 없음
- **개선안**:
  ```
  Graceful Shutdown 프로토콜:
  1. abort 신호 수신 → 현재 에이전트 프로세스에 SIGTERM
  2. 30초 대기 (에이전트 자연 종료 기회)
  3. 미종료 시 SIGKILL
  4. git status 확인 → uncommitted 변경 있으면 자동 stash
  5. fix_plan.md의 IN_PROGRESS 태스크를 INTERRUPTED로 변경
  6. 재개 시 INTERRUPTED 태스크부터 다시 시작
  ```

#### M-7. 대회 시간 제약 반영 부족

- **위치**: Section 4.1, config.yaml
- **문제**: 대회는 09:00~21:00 (12시간)인데, config에 **전체 타임아웃**이 없음. max_iterations만 있고 시간 제한이 없음
- **개선안**:
  ```yaml
  loop:
    max_iterations: 100
    max_total_time: 43200    # 12시간 = 43200초
    end_time: "2026-03-29T21:00:00+09:00"  # 절대 종료 시간
    wind_down_minutes: 30    # 종료 30분 전 새 태스크 시작 금지, 정리 모드
  ```

#### M-8. fix_plan.md 동시 쓰기 충돌

- **위치**: FR-013 (Parallel Executor), FR-002 (Plan Reader)
- **문제**: 멀티 에이전트가 동시에 fix_plan.md를 읽고 쓰면 **race condition** 발생. 파일 기반 상태의 근본적 한계
- **개선안**:
  ```
  방법 1: 파일 잠금 (fcntl.flock)으로 동시 쓰기 방지
  방법 2: 에이전트별 개별 상태 파일 → 오케스트레이터가 통합
  방법 3: SQLite (파일 기반 DB)로 상태 관리 전환
  → 방법 2 권장 (단순, 충돌 없음)
  ```

---

### 🟢 Minor (개선 제안)

#### m-1. Docker가 해커톤에서 오버엔지니어링일 수 있음

- **위치**: FR-023
- **문제**: Docker 격리는 좋지만, 대회 현장에서 Docker 설정 문제로 시간 낭비 가능. **대회장 네트워크에서 Docker pull 실패** 등
- **개선안**: Docker를 P2로 하향. 대신 `isolation: worktree` (Claude Code 내장)로 충분한 격리 확보. Docker는 사전 이미지 빌드한 경우에만 사용

#### m-2. 용어 불일치

- **위치**: 전체
- **문제**:
  - `fix_plan.md` vs `태스크 상태 관리` — fix_plan이란 이름이 "수정 계획"에 가까운데 실제로는 전체 태스크 트래커
  - `lessons.md` vs `lessons_learned.md` — US-002에서는 `lessons_learned.md`, FR-009에서는 `lessons.md`
- **개선안**: `task_plan.md`로 개명 (더 직관적), `lessons.md`로 통일

#### m-3. dry-run 모드 검증 시나리오 없음

- **위치**: CLI Section — `mobiusforge start --dry-run`
- **문제**: dry-run이 뭘 시뮬레이션하는지 정의 없음
- **개선안**:
  ```
  dry-run 모드:
  - 실제 에이전트 호출 없이 루프 흐름만 시뮬레이션
  - specs 파싱, DAG 생성, 프롬프트 조립까지 실행
  - 예상 루프 수, 토큰 소비, 비용을 추정하여 출력
  - 대회 전 리허설에 필수
  ```

---

## 누락된 요구사항

| ID | 요구사항 | 권장 우선순위 |
|----|---------|--------------|
| NEW-1 | **Completion Verifier** — 태스크 완료 여부 재검증 | P0 |
| NEW-2 | **Goal Drift Detector** — 목표 이탈 감지 | P1 |
| NEW-3 | **Lesson Pruner** — lessons.md 크기/관련도 관리 | P1 |
| NEW-4 | **Absolute Time Guard** — 대회 종료 시간 기반 제어 | P1 |
| NEW-5 | **PROMPT.md / AGENTS.md 명세** — 에이전트 품질의 핵심 | P1 |
| NEW-6 | **Graceful Shutdown Protocol** — 안전한 중단/복구 | P1 |
| NEW-7 | **대회용 데모 프로젝트 템플릿** — 하네스가 돌릴 타깃 | P1 |

---

## 아키텍처 재설계 권장사항

### Claude Code Subagent 시스템 활용 시 아키텍처 변화

현재 PRD의 많은 기능이 **Claude Code에 이미 내장**되어 있음:

| MobiusForge 자체 구현 (현재) | Claude Code 내장 기능 (활용 가능) |
|---|---|
| FR-009/010: lessons.md 읽기/쓰기 | `memory: project` → 자동 크로스세션 학습 |
| FR-013: Parallel Executor | Subagent `background: true` + `isolation: worktree` |
| FR-014: Merge Resolver | `isolation: worktree` → git worktree 자동 관리 |
| FR-004: Auto Validator (린트/테스트) | `hooks.PreToolUse` + `hooks.PostToolUse` |
| FR-023: Docker Sandbox | `permissionMode: dontAsk` + 도구 제한 |
| FR-017: Token Tracker | Agent SDK → 토큰 사용량 반환 |

**권장**: 바퀴를 재발명하지 말고, Claude Code의 인프라 위에 MobiusForge만의 차별화 기능(Oscillation Detection, Strategy Rotation, Drift Detection, Agentic Flywheel)에 집중

### 제안 아키텍처 (하이브리드)

```
┌─────────────────────────────────────────────────────────┐
│                    MobiusForge CLI                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐                                       │
│  │ Orchestrator │ ← MobiusForge 핵심 (직접 구현)        │
│  │ - Loop 관리   │                                       │
│  │ - 태스크 선택  │                                       │
│  │ - 프롬프트 조립│                                       │
│  └──────┬───────┘                                       │
│         │                                               │
│  ┌──────▼───────┐                                       │
│  │ Claude Code  │ ← Claude Code 내장 기능 활용           │
│  │ --agents     │                                       │
│  │ (Subagent    │   - memory: project (크로스루프 학습)  │
│  │  System)     │   - isolation: worktree (병렬 격리)    │
│  │              │   - hooks (검증 자동화)                 │
│  └──────┬───────┘   - background (병렬 실행)             │
│         │                                               │
│  ┌──────▼───────┐                                       │
│  │ MobiusForge  │ ← MobiusForge 차별화 (직접 구현)      │
│  │ Intelligence │                                       │
│  │ - Oscillation│                                       │
│  │ - Drift Det. │                                       │
│  │ - Strategy   │                                       │
│  │ - Flywheel   │                                       │
│  │ - Budget     │                                       │
│  │ - Dashboard  │                                       │
│  └──────────────┘                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 권장 조치 요약

### 즉시 조치 (Critical) — PRD 수정 필수
1. ❗ **C-1**: Claude Code SDK/Subagent 기반으로 아키텍처 재설계
2. ❗ **C-2**: Drift Detection FR 추가 (FR-027, FR-028)
3. ❗ **C-3**: Completion Verifier FR 추가 (FR-029)
4. ❗ **C-4**: 토큰 추적 방법 명시 (SDK 활용)
5. ❗ **C-5**: API 키 보안 정책 추가

### 구현 전 조치 (Major)
1. ⚠️ **M-1**: Strategy Rotator 메커니즘 구체화
2. ⚠️ **M-2**: 병렬 에이전트 충돌 전략 → worktree 기반으로 변경
3. ⚠️ **M-3**: Lesson Pruner FR 추가
4. ⚠️ **M-4**: 대회용 데모 프로젝트 준비 계획
5. ⚠️ **M-5**: PROMPT.md/AGENTS.md 내용 정의
6. ⚠️ **M-6**: Graceful Shutdown 프로토콜 정의
7. ⚠️ **M-7**: 절대 시간 기반 종료 가드 추가
8. ⚠️ **M-8**: 병렬 상태 파일 전략 (race condition 방지)

### 선택적 조치 (Minor)
1. 💡 **m-1**: Docker P2로 하향, worktree 우선
2. 💡 **m-2**: 파일명/용어 통일
3. 💡 **m-3**: dry-run 시뮬레이션 정의

---

> ✅ **Critical 이슈가 모두 해결되면 구현을 시작해도 좋습니다.**
> 특히 C-1(아키텍처 재설계)이 가장 임팩트가 큰 변경이며, 다른 Critical 이슈의 해결에도 연쇄적으로 도움이 됩니다.
>
> **다음 단계**: PRD 수정 → `/implement` Phase 1 MVP
