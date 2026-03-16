"""Auto validator — runs tests and lint checks (FR-004)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    tests_passed: bool
    lint_passed: bool
    test_output: str = ""
    lint_output: str = ""

    @property
    def passed(self) -> bool:
        return self.tests_passed and self.lint_passed

    @property
    def summary(self) -> str:
        parts = []
        if self.tests_passed:
            parts.append("tests: PASS")
        else:
            parts.append("tests: FAIL")
        if self.lint_passed:
            parts.append("lint: PASS")
        else:
            parts.append("lint: FAIL")
        return " | ".join(parts)


def _run_command(cmd: str, working_dir: Path, timeout: int = 120) -> tuple[bool, str]:
    """Run a shell command and return (success, output)."""
    if not cmd.strip():
        return True, ""

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
        output = proc.stdout + proc.stderr
        # Truncate large output to save context
        if len(output) > 2000:
            output = output[:1000] + "\n...[truncated]...\n" + output[-1000:]
        return proc.returncode == 0, output

    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s: {cmd}"
    except Exception as e:
        return False, f"Command failed: {e}"


def validate(
    working_dir: Path,
    test_command: str = "pytest",
    lint_command: str = "ruff check .",
) -> ValidationResult:
    """Run test and lint commands, return results (FR-004)."""
    logger.info("Running validation: tests='%s', lint='%s'", test_command, lint_command)

    tests_ok, test_out = _run_command(test_command, working_dir)
    lint_ok, lint_out = _run_command(lint_command, working_dir)

    result = ValidationResult(
        tests_passed=tests_ok,
        lint_passed=lint_ok,
        test_output=test_out,
        lint_output=lint_out,
    )

    logger.info("Validation: %s", result.summary)
    return result
