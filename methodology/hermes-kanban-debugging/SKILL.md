---
name: hermes-kanban-debugging
description: Hermes Kanban v0.15.1 workflow, known bugs, SQLite schema, and debugging guide
---
# Hermes Kanban Debugging & Workflow Guide

## Known Issues & Solutions

### Issue 1: `hermes kanban create` hangs permanently (not timeout)
**Symptom**: `hermes kanban create` never returns — no output, no error, blocks forever.  
**Root cause**: Hermes LLM call blocks waiting for approval or some internal gate.  
**Solution**: Get user to grant `/approve always` before running, or use `--json` flag.  
**Verification**: After approval granted, command returns immediately with `Created t_xxxxxxx`.

### Issue 2: `hermes kanban dispatch` always Spawned: 0 on non-default boards
**Symptom**: `dispatch` returns all zeros (`Spawned: 0`) even with ready tasks.  
**Root cause**: Gateway dispatcher does not spawn workers for boards other than `default` (or boards created after gateway startup).  
**Workaround**: Manually run `hermes kanban claim <task_id>` to assign workspace.  
**Note**: Automatic dispatch cycle is broken for custom boards in v0.15.1.

### Issue 3: Claim lock PID mismatch (orphaned running tasks)
**Symptom**: Task shows `status: running` but no worker is executing.  
**Root cause**: Claiming process died, lock persists with stale PID.  
**Diagnosis**: `task_runs.worker_pid` is NULL despite status='running'.  
**Fix**: `hermes kanban reclaim <task_id>` then `hermes kanban claim <task_id>`.

### Issue 4: `platform/` directory name conflicts with Python stdlib
**Symptom**: `import uuid` raises `AttributeError: module 'platform' has no attribute 'system'`.  
**Root cause**: Project dir `platform/` shadows Python's stdlib `platform` module.  
**Fix**: Rename to `platform_core/` or any non-stdlib name.

## SQLite Schema (tasks table — v0.15.1)

**Wrong columns** (old/different schema):
- ❌ `board`, `workspace`, `phase` — do not exist

**Correct schema**:
```
tasks.id, title, body, status, assignee, priority,
created_at, started_at, completed_at,
workspace_kind,   -- TEXT: 'scratch'|'dir'|'worktree'
workspace_path,   -- TEXT: absolute path
goal_mode,       -- INTEGER: 0 or 1
goal_max_turns,  -- INTEGER
max_runtime_seconds, skills,   -- JSON string: '["kanban-worker"]'
claim_lock,      -- TEXT: 'hostname:PID'
claim_expires    -- INTEGER: Unix timestamp
```

**task_links**: `(parent_id, child_id)` — parent blocks child

## Verified Workflow

```bash
# 1. Create & switch board
hermes kanban boards create <slug>
hermes kanban boards use <slug>

# 2. Create tasks (creates on CURRENT board)
hermes kanban create "[PRD] 需求" --assignee <profile>-pm --goal --goal-max-turns 15
hermes kanban create "[Design] 设计" --assignee <profile>-arch --parent <prd_id> --goal

# 3. Claim & execute
hermes kanban claim <task_id>    # prints workspace path
# ... do work ...
hermes kanban complete <task_id> --summary "完成摘要"

# 4. Verify dependency auto-promote
hermes kanban show <child_id>    # status: todo → ready after parent done
```

## Direct SQLite (when CLI hangs)
```python
import sqlite3, uuid, time
db = f'/home/zcxx/.hermes/kanban/boards/{slug}/kanban.db'
conn = sqlite3.connect(db)
cur = conn.cursor()
task_id = 't_' + uuid.uuid4().hex[:8]
cur.execute('''INSERT INTO tasks (id,title,body,status,assignee,created_at,
    workspace_kind,workspace_path,goal_mode,goal_max_turns,max_runtime_seconds,skills)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
    (task_id, title, body, 'ready', assignee, int(time.time()),
     'dir', '/abs/path', 1, 15, 7200, '["kanban-worker"]'))
conn.commit()
```
