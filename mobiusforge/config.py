"""Configuration loader for MobiusForge."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AgentConfig:
    type: str = "claude-code"
    model: str = "claude-sonnet-4-6"
    timeout_per_loop: int = 600
    permission_mode: str = "dontAsk"
    allowed_tools: list[str] = field(
        default_factory=lambda: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
    )


@dataclass
class LoopConfig:
    max_iterations: int = 100
    max_parallel_agents: int = 2
    cooldown_seconds: int = 5
    max_total_time: int = 43200  # 12 hours
    end_time: str = ""  # ISO 8601
    wind_down_minutes: int = 30


@dataclass
class BudgetConfig:
    max_total_cost: float = 50.0
    warn_at_percent: int = 80
    cost_per_1k_input: float = 0.003
    cost_per_1k_output: float = 0.015


@dataclass
class ValidationConfig:
    test_command: str = "pytest"
    lint_command: str = "ruff check ."
    auto_commit: bool = True
    auto_rollback: bool = True
    completion_verify: bool = True


@dataclass
class SafetyConfig:
    oscillation_threshold: int = 3
    oscillation_window: int = 5
    max_strategy_retries: int = 3
    dead_end_action: str = "skip"  # skip | pause | abort
    drift_check_interval: int = 5
    drift_threshold: float = 0.7


@dataclass
class MemoryConfig:
    max_lessons: int = 30
    prune_strategy: str = "relevance_decay"  # relevance_decay | fifo
    use_claude_memory: bool = True


@dataclass
class MonitoringConfig:
    dashboard: bool = True
    log_level: str = "INFO"
    save_raw_output: bool = True
    mask_secrets: bool = True


@dataclass
class ProjectConfig:
    name: str = "my-project"
    path: str = "./workspace"


@dataclass
class MobiusConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)


def _merge_dict(target: Any, source: dict) -> None:
    """Merge a dict into a dataclass instance."""
    for key, value in source.items():
        if hasattr(target, key):
            setattr(target, key, value)


def load_config(config_path: Path | None = None) -> MobiusConfig:
    """Load configuration from YAML file, falling back to defaults."""
    cfg = MobiusConfig()

    if config_path is None:
        config_path = Path("config.yaml")

    if not config_path.exists():
        return cfg

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    section_map = {
        "project": cfg.project,
        "agent": cfg.agent,
        "loop": cfg.loop,
        "budget": cfg.budget,
        "validation": cfg.validation,
        "safety": cfg.safety,
        "memory": cfg.memory,
        "monitoring": cfg.monitoring,
    }

    for section_name, section_obj in section_map.items():
        if section_name in raw and isinstance(raw[section_name], dict):
            _merge_dict(section_obj, raw[section_name])

    # Override with environment variables
    if env_model := os.environ.get("MOBIUSFORGE_MODEL"):
        cfg.agent.model = env_model
    if env_budget := os.environ.get("MOBIUSFORGE_BUDGET"):
        cfg.budget.max_total_cost = float(env_budget)

    return cfg
