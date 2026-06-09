---
name: hermes-kanban-sqlite-workaround
description: Hermes Agent v0.15.1 kanban create 命令永久挂起的临时修复 — 直接写 SQLite
tags: [hermes, kanban, sqlite, workaround]
date_created: 2026-06-04
---

# Hermes Kanban SQLite Workaround

## Problem
`hermes kanban create` command hangs permanently (v0.15.1). Never returns, no error, no timeout — process is deadlocked waiting for LLM response that never comes.

## Workaround
Insert tasks directly into SQLite instead of using the CLI.

### Kanban DB Path
Each board has its own DB at:
```
~/.hermes/kanban/boards/<board_slug>/kanban.db
```

### Tasks Table Schema
Key columns (not obvious from CLI):
- `id` — TEXT, format: `t_{8hex}`
- `title` — TEXT
- `body` — TEXT
- `status` — TEXT: `ready` | `todo` | `in_progress` | `done` | `blocked`
- `assignee` — TEXT: profile name
- `created_at` — INTEGER: UNIX timestamp (seconds, not milliseconds)
- `workspace_kind` — TEXT: `scratch` | `dir` | `worktree`
- `workspace_path` — TEXT: absolute path
- `goal_mode` — INTEGER: 0 or 1
- `goal_max_turns` — INTEGER
- `max_runtime_seconds` — INTEGER
- `skills` — TEXT: JSON array string, e.g. `'["kanban-worker"]'`
- `result` — TEXT: completion summary

### Task Links Table
Table: `task_links`
- `parent_id` — TEXT
- `child_id` — TEXT
- Purpose: parent task must complete before child is promoted to `ready`

### Python Insert Template
```python
import sqlite3, uuid, time

db_path = '/home/zcxx/.hermes/kanban/boards/<board_slug>/kanban.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
now_ts = int(time.time())

task_id = 't_' + uuid.uuid4().hex[:8]
cur.execute('''
INSERT INTO tasks (id, title, body, status, assignee, created_at,
                   workspace_kind, workspace_path, goal_mode,
                   goal_max_turns, max_runtime_seconds, skills)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    task_id, title, body, 'ready', assignee, now_ts,
    'dir', '/abs/path/to/project', 1, 15, 7200, '["kanban-worker"]'
))
conn.commit()

# Add dependency
cur.execute('INSERT INTO task_links (parent_id, child_id) VALUES (?, ?)',
            (parent_id, task_id))
conn.commit()
print(f'Task: {task_id}')
```

## CRITICAL: Two Separate DBs

**Root DB** (`~/.hermes/kanban.db`) ≠ **board DB** (`boards/{slug}/kanban.db`)

If you only query the root DB, stt-whisper tasks show as `archived` or `NULL workspace_path` — they actually live in the board-level DB.

```python
# WRONG — queries root DB
conn = sqlite3.connect("/home/zcxx/.hermes/kanban.db")

# CORRECT — queries board-level DB
conn = sqlite3.connect("/home/zcxx/.hermes/kanban/boards/proj-proj_4be81199/kanban.db")
```

## Common Errors
- `table tasks has no column named 'board'` — board is per-DB file, not a column
- `INTEGER` for `created_at` — not TEXT ISO string, must be UNIX seconds
- **dangling task_links**: if a task insert fails (ID=None), `task_links` foreign key constraint causes rollback — always generate ID first with `t_' + secrets.token_hex(4)`

## Cleanup: Remove Dangling task_links
```python
cur.execute("""
    DELETE FROM task_links
    WHERE parent_id NOT IN (SELECT id FROM tasks)
       OR child_id NOT IN (SELECT id FROM tasks)
""")
```

## Cleanup: Remove NULL-ID Tasks
```python
cur.execute("DELETE FROM tasks WHERE id IS NULL")
```

## Discovery
- Tested: `hermes kanban create` via subprocess → hangs
- Tested: Python `subprocess.run(['hermes', 'kanban', 'create', ...])` → hangs
- Root cause: Hermes LLM call deadlocks in certain environments
