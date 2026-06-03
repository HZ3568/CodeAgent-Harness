from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class RecoveryState:
    has_escalated: bool = False
    recovery_count: int = 0
    consecutive_529: int = 0
    has_attempted_reactive_compact: bool = False
    current_model: str = ""


def retry_delay(base_delay_ms: int, attempt: int) -> float:
    base = min(base_delay_ms * (2**attempt), 32000) / 1000
    return base + random.uniform(0, base * 0.25)


def with_retry(fn: Callable[[], T], state: RecoveryState, settings) -> T:
    for attempt in range(settings.max_retries):
        try:
            result = fn()
            state.consecutive_529 = 0
            return result
        except Exception as exc:
            name = type(exc).__name__.lower()
            msg = str(exc).lower()
            if "ratelimit" in name or "429" in msg:
                time.sleep(retry_delay(settings.base_delay_ms, attempt))
                continue
            if "overloaded" in name or "529" in msg or "overloaded" in msg:
                state.consecutive_529 += 1
                if state.consecutive_529 >= settings.max_consecutive_529 and settings.fallback_model_id:
                    state.current_model = settings.fallback_model_id
                    state.consecutive_529 = 0
                time.sleep(retry_delay(settings.base_delay_ms, attempt))
                continue
            raise
    raise RuntimeError(f"Max retries ({settings.max_retries}) exceeded")


def is_prompt_too_long_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("prompt" in msg and "long" in msg) or "context_length_exceeded" in msg or "max_context_window" in msg
