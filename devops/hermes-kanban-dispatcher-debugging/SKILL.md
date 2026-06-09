---
name: hermes-kanban-dispatcher-debugging
description: Debug why Hermes Kanban tasks stay in ready and don't spawn, or why dispatcher seems to require manual dispatch.
triggers:
  - "hermes kanban dispatch required"
  - "task stays in ready forever"
  - "dispatcher not spawning tasks"
  - "kanban dispatcher stuck"
---

# Hermes Kanban Dispatcher Debugging

## Diagnostic Steps

### Step 1: Understand the dispatcher architecture
- The dispatcher lives in `gateway/run.py` → `_kanban_dispatcher_watcher()`
- Controlled by `kanban.dispatch_in_gateway` (default: `True`) and `kanban.dispatch_interval_seconds` (default: **60 seconds**)
- The dispatcher tick also runs auto-promotion via `recompute_ready()` (parents done → children auto-ready)

### Step 2: Check config
```python
from hermes_cli.config import load_config
cfg = load_config()
kanban = cfg.get('kanban', {}) if isinstance(cfg, dict) else {}
print('kanban config:', dict(kanban))
# Shows: dispatch_in_gateway, dispatch_interval_seconds, failure_limit, max_spawn, etc.
```

### Step 3: Check actual dispatcher behavior
```python
from hermes_cli import kanban_db as _kb

# Check if dispatcher sees spawnable ready tasks
for board in _kb.list_boards(include_archived=False):
    slug = board.get('slug')
    conn = _kb.connect(board=slug)
    has = _kb.has_spawnable_ready(conn)
    if has:
        rows = conn.execute(
            "SELECT id, title, status, assignee FROM tasks WHERE status='ready'"
        ).fetchall()
        print(f'{slug}: {len(rows)} ready tasks')
    conn.close()
```

### Step 4: Run dispatch_once manually to test
```python
from hermes_cli import kanban_db as _kb

conn = _kb.connect(board='<board_slug>')
result = _kb.dispatch_once(
    conn,
    board='<board_slug>',
    max_spawn=None,
    max_in_progress=None,
    failure_limit=2,
    stale_timeout_seconds=0,
)
print(f'spawned: {result.spawned}')
conn.close()
```
**If spawned list is empty**: check `has_spawnable_ready` — likely assignee has no corresponding Hermes profile.

**If spawned list has entries but wrong task**: the target task may be `blocked` or in wrong status, not a dispatcher issue.

### Step 5: Check why a specific task didn't spawn
```python
conn = _kb.connect(board='<board_slug>')
task = conn.execute("SELECT * FROM tasks WHERE id='<task_id>'").fetchone()
if task:
    for k, v in zip(task.keys(), task):
        print(f'{k}: {v}')
# Key fields: status, assignee, claim_lock, consecutive_failures,
#             goal_mode, goal_max_turns, last_failure_error
conn.close()
```

### Step 6: Common failure modes
| Symptom | Cause | Fix |
|---------|-------|-----|
| `hermes kanban dispatch` → Spawned: 0 | **Wrong board in `~/.hermes/kanban/current`** | Set `HERMES_KANBAN_BOARD=slug` env var or update current file |
| Task stays in `ready`, never spawns | Assignee profile doesn't exist | Check `profile_exists()` |
| Task is `blocked` | `consecutive_failures >= failure_limit` or `goal_max_turns` exhausted | Reduce scope or use `--goal --goal-max-turns 300` |
| Task is `running` | Already spawned | Dispatcher working fine |
| `spawned=[]` but `has_spawnable_ready=True` | `max_in_progress` cap reached | Wait for running tasks to finish |
| Dispatcher logs invisible | `gateway.run` logger → `gateway.*` handler → `gateway.log` (often not created) | Check `agent.log` or add file handler manually |
| "Must manually dispatch" every time | CLI dispatch targeting wrong board (current ≠ board with tasks) | See board resolution fix above |

### Quick board sanity check (run this first)
```python
from hermes_cli import kanban_db as _kb
import os
from pathlib import Path

current = Path("~/.hermes/kanban/current").expanduser().read_text().strip()
print(f"~/.hermes/kanban/current = {current}")

for board in _kb.list_boards(include_archived=False):
    slug = board.get('slug')
    conn = _kb.connect(board=slug)
    ready = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='ready'").fetchone()[0]
    running = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='running'").fetchone()[0]
    if ready or running:
        marker = " ← current" if slug == current else ""
        print(f"  {slug}: {ready} ready, {running} running{marker}")
    conn.close()
```

### Step 7: Increase task iteration budget (prevents blocked)
When creating a Dev task that may need many iterations:
```
hermes kanban create "<title>" --assignee dev --goal --goal-max-turns 300
```
Default is 90 iterations. Large projects exhaust this → task becomes `blocked`.

## Key Files
- `gateway/run.py`: `_kanban_dispatcher_watcher()` — embedded dispatcher loop
- `hermes_cli/kanban_db.py`: `dispatch_once()`, `has_spawnable_ready()`, `has_spawnable_review()`
- `hermes_cli/profiles.py`: `profile_exists()` — validates assignee maps to real profile
- `~/.hermes/config.yaml`: `kanban.dispatch_in_gateway`, `kanban.dispatch_interval_seconds`
- `~/.hermes/logs/agent.log`: See note below about logging

## ⚠️ Critical: Board Resolution (most common "manual dispatch required" cause)

### How board is resolved in different contexts

| Context | Board resolution method | Which board it targets |
|---------|------------------------|----------------------|
| `hermes kanban dispatch` (CLI) | Reads `~/.hermes/kanban/current` | **Single board** (current only) |
| Gateway dispatcher tick | Iterates ALL boards from DB | **All boards** |
| `hermes kanban create` (CLI) | `--board` flag → env var → `~/.hermes/kanban/current` → `default` | Single board |
| Python direct (`_kb.connect(board=slug)`) | Explicit `board=` parameter | Whatever you pass |

### The problem

Tasks exist in board `proj-proj_4be81199` but `~/.hermes/kanban/current` contains `project_1780702442019` (a different board with no ready tasks). Running `hermes kanban dispatch` spawns 0 tasks because it dispatches the EMPTY board, not the board with ready tasks.

### The fix

```bash
# ❌ Wrong board — tasks exist in proj-proj_4be81199, but current is project_1780702442019
hermes kanban dispatch
# Output: Spawned: 0

# ✅ Correct — target the board where tasks actually exist
HERMES_KANBAN_BOARD=proj-proj_4be81199 hermes kanban dispatch
# Output: Spawned: 3

# ✅ Alternative — write to current file first
echo "proj-proj_4be81199" > ~/.hermes/kanban/current
hermes kanban dispatch
```

### In app.py / automation scripts

Always set `HERMES_KANBAN_BOARD` env var before calling subprocess dispatch:

```python
import subprocess, os
os.environ['HERMES_KANBAN_BOARD'] = board_slug
subprocess.run(['hermes', 'kanban', 'dispatch'], check=True)
```

### Gateway dispatcher vs CLI dispatcher

The **Gateway dispatcher** (when `kanban.dispatch_in_gateway=true`) ticks ALL boards in a loop — it does NOT suffer from this board resolution issue. It will correctly dispatch tasks in any board.

The **CLI `hermes kanban dispatch`** only dispatches ONE board (current).

**Therefore**: if you see tasks stuck in `ready` but `hermes kanban dispatch` spawns 0, the issue is almost certainly board resolution (wrong `~/.hermes/kanban/current`).

## ⚠️ Logging: Dispatcher logs may be silently lost

The embedded dispatcher in `gateway/run.py` uses:
```python
logger = logging.getLogger(__name__)  # = "gateway.run"
```

The logging config (`hermes_logging.py`) routes `gateway.*` to `gateway.log`. However:
- `gateway.log` may not exist (log directory only has `agent.log`, `errors.log`)
- `gateway.run` logs are NOT the same as `gateway` prefix logs
- Result: all dispatcher heartbeat logs (`"kanban dispatcher: spawning..."`, `"dispatcher tick..."`) are silently discarded

**Workaround**: Check `~/.hermes/logs/agent.log` — the `gateway.run` logger may write there if the root logger has a handler, but most dispatcher info logs are lost.

## Verification
After fixes, verify:
1. `has_spawnable_ready(board)` returns `True` for the right tasks
2. `dispatch_once()` returns non-empty `spawned` list
3. Task transitions to `running` status in kanban board
