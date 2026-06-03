from __future__ import annotations

from datetime import datetime
from typing import Any

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain.",
    "tools": (
        "Available tools: bash, read_file, write_file, edit_file, glob, todo_write, task, "
        "load_skill, compact, create_task, list_tasks, get_task, claim_task, complete_task, "
        "schedule_cron, list_crons, cancel_cron, spawn_teammate, send_message, check_inbox, "
        "request_shutdown, request_plan, review_plan, create_worktree, remove_worktree, "
        "keep_worktree, connect_mcp. MCP tools are prefixed mcp__{server}__{tool}."
    ),
}


def assemble_system_prompt(runtime: Any, context: dict) -> str:
    sections = [
        PROMPT_SECTIONS["identity"],
        PROMPT_SECTIONS["tools"],
        f"Working directory: {runtime.settings.workdir}",
        f"Current time: {datetime.now().isoformat(timespec='seconds')}",
        "Skills catalog:\n" + runtime.skills.list() + "\nUse load_skill(name) when a skill is relevant.",
    ]
    if context.get("memories"):
        sections.append(f"Relevant memories:\n{context['memories']}")
    if runtime.mcp.connected_names():
        sections.append("Connected MCP servers: " + ", ".join(runtime.mcp.connected_names()))
    if runtime.active_teammates:
        sections.append("Active teammates: " + ", ".join(runtime.active_teammates.keys()))
    return "\n\n".join(sections)
