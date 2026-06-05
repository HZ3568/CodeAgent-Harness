from __future__ import annotations

from typing import Any


# def run_todo_write(runtime: Any, todos: list[dict]) -> str:
#     for index, todo in enumerate(todos):
#         if "content" not in todo or "status" not in todo:
#             return f"Error: todos[{index}] missing 'content' or 'status'"
#         if todo["status"] not in ("pending", "in_progress", "completed"):
#             return f"Error: todos[{index}] has invalid status '{todo['status']}'"
#     runtime.current_todos = todos
#     return f"Updated {len(runtime.current_todos)} todos"


CURRENT_TODOS: list[dict] = []


def run_todo_write(runtime: Any, todos: list[dict]) -> str:
    global CURRENT_TODOS

    valid_statuses = ("pending", "in_progress", "completed")
    icons = {
        "pending": "×",
        "in_progress": "▸",
        "completed": "✓",
    }

    for i, todo in enumerate(todos):
        if not isinstance(todo, dict):
            return f"Error: todos[{i}] must be a dict"

        if "content" not in todo or "status" not in todo:
            return f"Error: todos[{i}] missing 'content' or 'status'"

        if todo["status"] not in valid_statuses:
            return f"Error: todos[{i}] has invalid status '{todo['status']}'"

    CURRENT_TODOS = todos

    lines = ["\n## Current Tasks"]
    for todo in CURRENT_TODOS:
        icon = icons[todo["status"]]
        lines.append(f"  [{icon}] {todo['content']}")

    print("\n".join(lines))
    return f"Updated {len(CURRENT_TODOS)} todos"
