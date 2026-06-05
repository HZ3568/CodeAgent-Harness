from __future__ import annotations

from typing import Any

CURRENT_TODOS: list[dict] = []


def run_todo_write(first: Any = None, *args: Any, **kwargs: Any) -> str:
    global CURRENT_TODOS

    valid_statuses = ("pending", "in_progress", "completed")
    icons = {
        "pending": "×",
        "in_progress": "▸",
        "completed": "✓",
    }

    runtime = None
    payload = None

    # 情况 1：调度器调用 run_todo_write(runtime, ...)
    if hasattr(first, "current_todos") and hasattr(first, "settings"):
        runtime = first

        # run_todo_write(runtime, {"todos": [...]})
        if args:
            payload = args[0]

        # run_todo_write(runtime, todos=[...])
        elif kwargs:
            payload = kwargs

        else:
            payload = None

    # 情况 2：直接调用 run_todo_write({"todos": [...]}) 或 run_todo_write([...])
    else:
        payload = first

    if payload is None:
        return (
            "Error: missing todos. Expected {'todos': [...]} or a list of todo objects"
        )

    if isinstance(payload, dict):
        if "todos" in payload:
            todos = payload["todos"]
        elif "tasks" in payload:
            todos = payload["tasks"]
        elif "items" in payload:
            todos = payload["items"]
        else:
            return f"Error: missing 'todos' field. Got keys: {list(payload.keys())}"
    else:
        todos = payload

    if not isinstance(todos, list):
        return f"Error: todos must be a list, got {type(todos).__name__}: {repr(todos)}"

    for i, todo in enumerate(todos):
        if not isinstance(todo, dict):
            return f"Error: todos[{i}] must be a dict, got {type(todo).__name__}: {repr(todo)}"

        if "content" not in todo or "status" not in todo:
            return f"Error: todos[{i}] missing 'content' or 'status': {repr(todo)}"

        if todo["status"] not in valid_statuses:
            return f"Error: todos[{i}] has invalid status '{todo['status']}'"

    # 优先写入 runtime.current_todos
    if runtime is not None:
        runtime.current_todos = todos

    # 同时保留全局变量，兼容旧逻辑
    CURRENT_TODOS = todos

    lines = ["\n## Current Tasks"]
    for todo in todos:
        icon = icons[todo["status"]]
        lines.append(f"  [{icon}] {todo['content']}")

    print("\n".join(lines))
    return f"Updated {len(todos)} todos"
