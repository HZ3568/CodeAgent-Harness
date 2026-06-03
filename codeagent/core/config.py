from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class Settings:
    workdir: Path
    model_id: str
    primary_model: str
    fallback_model_id: str | None
    anthropic_base_url: str | None
    default_max_tokens: int = 8000
    escalated_max_tokens: int = 16000
    max_retries: int = 3
    max_consecutive_529: int = 2
    max_recovery_retries: int = 2
    base_delay_ms: int = 500
    context_limit: int = 50000
    keep_recent_tool_results: int = 3
    persist_threshold: int = 30000
    continuation_prompt: str = "Continue from the previous response. Do not repeat completed work."
    prompt: str = "\033[36magent >> \033[0m"


def _load_yaml(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a mapping: {path}")
    return data


def load_settings(config_path: str | Path | None = None) -> Settings:
    load_dotenv(override=True)
    path = Path(config_path) if config_path else Path("config.yaml")
    config = _load_yaml(path)

    if os.getenv("ANTHROPIC_BASE_URL"):
        # Anthropic-compatible reverse proxies normally use ANTHROPIC_API_KEY.
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

    limits = config.get("limits", {}) or {}
    runtime = config.get("runtime", {}) or {}

    model_id = os.getenv("MODEL_ID") or config.get("model_id") or "claude-sonnet-4-20250514"
    fallback = os.getenv("FALLBACK_MODEL_ID") or config.get("fallback_model_id")
    base_url = os.getenv("ANTHROPIC_BASE_URL") or config.get("anthropic_base_url")
    workdir = Path(os.getenv("CODEAGENT_WORKDIR") or config.get("workdir") or ".").resolve()

    return Settings(
        workdir=workdir,
        model_id=model_id,
        primary_model=model_id,
        fallback_model_id=fallback,
        anthropic_base_url=base_url,
        default_max_tokens=int(limits.get("default_max_tokens", 8000)),
        escalated_max_tokens=int(limits.get("escalated_max_tokens", 16000)),
        context_limit=int(limits.get("context_limit", 50000)),
        keep_recent_tool_results=int(limits.get("keep_recent_tool_results", 3)),
        persist_threshold=int(limits.get("persist_threshold", 30000)),
        max_retries=int(runtime.get("max_retries", 3)),
        max_consecutive_529=int(runtime.get("max_consecutive_529", 2)),
        max_recovery_retries=int(runtime.get("max_recovery_retries", 2)),
        base_delay_ms=int(runtime.get("base_delay_ms", 500)),
        prompt=str(runtime.get("prompt", "\033[36magent >> \033[0m")),
    )
