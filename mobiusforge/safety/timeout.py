"""Timeout and loop guards (FR-028, FR-029, FR-030)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class LoopGuard:
    """Manages all loop termination conditions."""

    max_iterations: int = 100
    max_total_time: int = 43200  # seconds (12h)
    end_time: str = ""  # ISO 8601
    wind_down_minutes: int = 30
    loop_timeout: int = 600  # per-loop timeout (seconds)

    _start_time: float = 0.0
    _current_loop: int = 0

    def start(self) -> None:
        self._start_time = time.monotonic()
        self._current_loop = 0

    def increment_loop(self) -> None:
        self._current_loop += 1

    @property
    def current_loop(self) -> int:
        return self._current_loop

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time == 0:
            return 0
        return time.monotonic() - self._start_time

    def can_continue(self) -> tuple[bool, str]:
        """Check if the loop should continue. Returns (can_continue, reason)."""
        # FR-028: Max loop limiter
        if self._current_loop >= self.max_iterations:
            return False, f"Max iterations reached ({self.max_iterations})"

        # FR-029: Total time guard
        if self.elapsed_seconds >= self.max_total_time:
            return False, f"Max total time reached ({self.max_total_time}s)"

        # FR-030: Absolute time guard
        if self.end_time:
            try:
                end_dt = datetime.fromisoformat(self.end_time)
                now = datetime.now(timezone.utc)
                if now >= end_dt:
                    return False, f"End time reached ({self.end_time})"
            except ValueError:
                logger.warning("Invalid end_time format: %s", self.end_time)

        return True, ""

    def is_wind_down(self) -> bool:
        """Check if we're in wind-down period (FR-030)."""
        if not self.end_time:
            # Fall back to max_total_time
            remaining = self.max_total_time - self.elapsed_seconds
            return remaining <= (self.wind_down_minutes * 60)

        try:
            end_dt = datetime.fromisoformat(self.end_time)
            now = datetime.now(timezone.utc)
            remaining = (end_dt - now).total_seconds()
            return remaining <= (self.wind_down_minutes * 60)
        except ValueError:
            return False

    def status(self) -> dict:
        can_go, reason = self.can_continue()
        return {
            "current_loop": self._current_loop,
            "max_iterations": self.max_iterations,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "max_total_time": self.max_total_time,
            "wind_down": self.is_wind_down(),
            "can_continue": can_go,
            "stop_reason": reason,
        }
