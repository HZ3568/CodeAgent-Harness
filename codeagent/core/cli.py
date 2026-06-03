from __future__ import annotations

import threading

from codeagent.core.loop import agent_loop, cron_autorun_loop, print_turn_assistants
from codeagent.core.runtime import create_runtime


def main() -> None:
    runtime = create_runtime()
    runtime.cli_active = True
    print("CodeAgent-Harness")
    print("Enter a question, press Enter to send. Type q to quit.\n")
    history: list = []
    context = runtime.update_context({}, [])
    threading.Thread(target=cron_autorun_loop, args=(runtime, history, context), daemon=True).start()
    while True:
        try:
            query = input(runtime.settings.prompt)
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        runtime.hooks.trigger("UserPromptSubmit", query)
        turn_start = len(history)
        history.append({"role": "user", "content": query})
        with runtime.agent_lock:
            agent_loop(runtime, history, context)
            context = runtime.update_context(context, history)
            print_turn_assistants(runtime, history, turn_start)

        inbox = runtime.protocols.consume_lead_inbox(route_protocol=True)
        if inbox:
            def label(msg: dict) -> str:
                req_id = msg.get("metadata", {}).get("request_id", "")
                suffix = f" req:{req_id}" if req_id else ""
                return f"{msg.get('type', 'message')}{suffix}"

            inbox_text = "\n".join(
                f"From {msg['from']} [{label(msg)}]: {msg['content'][:200]}" for msg in inbox
            )
            history.append({"role": "user", "content": f"[Inbox]\n{inbox_text}"})
        print()


if __name__ == "__main__":
    main()
