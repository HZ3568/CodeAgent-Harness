from __future__ import annotations

from pathlib import Path


class MemoryStore:
    def __init__(self, workdir: Path) -> None:
        self.memory_dir = workdir / ".memory"
        self.index = self.memory_dir / "MEMORY.md"

    def read_relevant(self, limit: int = 2000) -> str:
        if not self.index.exists():
            return ""
        return self.index.read_text(encoding="utf-8")[:limit]
