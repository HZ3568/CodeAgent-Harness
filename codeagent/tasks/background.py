from __future__ import annotations

import threading
from typing import Any, Callable


def call_tool_handler(handler: Callable[..., Any] | None, args: dict, name: str) -> str:
    if not handler:
        return f"Unknown: {name}"
    try:
        return str(handler(**(args or {})))
    except TypeError as exc:
        return f"Error: {exc}"


class BackgroundManager:
    def __init__(self) -> None:
        self._counter = 0
        self.tasks: dict[str, dict] = {}
        self.results: dict[str, str] = {}
        self.lock = threading.Lock()

    def is_slow_operation(self, tool_name: str, tool_input: dict) -> bool:
        if tool_name != "bash":
            return False
        command = tool_input.get("command", "").lower()
        keywords = ["install", "build", "test", "deploy", "compile", "docker build", "pip install", "npm install", "cargo build", "pytest", "make"]
        return any(keyword in command for keyword in keywords)

    def should_run(self, tool_name: str, tool_input: dict) -> bool:
        if tool_name != "bash":
            return False
        return bool(tool_input.get("run_in_background")) or self.is_slow_operation(tool_name, tool_input)

    def start(self, block: Any, handlers: dict[str, Callable[..., Any]], post_hook: Callable[[Any, str], Any]) -> str:
        self._counter += 1
        bg_id = f"bg_{self._counter:04d}"
        command = block.input.get("command", block.name)

        def worker() -> None:
            handler = handlers.get(block.name)
            result = call_tool_handler(handler, block.input, block.name)
            post_hook(block, result)
            with self.lock:
                self.tasks[bg_id]["status"] = "completed"
                self.results[bg_id] = result

        with self.lock:
            self.tasks[bg_id] = {"tool_use_id": block.id, "command": command, "status": "running"}
        threading.Thread(target=worker, daemon=True).start()
        return bg_id

    def collect_results(self) -> list[str]:
        with self.lock:
            ready = [bg_id for bg_id, item in self.tasks.items() if item["status"] == "completed"]
        notifications: list[str] = []
        for bg_id in ready:
            with self.lock:
                task = self.tasks.pop(bg_id)
                output = self.results.pop(bg_id, "")
            summary = output[:200] if len(output) > 200 else output
            notifications.append(
                "<task_notification>\n"
                f"  <task_id>{bg_id}</task_id>\n"
                "  <status>completed</status>\n"
                f"  <command>{task['command']}</command>\n"
                f"  <summary>{summary}</summary>\n"
                "</task_notification>"
            )
        return notifications
