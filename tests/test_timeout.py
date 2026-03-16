"""Tests for loop guard (FR-028, FR-029, FR-030)."""

from mobiusforge.safety.timeout import LoopGuard


def test_max_iterations():
    guard = LoopGuard(max_iterations=3)
    guard.start()

    for _ in range(3):
        guard.increment_loop()

    can_go, reason = guard.can_continue()
    assert not can_go
    assert "Max iterations" in reason


def test_can_continue_initially():
    guard = LoopGuard(max_iterations=100)
    guard.start()

    can_go, reason = guard.can_continue()
    assert can_go
    assert reason == ""


def test_status():
    guard = LoopGuard(max_iterations=10, max_total_time=3600)
    guard.start()
    guard.increment_loop()

    status = guard.status()
    assert status["current_loop"] == 1
    assert status["max_iterations"] == 10
    assert status["can_continue"] is True
