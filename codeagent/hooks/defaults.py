from __future__ import annotations

from typing import Any

from codeagent.tools.basic import safe_path

DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]
DESTRUCTIVE = ["rm ", "> /etc/", "chmod 777", "rmdir"]


# PreToolUse: 权限检查
def make_permission_hook(runtime: Any):
    def permission_hook(block: Any) -> str | None:
        block_name = getattr(block, "name", None)
        block_input = getattr(block, "input", None) or {}
        if block_name == "bash":
            command = block_input.get("command", "")
            for pattern in DENY_LIST:
                if pattern in command:
                    return f"Permission denied: '{pattern}' is on the deny list"
            if any(token in command for token in DESTRUCTIVE):
                print("\n\033[33m[permission] destructive command\033[0m")
                print(f"  {command}")
                choice = input("  Allow? [y/N] ").strip().lower()
                if choice not in ("y", "yes"):
                    return "Permission denied by user"
        if block_name in ("write_file", "edit_file"):
            path = block_input.get("path", "")
            try:
                safe_path(path, runtime.settings.workdir)
            except Exception:
                return f"Permission denied: path escapes workspace: {path}"
        if (
            isinstance(block_name, str)
            and block_name.startswith("mcp__")
            and "deploy" in block_name
        ):
            print(
                f"\n\033[33m[permission] MCP destructive-looking tool: {block_name}\033[0m"
            )
            choice = input("  Allow? [y/N] ").strip().lower()
            if choice not in ("y", "yes"):
                return "Permission denied by user"
        return None

    return permission_hook


# PreToolUse: 日志
def log_hook(block: Any) -> None:
    print(f"\033[90m[HOOK] {block.name}\033[0m")
    return None


# PostToolUse: 大文件提醒
def large_output_hook(block: Any, output: str) -> None:
    if len(str(output)) > 100000:
        print(
            f"\033[33m[HOOK] large output from {block.name}: {len(str(output))} chars\033[0m"
        )
    return None


def make_user_prompt_hook(runtime: Any):
    def user_prompt_hook(query: str) -> None:
        del query
        print(f"\033[90m[HOOK] UserPromptSubmit: {runtime.settings.workdir}\033[0m")
        return None

    return user_prompt_hook


def stop_hook(messages: list) -> None:
    tool_count = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            tool_count += sum(
                1
                for item in content
                if isinstance(item, dict) and item.get("type") == "tool_result"
            )
    print(f"\033[90m[HOOK] Stop: {tool_count} tool result(s)\033[0m")
    return None


def register_default_hooks(runtime: Any) -> None:
    runtime.hooks.register("UserPromptSubmit", make_user_prompt_hook(runtime))
    runtime.hooks.register("PreToolUse", make_permission_hook(runtime))
    runtime.hooks.register("PreToolUse", log_hook)
    runtime.hooks.register("PostToolUse", large_output_hook)
    runtime.hooks.register("Stop", stop_hook)
