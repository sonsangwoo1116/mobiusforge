"""Agent runner — executes Claude Code CLI and parses JSON output (FR-001, FR-005)."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from mobiusforge.config import AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    success: bool
    output: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    duration_seconds: float = 0.0
    error: str = ""


def run_agent(
    prompt: str,
    agent_config: AgentConfig,
    working_dir: Path,
    timeout: int = 600,
    cost_per_1k_input: float = 0.003,
    cost_per_1k_output: float = 0.015,
) -> AgentResult:
    """Run Claude Code CLI with the given prompt and return parsed result."""
    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "json",
        "--model", agent_config.model,
    ]

    # Add allowed tools
    if agent_config.allowed_tools:
        cmd.extend(["--allowedTools", ",".join(agent_config.allowed_tools)])

    logger.info("Running agent: claude -p <prompt> --output-format json")
    start_time = time.monotonic()

    try:
        proc = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
        duration = time.monotonic() - start_time

        if proc.returncode != 0:
            return AgentResult(
                success=False,
                output=proc.stdout,
                duration_seconds=duration,
                error=proc.stderr[:500] if proc.stderr else f"Exit code {proc.returncode}",
            )

        # Parse JSON output for token usage
        input_tokens = 0
        output_tokens = 0
        text_output = proc.stdout

        try:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, dict):
                text_output = parsed.get("result", parsed.get("content", proc.stdout))
                usage = parsed.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
        except json.JSONDecodeError:
            # Non-JSON output, use raw text
            pass

        cost = (input_tokens / 1000 * cost_per_1k_input) + (
            output_tokens / 1000 * cost_per_1k_output
        )

        return AgentResult(
            success=True,
            output=str(text_output),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start_time
        return AgentResult(
            success=False,
            output="",
            duration_seconds=duration,
            error=f"Timeout after {timeout}s",
        )
    except FileNotFoundError:
        return AgentResult(
            success=False,
            output="",
            error="Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code",
        )


def auto_commit(working_dir: Path, message: str) -> bool:
    """Auto git add + commit (FR-005)."""
    try:
        # Check for changes
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            logger.info("No changes to commit")
            return True

        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=working_dir,
            check=True,
        )

        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=working_dir,
            check=True,
            capture_output=True,
        )
        logger.info("Committed: %s", message)
        return True

    except subprocess.CalledProcessError as e:
        logger.error("Commit failed: %s", e)
        return False
