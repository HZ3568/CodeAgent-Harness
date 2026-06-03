from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def extract_text(content: Any) -> str:
    if not isinstance(content, list):
        return str(content)
    return "\n".join(
        getattr(block, "text", "") for block in content if getattr(block, "type", None) == "text"
    ).strip()


def has_tool_use(content: Any) -> bool:
    return any(getattr(block, "type", None) == "tool_use" for block in content)


def estimate_size(messages: list) -> int:
    return len(json.dumps(messages, default=str))


def collect_tool_results(messages: list) -> list[tuple[int, int, dict]]:
    found: list[tuple[int, int, dict]] = []
    for mi, msg in enumerate(messages):
        content = msg.get("content")
        if msg.get("role") != "user" or not isinstance(content, list):
            continue
        for bi, block in enumerate(content):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                found.append((mi, bi, block))
    return found


def persist_large_output(runtime: Any, tool_use_id: str, output: str) -> str:
    if len(output) <= runtime.settings.persist_threshold:
        return output
    out_dir = runtime.settings.workdir / ".task_outputs" / "tool-results"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{tool_use_id}.txt"
    if not path.exists():
        path.write_text(output, encoding="utf-8")
    return f"<persisted-output>\nFull output: {path}\nPreview:\n{output[:2000]}\n</persisted-output>"


def tool_result_budget(runtime: Any, messages: list, max_bytes: int = 200_000) -> list:
    if not messages:
        return messages
    last = messages[-1]
    content = last.get("content")
    if last.get("role") != "user" or not isinstance(content, list):
        return messages
    blocks = [(i, b) for i, b in enumerate(content) if isinstance(b, dict) and b.get("type") == "tool_result"]
    total = sum(len(str(b.get("content", ""))) for _, b in blocks)
    if total <= max_bytes:
        return messages
    for _, block in sorted(blocks, key=lambda pair: len(str(pair[1].get("content", ""))), reverse=True):
        if total <= max_bytes:
            break
        text = str(block.get("content", ""))
        block["content"] = persist_large_output(runtime, block.get("tool_use_id", "unknown"), text)
        total = sum(len(str(b.get("content", ""))) for _, b in blocks)
    return messages


def snip_compact(messages: list, max_messages: int = 50) -> list:
    if len(messages) <= max_messages:
        return messages
    keep_head, keep_tail = 3, max_messages - 3
    snipped = len(messages) - keep_head - keep_tail
    return messages[:keep_head] + [{"role": "user", "content": f"[snipped {snipped} messages]"}] + messages[-keep_tail:]


def micro_compact(runtime: Any, messages: list) -> list:
    tool_results = collect_tool_results(messages)
    if len(tool_results) <= runtime.settings.keep_recent_tool_results:
        return messages
    for _, _, block in tool_results[: -runtime.settings.keep_recent_tool_results]:
        if len(str(block.get("content", ""))) > 120:
            block["content"] = "[Earlier tool result compacted. Re-run if needed.]"
    return messages


def write_transcript(runtime: Any, messages: list) -> Path:
    out_dir = runtime.settings.workdir / ".transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"transcript_{int(time.time())}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    return path


def summarize_history(runtime: Any, messages: list) -> str:
    conversation = json.dumps(messages, default=str)[:80000]
    prompt = (
        "Summarize this coding-agent conversation so work can continue. "
        "Preserve current goal, key findings, changed files, remaining work, and user constraints.\n\n"
        + conversation
    )
    response = runtime.client.messages.create(
        model=runtime.settings.model_id,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )
    return extract_text(response.content) or "(empty summary)"


def compact_history(runtime: Any, messages: list) -> list:
    write_transcript(runtime, messages)
    summary = summarize_history(runtime, messages)
    return [{"role": "user", "content": f"[Compacted]\n\n{summary}"}]


def reactive_compact(runtime: Any, messages: list) -> list:
    write_transcript(runtime, messages)
    try:
        summary = summarize_history(runtime, messages)
    except Exception:
        summary = "Earlier conversation was trimmed after a prompt-too-long error."
    return [{"role": "user", "content": f"[Reactive compact]\n\n{summary}"}, *messages[-5:]]


def prepare_context(runtime: Any, messages: list) -> list:
    messages[:] = tool_result_budget(runtime, messages)
    messages[:] = snip_compact(messages)
    messages[:] = micro_compact(runtime, messages)
    if estimate_size(messages) > runtime.settings.context_limit:
        messages[:] = compact_history(runtime, messages)
    return messages
