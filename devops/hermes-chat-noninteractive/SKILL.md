---
name: hermes-chat-noninteractive
description: Trigger Hermes agent programmatically with subprocess — correct -q flag vs wrong -z, discovered 2026-06-05
tags:
  - hermes
  - subprocess
  - automation
---

# Hermes chat non-interactive mode

## When to use
Trigger a Hermes agent to process a task programmatically (from subprocess, cron, Flask, etc.) without interactive TUI.

## Correct syntax (v0.15.1)
```bash
hermes chat -q "your prompt here"
```
Use `--query` for the full form.

## Common mistake
`-z` does NOT exist in `hermes chat`. The error:
```
hermes: error: unrecognized arguments: -z ...
```
means you used the wrong flag. Always use `-q`.

## Subprocess example (Python/Flask)
```python
cmd = [
    "hermes", "chat", "-q",
    f"项目 {project_name} 已创建。请作为 CEO 读取 {idea_path}，分析需求。"
]
subprocess.Popen(cmd, cwd=base_dir)
```

## Important notes
- The prompt is passed as a **single string argument** after `-q`, not split across multiple args
- The command runs **asynchronously** — `subprocess.Popen` does not block
- Each invocation starts a **new session** (not resumed)
- Works with `--continue SESSION_ID` to resume a previous session
- Works from any `cwd` — pass `cwd=` to `subprocess.Popen` for project-scoped context

## Related
- Hermes SOUL.md path: `~/.hermes/SOUL.md`
- Kanban boards: `~/.hermes/kanban/boards/<board_name>/kanban.db`
- Kanban tasks table schema: id, title, status, assignee, body, created_at (no `profile` column)
