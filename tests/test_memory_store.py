from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from codeagent.memory.store import MemoryStore


class FakeMessages:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        text = self.responses.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.messages = FakeMessages(responses)


def test_write_memory_file_rebuilds_index(tmp_path: Path):
    store = MemoryStore(tmp_path)

    path = store.write_memory_file(
        "user-tabs",
        "feedback",
        "User prefers tabs for indentation.",
        "Use tabs when editing project files.",
    )

    assert path.exists()
    assert "type: feedback" in path.read_text(encoding="utf-8")
    index = store.read_index()
    assert "- [user-tabs](user-tabs.md) - User prefers tabs for indentation." in index


def test_build_context_loads_llm_selected_memory(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.write_memory_file(
        "project-api",
        "project",
        "The API module owns request validation.",
        "Keep request validation changes in `api/`.",
    )
    client = FakeClient(["[0]"])

    context = store.build_context(
        [{"role": "user", "content": "Change request validation in the API module."}],
        client=client,
        model="fake-model",
    )

    assert "Memory index:" in context
    assert "<relevant_memories>" in context
    assert "Keep request validation changes in `api/`." in context


def test_llm_empty_selection_does_not_keyword_fallback(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.write_memory_file(
        "api-memory",
        "project",
        "API request validation details.",
        "This would match the user query by keyword.",
    )
    client = FakeClient(["[]"])

    context = store.build_context(
        [{"role": "user", "content": "api request validation"}],
        client=client,
        model="fake-model",
    )

    assert "Memory index:" in context
    assert "<relevant_memories>" not in context


def test_read_index_rebuilds_missing_index(tmp_path: Path):
    store = MemoryStore(tmp_path)
    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()
    (memory_dir / "manual.md").write_text(
        "---\nname: manual\ndescription: Manual memory.\ntype: project\n---\n\nBody.\n",
        encoding="utf-8",
    )

    assert "Manual memory." in store.read_index()


def test_extract_new_memories_writes_files(tmp_path: Path):
    store = MemoryStore(tmp_path)
    client = FakeClient(
        [
            """
            [
              {
                "name": "user-prefers-concise",
                "type": "user",
                "description": "User prefers concise final answers.",
                "body": "Keep final answers short unless detail is requested."
              }
            ]
            """
        ]
    )

    count = store.extract_new_memories(
        [{"role": "user", "content": "Please remember that I prefer concise final answers."}],
        client=client,
        model="fake-model",
    )

    assert count == 1
    assert (tmp_path / ".memory" / "user-prefers-concise.md").exists()
    assert "User prefers concise final answers." in store.read_index()


def test_consolidate_rewrites_memory_files(tmp_path: Path):
    store = MemoryStore(tmp_path, consolidate_threshold=2)
    store.write_memory_file("first", "user", "First preference.", "A")
    store.write_memory_file("second", "user", "Duplicate preference.", "B")
    client = FakeClient(
        [
            """
            [
              {
                "name": "merged",
                "type": "user",
                "description": "Merged preference.",
                "body": "A and B."
              }
            ]
            """
        ]
    )

    result = store.consolidate_memories(client=client, model="fake-model")

    assert result == (2, 1)
    files = sorted(path.name for path in (tmp_path / ".memory").glob("*.md"))
    assert files == ["MEMORY.md", "merged.md"]
    assert "Merged preference." in store.read_index()
