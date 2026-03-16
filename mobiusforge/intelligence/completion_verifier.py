"""Completion verifier — checks if agent truly finished the task (FR-013)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mobiusforge.memory.state import Task

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    complete: bool
    missing_items: list[str]
    confidence: float  # 0.0 - 1.0

    @property
    def summary(self) -> str:
        if self.complete:
            return f"COMPLETE (confidence: {self.confidence:.0%})"
        missing = ", ".join(self.missing_items[:3])
        return f"INCOMPLETE — missing: {missing}"


def verify_completion(
    task: Task,
    spec: str,
    working_dir: Path,
    test_command: str = "pytest",
) -> VerificationResult:
    """Verify that a task is truly complete by checking against spec criteria."""
    missing: list[str] = []
    checks_total = 0
    checks_passed = 0

    # 1. Check that tests pass
    checks_total += 1
    try:
        result = subprocess.run(
            test_command,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            checks_passed += 1
        else:
            missing.append("Tests failing")
    except (subprocess.TimeoutExpired, Exception):
        missing.append("Tests could not be run")

    # 2. Check that task-related files exist (heuristic)
    if spec:
        # Check for mentioned file patterns
        file_indicators = _extract_file_indicators(spec)
        for indicator in file_indicators:
            checks_total += 1
            matches = list(working_dir.glob(indicator))
            if matches:
                checks_passed += 1
            else:
                missing.append(f"Expected file pattern: {indicator}")

        # Check for mentioned endpoints/functions (heuristic via grep)
        function_indicators = _extract_function_indicators(spec)
        for func_name in function_indicators:
            checks_total += 1
            try:
                grep = subprocess.run(
                    ["grep", "-r", func_name, "--include=*.py", "--include=*.ts",
                     "--include=*.js", "-l"],
                    cwd=working_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if grep.stdout.strip():
                    checks_passed += 1
                else:
                    missing.append(f"Expected implementation: {func_name}")
            except Exception:
                pass

    if checks_total == 0:
        # No spec to verify against — trust the agent
        return VerificationResult(complete=True, missing_items=[], confidence=0.5)

    confidence = checks_passed / checks_total
    complete = confidence >= 0.7 and "Tests failing" not in missing

    logger.info(
        "Completion check for %s: %d/%d passed (%.0f%%) — %s",
        task.id, checks_passed, checks_total, confidence * 100,
        "COMPLETE" if complete else "INCOMPLETE",
    )

    return VerificationResult(
        complete=complete,
        missing_items=missing,
        confidence=confidence,
    )


def _extract_file_indicators(spec: str) -> list[str]:
    """Extract file path patterns from spec text."""
    indicators: list[str] = []
    import re

    # Match patterns like `src/api/auth.py` or `components/Login.tsx`
    file_pattern = re.compile(r"`([a-zA-Z0-9_/\-]+\.\w{1,5})`")
    for match in file_pattern.finditer(spec):
        path = match.group(1)
        # Convert to glob pattern
        indicators.append(f"**/{path}")

    return indicators[:5]  # Limit to avoid too many checks


def _extract_function_indicators(spec: str) -> list[str]:
    """Extract function/endpoint names from spec text."""
    indicators: list[str] = []
    import re

    # Match function-like patterns: def xxx, function xxx, export xxx
    func_pattern = re.compile(r"(?:def|function|export)\s+(\w+)")
    for match in func_pattern.finditer(spec):
        indicators.append(match.group(1))

    # Match API endpoint paths like POST /api/auth/login
    endpoint_pattern = re.compile(r"(?:GET|POST|PUT|DELETE|PATCH)\s+/\w+/(\w+)")
    for match in endpoint_pattern.finditer(spec):
        indicators.append(match.group(1))

    return indicators[:5]
