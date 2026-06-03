# Permission System Design

## 1. Design Principle

权限系统必须位于工具执行之前，而不是分散在每个工具内部。这样可以保证任何工具调用在真正执行前都经过统一边界检查。

## 2. Hook Entry

默认权限 Hook 位于 `codeagent/hooks/defaults.py`：

```python
runtime.hooks.register("PreToolUse", make_permission_hook(runtime))
```

Agent Loop 在执行工具前调用：

```python
blocked = runtime.hooks.trigger("PreToolUse", block)
if blocked:
    return tool_result(block.id, blocked)
```

## 3. Bash Policy

当前策略分为两类：

- **Deny List**：直接拒绝，例如 `rm -rf /`、`sudo`、`shutdown`、`mkfs`、`dd if=`。
- **Destructive Pattern**：需要人工确认，例如 `rm `、`chmod 777`、`> /etc/`。

## 4. File Policy

文件写入和编辑工具必须通过 `safe_path`：

- 只允许访问 `workdir` 内部路径。
- 拒绝 `../` 逃逸工作区。
- Worktree teammate 会把 base path 切换到对应 worktree。

## 5. MCP Policy

默认策略会拦截名称包含 `deploy` 的 MCP 工具，并要求人工确认。这是教学型策略，真实项目中建议基于 MCP tool annotation 或配置文件判断 readOnly/destructive。

## 6. Suggested Improvements

| Improvement | Description |
|---|---|
| Policy YAML | 将 deny/ask/allow 规则配置化 |
| Audit Log | 保存工具名、参数摘要、执行人、时间、结果 |
| Approval UI | 在 Web UI 中弹出审批窗口 |
| Role-based Policy | 对 lead/subagent/teammate 设置不同权限 |
| Sandbox | 对 Bash 工具接入容器/临时目录沙箱 |
