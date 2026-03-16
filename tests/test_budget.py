"""Tests for budget tracker (FR-021, FR-022)."""

from pathlib import Path

from mobiusforge.safety.budget import BudgetStatus, BudgetTracker


def test_record_and_track():
    tracker = BudgetTracker(max_total_cost=10.0)

    tracker.record(1, input_tokens=10000, output_tokens=2000, cost=0.06)
    tracker.record(2, input_tokens=15000, output_tokens=3000, cost=0.09)

    assert tracker.total_cost == 0.15
    assert tracker.total_input_tokens == 25000
    assert tracker.total_output_tokens == 5000
    assert len(tracker.history) == 2


def test_budget_status():
    tracker = BudgetTracker(max_total_cost=1.0, warn_at_percent=80)

    tracker.record(1, 0, 0, 0.5)
    assert tracker.check_budget() == BudgetStatus.OK

    tracker.record(2, 0, 0, 0.35)
    assert tracker.check_budget() == BudgetStatus.WARNING

    tracker.record(3, 0, 0, 0.20)
    assert tracker.check_budget() == BudgetStatus.EXCEEDED


def test_persistence(tmp_path):
    path = tmp_path / "budget.json"

    tracker1 = BudgetTracker(max_total_cost=50.0)
    tracker1.record(1, 10000, 2000, 0.06)
    tracker1.save(path)

    tracker2 = BudgetTracker.load(path, max_cost=50.0)
    assert len(tracker2.history) == 1
    assert tracker2.total_cost == 0.06


def test_summary():
    tracker = BudgetTracker(max_total_cost=50.0)
    tracker.record(1, 10000, 2000, 0.06)

    summary = tracker.summary()
    assert summary["total_cost"] == 0.06
    assert summary["budget_limit"] == 50.0
    assert summary["loops_recorded"] == 1
