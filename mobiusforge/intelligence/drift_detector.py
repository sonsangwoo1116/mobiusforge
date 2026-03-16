"""Goal drift detector — detects when agent strays from task objectives (FR-014, FR-015)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mobiusforge.memory.state import Task

logger = logging.getLogger(__name__)


@dataclass
class DriftResult:
    drifted: bool
    score: float  # 0.0 = on track, 1.0 = completely off track
    reason: str = ""
    irrelevant_files: list[str] | None = None


def detect_drift(
    task: Task,
    spec: str,
    working_dir: Path,
    threshold: float = 0.7,
) -> DriftResult:
    """Detect if recent changes are drifting from the task objective.

    Uses heuristic analysis:
    1. Get list of changed files since task started
    2. Compare changed files against task/spec keywords
    3. Flag files that seem unrelated to the task
    """
    changed_files = _get_recent_changes(working_dir)
    if not changed_files:
        return DriftResult(drifted=False, score=0.0)

    # Build relevance keywords from task + spec
    keywords = _extract_keywords(task, spec)
    if not keywords:
        # Can't assess drift without context
        return DriftResult(drifted=False, score=0.0, reason="No keywords to compare")

    # Score each changed file for relevance
    relevant_count = 0
    irrelevant_files = []

    for filepath in changed_files:
        if _is_relevant(filepath, keywords):
            relevant_count += 1
        else:
            irrelevant_files.append(filepath)

    if not changed_files:
        return DriftResult(drifted=False, score=0.0)

    # Drift score = ratio of irrelevant files
    drift_score = len(irrelevant_files) / len(changed_files)

    drifted = drift_score >= threshold and len(irrelevant_files) >= 2

    if drifted:
        logger.warning(
            "Drift detected for %s: score=%.2f, irrelevant files: %s",
            task.id, drift_score, ", ".join(irrelevant_files[:5]),
        )

    return DriftResult(
        drifted=drifted,
        score=drift_score,
        reason=f"{len(irrelevant_files)}/{len(changed_files)} files seem unrelated to task",
        irrelevant_files=irrelevant_files,
    )


def _get_recent_changes(working_dir: Path, num_commits: int = 3) -> list[str]:
    """Get files changed in recent commits."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"HEAD~{num_commits}", "HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            # Might not have enough commits, try HEAD only
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def _extract_keywords(task: Task, spec: str) -> set[str]:
    """Extract relevance keywords from task context."""
    keywords: set[str] = set()

    # From task title (split into words)
    for word in task.title.lower().split():
        if len(word) >= 3:
            keywords.add(word)

    # From spec content
    if spec:
        # Extract significant words (skip common ones)
        skip_words = {
            "the", "and", "for", "that", "this", "with", "from", "have", "will",
            "should", "must", "can", "are", "not", "all", "when", "each", "use",
            "using", "used", "also", "into", "been", "has", "was", "were", "being",
        }
        for word in spec.lower().split():
            clean = word.strip(".,;:()[]{}\"'`#*-_/")
            if len(clean) >= 3 and clean not in skip_words:
                keywords.add(clean)

    return keywords


def _is_relevant(filepath: str, keywords: set[str]) -> bool:
    """Check if a file path seems relevant to the task."""
    # Always relevant: config, test, spec files
    always_relevant = [
        "test", "spec", "config", "package.json", "pyproject.toml",
        "requirements", "task_plan", "lessons", "guardrails", ".mobiusforge",
    ]
    path_lower = filepath.lower()
    for pattern in always_relevant:
        if pattern in path_lower:
            return True

    # Check if any keyword appears in the file path
    path_parts = path_lower.replace("/", " ").replace("_", " ").replace("-", " ").split()
    for part in path_parts:
        if part in keywords:
            return True

    # Check file extension relevance (code files are usually relevant)
    # But if we have many irrelevant code files, that's a sign of drift
    return False
