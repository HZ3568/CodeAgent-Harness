from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class HookManager:
    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def register(self, event: str, callback: Callable[..., Any]) -> None:
        self._hooks[event].append(callback)

    def trigger(self, event: str, *args: Any) -> Any:
        for callback in self._hooks.get(event, []):
            result = callback(*args)
            if result is not None:
                return result
        return None
