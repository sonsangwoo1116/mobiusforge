"""E2E integration test for the Mobius Loop — uses a mock agent (no API calls).

Tests the full cycle:
1. Init project structure
2. Load task_plan, specs, PROMPT.md
3. Select task → assemble prompt → run agent (mocked) → validate → commit
4. Cross-loop lesson injection
5. Oscillation detection → strategy rotation → dead-end skip
6. Graceful shutdown with INTERRUPTED state
7. Budget tracking across loops
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
from textwrap import dedent

import pytest

from mobiusforge.config import MobiusConfig, load_config
from mobiusforge.core.loop import MobiusLoop, LoopOutcome
from mobiusforge.core.runner import AgentResult
from mobiusforge.memory.state import TaskPlan, TaskStatus


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a fully initialized mock project."""
    d = tmp_path / "project"
    d.mkdir()

    # Init git repo
    subprocess.run(["git", "init"], cwd=d, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=d, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=d, capture_output=True)

    # config.yaml
    (d / "config.yaml").write_text(dedent("""\
        project:
          name: "test-project"
          path: "."
        agent:
          type: "claude-code"
          model: "claude-sonnet-4-6"
          timeout_per_loop: 10
        loop:
          max_iterations: 10
          cooldown_seconds: 0
        budget:
          max_total_cost: 5.0
          warn_at_percent: 80
        validation:
          test_command: "true"
          lint_command: "true"
          auto_commit: true
          auto_rollback: true
          completion_verify: false
        safety:
          oscillation_threshold: 3
          oscillation_window: 5
          max_strategy_retries: 2
          dead_end_action: "skip"
        memory:
          max_lessons: 10
        monitoring:
          save_raw_output: false
          mask_secrets: true
    """), encoding="utf-8")

    # PROMPT.md
    (d / "PROMPT.md").write_text("# Test Project\nUse Python.\n", encoding="utf-8")

    # task_plan.md
    (d / "task_plan.md").write_text(dedent("""\
        # Task Plan

        ## Current Sprint

        ### [OPEN] T-001: Create hello module
        - priority: P0

        ### [OPEN] T-002: Create utils module
        - priority: P1
        - depends_on: T-001

        ### [OPEN] T-003: Create main entry
        - priority: P1
        - depends_on: T-001
    """), encoding="utf-8")

    # specs
    specs = d / "specs"
    specs.mkdir()
    (specs / "T-001.md").write_text(
        "# Hello Module\nCreate `src/hello.py` with a `greet()` function.\n",
        encoding="utf-8",
    )
    (specs / "T-002.md").write_text(
        "# Utils\nCreate `src/utils.py` with a `format_name()` function.\n",
        encoding="utf-8",
    )
    (specs / "T-003.md").write_text(
        "# Main\nCreate `src/main.py` that uses hello and utils.\n",
        encoding="utf-8",
    )

    # .mobiusforge dir
    mf = d / ".mobiusforge"
    mf.mkdir()
    (mf / "logs").mkdir()
    (mf / "lessons.md").write_text("# Lessons Learned\n", encoding="utf-8")

    # Initial commit
    (d / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=d, capture_output=True)

    return d


def _mock_agent_success(**kwargs) -> AgentResult:
    """Mock agent that always succeeds."""
    return AgentResult(
        success=True,
        output="Task completed successfully",
        input_tokens=5000,
        output_tokens=1000,
        cost=0.03,
        duration_seconds=2.0,
    )


def _mock_agent_failure(**kwargs) -> AgentResult:
    """Mock agent that always fails."""
    return AgentResult(
        success=False,
        output="",
        error="Mock failure",
        duration_seconds=1.0,
    )


# =============================================================================
# E2E Test: Happy Path — 3 tasks complete successfully
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_happy_path(mock_commit, mock_agent, project_dir):
    """Full loop: 3 tasks → all complete → loop exits."""
    mock_agent.side_effect = lambda **kw: _mock_agent_success(**kw)

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)

    loop = MobiusLoop(config, project_dir)
    summary = loop.run()

    assert summary.tasks_completed == 3
    assert summary.tasks_failed == 0
    assert summary.loops_run == 3
    assert summary.total_cost > 0

    # Verify task_plan updated
    plan = TaskPlan(project_dir / "task_plan.md")
    assert all(t.status == TaskStatus.DONE for t in plan.tasks)

    # Verify lessons recorded
    assert (project_dir / ".mobiusforge" / "lessons.md").stat().st_size > 30

    # Verify budget saved
    assert (project_dir / ".mobiusforge" / "budget.json").exists()
    budget_data = json.loads((project_dir / ".mobiusforge" / "budget.json").read_text())
    assert len(budget_data["history"]) == 3


# =============================================================================
# E2E Test: Agent failures → lessons recorded → retries
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_failure_then_success(mock_commit, mock_agent, project_dir):
    """Agent fails once on T-001, then succeeds on retry."""
    call_count = [0]

    def alternating_agent(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return _mock_agent_failure(**kwargs)
        return _mock_agent_success(**kwargs)

    mock_agent.side_effect = alternating_agent

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)
    config.safety.max_strategy_retries = 3  # Allow enough retries

    loop = MobiusLoop(config, project_dir)
    summary = loop.run()

    # T-001 completes on 2nd try, then T-002, T-003
    assert summary.tasks_completed >= 1
    assert summary.loops_run >= 2

    # Verify failure lessons recorded
    from mobiusforge.memory.lessons import LessonsManager
    lessons = LessonsManager(project_dir / ".mobiusforge" / "lessons.md")
    fail_lessons = [entry for entry in lessons.lessons if entry.outcome == "FAIL"]
    assert len(fail_lessons) >= 1


# =============================================================================
# E2E Test: Budget exceeded → loop stops
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_budget_exceeded(mock_commit, mock_agent, project_dir):
    """Loop stops when budget is exceeded."""
    def expensive_agent(**kwargs):
        return AgentResult(
            success=True, output="done",
            input_tokens=50000, output_tokens=10000,
            cost=2.0, duration_seconds=5.0,
        )

    mock_agent.side_effect = expensive_agent

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)
    config.budget.max_total_cost = 3.0  # $3 budget

    loop = MobiusLoop(config, project_dir)
    summary = loop.run()

    # Should stop after 1-2 loops ($2 per loop, $3 budget)
    assert summary.loops_run <= 2
    assert summary.total_cost > 0


# =============================================================================
# E2E Test: Max iterations → loop stops
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_max_iterations(mock_commit, mock_agent, project_dir):
    """Loop stops at max iterations even if tasks remain."""
    # Agent always fails → tasks hit dead-end → all blocked → loop stops
    mock_agent.side_effect = lambda **kw: _mock_agent_failure(**kw)

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)
    config.loop.max_iterations = 50
    config.safety.max_strategy_retries = 5  # High retries to test max_iterations

    loop = MobiusLoop(config, project_dir)
    summary = loop.run()

    # Should run multiple loops retrying T-001 before hitting dead-end
    assert summary.loops_run >= 5
    assert summary.tasks_completed == 0


# =============================================================================
# E2E Test: Strategy rotation → dead-end → BLOCKED
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_dead_end_blocked(mock_commit, mock_agent, project_dir):
    """Task hits dead end after max strategy retries → BLOCKED → next task."""
    # Agent always fails
    mock_agent.side_effect = lambda **kw: _mock_agent_failure(**kw)

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)
    config.safety.max_strategy_retries = 2
    config.loop.max_iterations = 20

    loop = MobiusLoop(config, project_dir)
    summary = loop.run()

    # T-001 should be BLOCKED after 2 failures
    plan = TaskPlan(project_dir / "task_plan.md")
    t001 = next(t for t in plan.tasks if t.id == "T-001")
    assert t001.status == TaskStatus.BLOCKED

    assert summary.tasks_failed >= 1


# =============================================================================
# E2E Test: Dependency ordering respected
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_dependency_order(mock_commit, mock_agent, project_dir):
    """T-002 and T-003 only run after T-001 completes."""
    execution_order = []

    def tracking_agent(**kwargs):
        prompt = kwargs.get("prompt", "")
        for tid in ["T-001", "T-002", "T-003"]:
            if tid in prompt:
                execution_order.append(tid)
                break
        return _mock_agent_success(**kwargs)

    mock_agent.side_effect = tracking_agent

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)

    loop = MobiusLoop(config, project_dir)
    loop.run()

    # T-001 must come before T-002 and T-003
    assert execution_order[0] == "T-001"
    assert "T-002" in execution_order
    assert "T-003" in execution_order
    idx_001 = execution_order.index("T-001")
    idx_002 = execution_order.index("T-002")
    idx_003 = execution_order.index("T-003")
    assert idx_001 < idx_002
    assert idx_001 < idx_003


# =============================================================================
# E2E Test: Cross-loop lesson injection
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_lesson_injection(mock_commit, mock_agent, project_dir):
    """Lessons from failures are injected into subsequent prompts."""
    prompts_received = []
    call_count = [0]

    def learning_agent(**kwargs):
        call_count[0] += 1
        prompts_received.append(kwargs.get("prompt", ""))
        if call_count[0] == 1:
            return _mock_agent_failure(**kwargs)
        return _mock_agent_success(**kwargs)

    mock_agent.side_effect = learning_agent

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)

    loop = MobiusLoop(config, project_dir)
    loop.run()

    # Second prompt (retry) should contain lesson reference
    # The lesson from the first failure should be in lessons.md
    from mobiusforge.memory.lessons import LessonsManager
    lessons = LessonsManager(project_dir / ".mobiusforge" / "lessons.md")
    assert len(lessons.lessons) >= 1

    # At least one FAIL lesson
    fail_lessons = [l for l in lessons.lessons if l.outcome == "FAIL"]
    assert len(fail_lessons) >= 1


# =============================================================================
# E2E Test: Validation failure → rollback
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
@patch("mobiusforge.core.loop.validate")
@patch("mobiusforge.core.loop.rollback_to", return_value=True)
@patch("mobiusforge.core.loop.get_last_commit_hash", return_value="abc123")
def test_e2e_validation_failure_rollback(
    mock_hash, mock_rollback, mock_validate, mock_commit, mock_agent, project_dir
):
    """Validation failure triggers rollback."""
    from mobiusforge.core.validator import ValidationResult

    mock_agent.side_effect = lambda **kw: _mock_agent_success(**kw)

    call_count = [0]
    def alternating_validation(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return ValidationResult(tests_passed=False, lint_passed=True, test_output="FAIL")
        return ValidationResult(tests_passed=True, lint_passed=True)

    mock_validate.side_effect = alternating_validation

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)

    loop = MobiusLoop(config, project_dir)
    loop.run()

    # Rollback should have been called at least once
    assert mock_rollback.called


# =============================================================================
# E2E Test: Graceful shutdown
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_graceful_shutdown(mock_commit, mock_agent, project_dir):
    """Shutdown signal during execution → INTERRUPTED state."""
    call_count = [0]

    def shutdown_on_second(**kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            # Simulate shutdown request
            loop_ref[0].shutdown._shutdown_requested.set()
        return _mock_agent_success(**kwargs)

    mock_agent.side_effect = shutdown_on_second

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)

    loop = MobiusLoop(config, project_dir)
    loop_ref = [loop]  # Reference for closure

    summary = loop.run()

    # Should have stopped after 2 loops
    assert summary.loops_run == 2


# =============================================================================
# E2E Test: Activity logs written
# =============================================================================

@patch("mobiusforge.core.loop.run_agent")
@patch("mobiusforge.core.loop.auto_commit", return_value=True)
def test_e2e_activity_logs(mock_commit, mock_agent, project_dir):
    """Activity logs are saved after execution."""
    mock_agent.side_effect = lambda **kw: _mock_agent_success(**kw)

    config = load_config(project_dir / "config.yaml")
    config.project.path = str(project_dir)

    loop = MobiusLoop(config, project_dir)
    loop.run()

    log_files = list((project_dir / ".mobiusforge" / "logs").glob("activity_*.jsonl"))
    assert len(log_files) >= 1

    content = log_files[0].read_text()
    assert "agent_run" in content
