"""Task plan state manager — parses and updates task_plan.md (FR-002)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class TaskStatus(Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    INTERRUPTED = "INTERRUPTED"


@dataclass
class Task:
    id: str
    title: str
    status: TaskStatus = TaskStatus.OPEN
    priority: str = "P1"
    depends_on: list[str] = field(default_factory=list)
    approach: str = ""
    loops_taken: int = 0
    started_at: str = ""
    completed_at: str = ""
    blocked_reason: str = ""
    failed_approaches: list[str] = field(default_factory=list)
    resume_hint: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.status in (TaskStatus.OPEN, TaskStatus.INTERRUPTED)


_HEADER_RE = re.compile(
    r"^###\s+\[(?P<status>[A-Z_]+)\]\s+(?P<id>T-\d+):\s+(?P<title>.+)$"
)
_KV_RE = re.compile(r"^-\s+(?P<key>\w+):\s+(?P<value>.+)$")
_LIST_ITEM_RE = re.compile(r'^\s+-\s+"(?P<value>.+)"$')


class TaskPlan:
    """Reads and writes task_plan.md."""

    def __init__(self, plan_path: Path) -> None:
        self.path = plan_path
        self.tasks: list[Task] = []
        if self.path.exists():
            self._parse()

    def _parse(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        self.tasks = []
        current: Task | None = None

        for line in text.splitlines():
            header_match = _HEADER_RE.match(line)
            if header_match:
                if current:
                    self.tasks.append(current)
                current = Task(
                    id=header_match.group("id"),
                    title=header_match.group("title").strip(),
                    status=TaskStatus(header_match.group("status")),
                )
                continue

            if current is None:
                continue

            kv_match = _KV_RE.match(line)
            if kv_match:
                key = kv_match.group("key")
                value = kv_match.group("value").strip()
                if key == "priority":
                    current.priority = value
                elif key == "depends_on":
                    current.depends_on = [d.strip() for d in value.split(",")]
                elif key == "approach":
                    current.approach = value
                elif key == "loops_taken":
                    current.loops_taken = int(value)
                elif key == "started_at":
                    current.started_at = value
                elif key == "completed_at":
                    current.completed_at = value
                elif key == "blocked_reason":
                    current.blocked_reason = value.strip('"')
                elif key == "resume_hint":
                    current.resume_hint = value.strip('"')
                continue

            list_match = _LIST_ITEM_RE.match(line)
            if list_match and current:
                current.failed_approaches.append(list_match.group("value"))

        if current:
            self.tasks.append(current)

    def get_next_task(self) -> Task | None:
        """Select the next actionable task respecting dependencies and priority."""
        done_ids = {t.id for t in self.tasks if t.status == TaskStatus.DONE}

        # Interrupted tasks first (resume)
        for task in self.tasks:
            if task.status == TaskStatus.INTERRUPTED:
                deps_met = all(d in done_ids for d in task.depends_on)
                if deps_met:
                    return task

        # Then open tasks by priority
        actionable = []
        for task in self.tasks:
            if task.status != TaskStatus.OPEN:
                continue
            deps_met = all(d in done_ids for d in task.depends_on)
            if deps_met:
                actionable.append(task)

        if not actionable:
            return None

        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        actionable.sort(key=lambda t: priority_order.get(t.priority, 99))
        return actionable[0]

    def update_task(self, task_id: str, **kwargs: str | int | list) -> None:
        """Update a task's fields and persist to disk."""
        for task in self.tasks:
            if task.id == task_id:
                for key, value in kwargs.items():
                    if key == "status":
                        task.status = TaskStatus(value)
                    elif hasattr(task, key):
                        setattr(task, key, value)
                break
        self._write()

    def mark_in_progress(self, task_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.update_task(task_id, status="IN_PROGRESS", started_at=now)

    def mark_done(self, task_id: str, loops: int) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.update_task(task_id, status="DONE", completed_at=now, loops_taken=loops)

    def mark_blocked(self, task_id: str, reason: str, failed: list[str]) -> None:
        self.update_task(
            task_id, status="BLOCKED", blocked_reason=reason, failed_approaches=failed
        )

    def mark_interrupted(self, task_id: str, hint: str) -> None:
        self.update_task(task_id, status="INTERRUPTED", resume_hint=hint)

    def all_done(self) -> bool:
        non_blocked = [t for t in self.tasks if t.status != TaskStatus.BLOCKED]
        return all(t.status == TaskStatus.DONE for t in non_blocked)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in self.tasks:
            counts[task.status.value] = counts.get(task.status.value, 0) + 1
        return counts

    def _write(self) -> None:
        lines = ["# Task Plan", "", "## Current Sprint", ""]
        for task in self.tasks:
            lines.append(f"### [{task.status.value}] {task.id}: {task.title}")
            if task.priority:
                lines.append(f"- priority: {task.priority}")
            if task.depends_on:
                lines.append(f"- depends_on: {', '.join(task.depends_on)}")
            if task.started_at:
                lines.append(f"- started_at: {task.started_at}")
            if task.completed_at:
                lines.append(f"- completed_at: {task.completed_at}")
            if task.approach:
                lines.append(f"- approach: {task.approach}")
            if task.loops_taken:
                lines.append(f"- loops_taken: {task.loops_taken}")
            if task.blocked_reason:
                lines.append(f'- blocked_reason: "{task.blocked_reason}"')
            if task.failed_approaches:
                lines.append("- failed_approaches:")
                for fa in task.failed_approaches:
                    lines.append(f'  - "{fa}"')
            if task.resume_hint:
                lines.append(f'- resume_hint: "{task.resume_hint}"')
            lines.append("")

        self.path.write_text("\n".join(lines), encoding="utf-8")
