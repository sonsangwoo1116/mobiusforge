"""Task dependency DAG builder (FR-016)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from mobiusforge.memory.state import Task, TaskPlan, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class DAGNode:
    task: Task
    children: list[str] = field(default_factory=list)  # task IDs that depend on this
    parents: list[str] = field(default_factory=list)    # task IDs this depends on


class TaskDAG:
    """Builds and queries a task dependency DAG."""

    def __init__(self, task_plan: TaskPlan) -> None:
        self.nodes: dict[str, DAGNode] = {}
        self._build(task_plan)

    def _build(self, plan: TaskPlan) -> None:
        # Create nodes
        for task in plan.tasks:
            self.nodes[task.id] = DAGNode(
                task=task,
                parents=list(task.depends_on),
            )

        # Build children (reverse edges)
        for task_id, node in self.nodes.items():
            for parent_id in node.parents:
                if parent_id in self.nodes:
                    self.nodes[parent_id].children.append(task_id)

    def get_ready_tasks(self) -> list[Task]:
        """Get tasks that are ready to execute (all deps satisfied)."""
        done_ids = {
            tid for tid, node in self.nodes.items()
            if node.task.status == TaskStatus.DONE
        }

        ready = []
        for tid, node in self.nodes.items():
            if node.task.status not in (TaskStatus.OPEN, TaskStatus.INTERRUPTED):
                continue
            if all(pid in done_ids for pid in node.parents):
                ready.append(node.task)

        # Sort by priority
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        ready.sort(key=lambda t: priority_order.get(t.priority, 99))
        return ready

    def get_parallel_groups(self) -> list[list[Task]]:
        """Get groups of tasks that can run in parallel (topological layers)."""
        done_ids: set[str] = set()
        remaining = {
            tid for tid, node in self.nodes.items()
            if node.task.status in (TaskStatus.OPEN, TaskStatus.INTERRUPTED)
        }
        layers: list[list[Task]] = []

        # Include already-done tasks in done set
        for tid, node in self.nodes.items():
            if node.task.status == TaskStatus.DONE:
                done_ids.add(tid)

        while remaining:
            # Find tasks whose all parents are done
            layer = []
            for tid in list(remaining):
                node = self.nodes[tid]
                if all(pid in done_ids for pid in node.parents):
                    layer.append(node.task)

            if not layer:
                # Remaining tasks have unresolvable dependencies
                break

            layers.append(layer)
            for task in layer:
                done_ids.add(task.id)
                remaining.discard(task.id)

        return layers

    def visualize(self) -> str:
        """Generate a text visualization of the DAG."""
        lines = ["Task Dependency Graph:", ""]

        layers = self.get_parallel_groups()

        # Also show already done
        done = [
            node.task for node in self.nodes.values()
            if node.task.status == TaskStatus.DONE
        ]
        if done:
            names = ", ".join(f"{t.id}" for t in done)
            lines.append(f"  [DONE] {names}")
            lines.append("    |")

        for i, layer in enumerate(layers):
            names = " | ".join(f"{t.id}:{t.title[:20]}" for t in layer)
            parallel = " (parallel)" if len(layer) > 1 else ""
            lines.append(f"  Layer {i + 1}{parallel}: {names}")
            if i < len(layers) - 1:
                lines.append("    |")

        # Show blocked
        blocked = [
            node.task for node in self.nodes.values()
            if node.task.status == TaskStatus.BLOCKED
        ]
        if blocked:
            lines.append("")
            names = ", ".join(f"{t.id}" for t in blocked)
            lines.append(f"  [BLOCKED] {names}")

        return "\n".join(lines)
