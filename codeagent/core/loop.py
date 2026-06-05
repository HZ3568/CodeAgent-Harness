from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from codeagent.core.context import (
    compact_history,
    extract_text,
    has_tool_use,
    prepare_context,
    reactive_compact,
)
from codeagent.core.llm import RecoveryState, is_prompt_too_long_error, with_retry
from codeagent.core.prompt import assemble_system_prompt
from codeagent.tasks.background import call_tool_handler
from codeagent.tools.registry import build_tool_pool


def build_user_content(runtime: Any, results: list[dict]) -> list[dict]:
    content = list(results)
    for note in runtime.background.collect_results():
        content.append({"type": "text", "text": note})
    return content


def inject_background_notifications(runtime: Any, messages: list) -> None:
    notes = runtime.background.collect_results()
    if notes:
        messages.append(
            {
                "role": "user",
                "content": [{"type": "text", "text": note} for note in notes],
            }
        )


def call_llm(
    runtime: Any,
    messages: list,
    context: dict,
    tools: list,
    state: RecoveryState,
    max_tokens: int,
):
    system = assemble_system_prompt(runtime, context)
    return with_retry(
        lambda: runtime.client.messages.create(
            model=state.current_model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        ),
        state,
        runtime.settings,
    )


def agent_loop(runtime: Any, messages: list, context: dict) -> None:
    tools, handlers = build_tool_pool(runtime)
    state = RecoveryState(current_model=runtime.settings.primary_model)
    max_tokens = runtime.settings.default_max_tokens

    while True:
        for job in runtime.cron.consume():
            messages.append({"role": "user", "content": f"[Scheduled] {job.prompt}"})
            print(f"  \033[35m[cron inject] {job.prompt[:60]}\033[0m")

        inject_background_notifications(runtime, messages)

        # if runtime.rounds_since_todo >= 3:
        #     messages.append({"role": "user", "content": "<reminder>Update your todos.</reminder>"})
        #     runtime.rounds_since_todo = 0

        memory_snapshot = runtime.memory.snapshot_messages(messages)
        prepare_context(runtime, messages)
        context.update(runtime.update_context(context, messages))
        tools, handlers = build_tool_pool(runtime)

        try:
            response = call_llm(runtime, messages, context, tools, state, max_tokens)
        except Exception as exc:
            if (
                is_prompt_too_long_error(exc)
                and not state.has_attempted_reactive_compact
            ):
                messages[:] = reactive_compact(runtime, messages)
                state.has_attempted_reactive_compact = True
                continue
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": f"[Error] {type(exc).__name__}: {exc}"}
                    ],
                }
            )
            return

        if response.stop_reason == "max_tokens":
            if not state.has_escalated:
                max_tokens = runtime.settings.escalated_max_tokens
                state.has_escalated = True
                continue
            messages.append({"role": "assistant", "content": response.content})
            if state.recovery_count < runtime.settings.max_recovery_retries:
                messages.append(
                    {"role": "user", "content": runtime.settings.continuation_prompt}
                )
                state.recovery_count += 1
                continue
            return

        max_tokens = runtime.settings.default_max_tokens
        state.has_escalated = False
        messages.append({"role": "assistant", "content": response.content})
        if not has_tool_use(response.content):
            extracted = runtime.memory.extract_new_memories(
                memory_snapshot,
                client=runtime.client,
                model=runtime.settings.model_id,
            )
            if extracted:
                print(f"\033[33m[Memory: extracted {extracted} new memories]\033[0m")
            consolidated = runtime.memory.consolidate_memories(
                client=runtime.client,
                model=runtime.settings.model_id,
            )
            if consolidated:
                before, after = consolidated
                print(
                    f"\033[33m[Memory: consolidated {before} -> {after} memories]\033[0m"
                )
            runtime.hooks.trigger("Stop", messages)
            return

        results: list[dict] = []
        compacted_now = False
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"\033[36m> {block.name}\033[0m")
            if block.name == "compact":
                messages[:] = compact_history(runtime, messages)
                messages.append(
                    {
                        "role": "user",
                        "content": "[Compacted. Continue with summarized context.]",
                    }
                )
                compacted_now = True
                break

            blocked = runtime.hooks.trigger("PreToolUse", block)
            if blocked:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(blocked),
                    }
                )
                continue

            if runtime.background.should_run(block.name, block.input):
                bg_id = runtime.background.start(
                    block,
                    handlers,
                    lambda b, out: runtime.hooks.trigger("PostToolUse", b, out),
                )
                output = f"[Background task {bg_id} started] Result will arrive as a task_notification."
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": output}
                )
                continue

            output = call_tool_handler(
                handlers.get(block.name), block.input, block.name
            )
            runtime.hooks.trigger("PostToolUse", block, output)
            print(str(output)[:300])

            if block.name == "todo_write":
                runtime.rounds_since_todo = 0
            else:
                runtime.rounds_since_todo += 1
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": output}
            )

        if compacted_now:
            continue
        messages.append(
            {"role": "user", "content": build_user_content(runtime, results)}
        )


def print_turn_assistants(runtime: Any, messages: list, turn_start: int) -> None:
    from codeagent.core.console import terminal_print

    for msg in messages[turn_start:]:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if getattr(block, "type", None) == "text":
                    terminal_print(
                        block.text, runtime.settings.prompt, runtime.cli_active
                    )
        else:
            terminal_print(str(content), runtime.settings.prompt, runtime.cli_active)


def cron_autorun_loop(
    runtime: Any,
    history: list,
    context: dict,
    on_history_changed: Callable[[], Any] | None = None,
) -> None:
    from codeagent.core.console import terminal_print

    while True:
        time.sleep(1)
        fired = runtime.cron.consume()
        if not fired:
            continue
        with runtime.agent_lock:
            turn_start = len(history)
            for job in fired:
                history.append({"role": "user", "content": f"[Scheduled] {job.prompt}"})
                terminal_print(
                    f"  \033[35m[cron auto] {job.prompt[:60]}\033[0m",
                    runtime.settings.prompt,
                    runtime.cli_active,
                )
            agent_loop(runtime, history, context)
            context.clear()
            context.update(runtime.update_context({}, history))
            print_turn_assistants(runtime, history, turn_start)
            if on_history_changed:
                on_history_changed()
