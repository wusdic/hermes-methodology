---
name: hermes-kanban-architecture
description: Hermes Kanban v0.15.1 实际架构调研 — Board 隔离模式、全局注册表方案、常见错误
category: methodology
---

# Hermes Kanban Architecture (v0.15.1)

## 实际架构

Hermes Kanban 使用 **Board 隔离架构**：
- 主库 `~/.hermes/kanban/kanban.db` — **空的**（零张表），不是全局主库
- 每个项目 = 一个 Board，SQLite 路径：`~/.hermes/kanban/boards/<board名>/kanban.db`
- Board 列表通过 `hermes kanban boards list` 查看

### tasks 表真实 schema（data-trader board 实测）
```sql
id, title, body, assignee, status, priority,
created_by, created_at, started_at, completed_at,
workspace_kind, workspace_path, branch_name, ...
-- 注意：无 profile 列
```

**常见错误**：
- 假设主库有 boards 表 → 实际主库是空的
- 查询 tasks 表加 `profile` 列 → 列不存在，报 `sqlite3.OperationalError: no such column: profile`

## 全局项目注册表方案（B1）

由于 Board 数据完全隔离，无法从单一入口查询所有项目。解决方案：

1. 创建 `~/hermes-projects/projects.json` 作为中心注册表
2. 新建项目时自动写入：name, board, created_at, status
3. Flask app.py 读取 projects.json 实现全局视图

```python
# app.py 关键函数
def load_registry():
    with open("projects.json") as f:
        return json.load(f)

@app.route("/api/projects/<name>/tasks")
def get_project_tasks(name):
    board = get_project_board(name)  # 从注册表查 board 名
    db = f"~/.hermes/kanban/boards/{board}/kanban.db"
    # sqlite3 读取 tasks 表
```

## 验证命令
```bash
# 列出所有 board
hermes kanban boards list

# 查 board 的 tasks
curl http://localhost:8080/api/projects/<name>/tasks

# 查 tasks 表结构
python3 -c "
import sqlite3
conn = sqlite3.connect('~/.hermes/kanban/boards/<board>/kanban.db')
c = conn.cursor()
c.execute('PRAGMA table_info(tasks)')
for row in c.fetchall(): print(row)
"
```

## 注意事项
- `hermes chat -z PROMPT` 用 `-z` 传 prompt（不用 positional arg）
- Flask 自动 reload：改完 app.py 等 2-3 秒即可
- pkill flask 后重启要用 `background=true` 避免 PTY 错误
