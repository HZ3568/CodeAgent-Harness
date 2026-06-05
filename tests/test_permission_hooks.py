from __future__ import annotations

from types import SimpleNamespace

from codeagent.hooks.defaults import make_permission_hook, register_default_hooks
from codeagent.hooks.manager import HookManager


def test_permission_hook_denies_destructive_bash_inside_echo(tmp_path, monkeypatch, capsys):
    runtime = SimpleNamespace(settings=SimpleNamespace(workdir=tmp_path))
    block = SimpleNamespace(
        name="bash",
        input={"command": 'echo "rmdir test_dir"'},
    )
    monkeypatch.setattr("builtins.input", lambda _: "n")

    result = make_permission_hook(runtime)(block)

    assert result == "Permission denied by user"
    output = capsys.readouterr().out
    assert "[permission-debug] hook called" in output
    assert "[permission-debug] block.name=bash" in output
    assert "[permission-debug] command='echo \"rmdir test_dir\"'" in output
    assert "[permission-debug] destructive hits=['rmdir']" in output
    assert "[permission] destructive command" in output


def test_default_pretool_hook_registers_permission_before_log(tmp_path, monkeypatch, capsys):
    runtime = SimpleNamespace(
        settings=SimpleNamespace(workdir=tmp_path),
        hooks=HookManager(),
    )
    register_default_hooks(runtime)
    block = SimpleNamespace(
        name="bash",
        input={"command": 'echo "rmdir test_dir"'},
    )
    monkeypatch.setattr("builtins.input", lambda _: "n")

    result = runtime.hooks.trigger("PreToolUse", block)

    assert result == "Permission denied by user"
    output = capsys.readouterr().out
    assert "[permission-debug] hook called" in output
    assert "[permission-debug] destructive hits=['rmdir']" in output
    assert "[HOOK] bash" not in output
