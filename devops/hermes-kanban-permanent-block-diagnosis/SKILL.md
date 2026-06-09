---
name: hermes-kanban-permanent-block-diagnosis
description: Hermes Kanban v0.15.1 永久 blocked 任务根因诊断 — circuit breaker、goal_max_turns、consecutive_failures
triggers:
  - Dev/QA task permanently blocked after "Iteration budget exhausted" or "pid not alive"
  - hermes kanban dispatch returns 0 spawned but tasks are ready
  - dispatcher appears stuck despite running
---

# Hermes Kanban 永久 Blocked 任务诊断

## 触发条件
Dev/QA 任务永久处于 `blocked` 状态，dispatcher 无法自动复活，`hermes kanban dispatch` 也不生效。

## 根因速查表

| 症状 | 根因 | 关键代码位置 |
|------|------|-------------|
| `consecutive_failures=N` (N≥2) | Circuit breaker 永久 trip | `kanban_db.py` DEFAULT_FAILURE_LIMIT=2 |
| `failure: Iteration budget exhausted (90/90)` | `goal_max_turns=None`（默认只有90次） | app.py 创建任务时未传 `--goal --goal-max-turns` |
| `failure: pid XXXX not alive` | Worker 崩溃后 circuit breaker trip | Worker 进程异常退出 |
| `status=blocked`，dispatcher tick 也不 spawn | `recompute_ready` 拒绝复活 | `kanban_db.py` `_has_sticky_block` |

## 核心电路断路器逻辑

```python
# kanban_db.py DEFAULT_FAILURE_LIMIT = 2
# kanban_db.py recompute_ready() 核心判断：

failures = int(row["consecutive_failures"] or 0)
task_limit = row["max_retries"]
effective_limit = int(task_limit) if task_limit is not None else int(failure_limit)
if failures >= effective_limit:
    continue  # ← 永久跳过，无法自动复活
```

**结论**：`consecutive_failures >= 2` 的任务，circuit breaker 永久跳闸，`recompute_ready` 拒绝复活。

## 验证命令

```bash
# 1. 查看所有 board 的 blocked 任务
python3 -c "
from hermes_cli import kanban_db as _kb
boards = _kb.list_boards()
for board in boards:
    slug = board['slug']
    conn = _kb.connect(board=slug)
    rows = conn.execute('''SELECT id, title, status, assignee,
        consecutive_failures, last_failure_error
        FROM tasks WHERE status IN ('blocked', 'ready')
        ORDER BY created_at''').fetchall()
    for r in rows:
        print(f'{slug}: {r[\"id\"]} [{r[\"status\"]}] [{r[\"assignee\"]}] failures={r[\"consecutive_failures\"]}')
        if r['last_failure_error']:
            print(f'  failure: {r[\"last_failure_error\"][:100]}')
    conn.close()
"

# 2. 检查 task_runs 中最新 run 的 outcome
python3 -c "
from hermes_cli import kanban_db as _kb
conn = _kb.connect(board='<board_slug>')
runs = conn.execute('''SELECT outcome, ended_at, error FROM task_runs
    WHERE task_id='<task_id>' ORDER BY ended_at DESC LIMIT 3''').fetchall()
for run in runs:
    print(f'outcome={run[\"outcome\"]} ended_at={run[\"ended_at\"]}')
conn.close()
"

# 3. 验证 dispatcher 是否在运行
ps aux | grep 'gateway run' | grep -v grep

# 4. 检查 DEFAULT_FAILURE_LIMIT
python3 -c "from hermes_cli import kanban_db as _kb; print('DEFAULT_FAILURE_LIMIT:', _kb.DEFAULT_FAILURE_LIMIT)"
```

## 复活 blocked 任务的 3 种方案

### 方案 A：手动 unblock（快速，但可能再次耗尽）
```bash
hermes kanban unblock <task_id>
```
→ 任务回到 ready，下次 dispatcher tick 自动 spawn

### 方案 B：设置 goal_max_turns 后重建（彻底）
```bash
# 1. 设置全局默认（永久生效）
hermes config set kanban.default_goal_max_turns 300

# 2. 重建任务时带上参数
hermes kanban create --assignee dev --goal --goal-max-turns 300 "Dev: ..."
```

### 方案 C：清除 failure count（临时恢复）
```python
# 直接修改数据库（诊断时有用）
from hermes_cli import kanban_db as _kb
conn = _kb.connect(board='<board_slug>')
conn.execute("UPDATE tasks SET consecutive_failures=0 WHERE id='<task_id>'")
conn.commit()
conn.close()
```

## 预防措施

1. **创建任务时始终指定 `--goal --goal-max-turns 300`**，复杂项目用 `--goal-max-turns 500`
2. **在 `~/.hermes/config.yaml` 设置全局默认**：
   ```yaml
   kanban:
     default_goal_max_turns: 300
     failure_limit: 5  # 提高 circuit breaker 阈值
   ```
3. **监控 blocked 任务**：定期检查 `consecutive_failures` 接近阈值的任务

## 常见误区

- ❌ 认为 dispatcher 没有运行 → 验证：`ps aux | grep gateway`
- ❌ 认为 board 配置错误 → 验证：`~/.hermes/kanban/current`
- ❌ 认为 `profile_exists` 导致跳过 → 验证：`python3 -c "from hermes_cli.profiles import profile_exists; print(profile_exists('dev'))"`
- ❌ 认为 health telemetry 日志证明 dispatcher 卡住 → health log 写入 `gateway.run` logger，实际写入 `agent.log`，需 `grep 'kanban dispatcher' ~/.hermes/logs/agent.log`

## dispatcher 实际行为（关键发现）

- dispatcher **自动运行**，每 60 秒 tick 一次（`dispatch_interval_seconds`）
- `hermes kanban dispatch` CLI **只作用于** `~/.hermes/kanban/current` 指定的 board
- dispatcher **遍历所有 board**，调用 `dispatch_once(board=slug)` 对每个 board 独立运行
- `has_spawnable_ready` 在 **每个 board** 上检查，不是全局
- health telemetry 写入 `gateway.run` logger（不是 `gateway.*`），日志实际写到 `agent.log`
