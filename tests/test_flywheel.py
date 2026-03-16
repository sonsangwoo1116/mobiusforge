"""Tests for flywheel analyzer and tuner (FR-024, FR-025, FR-026)."""

import json
from pathlib import Path

from mobiusforge.flywheel.analyzer import analyze_execution, AnalysisInsight, HarnessAnalysis
from mobiusforge.flywheel.tuner import (
    generate_prompt_improvements,
    generate_spec_refinements,
    auto_apply_guardrails,
)
from mobiusforge.memory.lessons import LessonsManager


def _setup_budget(tmp_path: Path, history: list[dict]) -> Path:
    budget_path = tmp_path / "budget.json"
    budget_path.write_text(json.dumps({"history": history}), encoding="utf-8")
    return budget_path


def _setup_activity(tmp_path: Path, events: list[dict]) -> Path:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    activity = logs_dir / "activity_test.jsonl"
    lines = [json.dumps(e) for e in events]
    activity.write_text("\n".join(lines), encoding="utf-8")
    return logs_dir


def test_analyze_high_failure_rate(tmp_path):
    budget_path = _setup_budget(tmp_path, [
        {"loop": i, "input_tokens": 10000, "output_tokens": 2000, "cost": 0.05, "timestamp": "t"}
        for i in range(10)
    ])
    logs_dir = _setup_activity(tmp_path, [
        {"event": "agent_run", "success": False} for _ in range(7)
    ] + [
        {"event": "agent_run", "success": True} for _ in range(3)
    ])

    analysis = analyze_execution(logs_dir, budget_path, tmp_path / "lessons.md")

    assert analysis.stats.get("fail_rate", 0) > 0.4
    high_findings = [i for i in analysis.insights if i.severity == "high"]
    assert len(high_findings) >= 1


def test_analyze_oscillation_count(tmp_path):
    budget_path = _setup_budget(tmp_path, [
        {"loop": 1, "input_tokens": 10000, "output_tokens": 2000, "cost": 0.05, "timestamp": "t"}
    ])
    logs_dir = _setup_activity(tmp_path, [
        {"event": "oscillation_detected"} for _ in range(5)
    ])

    analysis = analyze_execution(logs_dir, budget_path, tmp_path / "lessons.md")
    osc_insights = [i for i in analysis.insights if i.category == "oscillation"]
    assert len(osc_insights) >= 1


def test_prompt_improvements():
    analysis = HarnessAnalysis(insights=[
        AnalysisInsight("completion", "high", "High failure rate", "Improve specs"),
        AnalysisInsight("oscillation", "high", "Frequent oscillation", "Decompose tasks"),
    ])
    lessons = LessonsManager(Path("/nonexistent"))
    lessons.lessons = []

    suggestions = generate_prompt_improvements(analysis, lessons, Path("PROMPT.md"))
    assert len(suggestions) >= 2


def test_spec_refinements(tmp_path):
    lessons_path = tmp_path / "lessons.md"
    mgr = LessonsManager(lessons_path, max_lessons=30)
    mgr.add(1, "FAIL", "Error 1", "Approach A failed", ["api"])
    mgr.add(2, "FAIL", "Error 2", "Approach B failed", ["api"])
    mgr.add(3, "FAIL", "Error 3", "Approach C failed", ["api"])

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "api-auth.md").write_text("# API Auth Spec", encoding="utf-8")

    refinements = generate_spec_refinements(mgr, specs_dir)
    assert len(refinements) >= 1


def test_auto_apply_guardrails(tmp_path):
    guardrails_path = tmp_path / "guardrails.md"
    guardrails_path.write_text("# Guardrails\n", encoding="utf-8")

    analysis = HarnessAnalysis(insights=[
        AnalysisInsight("completion", "high", "High failure rate", "Run tests before completion"),
    ])

    added = auto_apply_guardrails(analysis, guardrails_path)
    assert added == 1

    content = guardrails_path.read_text()
    assert "Run tests before completion" in content

    # Should not duplicate
    added2 = auto_apply_guardrails(analysis, guardrails_path)
    assert added2 == 0
