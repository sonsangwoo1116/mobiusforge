"""Tests for task_plan.md parser (FR-002)."""

from pathlib import Path
from textwrap import dedent

from mobiusforge.memory.state import TaskPlan, TaskStatus


def _write_plan(tmp_path: Path, content: str) -> Path:
    plan_path = tmp_path / "task_plan.md"
    plan_path.write_text(dedent(content), encoding="utf-8")
    return plan_path


def test_parse_basic(tmp_path):
    path = _write_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [OPEN] T-001: Setup project
        - priority: P0

        ### [DONE] T-002: Init database
        - priority: P0
        - completed_at: 2026-03-29T09:30:00
        - loops_taken: 2
    """)
    plan = TaskPlan(path)

    assert len(plan.tasks) == 2
    assert plan.tasks[0].id == "T-001"
    assert plan.tasks[0].status == TaskStatus.OPEN
    assert plan.tasks[1].status == TaskStatus.DONE
    assert plan.tasks[1].loops_taken == 2


def test_get_next_task_respects_dependencies(tmp_path):
    path = _write_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [OPEN] T-001: Setup
        - priority: P0

        ### [OPEN] T-002: Feature A
        - priority: P0
        - depends_on: T-001

        ### [OPEN] T-003: Feature B
        - priority: P1
    """)
    plan = TaskPlan(path)

    # T-001 should be selected (T-002 depends on it)
    next_task = plan.get_next_task()
    assert next_task is not None
    assert next_task.id == "T-001"


def test_get_next_task_interrupted_first(tmp_path):
    path = _write_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [DONE] T-001: Setup
        - priority: P0

        ### [INTERRUPTED] T-002: Feature A
        - priority: P1
        - resume_hint: "Was working on API endpoint"

        ### [OPEN] T-003: Feature B
        - priority: P0
    """)
    plan = TaskPlan(path)

    # Interrupted tasks should be resumed first
    next_task = plan.get_next_task()
    assert next_task is not None
    assert next_task.id == "T-002"


def test_mark_done(tmp_path):
    path = _write_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [OPEN] T-001: Setup
        - priority: P0
    """)
    plan = TaskPlan(path)
    plan.mark_in_progress("T-001")
    plan.mark_done("T-001", loops=3)

    # Reload from disk
    plan2 = TaskPlan(path)
    assert plan2.tasks[0].status == TaskStatus.DONE
    assert plan2.tasks[0].loops_taken == 3


def test_all_done(tmp_path):
    path = _write_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [DONE] T-001: Setup
        - priority: P0

        ### [BLOCKED] T-002: Feature
        - priority: P0
        - blocked_reason: "Oscillation"
    """)
    plan = TaskPlan(path)

    # All non-blocked tasks are done
    assert plan.all_done()


def test_blocked_with_failed_approaches(tmp_path):
    path = _write_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [BLOCKED] T-001: Payment
        - priority: P0
        - blocked_reason: "Oscillation detected"
        - failed_approaches:
          - "Direct SDK integration"
          - "Adapter pattern"
    """)
    plan = TaskPlan(path)

    assert plan.tasks[0].status == TaskStatus.BLOCKED
    assert len(plan.tasks[0].failed_approaches) == 2
    assert "Direct SDK integration" in plan.tasks[0].failed_approaches
