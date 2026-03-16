"""TUI Dashboard for MobiusForge (FR-020).

Uses Rich for a lightweight, non-blocking live display.
Textual-based full TUI is optional (requires `pip install mobiusforge[tui]`).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def run_dashboard(working_dir: Path, refresh_rate: float = 2.0) -> None:
    """Run a live Rich dashboard that refreshes periodically."""
    if not HAS_RICH:
        print("Rich not installed. Install with: pip install mobiusforge[tui]")
        print("Falling back to simple status display...\n")
        _simple_dashboard(working_dir)
        return

    console = Console()

    try:
        with Live(console=console, refresh_per_second=1 / refresh_rate, screen=True) as live:
            while True:
                layout = _build_layout(working_dir)
                live.update(layout)
                time.sleep(refresh_rate)
    except KeyboardInterrupt:
        console.print("\n[bold]Dashboard closed.[/bold]")


def _build_layout(working_dir: Path) -> Layout:
    """Build the dashboard layout from current state files."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="tasks", ratio=2),
        Layout(name="sidebar"),
    )
    layout["sidebar"].split_column(
        Layout(name="budget"),
        Layout(name="lessons"),
    )

    # Header
    layout["header"].update(
        Panel(Text("MobiusForge Dashboard", style="bold cyan", justify="center"), style="cyan")
    )

    # Tasks
    layout["tasks"].update(_build_tasks_panel(working_dir))

    # Budget
    layout["budget"].update(_build_budget_panel(working_dir))

    # Lessons
    layout["lessons"].update(_build_lessons_panel(working_dir))

    # Footer
    elapsed = _get_elapsed(working_dir)
    layout["footer"].update(
        Panel(f"Elapsed: {elapsed} | Press Ctrl+C to exit", style="dim")
    )

    return layout


def _build_tasks_panel(working_dir: Path) -> Panel:
    """Build the tasks status table."""
    table = Table(title="Tasks", expand=True)
    table.add_column("ID", style="cyan", width=8)
    table.add_column("Title", ratio=2)
    table.add_column("Status", width=14)
    table.add_column("Loops", width=6, justify="right")

    plan_path = working_dir / "task_plan.md"
    if plan_path.exists():
        from mobiusforge.memory.state import TaskPlan
        plan = TaskPlan(plan_path)
        for task in plan.tasks:
            status_style = {
                "DONE": "green",
                "IN_PROGRESS": "yellow",
                "OPEN": "dim",
                "BLOCKED": "red",
                "INTERRUPTED": "magenta",
            }.get(task.status.value, "white")

            table.add_row(
                task.id,
                task.title[:40],
                f"[{status_style}]{task.status.value}[/{status_style}]",
                str(task.loops_taken) if task.loops_taken else "-",
            )

    return Panel(table, title="Task Progress", border_style="blue")


def _build_budget_panel(working_dir: Path) -> Panel:
    """Build the budget/cost panel."""
    budget_path = working_dir / ".mobiusforge" / "budget.json"

    if budget_path.exists():
        try:
            data = json.loads(budget_path.read_text(encoding="utf-8"))
            summary = data.get("summary", {})
            cost = summary.get("total_cost", 0)
            limit = summary.get("budget_limit", 50)
            pct = summary.get("budget_percent_used", 0)
            loops = summary.get("loops_recorded", 0)
            tokens_in = summary.get("total_input_tokens", 0)
            tokens_out = summary.get("total_output_tokens", 0)

            bar_len = 20
            filled = int(bar_len * pct / 100)
            bar_char = "█" * filled + "░" * (bar_len - filled)

            color = "green" if pct < 60 else "yellow" if pct < 80 else "red"

            text = (
                f"Cost: ${cost:.2f} / ${limit:.2f}\n"
                f"[{color}]{bar_char}[/{color}] {pct:.1f}%\n"
                f"Loops: {loops}\n"
                f"Tokens: {tokens_in:,} in / {tokens_out:,} out"
            )
            return Panel(text, title="Budget", border_style="green")
        except Exception:
            pass

    return Panel("No budget data yet", title="Budget", border_style="green")


def _build_lessons_panel(working_dir: Path) -> Panel:
    """Build the recent lessons panel."""
    lessons_path = working_dir / ".mobiusforge" / "lessons.md"
    if lessons_path.exists():
        from mobiusforge.memory.lessons import LessonsManager
        mgr = LessonsManager(lessons_path)
        recent = mgr.lessons[-5:]  # Last 5

        if recent:
            lines = []
            for lesson in recent:
                icon = "[red]✗[/red]" if lesson.outcome == "FAIL" else "[green]✓[/green]"
                lines.append(f"{icon} L{lesson.loop_number}: {lesson.lesson[:50]}")
            return Panel("\n".join(lines), title="Recent Lessons", border_style="yellow")

    return Panel("No lessons yet", title="Recent Lessons", border_style="yellow")


def _get_elapsed(working_dir: Path) -> str:
    """Get elapsed time from budget history."""
    budget_path = working_dir / ".mobiusforge" / "budget.json"
    if budget_path.exists():
        try:
            data = json.loads(budget_path.read_text(encoding="utf-8"))
            history = data.get("history", [])
            if history:
                first_ts = history[0].get("timestamp", "")
                last_ts = history[-1].get("timestamp", "")
                return f"{first_ts[:19]} → {last_ts[:19]}"
        except Exception:
            pass
    return "Not started"


def _simple_dashboard(working_dir: Path) -> None:
    """Fallback dashboard without Rich."""
    from mobiusforge.memory.state import TaskPlan

    plan_path = working_dir / "task_plan.md"
    if plan_path.exists():
        plan = TaskPlan(plan_path)
        print("=== Tasks ===")
        for task in plan.tasks:
            print(f"  [{task.status.value:14s}] {task.id}: {task.title}")
        print(f"\nSummary: {plan.summary()}")

    budget_path = working_dir / ".mobiusforge" / "budget.json"
    if budget_path.exists():
        data = json.loads(budget_path.read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        print("\n=== Budget ===")
        print(f"  Cost: ${summary.get('total_cost', 0):.2f} / ${summary.get('budget_limit', 50)}")
        print(f"  Loops: {summary.get('loops_recorded', 0)}")
