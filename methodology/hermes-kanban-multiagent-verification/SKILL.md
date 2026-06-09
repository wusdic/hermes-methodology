---
name: hermes-kanban-multiagent-verification
description: Verify and debug Hermes Kanban multi-agent workflow — why a board is empty, gateway dispatcher status, chat -q vs chat distinction, SQLite task inspection.
---

# Hermes Kanban Multi-Agent Workflow Verification

## Context
When investigating why a new Hermes Kanban project board was empty while `proj-proj_4be81199` had full multi-role分工, discovered a critical distinction between Kanban-aware and Kanban-ignorant invocation modes.

## Trigger Condition
Investigating empty Kanban boards or verifying whether Hermes multi-agent Kanban workflow is actually working.

## Verification Steps

### 1. Check Gateway Dispatcher Running
```bash
ps aux | grep gateway
```
Should show `gateway run --replace` processes running. If absent, multi-agent dispatch won't work.

### 2. List Boards and Task Counts
```bash
hermes kanban boards ls
```
Empty boards `(empty)` = no tasks created yet, not a system failure.

### 3. Query SQLite Directly for Task Details
```bash
sqlite3 ~/.hermes/kanban/kanban.db "SELECT id, title, status, assignee FROM tasks WHERE board_id='<board_id>' ORDER BY created_at;"
```
Board ID found via: `sqlite3 ~/.hermes/kanban/kanban.db "SELECT id, slug FROM boards;"`

### 4. Verify Profile Exists for Each Role
```bash
hermes profile list
```
Multi-role projects create profiles like `proj-<id>-dev`, `proj-<id>-qa`, etc.

## Critical Distinction: `hermes chat -q` vs `hermes chat`

| Invocation | Mode | Creates Kanban Tasks? | Use Case |
|---|---|---|---|
| `hermes chat -q "prompt"` | Single-person Q&A | **NO** — AI responds textually but does NOT call kanban tools | Quick questions |
| `hermes chat` (interactive) | Agent mode | **YES** — AI can call `kanban_create` etc. | Multi-step tasks |
| `hermes kanban create` | Direct command | **YES** | Scripted task creation |
| `hermes kanban swarm` | Swarm graph | **YES** — auto-creates worker/verifier/synthesizer tasks | Automated workflows |

**Key insight**: `hermes chat -q` simulates an AI that "says" it will create tasks but never actually calls the Kanban tool. The AI just generates a textual response.

## Multi-Role Board Anatomy (verified on `proj-proj_4be81199`)

Correct task naming convention for role assignment:
- `[PM]` prefix → assigned to `pm` role
- `[Dev]` prefix → assigned to `dev` role
- `[QA]` prefix → assigned to `qa` role
- `[Design]` or `[Arch]` → assigned to `arch` role
- No prefix → assumed `ceo` or unassigned

Correct task lifecycle:
1. `todo` — created by CEO/PM
2. `ready` — picked up by Gateway dispatcher for the role's worker
3. `in_progress` → `done` → `archived`

## Root Cause Pattern: Empty Board

If a board shows `(empty)` but the project clearly did work:
- Likely was created via `hermes chat -q` subprocess (AI bypasses Kanban)
- Or created via Flask `hermes chat -q` in app.py
- Or never properly connected to the Kanban workflow

**Not** a system failure — the workflow exists and works (proven by `proj-proj_4be81199`).

## Fix Approaches

### A. Use `hermes kanban create` directly in app.py
```python
subprocess.run(["hermes", "kanban", "create", "--title", title, "--role", "pm", ...])
```
Bypasses AI entirely, guaranteed to create tasks.

### B. Use `hermes kanban swarm`
Starts automated decompose→parallel→verify→synthesize workflow.

### C. Keep app.py but acknowledge Kanban won't track it
The work happens in the subprocess, Kanban board stays empty. Acceptable if Kanban tracking isn't required.

## Pitfalls
- Gateway dispatcher only polls the **current** board (`hermes kanban boards` shows `●` marker)
- `ps aux | grep gateway` may show multiple gateway processes; check `--profile` to know which board each monitors
- Board slug and board_id are different (slug is human-readable, id is UUID used in SQLite)

## Workspace 生命周期诊断

### 症状：QA blocked，报告"Dev 代码不存在"

```
Latest summary: dev's source code and PRD no longer exist on disk
(workspaces/t_907d0dbe has been cleaned up). Cannot QA-test code
that isn't there.
```

### 诊断步骤

```bash
# 1. 检查 Dev workspace 是否被清理
ls ~/.hermes/kanban/boards/<board>/workspaces/
# scratch 模式下，done 任务的 workspace 可能已不存在

# 2. 检查 workspace 配置
hermes kanban show <dev_task_id> | grep workspace
# 预期（非 scratch）：workspace: dir @ /path/to/project/dev
# scratch 模式（错误）：workspace: scratch @ /tmp/...

# 3. 检查持久化目录是否有文件
ls /path/to/project/dev/
# 无文件 = workspace 未持久化，Dev→QA 传递链断裂
```

### 修复：重新创建任务并指定 `--workspace dir:`

```bash
hermes kanban create "Dev: 开发" --assignee dev --board <board> \
  --workspace dir:/path/to/project/dev
```
