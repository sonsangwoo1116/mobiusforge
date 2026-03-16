"""Oscillation detector — detects repeated fix/revert patterns (FR-006)."""

from __future__ import annotations

import hashlib
import logging
import subprocess
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LoopSnapshot:
    loop_number: int
    diff_hash: str
    changed_files: list[str]


@dataclass
class OscillationDetector:
    """Detects when an agent oscillates between two broken states.

    Tracks diff hashes over a sliding window. If the same hash appears
    multiple times, the agent is toggling between states.
    """

    threshold: int = 3
    window_size: int = 5
    _history: deque[LoopSnapshot] = field(default_factory=lambda: deque(maxlen=10))

    def record(self, loop_number: int, working_dir: Path) -> None:
        """Record the current diff state after an agent run."""
        diff_hash = _get_diff_hash(working_dir)
        changed = _get_changed_files(working_dir)

        snapshot = LoopSnapshot(
            loop_number=loop_number,
            diff_hash=diff_hash,
            changed_files=changed,
        )
        self._history.append(snapshot)

    def detect(self) -> OscillationResult:
        """Check if oscillation is occurring in the recent window."""
        if len(self._history) < 2:
            return OscillationResult(detected=False)

        # Look at recent window
        recent = list(self._history)[-self.window_size :]

        # Count hash occurrences
        hash_counts: dict[str, int] = {}
        for snap in recent:
            if snap.diff_hash:
                hash_counts[snap.diff_hash] = hash_counts.get(snap.diff_hash, 0) + 1

        # Check if any hash repeats >= threshold
        for diff_hash, count in hash_counts.items():
            if count >= self.threshold:
                # Find which files are oscillating
                oscillating_files = set()
                for snap in recent:
                    if snap.diff_hash == diff_hash:
                        oscillating_files.update(snap.changed_files)

                logger.warning(
                    "Oscillation detected! Hash %s appeared %d times in last %d loops. "
                    "Files: %s",
                    diff_hash[:8], count, self.window_size,
                    ", ".join(oscillating_files),
                )

                return OscillationResult(
                    detected=True,
                    repeat_count=count,
                    oscillating_files=list(oscillating_files),
                    pattern_hash=diff_hash,
                )

        # Also detect ping-pong: A→B→A→B pattern (two alternating hashes)
        if len(recent) >= 4:
            last_hashes = [s.diff_hash for s in recent[-4:] if s.diff_hash]
            if len(last_hashes) == 4:
                if last_hashes[0] == last_hashes[2] and last_hashes[1] == last_hashes[3]:
                    oscillating_files = set()
                    for snap in recent[-4:]:
                        oscillating_files.update(snap.changed_files)

                    logger.warning("Ping-pong oscillation detected: A→B→A→B pattern")
                    return OscillationResult(
                        detected=True,
                        repeat_count=2,
                        oscillating_files=list(oscillating_files),
                        pattern_hash=f"pingpong:{last_hashes[0][:8]}<>{last_hashes[1][:8]}",
                    )

        return OscillationResult(detected=False)

    def reset(self) -> None:
        """Reset history (e.g., when moving to a new task)."""
        self._history.clear()


@dataclass
class OscillationResult:
    detected: bool
    repeat_count: int = 0
    oscillating_files: list[str] = field(default_factory=list)
    pattern_hash: str = ""


def _get_diff_hash(working_dir: Path) -> str:
    """Get a hash of the current uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        diff_text = result.stdout.strip()
        if not diff_text:
            # Also check staged changes
            result = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            diff_text = result.stdout.strip()

        if not diff_text:
            return ""

        return hashlib.sha256(diff_text.encode()).hexdigest()[:16]
    except Exception:
        return ""


def _get_changed_files(working_dir: Path) -> list[str]:
    """Get list of changed files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        if not files:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        return files
    except Exception:
        return []
