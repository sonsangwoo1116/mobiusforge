"""Budget guard and token/cost tracker (FR-021, FR-022)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LoopCost:
    loop_number: int
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: str


@dataclass
class BudgetTracker:
    max_total_cost: float = 50.0
    warn_at_percent: int = 80
    cost_per_1k_input: float = 0.003
    cost_per_1k_output: float = 0.015
    history: list[LoopCost] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(h.cost for h in self.history)

    @property
    def total_input_tokens(self) -> int:
        return sum(h.input_tokens for h in self.history)

    @property
    def total_output_tokens(self) -> int:
        return sum(h.output_tokens for h in self.history)

    @property
    def budget_remaining(self) -> float:
        return self.max_total_cost - self.total_cost

    @property
    def budget_percent_used(self) -> float:
        if self.max_total_cost <= 0:
            return 100.0
        return (self.total_cost / self.max_total_cost) * 100

    def record(self, loop_number: int, input_tokens: int, output_tokens: int, cost: float) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.history.append(LoopCost(loop_number, input_tokens, output_tokens, cost, ts))
        logger.info(
            "Loop %d cost: $%.4f (tokens: %d in, %d out) | Total: $%.2f / $%.2f",
            loop_number, cost, input_tokens, output_tokens,
            self.total_cost, self.max_total_cost,
        )

    def check_budget(self) -> BudgetStatus:
        """Check if budget allows continuing (FR-022)."""
        pct = self.budget_percent_used

        if pct >= 100:
            return BudgetStatus.EXCEEDED
        if pct >= self.warn_at_percent:
            return BudgetStatus.WARNING
        return BudgetStatus.OK

    def summary(self) -> dict:
        return {
            "total_cost": round(self.total_cost, 4),
            "budget_limit": self.max_total_cost,
            "budget_remaining": round(self.budget_remaining, 4),
            "budget_percent_used": round(self.budget_percent_used, 1),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "loops_recorded": len(self.history),
        }

    def save(self, path: Path) -> None:
        data = {
            "config": {
                "max_total_cost": self.max_total_cost,
                "warn_at_percent": self.warn_at_percent,
            },
            "summary": self.summary(),
            "history": [
                {
                    "loop": h.loop_number,
                    "input_tokens": h.input_tokens,
                    "output_tokens": h.output_tokens,
                    "cost": h.cost,
                    "timestamp": h.timestamp,
                }
                for h in self.history
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, max_cost: float = 50.0, warn_pct: int = 80) -> BudgetTracker:
        tracker = cls(max_total_cost=max_cost, warn_at_percent=warn_pct)
        if not path.exists():
            return tracker
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for h in data.get("history", []):
                tracker.history.append(
                    LoopCost(h["loop"], h["input_tokens"], h["output_tokens"],
                             h["cost"], h["timestamp"])
                )
        except Exception as e:
            logger.warning("Failed to load budget history: %s", e)
        return tracker


class BudgetStatus:
    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"
