"""Mobius Loop Engine — the core execution loop (FR-001)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from mobiusforge.config import MobiusConfig
from mobiusforge.core.prompt_assembler import assemble_prompt, load_spec
from mobiusforge.core.runner import auto_commit, run_agent
from mobiusforge.core.validator import validate
from mobiusforge.intelligence.completion_verifier import verify_completion
from mobiusforge.intelligence.drift_detector import detect_drift
from mobiusforge.intelligence.oscillation import OscillationDetector
from mobiusforge.intelligence.strategy_rotator import StrategyRotation
from mobiusforge.memory.guardrails import GuardrailsManager
from mobiusforge.memory.lessons import LessonsManager
from mobiusforge.memory.state import Task, TaskPlan, TaskStatus
from mobiusforge.monitor.logger import ActivityLogger
from mobiusforge.safety.budget import BudgetStatus, BudgetTracker
from mobiusforge.safety.rollback import get_last_commit_hash, rollback_to
from mobiusforge.safety.shutdown import ShutdownHandler
from mobiusforge.safety.timeout import LoopGuard

logger = logging.getLogger(__name__)


class MobiusLoop:
    """The core autonomous execution loop."""

    def __init__(self, config: MobiusConfig, working_dir: Path) -> None:
        self.config = config
        self.working_dir = working_dir
        self.mobiusforge_dir = working_dir / ".mobiusforge"
        self.mobiusforge_dir.mkdir(parents=True, exist_ok=True)
        (self.mobiusforge_dir / "logs").mkdir(exist_ok=True)

        # State
        self.task_plan = TaskPlan(working_dir / "task_plan.md")
        self.lessons = LessonsManager(
            self.mobiusforge_dir / "lessons.md",
            max_lessons=config.memory.max_lessons,
        )
        self.budget = BudgetTracker.load(
            self.mobiusforge_dir / "budget.json",
            max_cost=config.budget.max_total_cost,
            warn_pct=config.budget.warn_at_percent,
        )

        # Guardrails (FR-011)
        self.guardrails_mgr = GuardrailsManager(self.mobiusforge_dir / "guardrails.md")
        self.guardrails_mgr.init_default()

        # Intelligence (Phase 2)
        self.oscillation = OscillationDetector(
            threshold=config.safety.oscillation_threshold,
            window_size=config.safety.oscillation_window,
        )
        self.strategy = StrategyRotation(
            max_retries=config.safety.max_strategy_retries,
            dead_end_action=config.safety.dead_end_action,
        )

        # Activity Logger (FR-023)
        self.activity = ActivityLogger(
            self.mobiusforge_dir / "logs",
            mask=config.monitoring.mask_secrets,
        )

        # Guards
        self.loop_guard = LoopGuard(
            max_iterations=config.loop.max_iterations,
            max_total_time=config.loop.max_total_time,
            end_time=config.loop.end_time,
            wind_down_minutes=config.loop.wind_down_minutes,
            loop_timeout=config.agent.timeout_per_loop,
        )
        self.shutdown = ShutdownHandler()

        # Load PROMPT.md
        prompt_path = working_dir / "PROMPT.md"
        self.prompt_md = ""
        if prompt_path.exists():
            self.prompt_md = prompt_path.read_text(encoding="utf-8")

        self.specs_dir = working_dir / "specs"

        # Track current task for oscillation reset
        self._current_task_id: str = ""

    def run(self) -> LoopSummary:
        """Execute the Mobius Loop until completion or termination."""
        self.shutdown.install()
        self.loop_guard.start()

        logger.info("=== MobiusForge started ===")
        logger.info("Project: %s | Max loops: %d | Budget: $%.2f",
                     self.config.project.name,
                     self.config.loop.max_iterations,
                     self.config.budget.max_total_cost)

        loops_run = 0
        tasks_completed = 0
        tasks_failed = 0

        try:
            while True:
                # --- Pre-loop guards ---
                can_go, reason = self.loop_guard.can_continue()
                if not can_go:
                    logger.info("Stopping: %s", reason)
                    break

                if self.shutdown.should_stop:
                    logger.info("Shutdown requested")
                    break

                budget_status = self.budget.check_budget()
                if budget_status == BudgetStatus.EXCEEDED:
                    logger.info("Budget exceeded ($%.2f / $%.2f)",
                                self.budget.total_cost, self.budget.max_total_cost)
                    break
                if budget_status == BudgetStatus.WARNING:
                    logger.warning("Budget warning: %.1f%% used",
                                   self.budget.budget_percent_used)

                if self.task_plan.all_done():
                    logger.info("All tasks completed!")
                    break

                # --- Select task ---
                task = self.task_plan.get_next_task()
                if task is None:
                    logger.info("No actionable tasks remaining")
                    break

                # Wind-down check: don't start new tasks
                if self.loop_guard.is_wind_down() and task.status == TaskStatus.OPEN:
                    logger.info("Wind-down mode — not starting new tasks")
                    break

                # Reset oscillation detector when switching tasks
                if task.id != self._current_task_id:
                    self.oscillation.reset()
                    self._current_task_id = task.id

                # Check dead-end before attempting (FR-008)
                if self.strategy.is_dead_end(task.id):
                    action = self.strategy.handle_dead_end(task, self.task_plan)
                    self.activity.log_task_blocked(
                        self.loop_guard.current_loop, task.id,
                        f"Dead end — action: {action}",
                    )
                    if action == "abort":
                        break
                    tasks_failed += 1
                    continue

                # --- Execute loop ---
                self.loop_guard.increment_loop()
                loop_num = self.loop_guard.current_loop
                loops_run += 1

                logger.info("--- Loop %d: %s [%s] ---", loop_num, task.id, task.title)

                result = self._execute_single_loop(task, loop_num)

                if result == LoopOutcome.COMPLETED:
                    tasks_completed += 1
                    self.activity.log_task_complete(loop_num, task.id, task.loops_taken)
                elif result == LoopOutcome.BLOCKED:
                    tasks_failed += 1

                # Cooldown between loops
                if self.config.loop.cooldown_seconds > 0:
                    time.sleep(self.config.loop.cooldown_seconds)

        finally:
            # Shutdown finalization
            self.shutdown.finalize(self.working_dir, self.task_plan)
            self.budget.save(self.mobiusforge_dir / "budget.json")
            self.activity.save()
            self.shutdown.uninstall()

        summary = LoopSummary(
            loops_run=loops_run,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            total_cost=self.budget.total_cost,
            elapsed_seconds=self.loop_guard.elapsed_seconds,
            task_summary=self.task_plan.summary(),
        )
        logger.info("=== MobiusForge finished === %s", summary)
        return summary

    def _execute_single_loop(self, task: Task, loop_num: int) -> LoopOutcome:
        """Execute one iteration of the Mobius Loop."""
        # Mark task in progress
        if task.status != TaskStatus.IN_PROGRESS:
            self.task_plan.mark_in_progress(task.id)
            task.loops_taken = 0

        task.loops_taken += 1

        # Save commit hash for potential rollback
        pre_commit = get_last_commit_hash(self.working_dir)

        # Assemble prompt with strategy rotation hints (FR-007)
        spec = load_spec(self.specs_dir, task)
        guardrails = self.guardrails_mgr.load()
        rotation_hint = self.strategy.get_rotation_hint(task.id)

        # Combine failed approaches from task_plan + strategy rotator
        failed_approaches = (
            task.failed_approaches
            + self.strategy.get_failed_approaches(task.id)
        )
        # Deduplicate
        seen: set[str] = set()
        unique_failed = []
        for fa in failed_approaches:
            if fa not in seen:
                seen.add(fa)
                unique_failed.append(fa)

        prompt = assemble_prompt(
            task=task,
            prompt_md=self.prompt_md,
            spec=spec,
            lessons_manager=self.lessons,
            guardrails=guardrails,
            failed_approaches=unique_failed if unique_failed else None,
        )

        # Inject rotation hint if applicable
        if rotation_hint:
            prompt = f"{rotation_hint}\n\n{prompt}"
            self.activity.log_strategy_rotation(
                loop_num, task.id,
                len(self.strategy.get_failed_approaches(task.id)) + 1,
                rotation_hint,
            )

        # Run agent
        agent_result = run_agent(
            prompt=prompt,
            agent_config=self.config.agent,
            working_dir=self.working_dir,
            timeout=self.config.agent.timeout_per_loop,
            cost_per_1k_input=self.config.budget.cost_per_1k_input,
            cost_per_1k_output=self.config.budget.cost_per_1k_output,
        )

        # Track cost
        self.budget.record(
            loop_num,
            agent_result.input_tokens,
            agent_result.output_tokens,
            agent_result.cost,
        )

        # Log agent run
        self.activity.log_agent_run(
            loop_num, task.id,
            prompt_length=len(prompt),
            output_length=len(agent_result.output),
            tokens_in=agent_result.input_tokens,
            tokens_out=agent_result.output_tokens,
            cost=agent_result.cost,
            duration=agent_result.duration_seconds,
            success=agent_result.success,
        )

        # Save raw output for debugging
        if self.config.monitoring.save_raw_output:
            self.activity.save_raw_output(loop_num, task.id, agent_result.output)

        if not agent_result.success:
            logger.error("Agent failed: %s", agent_result.error)
            self._handle_failure(loop_num, task, spec, agent_result.error)
            return LoopOutcome.FAILED

        # --- Oscillation check (FR-006) ---
        self.oscillation.record(loop_num, self.working_dir)
        osc_result = self.oscillation.detect()
        if osc_result.detected:
            self.activity.log_oscillation(loop_num, task.id, osc_result.oscillating_files)

            # Rollback and record failure
            if pre_commit:
                rollback_to(self.working_dir, pre_commit)

            approach_desc = (
                f"Oscillation on files: {', '.join(osc_result.oscillating_files[:3])}"
            )
            self.strategy.record_failure(task.id, approach_desc)
            self._record_lesson(
                loop_num, "FAIL", approach_desc,
                "Oscillation detected — strategy rotated", task, spec,
            )

            # Check if dead end after this failure
            if self.strategy.is_dead_end(task.id):
                action = self.strategy.handle_dead_end(task, self.task_plan)
                self.activity.log_task_blocked(loop_num, task.id, f"Dead end: {action}")
                return LoopOutcome.BLOCKED

            self.task_plan.update_task(task.id, loops_taken=task.loops_taken)
            return LoopOutcome.FAILED

        # --- Drift check (FR-014, FR-015) ---
        drift_interval = self.config.safety.drift_check_interval
        if drift_interval > 0 and loop_num % drift_interval == 0:
            drift = detect_drift(
                task, spec, self.working_dir,
                threshold=self.config.safety.drift_threshold,
            )
            if drift.drifted:
                self.activity.log_drift(
                    loop_num, task.id, drift.score,
                    drift.irrelevant_files or [],
                )
                logger.warning("Drift: %s", drift.reason)

                # Rollback drift changes
                if pre_commit:
                    rollback_to(self.working_dir, pre_commit)

                self._record_lesson(
                    loop_num, "FAIL", drift.reason,
                    f"Drift detected (score {drift.score:.2f}) — rolled back",
                    task, spec,
                )
                self.task_plan.update_task(task.id, loops_taken=task.loops_taken)
                return LoopOutcome.FAILED

        # --- Validate (FR-004) ---
        validation = validate(
            self.working_dir,
            self.config.validation.test_command,
            self.config.validation.lint_command,
        )
        self.activity.log_validation(loop_num, task.id, validation.passed, validation.summary)

        if not validation.passed:
            logger.warning("Validation failed: %s", validation.summary)

            if self.config.validation.auto_rollback and pre_commit:
                rollback_to(self.working_dir, pre_commit)

            self._handle_failure(
                loop_num, task, spec,
                f"Validation: {validation.summary}",
            )
            return LoopOutcome.FAILED

        # --- Completion verification (FR-013) ---
        if self.config.validation.completion_verify:
            verification = verify_completion(
                task, spec, self.working_dir, self.config.validation.test_command
            )

            if not verification.complete:
                logger.warning("Completion check: %s", verification.summary)
                self.task_plan.update_task(task.id, loops_taken=task.loops_taken)
                return LoopOutcome.INCOMPLETE

        # --- Success path ---
        if self.config.validation.auto_commit:
            commit_msg = f"feat({task.id}): {task.title} [loop {loop_num}]"
            auto_commit(self.working_dir, commit_msg)

        self._record_lesson(
            loop_num, "SUCCESS",
            f"Completed {task.id}: {task.title}",
            "Task completed successfully",
            task, spec,
        )

        self.task_plan.mark_done(task.id, task.loops_taken)
        self.oscillation.reset()  # Clear oscillation history for next task
        logger.info("Task %s completed in %d loops", task.id, task.loops_taken)

        return LoopOutcome.COMPLETED

    def _handle_failure(self, loop_num: int, task: Task, spec: str, error: str) -> None:
        """Common failure handling: record lesson + strategy rotation."""
        self.strategy.record_failure(task.id, error[:200])
        self._record_lesson(loop_num, "FAIL", error[:200], f"Failed in {task.id}", task, spec)
        self.task_plan.update_task(task.id, loops_taken=task.loops_taken)

    def _record_lesson(self, loop_num: int, outcome: str, description: str,
                        lesson: str, task: Task, spec: str) -> None:
        from mobiusforge.core.prompt_assembler import _extract_tags
        tags = _extract_tags(task, spec)
        self.lessons.add(loop_num, outcome, description, lesson, tags)


class LoopOutcome:
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    BLOCKED = "blocked"


class LoopSummary:
    def __init__(self, loops_run: int, tasks_completed: int, tasks_failed: int,
                 total_cost: float, elapsed_seconds: float,
                 task_summary: dict[str, int]) -> None:
        self.loops_run = loops_run
        self.tasks_completed = tasks_completed
        self.tasks_failed = tasks_failed
        self.total_cost = total_cost
        self.elapsed_seconds = elapsed_seconds
        self.task_summary = task_summary

    def __str__(self) -> str:
        hours = self.elapsed_seconds / 3600
        return (
            f"Loops: {self.loops_run} | "
            f"Completed: {self.tasks_completed} | "
            f"Failed: {self.tasks_failed} | "
            f"Cost: ${self.total_cost:.2f} | "
            f"Time: {hours:.1f}h | "
            f"Tasks: {self.task_summary}"
        )
