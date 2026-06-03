# Architecture Design

## 1. Overall Goal

CodeAgent-Harness 将单文件 Coding Agent 示例拆成可维护的 Harness 架构。Harness 的核心职责不是“生成代码”本身，而是管理模型与外部环境之间的交互边界：工具调用、权限控制、上下文管理、任务状态、协作协议和可观测性。

## 2. Core Agent Loop

主循环位于 `codeagent/core/loop.py`，每轮执行以下步骤：

1. 消费 Cron 触发的计划任务。
2. 注入后台任务完成通知。
3. 对上下文执行预算控制与压缩。
4. 组装系统提示词。
5. 调用 LLM。
6. 如果返回普通文本，则结束本轮。
7. 如果返回 `tool_use`，进入工具分发流程。
8. 将 `tool_result` 作为用户侧消息返回给模型。

```mermaid
sequenceDiagram
    participant User
    participant Loop
    participant LLM
    participant Dispatcher
    participant Tool
    User->>Loop: query
    Loop->>LLM: messages + tools + system prompt
    LLM-->>Loop: text or tool_use
    Loop->>Dispatcher: tool_use blocks
    Dispatcher->>Tool: validated call
    Tool-->>Dispatcher: output
    Dispatcher-->>Loop: tool_result
    Loop->>LLM: tool_result feedback
```

## 3. Module Responsibilities

| Module | Responsibility |
|---|---|
| `core` | 配置、CLI、LLM 调用、错误恢复、Prompt Assembly、上下文压缩、Agent Loop |
| `tools` | 工具 Schema、工具 Handler、文件工具、Bash、Todo、Skill、Tool Registry |
| `hooks` | HookManager、权限检查、日志、Stop 统计 |
| `memory` | `.memory/MEMORY.md` 与 `skills/*/SKILL.md` 加载 |
| `tasks` | durable task、任务依赖、Worktree、Cron、后台任务 |
| `agents` | Subagent、teammate thread、message bus、计划审批协议 |
| `mcp` | mock MCP server、工具发现、动态工具拼接 |

## 4. Tool Dispatch

`tools/registry.py` 暴露 `build_tool_pool(runtime)`：

- 返回给模型看的 `tools` schema。
- 返回 Python 内部执行用的 `handlers`。
- 将 MCP 动态工具转换成 `mcp__{server}__{tool}` 命名。

这种设计把“模型看到的工具接口”和“Python 实际执行函数”分开，便于后续替换模型或接入真实 MCP。

## 5. Memory and Skills

系统提示词每轮重新组装：

- `MemoryStore` 注入 `.memory/MEMORY.md` 的前若干字符。
- `SkillRegistry` 扫描 `skills/*/SKILL.md` 并生成技能目录。
- 模型可调用 `load_skill(name)` 获取完整技能内容。

## 6. Context Compaction

上下文压缩分三层：

1. **Tool Result Budget**：超大工具输出写入 `.task_outputs/tool-results/`。
2. **Micro Compact**：旧工具结果替换成简短占位符。
3. **Summary Compact**：超过上下文预算后调用 LLM 生成摘要，并保存 transcript。

## 7. Multi-Agent

`agents/teammate.py` 中 teammate 通过后台线程运行，使用 `MessageBus` 的 JSONL mailbox 通信。协议请求使用 request id 进行匹配，支持：

- `plan_approval_request`
- `plan_approval_response`
- `shutdown_request`
- `shutdown_response`

## 8. Extensibility Roadmap

- 将 mock MCP 替换为真实 stdio/http MCP client。
- 增加 WebSocket/SSE 前端实时日志。
- 将权限策略从硬编码改为 YAML 配置。
- 增加工具执行审计日志与 replay。
- 增加更完整的端到端测试。
