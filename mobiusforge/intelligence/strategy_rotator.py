"""Strategy rotator — switches to alternative approaches on oscillation (FR-007, FR-008)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from mobiusforge.memory.state import Task, TaskPlan

logger = logging.getLogger(__name__)


@dataclass
class StrategyRotation:
    """Tracks strategy attempts per task and generates alternative approach hints."""

    max_retries: int = 3
    dead_end_action: str = "skip"  # skip | pause | abort
    _attempts: dict[str, list[str]] = field(default_factory=dict)

    def record_failure(self, task_id: str, approach_description: str) -> None:
        """Record a failed approach for a task."""
        if task_id not in self._attempts:
            self._attempts[task_id] = []
        self._attempts[task_id].append(approach_description)
        logger.info(
            "Strategy failure recorded for %s (attempt %d/%d): %s",
            task_id, len(self._attempts[task_id]), self.max_retries,
            approach_description[:80],
        )

    def get_failed_approaches(self, task_id: str) -> list[str]:
        """Get all failed approaches for a task."""
        return self._attempts.get(task_id, [])

    def attempts_remaining(self, task_id: str) -> int:
        """How many strategy attempts remain."""
        used = len(self._attempts.get(task_id, []))
        return max(0, self.max_retries - used)

    def is_dead_end(self, task_id: str) -> bool:
        """Check if all strategies are exhausted (FR-008)."""
        return self.attempts_remaining(task_id) == 0

    def get_rotation_hint(self, task_id: str) -> str:
        """Generate a hint for the next strategy attempt.

        FR-007 mechanism:
        1. Attempt 1: "Previous approach X failed. Try a completely different method."
        2. Attempt 2: "Both X and Y failed. Try decomposing into smaller subtasks."
        3. Attempt 3 (final): "All approaches failed. Make minimal changes to get tests passing."
        """
        failed = self.get_failed_approaches(task_id)
        attempt_num = len(failed) + 1

        if attempt_num == 1:
            return ""  # First attempt, no hint needed

        failed_summary = "\n".join(f"  - {f}" for f in failed)

        if attempt_num == 2:
            return (
                f"PREVIOUS APPROACH FAILED:\n{failed_summary}\n\n"
                "You MUST use a completely different approach. "
                "Consider alternative libraries, patterns, or algorithms. "
                "Do NOT retry the same strategy with minor modifications."
            )

        if attempt_num == 3:
            return (
                f"MULTIPLE APPROACHES FAILED:\n{failed_summary}\n\n"
                "Try decomposing this task into smaller subtasks. "
                "Implement the simplest possible version first, then iterate. "
                "Focus on getting tests to pass with minimal code."
            )

        # Final attempt
        return (
            f"ALL PREVIOUS APPROACHES FAILED:\n{failed_summary}\n\n"
            "This is the FINAL attempt. Make the most minimal change possible "
            "to satisfy the core requirement. Skip edge cases. "
            "If still impossible, mark the task as BLOCKED."
        )

    def handle_dead_end(self, task: Task, task_plan: TaskPlan) -> str:
        """Handle a task where all strategies are exhausted (FR-008).

        Returns action taken: 'skip', 'pause', or 'abort'.
        """
        failed = self.get_failed_approaches(task.id)

        if self.dead_end_action == "skip":
            task_plan.mark_blocked(
                task.id,
                reason=f"All {self.max_retries} strategies exhausted",
                failed=failed,
            )
            logger.warning(
                "Task %s marked BLOCKED — all %d strategies failed",
                task.id, self.max_retries,
            )
            return "skip"

        if self.dead_end_action == "pause":
            logger.warning(
                "Task %s hit dead end — pausing for human intervention",
                task.id,
            )
            return "pause"

        # abort
        logger.error("Task %s hit dead end — aborting", task.id)
        return "abort"
