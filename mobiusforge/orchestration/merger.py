"""Worktree merger — merges parallel branches back to main (FR-018)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    success: bool
    branch: str
    conflicts: list[str] | None = None
    error: str = ""


def merge_branch(working_dir: Path, branch_name: str) -> MergeResult:
    """Merge a worktree branch back into the current branch."""
    try:
        result = subprocess.run(
            ["git", "merge", branch_name, "--no-edit",
             "-m", f"merge: {branch_name} (MobiusForge parallel)"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            logger.info("Merged %s successfully", branch_name)
            return MergeResult(success=True, branch=branch_name)

        # Check for conflicts
        if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
            conflicts = _get_conflict_files(working_dir)
            logger.warning("Merge conflicts in %s: %s", branch_name, conflicts)

            # Abort the merge
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=working_dir,
                capture_output=True,
                timeout=10,
            )

            return MergeResult(
                success=False,
                branch=branch_name,
                conflicts=conflicts,
                error="Merge conflicts detected",
            )

        return MergeResult(
            success=False,
            branch=branch_name,
            error=result.stderr[:300],
        )

    except subprocess.CalledProcessError as e:
        return MergeResult(success=False, branch=branch_name, error=str(e))
    except subprocess.TimeoutExpired:
        return MergeResult(success=False, branch=branch_name, error="Merge timed out")


def merge_all_sequential(working_dir: Path, branches: list[str]) -> list[MergeResult]:
    """Merge multiple branches sequentially (safest approach)."""
    results = []
    for branch in branches:
        result = merge_branch(working_dir, branch)
        results.append(result)
        if not result.success:
            logger.warning("Stopping sequential merge at %s due to failure", branch)
            break
    return results


def cleanup_branch(working_dir: Path, branch_name: str) -> None:
    """Delete a merged branch."""
    try:
        subprocess.run(
            ["git", "branch", "-d", branch_name],
            cwd=working_dir,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass


def _get_conflict_files(working_dir: Path) -> list[str]:
    """Get list of files with merge conflicts."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []
