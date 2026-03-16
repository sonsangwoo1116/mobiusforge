"""Prompt assembler — builds the agent prompt from state files (FR-003, FR-010)."""

from __future__ import annotations

import logging
from pathlib import Path

from mobiusforge.memory.lessons import LessonsManager
from mobiusforge.memory.state import Task

logger = logging.getLogger(__name__)


def load_spec(specs_dir: Path, task: Task) -> str:
    """Load the spec file for a given task (FR-003)."""
    # Try matching by task ID (e.g., specs/T-001.md)
    spec_by_id = specs_dir / f"{task.id}.md"
    if spec_by_id.exists():
        return spec_by_id.read_text(encoding="utf-8")

    # Try matching by task title slug
    slug = task.title.lower().replace(" ", "-").replace("/", "-")
    spec_by_slug = specs_dir / f"{slug}.md"
    if spec_by_slug.exists():
        return spec_by_slug.read_text(encoding="utf-8")

    # Try finding any spec that mentions the task ID
    if specs_dir.exists():
        for spec_file in specs_dir.glob("*.md"):
            content = spec_file.read_text(encoding="utf-8")
            if task.id in content or task.title in content:
                return content

    logger.warning("No spec found for task %s: %s", task.id, task.title)
    return ""


def load_guardrails(mobiusforge_dir: Path) -> str:
    """Load guardrails file."""
    path = mobiusforge_dir / "guardrails.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def assemble_prompt(
    task: Task,
    prompt_md: str,
    spec: str,
    lessons_manager: LessonsManager,
    guardrails: str,
    failed_approaches: list[str] | None = None,
) -> str:
    """Assemble the full prompt for the agent."""
    parts: list[str] = []

    # 1. Base prompt (PROMPT.md)
    if prompt_md:
        parts.append(prompt_md)
        parts.append("")

    # 2. Guardrails
    if guardrails:
        parts.append("## Project Guardrails")
        parts.append(guardrails)
        parts.append("")

    # 3. Current task
    parts.append("## Current Task")
    parts.append(f"**{task.id}: {task.title}**")
    parts.append(f"- Status: {task.status.value}")
    if task.approach:
        parts.append(f"- Current approach: {task.approach}")
    if task.resume_hint:
        parts.append(f"- Resume from: {task.resume_hint}")
    parts.append("")

    # 4. Task spec
    if spec:
        parts.append("## Task Specification")
        parts.append(spec)
        parts.append("")

    # 5. Failed approaches (for strategy rotation)
    if failed_approaches:
        parts.append("## FAILED Approaches (DO NOT repeat these)")
        for i, approach in enumerate(failed_approaches, 1):
            parts.append(f"{i}. {approach}")
        parts.append("")
        parts.append("You MUST use a completely different approach from the ones listed above.")
        parts.append("")

    # 6. Relevant lessons from previous loops
    tags = _extract_tags(task, spec)
    lessons_text = lessons_manager.format_for_prompt(tags)
    if lessons_text:
        parts.append(lessons_text)
        parts.append("")

    # 7. Completion instruction
    parts.append("## Completion Criteria")
    parts.append("When you have completed the task:")
    parts.append("1. Ensure all tests pass")
    parts.append("2. Ensure lint checks pass")
    parts.append("3. Update task_plan.md to mark this task as DONE if fully complete")
    parts.append("4. If blocked, mark as BLOCKED with reason")

    return "\n".join(parts)


def _extract_tags(task: Task, spec: str) -> list[str]:
    """Extract relevant tags from task context for lesson filtering."""
    tags: list[str] = []

    # From task title
    title_lower = task.title.lower()
    tag_keywords = [
        "api", "auth", "database", "db", "ui", "frontend", "backend",
        "test", "testing", "config", "deploy", "docker", "css", "style",
    ]
    for keyword in tag_keywords:
        if keyword in title_lower:
            tags.append(keyword)

    # From spec content
    if spec:
        spec_lower = spec.lower()
        for keyword in tag_keywords:
            if keyword in spec_lower and keyword not in tags:
                tags.append(keyword)

    return tags if tags else ["general"]
