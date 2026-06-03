from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str
    owner: str | None
    blockedBy: list[str]
    worktree: str | None = None


class TaskStore:
    def __init__(self, workdir: Path) -> None:
        self.tasks_dir = workdir / ".tasks"
        self.tasks_dir.mkdir(exist_ok=True)

    def path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def create(self, subject: str, description: str = "", blockedBy: list[str] | None = None) -> Task:
        task = Task(
            id=f"task_{int(time.time())}_{random.randint(0, 9999):04d}",
            subject=subject,
            description=description,
            status="pending",
            owner=None,
            blockedBy=blockedBy or [],
        )
        self.save(task)
        return task

    def save(self, task: Task) -> None:
        self.path(task.id).write_text(json.dumps(asdict(task), indent=2), encoding="utf-8")

    def load(self, task_id: str) -> Task:
        return Task(**json.loads(self.path(task_id).read_text(encoding="utf-8")))

    def list(self) -> list[Task]:
        return [Task(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(self.tasks_dir.glob("task_*.json"))]

    def can_start(self, task_id: str) -> bool:
        task = self.load(task_id)
        for dep_id in task.blockedBy:
            if not self.path(dep_id).exists():
                return False
            if self.load(dep_id).status != "completed":
                return False
        return True

    def claim(self, task_id: str, owner: str = "agent") -> str:
        task = self.load(task_id)
        if task.status != "pending":
            return f"Task {task_id} is {task.status}, cannot claim"
        if task.owner:
            return f"Task {task_id} already owned by {task.owner}"
        if not self.can_start(task_id):
            deps = [d for d in task.blockedBy if self.path(d).exists() and self.load(d).status != "completed"]
            missing = [d for d in task.blockedBy if not self.path(d).exists()]
            parts = []
            if deps:
                parts.append(f"blocked by: {deps}")
            if missing:
                parts.append(f"missing deps: {missing}")
            return "Cannot start — " + ", ".join(parts)
        task.owner = owner
        task.status = "in_progress"
        self.save(task)
        return f"Claimed {task.id} ({task.subject})"

    def complete(self, task_id: str) -> str:
        task = self.load(task_id)
        if task.status != "in_progress":
            return f"Task {task_id} is {task.status}, cannot complete"
        task.status = "completed"
        self.save(task)
        unblocked = [t.subject for t in self.list() if t.status == "pending" and t.blockedBy and self.can_start(t.id)]
        msg = f"Completed {task.id} ({task.subject})"
        if unblocked:
            msg += f"\nUnblocked: {', '.join(unblocked)}"
        return msg

    def bind_worktree(self, task_id: str, worktree: str) -> None:
        task = self.load(task_id)
        task.worktree = worktree
        self.save(task)

    def to_json(self, task_id: str) -> str:
        return json.dumps(asdict(self.load(task_id)), indent=2)

    def render_list(self) -> str:
        tasks = self.list()
        if not tasks:
            return "No tasks."
        return "\n".join(
            f"  {t.id}: {t.subject} [{t.status}]" + (f" (wt:{t.worktree})" if t.worktree else "")
            for t in tasks
        )
