from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="CodeAgent-Harness", layout="wide")
st.title("CodeAgent-Harness Dashboard")

workdir = Path.cwd()
st.caption(f"Workspace: `{workdir}`")

col1, col2, col3, col4 = st.columns(4)

with col1:
    tasks = sorted((workdir / ".tasks").glob("task_*.json")) if (workdir / ".tasks").exists() else []
    st.metric("Tasks", len(tasks))
with col2:
    crons = workdir / ".scheduled_tasks.json"
    cron_count = len(json.loads(crons.read_text(encoding="utf-8"))) if crons.exists() else 0
    st.metric("Cron Jobs", cron_count)
with col3:
    memory_dir = workdir / ".memory"
    memories = memory_dir / "MEMORY.md"
    memory_files = [p for p in memory_dir.glob("*.md") if p.name != "MEMORY.md"] if memory_dir.exists() else []
    st.metric("Memory", len(memory_files))
with col4:
    worktrees = list((workdir / ".worktrees").iterdir()) if (workdir / ".worktrees").exists() else []
    st.metric("Worktrees", len([p for p in worktrees if p.is_dir()]))

st.subheader("Tasks")
if tasks:
    rows = []
    for path in tasks:
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    st.dataframe(rows, use_container_width=True)
else:
    st.info("No tasks found. Run the CLI and ask the agent to create tasks.")

st.subheader("Scheduled Jobs")
if crons.exists():
    st.json(json.loads(crons.read_text(encoding="utf-8")))
else:
    st.info("No durable cron file found.")

st.subheader("Memory Preview")
if memories.exists():
    st.code(memories.read_text(encoding="utf-8")[:4000])
else:
    st.info("No memory index found yet. The agent creates `.memory/MEMORY.md` after durable memories are extracted.")
