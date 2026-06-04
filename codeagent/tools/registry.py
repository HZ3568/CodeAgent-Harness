from __future__ import annotations

from typing import Any, Callable

from codeagent.agents.subagent import spawn_subagent
from codeagent.agents.teammate import spawn_teammate_thread
from codeagent.mcp.client import normalize_mcp_name
from codeagent.tools.basic import run_bash, run_edit, run_glob, run_read, run_write
from codeagent.tools.todo import run_todo_write

BUILTIN_TOOLS: list[dict[str, Any]] = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "run_in_background": {"type": "boolean"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "todo_write",
        "description": "Create and manage a task list for the current session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["content", "status"],
                    },
                }
            },
            "required": ["todos"],
        },
    },
    {
        "name": "task",
        "description": "Launch a focused subagent. Returns only its final summary.",
        "input_schema": {
            "type": "object",
            "properties": {"description": {"type": "string"}},
            "required": ["description"],
        },
    },
    {
        "name": "load_skill",
        "description": "Load the full content of a skill by name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "compact",
        "description": "Summarize earlier conversation and continue with compacted context.",
        "input_schema": {
            "type": "object",
            "properties": {"focus": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "create_task",
        "description": "Create a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "blockedBy": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["subject"],
        },
    },
    {
        "name": "list_tasks",
        "description": "List all tasks.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_task",
        "description": "Get full task details.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "claim_task",
        "description": "Claim a pending task.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "complete_task",
        "description": "Complete an in-progress task.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "schedule_cron",
        "description": "Schedule a cron job. cron is 5-field: min hour dom month dow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cron": {"type": "string"},
                "prompt": {"type": "string"},
                "recurring": {"type": "boolean"},
                "durable": {"type": "boolean"},
            },
            "required": ["cron", "prompt"],
        },
    },
    {
        "name": "list_crons",
        "description": "List registered cron jobs.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "cancel_cron",
        "description": "Cancel a cron job by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
        },
    },
    {
        "name": "spawn_teammate",
        "description": "Spawn an autonomous teammate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"},
                "prompt": {"type": "string"},
            },
            "required": ["name", "role", "prompt"],
        },
    },
    {
        "name": "send_message",
        "description": "Send message to a teammate.",
        "input_schema": {
            "type": "object",
            "properties": {"to": {"type": "string"}, "content": {"type": "string"}},
            "required": ["to", "content"],
        },
    },
    {
        "name": "check_inbox",
        "description": "Check inbox for messages and protocol responses.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "request_shutdown",
        "description": "Request a teammate to shut down.",
        "input_schema": {
            "type": "object",
            "properties": {"teammate": {"type": "string"}},
            "required": ["teammate"],
        },
    },
    {
        "name": "request_plan",
        "description": "Ask a teammate to submit a plan.",
        "input_schema": {
            "type": "object",
            "properties": {"teammate": {"type": "string"}, "task": {"type": "string"}},
            "required": ["teammate", "task"],
        },
    },
    {
        "name": "review_plan",
        "description": "Approve or reject a submitted plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "approve": {"type": "boolean"},
                "feedback": {"type": "string"},
            },
            "required": ["request_id", "approve"],
        },
    },
    {
        "name": "create_worktree",
        "description": "Create an isolated git worktree.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "task_id": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "remove_worktree",
        "description": "Remove a worktree. Refuses if changes exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "discard_changes": {"type": "boolean"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "keep_worktree",
        "description": "Keep a worktree for manual review.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "connect_mcp",
        "description": "Connect to an MCP server (docs, deploy) and discover tools.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
]


def build_builtin_handlers(runtime: Any) -> dict[str, Callable[..., str]]:
    cwd = runtime.settings.workdir
    return {
        "bash": lambda command, run_in_background=False: run_bash(
            command, cwd, run_in_background
        ),
        "read_file": lambda path, limit=None, offset=0: run_read(
            path, cwd, limit, offset
        ),
        "write_file": lambda path, content: run_write(path, content, cwd),
        "edit_file": lambda path, old_text, new_text: run_edit(
            path, old_text, new_text, cwd
        ),
        "glob": lambda pattern: run_glob(pattern, cwd),
        "todo_write": lambda todos: run_todo_write(runtime, todos),
        "task": lambda description: spawn_subagent(runtime, description),
        "load_skill": lambda name: runtime.skills.load(name),
        "create_task": lambda subject, description="", blockedBy=None: _create_task(
            runtime, subject, description, blockedBy
        ),
        "list_tasks": lambda: runtime.tasks.render_list(),
        "get_task": lambda task_id: _get_task(runtime, task_id),
        "claim_task": lambda task_id: _claim_task(runtime, task_id),
        "complete_task": lambda task_id: _complete_task(runtime, task_id),
        "schedule_cron": lambda cron, prompt, recurring=True, durable=True: runtime.cron.schedule(
            cron, prompt, recurring, durable
        ),
        "list_crons": lambda: runtime.cron.list_jobs(),
        "cancel_cron": lambda job_id: runtime.cron.cancel(job_id),
        "spawn_teammate": lambda name, role, prompt: spawn_teammate_thread(
            runtime, name, role, prompt
        ),
        "send_message": lambda to, content: (
            runtime.bus.send("lead", to, content),
            f"Sent to {to}",
        )[1],
        "check_inbox": lambda: _check_inbox(runtime),
        "request_shutdown": lambda teammate: runtime.protocols.request_shutdown(
            teammate
        ),
        "request_plan": lambda teammate, task: runtime.protocols.request_plan(
            teammate, task
        ),
        "review_plan": lambda request_id, approve, feedback="": runtime.protocols.review_plan(
            request_id, approve, feedback
        ),
        "create_worktree": lambda name, task_id="": runtime.worktrees.create(
            name, task_id
        ),
        "remove_worktree": lambda name, discard_changes=False: runtime.worktrees.remove(
            name, discard_changes
        ),
        "keep_worktree": lambda name: runtime.worktrees.keep(name),
        "connect_mcp": lambda name: runtime.mcp.connect(name),
    }


def _create_task(
    runtime: Any,
    subject: str,
    description: str = "",
    blockedBy: list[str] | None = None,
) -> str:
    task = runtime.tasks.create(subject, description, blockedBy)
    deps = f" (blockedBy: {', '.join(blockedBy)})" if blockedBy else ""
    return f"Created {task.id}: {task.subject}{deps}"


def _get_task(runtime: Any, task_id: str) -> str:
    try:
        return runtime.tasks.to_json(task_id)
    except FileNotFoundError:
        return f"Error: task {task_id} not found"


def _claim_task(runtime: Any, task_id: str) -> str:
    try:
        return runtime.tasks.claim(task_id, owner="agent")
    except FileNotFoundError:
        return f"Error: task {task_id} not found"


def _complete_task(runtime: Any, task_id: str) -> str:
    try:
        return runtime.tasks.complete(task_id)
    except FileNotFoundError:
        return f"Error: task {task_id} not found"


def _check_inbox(runtime: Any) -> str:
    msgs = runtime.protocols.consume_lead_inbox(route_protocol=True)
    if not msgs:
        return "(inbox empty)"
    lines = []
    for msg in msgs:
        meta = msg.get("metadata", {})
        req_id = meta.get("request_id", "")
        tag = f" [{msg['type']} req:{req_id}]" if req_id else f" [{msg['type']}]"
        lines.append(f"  [{msg['from']}]{tag} {msg['content'][:200]}")
    return "\n".join(lines)


"""
    把内置工具和 MCP 服务器提供的工具统一整理成一个“工具池”，并同时建立工具名到执行函数的映射。
"""


def build_tool_pool(
    runtime: Any,
) -> tuple[list[dict[str, Any]], dict[str, Callable[..., str]]]:
    tools = list(BUILTIN_TOOLS)
    handlers = build_builtin_handlers(runtime)
    for server_name, client in runtime.mcp.clients.items():
        safe_server = normalize_mcp_name(server_name)
        for tool_def in client.tools:
            safe_tool = normalize_mcp_name(tool_def["name"])
            prefixed = f"mcp__{safe_server}__{safe_tool}"
            tools.append(
                {
                    "name": prefixed,
                    "description": tool_def.get("description", ""),
                    "input_schema": tool_def.get("inputSchema", {}),
                }
            )
            handlers[prefixed] = lambda c=client, t=tool_def["name"], **kw: c.call_tool(
                t, kw
            )
    return tools, handlers
