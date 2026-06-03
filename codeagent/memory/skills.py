from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class SkillRegistry:
    def __init__(self, workdir: Path) -> None:
        self.skills_dir = workdir / "skills"
        self.registry: dict[str, dict[str, str]] = {}
        self.scan()

    def _parse_frontmatter(self, text: str) -> tuple[dict[str, Any], str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        try:
            meta = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            meta = {}
        return meta, parts[2].strip()

    def scan(self) -> None:
        self.registry.clear()
        if not self.skills_dir.exists():
            return
        for directory in sorted(self.skills_dir.iterdir()):
            if not directory.is_dir():
                continue
            manifest = directory / "SKILL.md"
            if not manifest.exists():
                continue
            raw = manifest.read_text(encoding="utf-8")
            meta, _ = self._parse_frontmatter(raw)
            name = meta.get("name", directory.name)
            desc = meta.get("description", raw.split("\n")[0].lstrip("#").strip())
            self.registry[name] = {"name": name, "description": desc, "content": raw}

    def list(self) -> str:
        if not self.registry:
            return "(no skills found)"
        return "\n".join(
            f"- {item['name']}: {item['description']}" for item in self.registry.values()
        )

    def load(self, name: str) -> str:
        item = self.registry.get(name)
        if not item:
            available = ", ".join(self.registry.keys()) or "(none)"
            return f"Skill not found: {name}. Available: {available}"
        return item["content"]
