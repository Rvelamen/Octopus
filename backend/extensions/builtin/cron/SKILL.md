---
name: cron
description: Schedule tasks to be executed at specific times.
---

# Cron

Use the `cron` tool to schedule tasks. All tasks are executed by a subagent.

## Time Options

| Option | Description | Example |
|--------|-------------|---------|
| `at` | One-time task at specific time | `at="2026-02-11T16:30:00"` |
| `every_seconds` | Recurring task with interval | `every_seconds=3600` |
| `cron_expr` | Cron expression for complex schedules | `cron_expr="0 9 * * *"` |

## Examples

### One-time Task
```
cron(action="add", message="发送文件给用户", at="2026-02-13T10:30:00")
```

### Recurring Task
```
cron(action="add", message="检查服务器状态", every_seconds=3600)
```

### Daily Schedule
```
cron(action="add", message="每日报告", cron_expr="0 9 * * *")
```

### List/Remove Jobs
```
cron(action="list")
cron(action="remove", job_id="abc123")
```

## How It Works

When a scheduled time arrives:
1. A subagent is spawned to execute the task
2. The subagent has access to files, shell, web, channel, and plugins
3. After completion, the subagent reports results to the user

## Task Description Tips

Write clear, actionable task descriptions:
- ✅ "发送元素周期表.xlsx文件给用户"
- ✅ "检查服务器状态并发送报告"
- ❌ "提醒我" (too vague)

The subagent will interpret and execute your task description.
