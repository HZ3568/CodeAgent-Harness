from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from codeagent.core.context import extract_text, has_tool_use
from codeagent.tasks.background import call_tool_handler
from codeagent.tools.basic import run_bash, run_read, run_write

IDLE_POLL_INTERVAL = 5
IDLE_TIMEOUT = 60

TEAMMATE_TOOLS = [
    {"name": "bash", "description": "Run a shell command.", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "send_message", "description": "Send message to another agent.", "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}}, "required": ["to", "content"]}},
    {"name": "submit_plan", "description": "Submit a plan for Lead approval.", "input_schema": {"type": "object", "properties": {"plan": {"type": "string"}}, "required": ["plan"]}},
    {"name": "list_tasks", "description": "List all tasks.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "claim_task", "description": "Claim a pending task.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "complete_task", "description": "Mark an in-progress task as completed.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
]


def scan_unclaimed_tasks(runtime: Any) -> list[dict]:
    unclaimed = []
    for task in runtime.tasks.list():
        if task.status == "pending" and not task.owner and runtime.tasks.can_start(task.id):
            unclaimed.append(task.__dict__)
    return unclaimed


def idle_poll(runtime: Any, agent_name: str, messages: list, worktree_context: dict | None = None) -> str:
    for _ in range(IDLE_TIMEOUT // IDLE_POLL_INTERVAL):
        time.sleep(IDLE_POLL_INTERVAL)
        inbox = runtime.bus.read_inbox(agent_name)
        if inbox:
            for msg in inbox:
                if msg.get("type") == "shutdown_request":
                    req_id = msg.get("metadata", {}).get("request_id", "")
                    runtime.bus.send(agent_name, "lead", "Shutting down.", "shutdown_response", {"request_id": req_id, "approve": True})
                    return "shutdown"
            messages.append({"role": "user", "content": "<inbox>" + json.dumps(inbox) + "</inbox>"})
            return "work"
        unclaimed = scan_unclaimed_tasks(runtime)
        if unclaimed:
            task_data = unclaimed[0]
            result = runtime.tasks.claim(task_data["id"], agent_name)
            if "Claimed" in result:
                wt_info = ""
                if task_data.get("worktree"):
                    wt_path = runtime.worktrees.worktrees_dir / task_data["worktree"]
                    wt_info = f"\nWork directory: {wt_path}"
                    if worktree_context is not None:
                        worktree_context["path"] = str(wt_path)
                messages.append({"role": "user", "content": f"<auto-claimed>Task {task_data['id']}: {task_data['subject']}{wt_info}</auto-claimed>"})
                return "work"
    return "timeout"


def spawn_teammate_thread(runtime: Any, name: str, role: str, prompt: str) -> str:
    if name in runtime.active_teammates:
        return f"Teammate '{name}' already exists"

    protocol_ctx = {"waiting_plan": None}
    system = f"You are '{name}', a {role}. Use tools to complete tasks. If a task has a worktree, work in that directory."

    def run() -> None:
        wt_ctx = {"path": None}

        def cwd() -> Path:
            return Path(wt_ctx["path"]) if wt_ctx["path"] else runtime.settings.workdir

        def claim_task(task_id: str) -> str:
            result = runtime.tasks.claim(task_id, owner=name)
            if "Claimed" in result:
                task = runtime.tasks.load(task_id)
                wt_ctx["path"] = str(runtime.worktrees.worktrees_dir / task.worktree) if task.worktree else None
            return result

        def complete_task(task_id: str) -> str:
            result = runtime.tasks.complete(task_id)
            wt_ctx["path"] = None
            return result

        handlers = {
            "bash": lambda command: run_bash(command, cwd()),
            "read_file": lambda path, limit=None, offset=0: run_read(path, cwd(), limit, offset),
            "write_file": lambda path, content: run_write(path, content, cwd()),
            "send_message": lambda to, content: (runtime.bus.send(name, to, content), "Sent")[1],
            "submit_plan": lambda plan: runtime.protocols.submit_plan_from_teammate(name, plan),
            "list_tasks": lambda: runtime.tasks.render_list(),
            "claim_task": claim_task,
            "complete_task": complete_task,
        }
        messages = [{"role": "user", "content": prompt}]
        should_shutdown = False
        while True:
            for _ in range(10):
                inbox = runtime.bus.read_inbox(name)
                for msg in inbox:
                    msg_type = msg.get("type", "message")
                    meta = msg.get("metadata", {})
                    req_id = meta.get("request_id", "")
                    if msg_type == "shutdown_request":
                        runtime.bus.send(name, "lead", "Shutting down.", "shutdown_response", {"request_id": req_id, "approve": True})
                        should_shutdown = True
                        break
                    if msg_type == "plan_approval_response":
                        approve = meta.get("approve", False)
                        if req_id == protocol_ctx["waiting_plan"]:
                            protocol_ctx["waiting_plan"] = None
                        messages.append({"role": "user", "content": "[Plan approved]" if approve else f"[Plan rejected] {msg['content']}"})
                if should_shutdown:
                    break
                if protocol_ctx["waiting_plan"]:
                    time.sleep(IDLE_POLL_INTERVAL)
                    continue
                if inbox:
                    non_protocol = [m for m in inbox if m.get("type") == "message"]
                    if non_protocol:
                        messages.append({"role": "user", "content": "<inbox>" + json.dumps(non_protocol) + "</inbox>"})
                try:
                    response = runtime.client.messages.create(model=runtime.settings.model_id, system=system, messages=messages[-20:], tools=TEAMMATE_TOOLS, max_tokens=runtime.settings.default_max_tokens)
                except Exception:
                    break
                messages.append({"role": "assistant", "content": response.content})
                if not has_tool_use(response.content):
                    break
                results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    blocked = runtime.hooks.trigger("PreToolUse", block)
                    if blocked:
                        output = str(blocked)
                    else:
                        output = call_tool_handler(handlers.get(block.name), block.input, block.name)
                        runtime.hooks.trigger("PostToolUse", block, output)
                    if block.name == "submit_plan":
                        match = re.search(r"(req_\d+)", output)
                        protocol_ctx["waiting_plan"] = match.group(1) if match else output
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
                    if protocol_ctx["waiting_plan"]:
                        break
                messages.append({"role": "user", "content": results})
                if protocol_ctx["waiting_plan"]:
                    break
            if should_shutdown:
                break
            if protocol_ctx["waiting_plan"]:
                continue
            idle_result = idle_poll(runtime, name, messages, wt_ctx)
            if idle_result in ("shutdown", "timeout"):
                break
        summary = "Done."
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                text = extract_text(msg["content"])
                if text:
                    summary = text
                    break
        runtime.bus.send(name, "lead", summary, "result")
        runtime.active_teammates.pop(name, None)

    runtime.active_teammates[name] = True
    threading.Thread(target=run, daemon=True).start()
    return f"Teammate '{name}' spawned as {role}"
