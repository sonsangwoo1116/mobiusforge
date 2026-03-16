"""Tests for lessons manager (FR-009, FR-010, FR-012)."""

from pathlib import Path

from mobiusforge.memory.lessons import LessonsManager


def test_add_and_read(tmp_path):
    path = tmp_path / "lessons.md"
    mgr = LessonsManager(path, max_lessons=30)

    mgr.add(1, "FAIL", "DB connection failed", "Use connection pool", ["database"])
    mgr.add(2, "SUCCESS", "API created", "Separate specs per endpoint", ["api"])

    assert len(mgr.lessons) == 2
    assert mgr.lessons[0].outcome == "FAIL"
    assert mgr.lessons[1].applies_to == ["api"]


def test_get_relevant(tmp_path):
    path = tmp_path / "lessons.md"
    mgr = LessonsManager(path, max_lessons=30)

    mgr.add(1, "FAIL", "DB issue", "Fix pool", ["database", "testing"])
    mgr.add(2, "SUCCESS", "API ok", "Split specs", ["api"])
    mgr.add(3, "FAIL", "UI broken", "Check CSS", ["frontend", "css"])

    relevant = mgr.get_relevant(["database"])
    assert len(relevant) == 1
    assert relevant[0].loop_number == 1

    relevant_api = mgr.get_relevant(["api", "testing"])
    assert len(relevant_api) == 2


def test_format_for_prompt(tmp_path):
    path = tmp_path / "lessons.md"
    mgr = LessonsManager(path, max_lessons=30)

    mgr.add(1, "FAIL", "Bad approach", "Don't use X", ["api"])
    mgr.add(2, "SUCCESS", "Good approach", "Use Y instead", ["api"])

    text = mgr.format_for_prompt(["api"])
    assert "AVOID" in text
    assert "REUSE" in text
    assert "Don't use X" in text
    assert "Use Y instead" in text


def test_prune_keeps_failures(tmp_path):
    path = tmp_path / "lessons.md"
    mgr = LessonsManager(path, max_lessons=5)

    # Add 4 successes and 4 failures
    for i in range(4):
        mgr.add(i, "SUCCESS", f"Success {i}", f"Lesson {i}", ["general"])
    for i in range(4, 8):
        mgr.add(i, "FAIL", f"Fail {i}", f"Lesson {i}", ["general"])

    # Should be pruned to 5, keeping more failures
    assert len(mgr.lessons) <= 5
    failures = [l for l in mgr.lessons if l.outcome == "FAIL"]
    assert len(failures) >= 2  # Failures should be preserved


def test_persistence(tmp_path):
    path = tmp_path / "lessons.md"

    mgr1 = LessonsManager(path, max_lessons=30)
    mgr1.add(1, "FAIL", "Error", "Fix it", ["api"])

    mgr2 = LessonsManager(path, max_lessons=30)
    assert len(mgr2.lessons) == 1
    assert mgr2.lessons[0].lesson == "Fix it"
