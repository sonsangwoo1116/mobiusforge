"""Rollback guard — auto git rollback on validation failure (FR-027)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def get_last_commit_hash(working_dir: Path) -> str | None:
    """Get the current HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def rollback_to(working_dir: Path, commit_hash: str) -> bool:
    """Rollback to a specific commit (FR-027)."""
    try:
        subprocess.run(
            ["git", "reset", "--hard", commit_hash],
            cwd=working_dir,
            check=True,
            capture_output=True,
        )
        logger.info("Rolled back to commit %s", commit_hash[:8])
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Rollback failed: %s", e)
        return False


def stash_changes(working_dir: Path, message: str = "mobiusforge-autostash") -> bool:
    """Stash uncommitted changes for graceful shutdown."""
    try:
        # Check if there are changes to stash
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            return True  # Nothing to stash

        subprocess.run(
            ["git", "stash", "push", "-m", message],
            cwd=working_dir,
            check=True,
            capture_output=True,
        )
        logger.info("Stashed changes: %s", message)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Stash failed: %s", e)
        return False
