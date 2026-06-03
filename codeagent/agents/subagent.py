from __future__ import annotations

from typing import Any

from codeagent.core.context import extract_text, has_tool_use
from codeagent.tasks.background import call_tool_handler
from codeagent.tools.basic import run_bash, run_edit, run_glob, run_read, run_write

SUB_TOOLS = [
    {"name": "bash", "description": "Run a shell command.", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to a file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in a file once.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "glob", "description": "Find files matching a glob pattern.", "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
]


def spawn_subagent(runtime: Any, description: str) -> str:
    system = (
        f"You are a coding subagent at {runtime.settings.workdir}. "
        "Complete the task, then return a concise final summary. Do not spawn more agents."
    )
    cwd = runtime.settings.workdir
    handlers = {
        "bash": lambda command: run_bash(command, cwd),
        "read_file": lambda path, limit=None, offset=0: run_read(path, cwd, limit, offset),
        "write_file": lambda path, content: run_write(path, content, cwd),
        "edit_file": lambda path, old_text, new_text: run_edit(path, old_text, new_text, cwd),
        "glob": lambda pattern: run_glob(pattern, cwd),
    }
    messages = [{"role": "user", "content": description}]
    for _ in range(30):
        response = runtime.client.messages.create(
            model=runtime.settings.model_id,
            system=system,
            messages=messages,
            tools=SUB_TOOLS,
            max_tokens=runtime.settings.default_max_tokens,
        )
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
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
        messages.append({"role": "user", "content": results})
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            text = extract_text(msg["content"])
            if text:
                return text
    return "Subagent finished without a text summary."
