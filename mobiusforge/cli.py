"""MobiusForge CLI — command-line interface (Click)."""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path

import click

from mobiusforge import __version__
from mobiusforge.config import load_config


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.version_option(__version__, prog_name="mobiusforge")
def cli() -> None:
    """MobiusForge — Autonomous Agent Harness."""


@cli.command()
@click.option("--from-prd", type=click.Path(exists=True), help="Generate specs from PRD")
@click.option("--path", type=click.Path(), default=".", help="Project path")
def init(from_prd: str | None, path: str) -> None:
    """Initialize MobiusForge in a project directory."""
    project_dir = Path(path).resolve()
    mf_dir = project_dir / ".mobiusforge"
    mf_dir.mkdir(parents=True, exist_ok=True)
    (mf_dir / "logs").mkdir(exist_ok=True)

    templates_dir = Path(__file__).parent.parent / "templates"

    # Copy config template
    config_dest = project_dir / "config.yaml"
    if not config_dest.exists():
        tmpl = templates_dir / "config.yaml.tmpl"
        if tmpl.exists():
            shutil.copy(tmpl, config_dest)
        else:
            _write_default_config(config_dest)
        click.echo(f"Created: {config_dest}")

    # Copy task plan template
    plan_dest = project_dir / "task_plan.md"
    if not plan_dest.exists():
        tmpl = templates_dir / "task_plan.md.tmpl"
        if tmpl.exists():
            shutil.copy(tmpl, plan_dest)
        else:
            plan_dest.write_text("# Task Plan\n\n## Current Sprint\n", encoding="utf-8")
        click.echo(f"Created: {plan_dest}")

    # Create specs dir
    specs_dir = project_dir / "specs"
    specs_dir.mkdir(exist_ok=True)
    click.echo(f"Created: {specs_dir}/")

    # Create PROMPT.md placeholder
    prompt_dest = project_dir / "PROMPT.md"
    if not prompt_dest.exists():
        prompt_dest.write_text(
            "# Project\n\n"
            "## Overview\n[Describe your project here]\n\n"
            "## Tech Stack\n- Language: Python 3.12\n- Test: pytest\n\n"
            "## Coding Conventions\n- Use snake_case\n- Max file size: 300 lines\n\n"
            "## Do NOT\n- Use print() for debugging (use logger)\n"
            "- Hardcode secrets\n- Skip tests\n",
            encoding="utf-8",
        )
        click.echo(f"Created: {prompt_dest}")

    # Create lessons.md
    lessons_dest = mf_dir / "lessons.md"
    if not lessons_dest.exists():
        lessons_dest.write_text("# Lessons Learned\n", encoding="utf-8")

    # Create .gitignore additions
    gitignore = project_dir / ".gitignore"
    ignore_lines = [
        ".mobiusforge/logs/",
        ".mobiusforge/raw/",
        ".mobiusforge/budget.json",
        ".env",
        "__pycache__/",
    ]
    if gitignore.exists():
        existing = gitignore.read_text()
        new_lines = [line for line in ignore_lines if line not in existing]
        if new_lines:
            with open(gitignore, "a") as f:
                f.write("\n# MobiusForge\n")
                for line in new_lines:
                    f.write(f"{line}\n")
    else:
        gitignore.write_text(
            "# MobiusForge\n" + "\n".join(ignore_lines) + "\n",
            encoding="utf-8",
        )

    click.echo(f"\nMobiusForge initialized in {project_dir}")
    click.echo("Next: Edit config.yaml, PROMPT.md, and add specs/ files")


@cli.command()
@click.option("--config", "config_path", type=click.Path(), default="config.yaml")
@click.option("--budget", type=float, help="Override budget limit ($)")
@click.option("--max-loops", type=int, help="Override max loop iterations")
@click.option("--end-time", type=str, help="Absolute end time (ISO 8601)")
@click.option("--dry-run", is_flag=True, help="Simulate without running agent")
@click.option("--log-level", type=str, default="INFO")
def start(
    config_path: str,
    budget: float | None,
    max_loops: int | None,
    end_time: str | None,
    dry_run: bool,
    log_level: str,
) -> None:
    """Start the Mobius Loop — autonomous agent execution."""
    _setup_logging(log_level)

    config = load_config(Path(config_path))

    # Apply CLI overrides
    if budget is not None:
        config.budget.max_total_cost = budget
    if max_loops is not None:
        config.loop.max_iterations = max_loops
    if end_time is not None:
        config.loop.end_time = end_time

    working_dir = Path(config.project.path).resolve()

    if not (working_dir / "task_plan.md").exists():
        click.echo("Error: task_plan.md not found. Run 'mobiusforge init' first.", err=True)
        sys.exit(1)

    if dry_run:
        _run_dry_run(config, working_dir)
        return

    from mobiusforge.core.loop import MobiusLoop

    loop = MobiusLoop(config, working_dir)
    summary = loop.run()

    click.echo(f"\n{summary}")


@cli.command()
@click.option("--config", "config_path", type=click.Path(), default="config.yaml")
def status(config_path: str) -> None:
    """Show current MobiusForge status."""
    config = load_config(Path(config_path))
    working_dir = Path(config.project.path).resolve()

    from mobiusforge.memory.state import TaskPlan
    from mobiusforge.safety.budget import BudgetTracker

    plan = TaskPlan(working_dir / "task_plan.md")
    budget = BudgetTracker.load(working_dir / ".mobiusforge" / "budget.json")

    click.echo("=== MobiusForge Status ===\n")

    # Task summary
    summary = plan.summary()
    click.echo("Tasks:")
    for status_name, count in summary.items():
        click.echo(f"  {status_name}: {count}")

    # Budget
    click.echo(f"\nBudget: ${budget.total_cost:.2f} / ${budget.max_total_cost:.2f} "
               f"({budget.budget_percent_used:.1f}%)")

    # Next task
    next_task = plan.get_next_task()
    if next_task:
        click.echo(f"\nNext task: {next_task.id} — {next_task.title}")
    else:
        click.echo("\nNo actionable tasks")


@cli.command()
@click.option("--config", "config_path", type=click.Path(), default="config.yaml")
def cost(config_path: str) -> None:
    """Show cost report."""
    config = load_config(Path(config_path))
    working_dir = Path(config.project.path).resolve()

    from mobiusforge.safety.budget import BudgetTracker

    budget = BudgetTracker.load(working_dir / ".mobiusforge" / "budget.json")
    click.echo(json.dumps(budget.summary(), indent=2))


@cli.command()
@click.option("--config", "config_path", type=click.Path(), default="config.yaml")
def lessons(config_path: str) -> None:
    """Show learned lessons."""
    config = load_config(Path(config_path))
    working_dir = Path(config.project.path).resolve()

    lessons_path = working_dir / ".mobiusforge" / "lessons.md"
    if lessons_path.exists():
        click.echo(lessons_path.read_text(encoding="utf-8"))
    else:
        click.echo("No lessons learned yet.")


@cli.command()
@click.option("--config", "config_path", type=click.Path(), default="config.yaml")
def dashboard(config_path: str) -> None:
    """Open the live TUI dashboard."""
    config = load_config(Path(config_path))
    working_dir = Path(config.project.path).resolve()

    from mobiusforge.monitor.dashboard import run_dashboard

    run_dashboard(working_dir)


@cli.command()
@click.option("--config", "config_path", type=click.Path(), default="config.yaml")
def dag(config_path: str) -> None:
    """Visualize task dependency graph."""
    config = load_config(Path(config_path))
    working_dir = Path(config.project.path).resolve()

    from mobiusforge.memory.state import TaskPlan
    from mobiusforge.orchestration.dag import TaskDAG

    plan = TaskPlan(working_dir / "task_plan.md")
    task_dag = TaskDAG(plan)
    click.echo(task_dag.visualize())

    parallel = task_dag.get_parallel_groups()
    if parallel:
        click.echo(f"\nParallel opportunities: {len(parallel)} layers")
        for i, layer in enumerate(parallel):
            if len(layer) > 1:
                names = ", ".join(t.id for t in layer)
                click.echo(f"  Layer {i + 1}: {names} can run simultaneously")


def _run_dry_run(config, working_dir: Path) -> None:
    """Simulate the loop without actually running the agent."""
    from mobiusforge.memory.state import TaskPlan

    click.echo("=== DRY RUN ===\n")

    plan = TaskPlan(working_dir / "task_plan.md")
    specs_dir = working_dir / "specs"

    click.echo(f"Tasks found: {len(plan.tasks)}")
    click.echo(f"Task summary: {plan.summary()}")
    click.echo(f"Specs dir exists: {specs_dir.exists()}")
    if specs_dir.exists():
        specs = list(specs_dir.glob("*.md"))
        click.echo(f"Spec files: {len(specs)}")
        for s in specs:
            click.echo(f"  - {s.name}")

    click.echo("\nConfig:")
    click.echo(f"  Model: {config.agent.model}")
    click.echo(f"  Max loops: {config.loop.max_iterations}")
    click.echo(f"  Budget: ${config.budget.max_total_cost}")
    click.echo(f"  Loop timeout: {config.agent.timeout_per_loop}s")
    click.echo(f"  End time: {config.loop.end_time or 'not set'}")

    # Simulate task order
    click.echo("\nExecution order:")
    done_ids: set[str] = set()
    order = 0
    while True:
        next_task = plan.get_next_task()
        if next_task is None:
            break
        order += 1
        click.echo(f"  {order}. {next_task.id}: {next_task.title} [{next_task.priority}]")
        # Simulate completion to see next
        plan.update_task(next_task.id, status="DONE")
        done_ids.add(next_task.id)

    # Estimate cost
    estimated_loops = order * 2  # ~2 loops per task average
    est_tokens = estimated_loops * 30000  # ~30k tokens per loop
    est_cost = (est_tokens / 1000 * config.budget.cost_per_1k_input +
                est_tokens / 1000 * 0.3 * config.budget.cost_per_1k_output)
    click.echo("\nEstimates (rough):")
    click.echo(f"  Loops: ~{estimated_loops}")
    click.echo(f"  Tokens: ~{est_tokens:,}")
    click.echo(f"  Cost: ~${est_cost:.2f}")

    click.echo("\n=== DRY RUN COMPLETE ===")


def _write_default_config(path: Path) -> None:
    """Write default config.yaml."""
    content = """# MobiusForge Configuration
project:
  name: "my-project"
  path: "."

agent:
  type: "claude-code"
  model: "claude-sonnet-4-6"
  timeout_per_loop: 600
  permission_mode: "dontAsk"
  allowed_tools:
    - Read
    - Write
    - Edit
    - Bash
    - Glob
    - Grep

loop:
  max_iterations: 100
  max_parallel_agents: 2
  cooldown_seconds: 5
  max_total_time: 43200
  end_time: ""
  wind_down_minutes: 30

budget:
  max_total_cost: 50.0
  warn_at_percent: 80
  cost_per_1k_input: 0.003
  cost_per_1k_output: 0.015

validation:
  test_command: "pytest"
  lint_command: "ruff check ."
  auto_commit: true
  auto_rollback: true
  completion_verify: true

safety:
  oscillation_threshold: 3
  oscillation_window: 5
  max_strategy_retries: 3
  dead_end_action: "skip"
  drift_check_interval: 5
  drift_threshold: 0.7

memory:
  max_lessons: 30
  prune_strategy: "relevance_decay"
  use_claude_memory: true

monitoring:
  dashboard: true
  log_level: "INFO"
  save_raw_output: true
  mask_secrets: true
"""
    path.write_text(content, encoding="utf-8")
