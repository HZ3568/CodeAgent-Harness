from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from codeagent.tasks.store import TaskStore

VALID_WT_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class WorktreeManager:
    def __init__(self, workdir: Path, tasks: TaskStore) -> None:
        self.workdir = workdir
        self.tasks = tasks
        self.worktrees_dir = workdir / ".worktrees"
        self.worktrees_dir.mkdir(exist_ok=True)

    def validate_name(self, name: str) -> str | None:
        if not name:
            return "Worktree name cannot be empty"
        if name in (".", ".."):
            return f"'{name}' is not a valid worktree name"
        if not VALID_WT_NAME.match(name):
            return f"Invalid worktree name '{name}': only letters, digits, dots, underscores, dashes (1-64 chars)"
        return None

    def run_git(self, args: list[str], cwd: Path | None = None) -> tuple[bool, str]:
        try:
            result = subprocess.run(["git"] + args, cwd=cwd or self.workdir, capture_output=True, text=True, timeout=30)
            out = (result.stdout + result.stderr).strip()
            return result.returncode == 0, out[:5000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return False, "Error: git timeout"

    def log_event(self, event_type: str, worktree_name: str, task_id: str = "") -> None:
        event = {"type": event_type, "worktree": worktree_name, "task_id": task_id, "ts": time.time()}
        with (self.worktrees_dir / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def create(self, name: str, task_id: str = "") -> str:
        err = self.validate_name(name)
        if err:
            return f"Error: {err}"
        if task_id:
            try:
                self.tasks.load(task_id)
            except FileNotFoundError:
                return f"Error: task {task_id} not found"
        path = self.worktrees_dir / name
        if path.exists():
            return f"Worktree '{name}' already exists at {path}"
        ok, output = self.run_git(["worktree", "add", str(path), "-b", f"wt/{name}", "HEAD"])
        if not ok:
            return f"Git error: {output}"
        if task_id:
            self.tasks.bind_worktree(task_id, name)
        self.log_event("create", name, task_id)
        return f"Worktree '{name}' created at {path}"

    def _count_changes(self, path: Path) -> tuple[int, int]:
        try:
            s = subprocess.run(["git", "status", "--porcelain"], cwd=path, capture_output=True, text=True, timeout=10)
            files = len([line for line in s.stdout.strip().splitlines() if line.strip()])
            l = subprocess.run(["git", "log", "@{push}..HEAD", "--oneline"], cwd=path, capture_output=True, text=True, timeout=10)
            commits = len([line for line in l.stdout.strip().splitlines() if line.strip()])
            return files, commits
        except Exception:
            return -1, -1

    def remove(self, name: str, discard_changes: bool = False) -> str:
        err = self.validate_name(name)
        if err:
            return err
        path = self.worktrees_dir / name
        if not path.exists():
            return f"Worktree '{name}' not found"
        if not discard_changes:
            files, commits = self._count_changes(path)
            if files < 0:
                return "Cannot verify status. Use discard_changes=true to force."
            if files > 0 or commits > 0:
                return f"Worktree '{name}' has {files} file(s), {commits} commit(s). Use discard_changes=true or keep_worktree."
        ok, _ = self.run_git(["worktree", "remove", str(path), "--force"])
        if not ok:
            return f"Failed to remove worktree '{name}'"
        self.run_git(["branch", "-D", f"wt/{name}"])
        self.log_event("remove", name)
        return f"Worktree '{name}' removed"

    def keep(self, name: str) -> str:
        err = self.validate_name(name)
        if err:
            return err
        self.log_event("keep", name)
        return f"Worktree '{name}' kept for review (branch: wt/{name})"
