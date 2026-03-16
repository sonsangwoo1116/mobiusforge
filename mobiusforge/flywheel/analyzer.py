"""Harness self-analyzer — finds inefficiencies in execution patterns (FR-024)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AnalysisInsight:
    category: str  # "oscillation" | "cost" | "speed" | "completion" | "drift"
    severity: str  # "high" | "medium" | "low"
    finding: str
    recommendation: str


@dataclass
class HarnessAnalysis:
    insights: list[AnalysisInsight] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def high_severity_count(self) -> int:
        return sum(1 for i in self.insights if i.severity == "high")

    def summary(self) -> str:
        lines = [f"Analysis: {len(self.insights)} insights found"]
        for ins in self.insights:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[ins.severity]
            lines.append(f"  {icon} [{ins.category}] {ins.finding}")
            lines.append(f"     → {ins.recommendation}")
        return "\n".join(lines)


def analyze_execution(
    logs_dir: Path,
    budget_path: Path,
    lessons_path: Path,
) -> HarnessAnalysis:
    """Analyze past execution patterns and identify inefficiencies."""
    analysis = HarnessAnalysis()

    # Load budget history
    budget_data = _load_json(budget_path)
    history = budget_data.get("history", [])

    if not history:
        return analysis

    # --- Cost analysis ---
    costs = [h["cost"] for h in history]
    avg_cost = sum(costs) / len(costs) if costs else 0
    max_cost = max(costs) if costs else 0

    analysis.stats["avg_cost_per_loop"] = round(avg_cost, 4)
    analysis.stats["max_cost_per_loop"] = round(max_cost, 4)
    analysis.stats["total_loops"] = len(history)

    if max_cost > avg_cost * 3 and len(costs) > 5:
        analysis.insights.append(AnalysisInsight(
            category="cost",
            severity="medium",
            finding=f"Cost spike detected: max ${max_cost:.4f} vs avg ${avg_cost:.4f}",
            recommendation="Check for overly complex prompts or large spec files in expensive loops",
        ))

    # --- Token efficiency ---
    input_tokens = [h.get("input_tokens", 0) for h in history]
    avg_input = sum(input_tokens) / len(input_tokens) if input_tokens else 0
    if avg_input > 40000:
        analysis.insights.append(AnalysisInsight(
            category="cost",
            severity="high",
            finding=f"High average input tokens: {avg_input:.0f} per loop",
            recommendation="Reduce prompt size: trim PROMPT.md, use smaller specs, limit lessons injection",
        ))

    # --- Failure rate ---
    activity_files = sorted(logs_dir.glob("activity_*.jsonl"))
    fail_count = 0
    success_count = 0
    oscillation_count = 0
    drift_count = 0

    for af in activity_files:
        for line in af.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                event = entry.get("event", "")
                if event == "agent_run":
                    if entry.get("success"):
                        success_count += 1
                    else:
                        fail_count += 1
                elif event == "oscillation_detected":
                    oscillation_count += 1
                elif event == "drift_detected":
                    drift_count += 1
            except json.JSONDecodeError:
                continue

    total_runs = fail_count + success_count
    if total_runs > 5:
        fail_rate = fail_count / total_runs
        analysis.stats["fail_rate"] = round(fail_rate, 2)

        if fail_rate > 0.4:
            analysis.insights.append(AnalysisInsight(
                category="completion",
                severity="high",
                finding=f"High failure rate: {fail_rate:.0%} ({fail_count}/{total_runs})",
                recommendation="Improve specs clarity, add more guardrails, or simplify tasks",
            ))

    if oscillation_count > 3:
        analysis.insights.append(AnalysisInsight(
            category="oscillation",
            severity="high",
            finding=f"Frequent oscillations: {oscillation_count} detected",
            recommendation="Tasks may be too ambiguous. Decompose into smaller subtasks with clearer specs",
        ))

    if drift_count > 2:
        analysis.insights.append(AnalysisInsight(
            category="drift",
            severity="medium",
            finding=f"Drift detected {drift_count} times",
            recommendation="Add stronger task boundaries in specs. List exact files to modify.",
        ))

    # --- Speed analysis ---
    durations = [h.get("duration", 0) for h in history if h.get("duration")]
    if not durations:
        # Try from activity logs
        for af in activity_files:
            for line in af.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                    if entry.get("event") == "agent_run" and entry.get("duration"):
                        durations.append(entry["duration"])
                except json.JSONDecodeError:
                    continue

    if durations:
        avg_duration = sum(durations) / len(durations)
        analysis.stats["avg_loop_duration"] = round(avg_duration, 1)

        if avg_duration > 300:  # > 5 minutes
            analysis.insights.append(AnalysisInsight(
                category="speed",
                severity="medium",
                finding=f"Slow loops: avg {avg_duration:.0f}s per loop",
                recommendation="Consider using a faster model (haiku) for simpler tasks, or reduce timeout",
            ))

    return analysis


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
