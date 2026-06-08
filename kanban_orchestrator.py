"""Kanban Orchestrator - Multi-agent collaboration for short drama production.

This module provides a lightweight Kanban-style task queue that works
without the full Hermes Kanban infrastructure. It can be replaced with
hermes kanban tools when running inside Hermes.
"""

import os
import json
import time
from typing import Optional, Dict, List, Callable
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    TODO = "todo"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"


class KanbanTask:
    """A single Kanban task with dependencies."""

    def __init__(
        self,
        task_id: str,
        title: str,
        assignee: str,
        body: str = "",
        parent_ids: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ):
        self.task_id = task_id
        self.title = title
        self.assignee = assignee
        self.body = body
        self.parent_ids = parent_ids or []
        self.status = TaskStatus.READY if not parent_ids else TaskStatus.TODO
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.result: Optional[Dict] = None
        self.error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "assignee": self.assignee,
            "body": self.body,
            "parent_ids": self.parent_ids,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class ShortDramaKanban:
    """Lightweight Kanban board for orchestrating short drama production."""

    def __init__(self, output_dir: Optional[str] = None):
        self.tasks: Dict[str, KanbanTask] = {}
        self.task_order: List[str] = []
        self.workflows: Dict[str, Callable] = {}
        self.output_dir = output_dir or "kanban_output"
        os.makedirs(self.output_dir, exist_ok=True)
        self._next_id = 0

    def register_workflow(self, name: str, handler: Callable):
        """Register a workflow handler for a specific assignee."""
        self.workflows[name] = handler

    def create_task(
        self,
        title: str,
        assignee: str,
        body: str = "",
        parent_ids: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Create a new task and return its ID."""
        self._next_id += 1
        task_id = f"sd_{self._next_id:04d}"
        task = KanbanTask(task_id, title, assignee, body, parent_ids, metadata)
        self.tasks[task_id] = task
        self.task_order.append(task_id)
        return task_id

    def get_ready_tasks(self) -> List[str]:
        """Get all tasks that are ready to run (status=ready, parents done)."""
        return [
            tid for tid in self.task_order
            if self.tasks[tid].status == TaskStatus.READY
        ]

    def get_done_tasks(self) -> List[str]:
        """Get all completed task IDs."""
        return [
            tid for tid in self.task_order
            if self.tasks[tid].status == TaskStatus.DONE
        ]

    def get_blocked_tasks(self) -> List[str]:
        """Get all blocked task IDs."""
        return [
            tid for tid in self.task_order
            if self.tasks[tid].status == TaskStatus.BLOCKED
        ]

    def execute_task(self, task_id: str) -> bool:
        """Execute a single task by running its assigned workflow.

        Returns True if successful.
        """
        task = self.tasks.get(task_id)
        if not task:
            print(f"  Task {task_id} not found")
            return False

        if task.status != TaskStatus.READY:
            print(f"  Task {task_id} not ready (status: {task.status.value})")
            return False

        handler = self.workflows.get(task.assignee)
        if not handler:
            print(f"  No workflow registered for assignee: {task.assignee}")
            task.status = TaskStatus.FAILED
            task.error = "No workflow handler"
            return False

        print(f"  [Kanban] Executing: {task.title} (assignee: {task.assignee})")
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().isoformat()

        try:
            result = handler(task)
            task.result = result
            task.status = TaskStatus.DONE
            task.completed_at = datetime.now().isoformat()
            self._unblock_dependents(task_id)
            return True
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()
            print(f"  [Kanban] Task {task_id} FAILED: {e}")
            return False

    def _unblock_dependents(self, completed_task_id: str):
        """Unblock any tasks that depended on the completed task."""
        for tid, task in self.tasks.items():
            if completed_task_id in task.parent_ids:
                # Check if all parents are done
                all_parents_done = all(
                    self.tasks[pid].status == TaskStatus.DONE
                    for pid in task.parent_ids
                )
                if all_parents_done:
                    task.status = TaskStatus.READY

    def run_all(self) -> Dict[str, bool]:
        """Run all ready tasks, looping until none are left.

        Returns dict of task_id -> success status.
        """
        results = {}

        while True:
            ready = self.get_ready_tasks()
            if not ready:
                break

            for task_id in ready:
                success = self.execute_task(task_id)
                results[task_id] = success

        return results

    def get_board_state(self) -> Dict:
        """Get a full board state summary."""
        return {
            "total": len(self.tasks),
            "ready": len(self.get_ready_tasks()),
            "running": sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING),
            "done": len(self.get_done_tasks()),
            "blocked": len(self.get_blocked_tasks()),
            "failed": sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED),
            "tasks": {
                tid: task.to_dict() for tid, task in self.tasks.items()
            },
        }

    def save_board(self, filename: Optional[str] = None):
        """Save board state to JSON file."""
        if not filename:
            ts = int(time.time())
            filename = f"board_{ts}.json"
        path = os.path.join(self.output_dir, filename)
        state = self.get_board_state()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        return path

    def print_board(self):
        """Print a text summary of the board."""
        state = self.get_board_state()
        print(f"\n{'='*60}")
        print(f"  SHORT DRAMA KANBAN BOARD")
        print(f"{'='*60}")
        print(f"  Total: {state['total']}  Ready: {state['ready']}  "
              f"Running: {state['running']}  Done: {state['done']}  "
              f"Failed: {state['failed']}")
        print(f"{'-'*60}")
        for tid in self.task_order:
            task = self.tasks[tid]
            status_icon = {
                "todo": "[TO]", "ready": "[RD]", "running": "[..]",
                "done": "[OK]", "blocked": "[BL]", "failed": "[XX]",
            }.get(task.status.value, "[??]")
            print(f"  {status_icon} {task.title} -> {task.assignee}")
        print(f"{'='*60}")
