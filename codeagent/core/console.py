from __future__ import annotations

import threading

try:
    import readline

    readline.parse_and_bind("set bind-tty-special-chars off")
    READLINE_AVAILABLE = True
except Exception:  # pragma: no cover - Windows often has no readline.
    READLINE_AVAILABLE = False


def terminal_print(text: str, prompt: str = "", cli_active: bool = False) -> None:
    if threading.current_thread() is threading.main_thread() or not cli_active:
        print(text)
        return
    line = ""
    if READLINE_AVAILABLE:
        try:
            line = readline.get_line_buffer()
        except Exception:
            line = ""
    print(f"\r\033[K{text}")
    print(prompt + line, end="", flush=True)
