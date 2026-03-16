"""Graceful shutdown protocol (FR-031)."""

from __future__ import annotations

import logging
import signal
import threading
from pathlib import Path

from mobiusforge.memory.state import TaskPlan, TaskStatus
from mobiusforge.safety.rollback import stash_changes

logger = logging.getLogger(__name__)


class ShutdownHandler:
    """Handles graceful shutdown on SIGINT/SIGTERM.

    Protocol:
    1. Set shutdown flag on signal
    2. Current loop completes naturally (checked by loop engine)
    3. Uncommitted changes are stashed
    4. IN_PROGRESS tasks marked as INTERRUPTED
    """

    def __init__(self) -> None:
        self._shutdown_requested = threading.Event()
        self._original_sigint = None
        self._original_sigterm = None

    @property
    def should_stop(self) -> bool:
        return self._shutdown_requested.is_set()

    def install(self) -> None:
        """Install signal handlers."""
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        logger.debug("Shutdown handler installed")

    def uninstall(self) -> None:
        """Restore original signal handlers."""
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)

    def _handle_signal(self, signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        if self._shutdown_requested.is_set():
            logger.warning("Second %s received — forcing exit", sig_name)
            raise SystemExit(1)

        logger.info("Received %s — graceful shutdown initiated", sig_name)
        logger.info("Waiting for current loop to complete. Send again to force exit.")
        self._shutdown_requested.set()

    def finalize(self, working_dir: Path, task_plan: TaskPlan) -> None:
        """Run shutdown finalization: stash + mark interrupted (FR-031)."""
        if not self.should_stop:
            return

        logger.info("Running shutdown finalization...")

        # Stash uncommitted changes
        stash_changes(working_dir, "mobiusforge-shutdown-autostash")

        # Mark in-progress tasks as interrupted
        for task in task_plan.tasks:
            if task.status == TaskStatus.IN_PROGRESS:
                task_plan.mark_interrupted(
                    task.id,
                    hint="Interrupted by shutdown signal. Resume from last state.",
                )
                logger.info("Marked %s as INTERRUPTED", task.id)

        logger.info("Shutdown finalization complete")
