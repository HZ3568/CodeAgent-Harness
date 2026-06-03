from __future__ import annotations

import glob as globlib
import subprocess
from pathlib import Path


def safe_path(path: str, base: Path) -> Path:
    root = base.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Path escapes workspace: {path}")
    return target


def run_bash(command: str, cwd: Path, run_in_background: bool = False) -> str:
    del run_in_background
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        parts: list[str] = []
        if result.stdout.strip():
            parts.append("STDOUT:\n" + result.stdout.strip())
        if result.stderr.strip():
            parts.append("STDERR:\n" + result.stderr.strip())
        if not parts:
            return f"(no output, exit={result.returncode})"
        return ("\n\n".join(parts))[:50000]
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, cwd: Path, limit: int | None = None, offset: int = 0) -> str:
    try:
        lines = safe_path(path, cwd).read_text(encoding="utf-8").splitlines()
        offset = max(int(offset or 0), 0)
        limit = int(limit) if limit is not None else None
        sliced = lines[offset:]
        if limit is not None and limit < len(sliced):
            sliced = sliced[:limit] + [f"... ({len(sliced) - limit} more lines)"]
        return "\n".join(sliced)
    except Exception as exc:
        return f"Error: {exc}"


def run_write(path: str, content: str, cwd: Path) -> str:
    try:
        fp = safe_path(path, cwd)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_edit(path: str, old_text: str, new_text: str, cwd: Path) -> str:
    try:
        fp = safe_path(path, cwd)
        text = fp.read_text(encoding="utf-8")
        if old_text not in text:
            return f"Error: text not found in {path}"
        fp.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_glob(pattern: str, cwd: Path) -> str:
    try:
        matches: list[str] = []
        for match in globlib.glob(pattern, root_dir=cwd):
            if (cwd / match).resolve().is_relative_to(cwd.resolve()):
                matches.append(match)
        return "\n".join(matches) if matches else "(no matches)"
    except Exception as exc:
        return f"Error: {exc}"
