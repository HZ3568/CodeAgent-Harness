from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import yaml

MEMORY_TYPES = {"user", "feedback", "project", "reference"}
DEFAULT_CONSOLIDATE_THRESHOLD = 10
DEFAULT_MAX_SELECTED = 5


class MemoryStore:
    def __init__(self, workdir: Path, consolidate_threshold: int = DEFAULT_CONSOLIDATE_THRESHOLD) -> None:
        self.memory_dir = workdir / ".memory"
        self.index = self.memory_dir / "MEMORY.md"
        self.consolidate_threshold = consolidate_threshold
        self._selection_cache: dict[tuple[str, str, int], list[str]] = {}

    def _parse_frontmatter(self, text: str) -> tuple[dict[str, Any], str]:
        if not text.startswith("---"):
            return {}, text.strip()
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text.strip()
        try:
            meta = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        return meta, parts[2].strip()

    def _memory_path(self, filename: str) -> Path:
        path = (self.memory_dir / filename).resolve()
        root = self.memory_dir.resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Memory path escapes memory directory: {filename}")
        return path

    def _slug(self, name: str) -> str:
        slug = re.sub(r"[^\w.-]+", "-", name.strip().lower(), flags=re.UNICODE).strip("-._")
        if not slug or slug.upper() == "MEMORY":
            slug = f"memory-{int(time.time())}"
        return slug

    def _catalog_signature(self, files: list[dict[str, str]]) -> str:
        return "|".join(f"{item['filename']}:{item['description']}" for item in files)

    def _content_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    parts.append(str(block.get("text", "")))
                elif block_type == "tool_result":
                    continue
                elif "content" in block:
                    parts.append(str(block.get("content", "")))
                continue
            if getattr(block, "type", None) == "text":
                parts.append(str(getattr(block, "text", "")))
        return "\n".join(part for part in parts if part).strip()

    def _response_text(self, content: Any) -> str:
        return self._content_text(content).strip()

    def _extract_json_array(self, text: str) -> list[Any] | None:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\[", text):
            try:
                value, _ = decoder.raw_decode(text[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(value, list):
                return value
        return None

    def snapshot_messages(self, messages: list) -> list[dict[str, str]]:
        snapshot: list[dict[str, str]] = []
        for msg in messages:
            text = self._content_text(msg.get("content", "")).strip()
            if text:
                snapshot.append({"role": str(msg.get("role", "?")), "content": text})
        return snapshot

    def write_memory_file(self, name: str, mem_type: str, description: str, body: str) -> Path:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        mem_type = mem_type if mem_type in MEMORY_TYPES else "user"
        filename = f"{self._slug(name)}.md"
        path = self._memory_path(filename)
        metadata = {
            "name": name.strip() or path.stem,
            "description": description.strip(),
            "type": mem_type,
        }
        frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
        path.write_text(f"---\n{frontmatter}\n---\n\n{body.strip()}\n", encoding="utf-8")
        self.rebuild_index()
        self._selection_cache.clear()
        return path

    def rebuild_index(self, max_lines: int = 200) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for item in self.list_memory_files():
            lines.append(f"- [{item['name']}]({item['filename']}) - {item['description']}")
            if len(lines) >= max_lines:
                break
        self.index.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _index_needs_rebuild(self) -> bool:
        if not self.memory_dir.exists():
            return False
        memory_files = [path for path in self.memory_dir.glob("*.md") if path.name != "MEMORY.md"]
        if not memory_files:
            return False
        if not self.index.exists():
            return True
        index_mtime = self.index.stat().st_mtime
        return any(path.stat().st_mtime > index_mtime for path in memory_files)

    def read_index(self, limit: int = 4000) -> str:
        if self._index_needs_rebuild():
            self.rebuild_index()
        if not self.index.exists():
            return ""
        return self.index.read_text(encoding="utf-8").strip()[:limit]

    def read_relevant(self, limit: int = 2000) -> str:
        return self.read_index(limit)

    def read_memory_file(self, filename: str) -> str | None:
        try:
            path = self._memory_path(filename)
        except ValueError:
            return None
        if not path.exists() or path.name == "MEMORY.md":
            return None
        return path.read_text(encoding="utf-8")

    def list_memory_files(self) -> list[dict[str, str]]:
        if not self.memory_dir.exists():
            return []
        result: list[dict[str, str]] = []
        for path in sorted(self.memory_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            raw = path.read_text(encoding="utf-8")
            meta, body = self._parse_frontmatter(raw)
            result.append(
                {
                    "filename": path.name,
                    "name": str(meta.get("name") or path.stem),
                    "description": str(meta.get("description") or (body.splitlines()[0][:120] if body else "")),
                    "type": str(meta.get("type") or "user"),
                    "body": body,
                }
            )
        return result

    def _recent_user_text(self, messages: list, max_messages: int = 3, limit: int = 2000) -> str:
        recent: list[str] = []
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            text = self._content_text(msg.get("content", "")).strip()
            if text:
                recent.append(text)
            if len(recent) >= max_messages:
                break
        return "\n".join(reversed(recent))[:limit]

    def _keyword_select(self, files: list[dict[str, str]], recent: str, max_items: int) -> list[str]:
        terms = re.findall(r"[\w.-]{2,}", recent.lower(), flags=re.UNICODE)
        scored: list[tuple[int, str]] = []
        for item in files:
            haystack = f"{item['name']} {item['description']} {item['body'][:500]}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, item["filename"]))
        scored.sort(reverse=True)
        return [filename for _, filename in scored[:max_items]]

    def select_relevant_memories(
        self,
        messages: list,
        client: Any | None = None,
        model: str | None = None,
        max_items: int = DEFAULT_MAX_SELECTED,
    ) -> list[str]:
        files = self.list_memory_files()
        if not files:
            return []
        recent = self._recent_user_text(messages)
        if not recent.strip():
            return []

        cache_key = (recent, self._catalog_signature(files), max_items)
        if cache_key in self._selection_cache:
            return list(self._selection_cache[cache_key])

        selected: list[str] = []
        selector_returned = False
        if client is not None and model:
            catalog = "\n".join(
                f"{idx}: {item['name']} - {item['description']}" for idx, item in enumerate(files)
            )
            prompt = (
                "Given the recent conversation and the memory catalog below, select only the memory "
                "indices that are clearly relevant. Return ONLY a JSON array of integers, for example [0, 3]. "
                "Return [] if none are relevant.\n\n"
                f"Recent conversation:\n{recent}\n\n"
                f"Memory catalog:\n{catalog}"
            )
            try:
                response = client.messages.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                )
                indices = self._extract_json_array(self._response_text(response.content))
                selector_returned = indices is not None
                indices = indices or []
                for idx in indices:
                    if isinstance(idx, int) and 0 <= idx < len(files):
                        filename = files[idx]["filename"]
                        if filename not in selected:
                            selected.append(filename)
                    if len(selected) >= max_items:
                        break
            except Exception:
                selected = []

        if not selector_returned and not selected:
            selected = self._keyword_select(files, recent, max_items)

        self._selection_cache[cache_key] = list(selected)
        return selected

    def load_relevant_memories(
        self,
        messages: list,
        client: Any | None = None,
        model: str | None = None,
        max_items: int = DEFAULT_MAX_SELECTED,
        per_file_limit: int = 5000,
    ) -> str:
        filenames = self.select_relevant_memories(messages, client, model, max_items)
        if not filenames:
            return ""
        parts = ["<relevant_memories>"]
        for filename in filenames:
            content = self.read_memory_file(filename)
            if not content:
                continue
            if len(content) > per_file_limit:
                content = content[:per_file_limit] + "\n...[memory truncated]"
            parts.append(content)
        parts.append("</relevant_memories>")
        return "\n\n".join(parts)

    def build_context(
        self,
        messages: list,
        client: Any | None = None,
        model: str | None = None,
        index_limit: int = 4000,
        max_items: int = DEFAULT_MAX_SELECTED,
    ) -> str:
        index = self.read_index(index_limit)
        relevant = self.load_relevant_memories(messages, client, model, max_items)
        parts: list[str] = []
        if index:
            parts.append("Memory index:\n" + index)
        if relevant:
            parts.append("Loaded memory files:\n" + relevant)
        return "\n\n".join(parts)

    def extract_new_memories(self, messages: list, client: Any | None, model: str | None) -> int:
        if client is None or not model:
            return 0

        normalized = self.snapshot_messages(messages)[-10:]
        dialogue = "\n".join(f"{msg['role']}: {msg['content']}" for msg in normalized)
        if not dialogue.strip():
            return 0

        existing = self.list_memory_files()
        existing_desc = "\n".join(
            f"- {item['name']}: {item['description']}" for item in existing
        ) or "(none)"
        prompt = (
            "Extract durable memories from this coding-agent dialogue.\n"
            "Return a JSON array. Each item must be {name, type, description, body}.\n"
            "- name: short kebab-case identifier.\n"
            "- type: one of user, feedback, project, reference.\n"
            "- description: one-line summary for MEMORY.md.\n"
            "- body: full detail in Markdown.\n"
            "Save only durable user preferences, explicit feedback, stable project facts, or external references. "
            "Do not save one-off task steps, transient errors, or anything already covered by existing memories. "
            "If there is nothing new, return [].\n\n"
            f"Existing memories:\n{existing_desc}\n\n"
            f"Dialogue:\n{dialogue[:4000]}"
        )

        try:
            response = client.messages.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
            )
            items = self._extract_json_array(self._response_text(response.content)) or []
        except Exception:
            return 0

        count = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or f"memory-{int(time.time())}")
            mem_type = str(item.get("type") or "user")
            description = str(item.get("description") or "").strip()
            body = str(item.get("body") or "").strip()
            if description and body:
                self.write_memory_file(name, mem_type, description, body)
                count += 1
        return count

    def consolidate_memories(self, client: Any | None, model: str | None) -> tuple[int, int] | None:
        files = self.list_memory_files()
        if len(files) < self.consolidate_threshold or client is None or not model:
            return None

        catalog = "\n\n".join(
            f"## {item['filename']}\n"
            f"name: {item['name']}\n"
            f"type: {item['type']}\n"
            f"description: {item['description']}\n\n"
            f"{item['body']}"
            for item in files
        )
        prompt = (
            "Consolidate the following memory files.\n"
            "Rules:\n"
            "1. Merge duplicates into one memory.\n"
            "2. Remove outdated or contradicted memories.\n"
            "3. Keep the total under 30 memories.\n"
            "4. Preserve important user preferences above all.\n"
            "Return ONLY a JSON array. Each item: {name, type, description, body}.\n\n"
            f"{catalog[:16000]}"
        )

        try:
            response = client.messages.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
            )
            items = self._extract_json_array(self._response_text(response.content)) or []
        except Exception:
            return None

        valid_items = [
            item
            for item in items
            if isinstance(item, dict)
            and str(item.get("description") or "").strip()
            and str(item.get("body") or "").strip()
        ]
        if not valid_items:
            return None

        for path in self.memory_dir.glob("*.md"):
            if path.name != "MEMORY.md":
                path.unlink()
        for item in valid_items:
            self.write_memory_file(
                str(item.get("name") or f"memory-{int(time.time())}"),
                str(item.get("type") or "user"),
                str(item.get("description") or ""),
                str(item.get("body") or ""),
            )
        self.rebuild_index()
        return len(files), len(valid_items)
