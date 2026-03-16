"""Cross-loop lesson management — write, inject, prune (FR-009, FR-010, FR-012)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Lesson:
    loop_number: int
    timestamp: str
    outcome: str  # "FAIL" or "SUCCESS"
    description: str
    lesson: str
    applies_to: list[str]

    def to_markdown(self) -> str:
        tags = ", ".join(self.applies_to)
        return (
            f"## Loop {self.loop_number} - {self.timestamp}\n"
            f"- **{self.outcome}**: {self.description}\n"
            f"- **LESSON**: {self.lesson}\n"
            f"- **APPLIES_TO**: {tags}\n"
        )


_LOOP_HEADER_RE = re.compile(r"^## Loop (\d+) - (.+)$")
_OUTCOME_RE = re.compile(r"^- \*\*(FAIL|SUCCESS)\*\*:\s+(.+)$")
_LESSON_RE = re.compile(r"^- \*\*LESSON\*\*:\s+(.+)$")
_TAGS_RE = re.compile(r"^- \*\*APPLIES_TO\*\*:\s+(.+)$")


class LessonsManager:
    """Manages .mobiusforge/lessons.md."""

    def __init__(self, lessons_path: Path, max_lessons: int = 30) -> None:
        self.path = lessons_path
        self.max_lessons = max_lessons
        self.lessons: list[Lesson] = []
        if self.path.exists():
            self._parse()

    def _parse(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        self.lessons = []
        current_loop = 0
        current_ts = ""
        current_outcome = ""
        current_desc = ""
        current_lesson = ""
        current_tags: list[str] = []
        in_entry = False

        for line in text.splitlines():
            header = _LOOP_HEADER_RE.match(line)
            if header:
                if in_entry:
                    self.lessons.append(
                        Lesson(current_loop, current_ts, current_outcome,
                               current_desc, current_lesson, current_tags)
                    )
                current_loop = int(header.group(1))
                current_ts = header.group(2)
                current_outcome = ""
                current_desc = ""
                current_lesson = ""
                current_tags = []
                in_entry = True
                continue

            if not in_entry:
                continue

            outcome = _OUTCOME_RE.match(line)
            if outcome:
                current_outcome = outcome.group(1)
                current_desc = outcome.group(2)
                continue

            lesson = _LESSON_RE.match(line)
            if lesson:
                current_lesson = lesson.group(1)
                continue

            tags = _TAGS_RE.match(line)
            if tags:
                current_tags = [t.strip() for t in tags.group(1).split(",")]

        if in_entry:
            self.lessons.append(
                Lesson(current_loop, current_ts, current_outcome,
                       current_desc, current_lesson, current_tags)
            )

    def add(self, loop_number: int, outcome: str, description: str,
            lesson: str, applies_to: list[str]) -> None:
        """Add a new lesson entry."""
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entry = Lesson(loop_number, ts, outcome, description, lesson, applies_to)
        self.lessons.append(entry)
        self._prune()
        self._write()

    def get_relevant(self, tags: list[str]) -> list[Lesson]:
        """Get lessons matching any of the given tags (FR-010)."""
        if not tags:
            return list(self.lessons)
        tag_set = {t.lower() for t in tags}
        return [
            lesson for lesson in self.lessons
            if any(t.lower() in tag_set for t in lesson.applies_to)
        ]

    def format_for_prompt(self, tags: list[str]) -> str:
        """Format relevant lessons for injection into agent prompt."""
        relevant = self.get_relevant(tags)
        if not relevant:
            return ""

        lines = ["## Previous Lessons (DO NOT repeat failed approaches)", ""]
        for lesson in relevant[-10:]:  # Last 10 relevant lessons
            prefix = "AVOID" if lesson.outcome == "FAIL" else "REUSE"
            lines.append(f"- [{prefix}] {lesson.lesson}")
        return "\n".join(lines)

    def _prune(self) -> None:
        """Remove oldest lessons when exceeding max (FR-012 simplified)."""
        if len(self.lessons) > self.max_lessons:
            # Keep failures longer (more valuable)
            failures = [entry for entry in self.lessons if entry.outcome == "FAIL"]
            successes = [entry for entry in self.lessons if entry.outcome == "SUCCESS"]

            # Remove oldest successes first
            while len(failures) + len(successes) > self.max_lessons and successes:
                successes.pop(0)

            # Then oldest failures if still over
            while len(failures) + len(successes) > self.max_lessons and failures:
                failures.pop(0)

            self.lessons = sorted(
                failures + successes, key=lambda entry: entry.loop_number
            )

    def _write(self) -> None:
        lines = ["# Lessons Learned", ""]
        for lesson in self.lessons:
            lines.append(lesson.to_markdown())
        self.path.write_text("\n".join(lines), encoding="utf-8")
