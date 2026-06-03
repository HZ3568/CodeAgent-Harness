from __future__ import annotations

from typing import Any


def run_todo_write(runtime: Any, todos: list[dict]) -> str:
    for index, todo in enumerate(todos):
        if "content" not in todo or "status" not in todo:
            return f"Error: todos[{index}] missing 'content' or 'status'"
        if todo["status"] not in ("pending", "in_progress", "completed"):
            return f"Error: todos[{index}] has invalid status '{todo['status']}'"
    runtime.current_todos = todos
    return f"Updated {len(runtime.current_todos)} todos"
