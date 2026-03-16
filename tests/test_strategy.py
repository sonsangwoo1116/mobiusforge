"""Tests for strategy rotator (FR-007, FR-008)."""

from pathlib import Path
from textwrap import dedent

from mobiusforge.intelligence.strategy_rotator import StrategyRotation
from mobiusforge.memory.state import TaskPlan


def test_record_and_track():
    rot = StrategyRotation(max_retries=3)

    rot.record_failure("T-001", "Approach A failed")
    assert rot.attempts_remaining("T-001") == 2
    assert not rot.is_dead_end("T-001")


def test_dead_end():
    rot = StrategyRotation(max_retries=2)

    rot.record_failure("T-001", "Approach A")
    rot.record_failure("T-001", "Approach B")

    assert rot.is_dead_end("T-001")
    assert rot.attempts_remaining("T-001") == 0


def test_rotation_hints():
    rot = StrategyRotation(max_retries=3)

    # First attempt: no hint
    hint = rot.get_rotation_hint("T-001")
    assert hint == ""

    # After first failure
    rot.record_failure("T-001", "Direct approach failed")
    hint = rot.get_rotation_hint("T-001")
    assert "completely different" in hint.lower()

    # After second failure
    rot.record_failure("T-001", "Alternative approach failed")
    hint = rot.get_rotation_hint("T-001")
    assert "decompos" in hint.lower()


def test_handle_dead_end_skip(tmp_path):
    plan_path = tmp_path / "task_plan.md"
    plan_path.write_text(dedent("""\
        # Task Plan

        ## Current Sprint

        ### [IN_PROGRESS] T-001: Feature
        - priority: P0
    """), encoding="utf-8")
    plan = TaskPlan(plan_path)

    rot = StrategyRotation(max_retries=1, dead_end_action="skip")
    rot.record_failure("T-001", "Failed")

    action = rot.handle_dead_end(plan.tasks[0], plan)
    assert action == "skip"

    # Reload and verify task is blocked
    plan2 = TaskPlan(plan_path)
    assert plan2.tasks[0].status.value == "BLOCKED"


def test_get_failed_approaches():
    rot = StrategyRotation(max_retries=3)
    rot.record_failure("T-001", "A")
    rot.record_failure("T-001", "B")
    rot.record_failure("T-002", "C")

    assert rot.get_failed_approaches("T-001") == ["A", "B"]
    assert rot.get_failed_approaches("T-002") == ["C"]
    assert rot.get_failed_approaches("T-999") == []
