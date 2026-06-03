from __future__ import annotations

import json
import time
from pathlib import Path

from codeagent.core.console import terminal_print


class MessageBus:
    def __init__(self, workdir: Path) -> None:
        self.mailbox_dir = workdir / ".mailboxes"
        self.mailbox_dir.mkdir(exist_ok=True)

    def send(self, from_agent: str, to_agent: str, content: str, msg_type: str = "message", metadata: dict | None = None) -> None:
        msg = {
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "type": msg_type,
            "ts": time.time(),
            "metadata": metadata or {},
        }
        inbox = self.mailbox_dir / f"{to_agent}.jsonl"
        with inbox.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg) + "\n")
        terminal_print(f"  \033[33m[bus] {from_agent} → {to_agent}: ({msg_type}) {content[:50]}\033[0m")

    def read_inbox(self, agent: str) -> list[dict]:
        inbox = self.mailbox_dir / f"{agent}.jsonl"
        if not inbox.exists():
            return []
        msgs = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines() if line.strip()]
        inbox.unlink()
        return msgs
