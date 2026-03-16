"""Tests for task DAG (FR-016)."""

from pathlib import Path
from textwrap import dedent

from mobiusforge.memory.state import TaskPlan
from mobiusforge.orchestration.dag import TaskDAG


def _make_plan(tmp_path: Path, content: str) -> TaskPlan:
    path = tmp_path / "task_plan.md"
    path.write_text(dedent(content), encoding="utf-8")
    return TaskPlan(path)


def test_ready_tasks_simple(tmp_path):
    plan = _make_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [OPEN] T-001: Setup
        - priority: P0

        ### [OPEN] T-002: Feature
        - priority: P1
        - depends_on: T-001
    """)
    dag = TaskDAG(plan)
    ready = dag.get_ready_tasks()

    assert len(ready) == 1
    assert ready[0].id == "T-001"


def test_ready_after_dependency_done(tmp_path):
    plan = _make_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [DONE] T-001: Setup
        - priority: P0

        ### [OPEN] T-002: Feature A
        - priority: P0
        - depends_on: T-001

        ### [OPEN] T-003: Feature B
        - priority: P1
        - depends_on: T-001
    """)
    dag = TaskDAG(plan)
    ready = dag.get_ready_tasks()

    assert len(ready) == 2
    assert {t.id for t in ready} == {"T-002", "T-003"}


def test_parallel_groups(tmp_path):
    plan = _make_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [OPEN] T-001: Setup
        - priority: P0

        ### [OPEN] T-002: Feature A
        - priority: P0
        - depends_on: T-001

        ### [OPEN] T-003: Feature B
        - priority: P1
        - depends_on: T-001

        ### [OPEN] T-004: Integration
        - priority: P0
        - depends_on: T-002, T-003
    """)
    dag = TaskDAG(plan)
    groups = dag.get_parallel_groups()

    # Layer 1: T-001 (alone)
    # Layer 2: T-002, T-003 (parallel)
    # Layer 3: T-004 (depends on both)
    assert len(groups) == 3
    assert len(groups[0]) == 1
    assert len(groups[1]) == 2
    assert len(groups[2]) == 1


def test_visualize(tmp_path):
    plan = _make_plan(tmp_path, """\
        # Task Plan

        ## Current Sprint

        ### [DONE] T-001: Setup
        - priority: P0

        ### [OPEN] T-002: Feature A
        - priority: P0
        - depends_on: T-001

        ### [BLOCKED] T-003: Feature B
        - priority: P1
        - blocked_reason: "Oscillation"
    """)
    dag = TaskDAG(plan)
    viz = dag.visualize()

    assert "T-001" in viz
    assert "T-002" in viz
    assert "BLOCKED" in viz
