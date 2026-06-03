# Demo Cases

## Demo 1: Basic File Editing

```text
请读取 README.md，并帮我补充一个快速开始部分。
```

Expected flow:

1. LLM 调用 `read_file`。
2. LLM 调用 `edit_file` 或 `write_file`。
3. Permission Hook 检查路径是否在 workspace 内。
4. 返回修改结果。

## Demo 2: Todo + Task Graph

```text
把这个需求拆成三个任务：分析代码、修改模块、补充测试。第二个任务依赖第一个，第三个任务依赖第二个。
```

Expected tools:

- `create_task`
- `list_tasks`
- `claim_task`
- `complete_task`

## Demo 3: Background Task

```text
运行 pytest，如果比较慢就放到后台。
```

Expected tools:

- `bash` with `run_in_background=true`
- 后台线程完成后注入 `<task_notification>`

## Demo 4: Cron Scheduler

```text
每 5 分钟提醒我检查一次 inbox。
```

Expected tools:

- `schedule_cron`
- `list_crons`
- Cron 触发后将计划任务注入 Agent Loop。

## Demo 5: Mock MCP

```text
连接 docs MCP，并搜索 agent loop 文档。
```

Expected tools:

1. `connect_mcp(name="docs")`
2. 动态出现 `mcp__docs__search`
3. 调用 MCP 工具返回搜索结果。

## Demo 6: Teammate Protocol

```text
创建一个 reviewer teammate，让它先提交修改计划，等我批准后再执行。
```

Expected flow:

1. `spawn_teammate`
2. teammate 调用 `submit_plan`
3. lead inbox 收到 `plan_approval_request`
4. lead 调用 `review_plan`
