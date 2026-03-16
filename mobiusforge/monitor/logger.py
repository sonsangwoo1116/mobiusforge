"""Structured activity logger with secret masking (FR-023)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"sk-ant-[a-zA-Z0-9\-_]{20,}"),  # Anthropic API keys
    re.compile(r"sk-proj-[a-zA-Z0-9\-_]{20,}"),  # OpenAI project keys
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),           # Generic sk- keys
    re.compile(r"ghp_[a-zA-Z0-9]{36,}"),           # GitHub PAT
    re.compile(r"Bearer\s+[a-zA-Z0-9\-_.]{20,}"),  # Bearer tokens
]


def mask_secrets(text: str) -> str:
    """Replace API key patterns with [MASKED]."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[MASKED]", text)
    return text


class ActivityLogger:
    """Logs all agent activities to structured JSON files (FR-023)."""

    def __init__(self, log_dir: Path, mask: bool = True) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.mask = mask
        self._entries: list[dict] = []

    def log(self, event: str, loop: int = 0, task_id: str = "", **kwargs: object) -> None:
        """Log an activity event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event,
            "loop": loop,
            "task_id": task_id,
            **kwargs,
        }

        if self.mask:
            entry = _mask_dict(entry)

        self._entries.append(entry)
        logging.getLogger("mobiusforge.activity").info(
            "[Loop %d] %s %s", loop, event, task_id,
        )

    def log_agent_run(
        self, loop: int, task_id: str, prompt_length: int,
        output_length: int, tokens_in: int, tokens_out: int,
        cost: float, duration: float, success: bool,
    ) -> None:
        self.log(
            "agent_run", loop=loop, task_id=task_id,
            prompt_length=prompt_length, output_length=output_length,
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost=round(cost, 4), duration=round(duration, 1),
            success=success,
        )

    def log_validation(self, loop: int, task_id: str, passed: bool, summary: str) -> None:
        self.log("validation", loop=loop, task_id=task_id, passed=passed, summary=summary)

    def log_oscillation(self, loop: int, task_id: str, files: list[str]) -> None:
        self.log("oscillation_detected", loop=loop, task_id=task_id, files=files)

    def log_drift(self, loop: int, task_id: str, score: float, files: list[str]) -> None:
        self.log("drift_detected", loop=loop, task_id=task_id, score=score, files=files)

    def log_strategy_rotation(self, loop: int, task_id: str, attempt: int, hint: str) -> None:
        self.log("strategy_rotation", loop=loop, task_id=task_id, attempt=attempt, hint=hint[:200])

    def log_task_complete(self, loop: int, task_id: str, loops_taken: int) -> None:
        self.log("task_complete", loop=loop, task_id=task_id, loops_taken=loops_taken)

    def log_task_blocked(self, loop: int, task_id: str, reason: str) -> None:
        self.log("task_blocked", loop=loop, task_id=task_id, reason=reason)

    def save(self) -> None:
        """Persist activity log to disk."""
        if not self._entries:
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.log_dir / f"activity_{ts}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for entry in self._entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def save_raw_output(self, loop: int, task_id: str, output: str) -> None:
        """Save raw agent output for debugging."""
        raw_dir = self.log_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        text = mask_secrets(output) if self.mask else output
        path = raw_dir / f"loop_{loop:04d}_{task_id}.txt"
        path.write_text(text, encoding="utf-8")


def _mask_dict(data: dict) -> dict:
    """Recursively mask secrets in a dict."""
    masked = {}
    for key, value in data.items():
        if isinstance(value, str):
            masked[key] = mask_secrets(value)
        elif isinstance(value, dict):
            masked[key] = _mask_dict(value)
        elif isinstance(value, list):
            masked[key] = [mask_secrets(v) if isinstance(v, str) else v for v in value]
        else:
            masked[key] = value
    return masked
