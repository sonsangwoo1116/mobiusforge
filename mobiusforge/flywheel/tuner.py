"""Prompt auto-tuner and spec refiner (FR-025, FR-026)."""

from __future__ import annotations

import logging
from pathlib import Path

from mobiusforge.flywheel.analyzer import HarnessAnalysis
from mobiusforge.memory.lessons import LessonsManager

logger = logging.getLogger(__name__)


def generate_prompt_improvements(
    analysis: HarnessAnalysis,
    lessons: LessonsManager,
    prompt_path: Path,
) -> list[str]:
    """Generate suggestions to improve PROMPT.md based on execution analysis (FR-025)."""
    suggestions: list[str] = []

    # From analysis insights
    for insight in analysis.insights:
        if insight.category == "completion" and insight.severity == "high":
            suggestions.append(
                "Add to PROMPT.md: '## Common Pitfalls\\n"
                "- Always run tests before marking a task as complete\\n"
                "- Verify all acceptance criteria from the spec'"
            )
        if insight.category == "oscillation":
            suggestions.append(
                "Add to PROMPT.md: '## When Stuck\\n"
                "- If the same approach fails twice, try a fundamentally different method\\n"
                "- If tests keep flip-flopping, simplify the implementation first'"
            )
        if insight.category == "drift":
            suggestions.append(
                "Add to PROMPT.md: '## Focus Rules\\n"
                "- Only modify files listed in the spec\\n"
                "- Do NOT refactor unrelated code\\n"
                "- One task at a time, no scope creep'"
            )
        if insight.category == "cost" and insight.severity == "high":
            suggestions.append(
                "Reduce PROMPT.md size — current prompt may be too verbose. "
                "Move detailed rules to guardrails.md instead."
            )

    # From recurring failure lessons
    fail_lessons = [entry for entry in lessons.lessons if entry.outcome == "FAIL"]
    if len(fail_lessons) >= 5:
        # Find most common failure tags
        tag_counts: dict[str, int] = {}
        for lesson in fail_lessons:
            for tag in lesson.applies_to:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_tags:
            problem_areas = ", ".join(f"{tag}({count})" for tag, count in top_tags)
            suggestions.append(
                f"Recurring failures in: {problem_areas}. "
                "Consider adding specific guardrails for these areas."
            )

    return suggestions


def generate_spec_refinements(
    lessons: LessonsManager,
    specs_dir: Path,
) -> dict[str, list[str]]:
    """Suggest spec improvements based on failure patterns (FR-026).

    Returns: {spec_filename: [suggestions]}
    """
    refinements: dict[str, list[str]] = {}

    fail_lessons = [entry for entry in lessons.lessons if entry.outcome == "FAIL"]

    # Group failures by tag (proxy for which spec they relate to)
    tag_failures: dict[str, list[str]] = {}
    for lesson in fail_lessons:
        for tag in lesson.applies_to:
            if tag not in tag_failures:
                tag_failures[tag] = []
            tag_failures[tag].append(lesson.lesson)

    # For each tag with multiple failures, suggest spec improvements
    for tag, failures in tag_failures.items():
        if len(failures) < 2:
            continue

        # Try to find matching spec file
        spec_candidates = list(specs_dir.glob(f"*{tag}*")) if specs_dir.exists() else []

        suggestions = []
        if len(failures) >= 3:
            suggestions.append(
                f"This area has {len(failures)} failures. "
                "Consider breaking this spec into smaller, more specific sub-specs."
            )
        suggestions.append(
            "Add explicit 'DO NOT' section listing failed approaches: "
            + "; ".join(f[:60] for f in failures[:3])
        )

        if spec_candidates:
            for spec in spec_candidates:
                refinements[spec.name] = suggestions
        else:
            refinements[f"[tag:{tag}]"] = suggestions

    return refinements


def auto_apply_guardrails(
    analysis: HarnessAnalysis,
    guardrails_path: Path,
) -> int:
    """Automatically add guardrails based on analysis findings.

    Returns number of guardrails added.
    """
    if not guardrails_path.exists():
        return 0

    existing = guardrails_path.read_text(encoding="utf-8")
    new_rules: list[str] = []

    for insight in analysis.insights:
        if insight.severity != "high":
            continue

        rule = f"- [AUTO] {insight.recommendation}"
        if rule not in existing:
            new_rules.append(rule)

    if new_rules:
        with open(guardrails_path, "a", encoding="utf-8") as f:
            f.write("\n## Auto-Generated (Flywheel)\n")
            for rule in new_rules:
                f.write(f"{rule}\n")

        logger.info("Added %d auto-generated guardrails", len(new_rules))

    return len(new_rules)
