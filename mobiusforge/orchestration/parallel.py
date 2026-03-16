"""Parallel executor — runs multiple agents in worktrees (FR-017, FR-019)."""

from __future__ import annotations

import logging
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

from mobiusforge.config import MobiusConfig
from mobiusforge.core.prompt_assembler import assemble_prompt, load_spec
from mobiusforge.core.runner import AgentResult, run_agent
from mobiusforge.core.validator import validate
from mobiusforge.memory.lessons import LessonsManager
from mobiusforge.memory.state import Task

logger = logging.getLogger(__name__)


@dataclass
class WorkerResult:
    task: Task
    agent_result: AgentResult
    validation_passed: bool
    worktree_path: Path | None = None
    branch_name: str = ""


@dataclass
class AgentPool:
    """Manages parallel agent execution with worktree isolation (FR-019)."""

    max_parallel: int = 2
    config: MobiusConfig | None = None
    working_dir: Path = field(default_factory=lambda: Path("."))
    _active: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def can_spawn(self) -> bool:
        with self._lock:
            return self._active < self.max_parallel

    def run_parallel(
        self,
        tasks: list[Task],
        prompt_md: str,
        lessons: LessonsManager,
        guardrails: str,
        specs_dir: Path,
    ) -> list[WorkerResult]:
        """Run multiple tasks in parallel using git worktrees."""
        if not self.config:
            raise RuntimeError("AgentPool not configured")

        # Limit to max_parallel
        batch = tasks[: self.max_parallel]

        if len(batch) == 1:
            # Single task — run in main working dir (no worktree needed)
            result = self._run_single(
                batch[0], prompt_md, lessons, guardrails, specs_dir, self.working_dir
            )
            return [result]

        # Multiple tasks — use worktrees
        threads: list[threading.Thread] = []
        results: list[WorkerResult] = []
        results_lock = threading.Lock()

        for task in batch:
            branch = f"mf-worker-{task.id.lower()}"
            worktree = self._create_worktree(branch)
            if worktree is None:
                logger.error("Failed to create worktree for %s", task.id)
                continue

            def worker(t=task, wt=worktree, bn=branch):
                res = self._run_single(t, prompt_md, lessons, guardrails, specs_dir, wt)
                res.worktree_path = wt
                res.branch_name = bn
                with results_lock:
                    results.append(res)

            thread = threading.Thread(target=worker, name=f"worker-{task.id}")
            threads.append(thread)

            with self._lock:
                self._active += 1

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        with self._lock:
            self._active = 0

        return results

    def _run_single(
        self,
        task: Task,
        prompt_md: str,
        lessons: LessonsManager,
        guardrails: str,
        specs_dir: Path,
        work_dir: Path,
    ) -> WorkerResult:
        """Run a single task in a given directory."""
        spec = load_spec(specs_dir, task)
        prompt = assemble_prompt(
            task=task,
            prompt_md=prompt_md,
            spec=spec,
            lessons_manager=lessons,
            guardrails=guardrails,
        )

        agent_result = run_agent(
            prompt=prompt,
            agent_config=self.config.agent,
            working_dir=work_dir,
            timeout=self.config.agent.timeout_per_loop,
            cost_per_1k_input=self.config.budget.cost_per_1k_input,
            cost_per_1k_output=self.config.budget.cost_per_1k_output,
        )

        val_passed = False
        if agent_result.success:
            val = validate(
                work_dir,
                self.config.validation.test_command,
                self.config.validation.lint_command,
            )
            val_passed = val.passed

        return WorkerResult(
            task=task,
            agent_result=agent_result,
            validation_passed=val_passed,
        )

    def _create_worktree(self, branch_name: str) -> Path | None:
        """Create a git worktree for parallel execution."""
        worktree_dir = self.working_dir / ".mobiusforge" / "worktrees" / branch_name

        try:
            # Clean up existing worktree if any
            if worktree_dir.exists():
                subprocess.run(
                    ["git", "worktree", "remove", str(worktree_dir), "--force"],
                    cwd=self.working_dir,
                    capture_output=True,
                    timeout=10,
                )

            # Create new branch from current HEAD
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=self.working_dir,
                capture_output=True,  # Ignore if doesn't exist
                timeout=10,
            )
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, str(worktree_dir)],
                cwd=self.working_dir,
                check=True,
                capture_output=True,
                timeout=30,
            )

            logger.info("Created worktree: %s → %s", branch_name, worktree_dir)
            return worktree_dir

        except subprocess.CalledProcessError as e:
            logger.error("Failed to create worktree %s: %s", branch_name, e)
            return None

    def cleanup_worktrees(self) -> None:
        """Remove all MobiusForge worktrees."""
        wt_dir = self.working_dir / ".mobiusforge" / "worktrees"
        if not wt_dir.exists():
            return

        for child in wt_dir.iterdir():
            if child.is_dir():
                try:
                    subprocess.run(
                        ["git", "worktree", "remove", str(child), "--force"],
                        cwd=self.working_dir,
                        capture_output=True,
                        timeout=10,
                    )
                except Exception:
                    pass
