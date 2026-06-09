---
name: hermes-kanban-multiagent-setup
description: Hermes Agent v0.15.1 多角色 Kanban 流水线搭建避坑指南 — 重点：`hermes chat -q` 不会调用 kanban_create()，必须用 `--profile` 交互模式。
version: 1.0.0
platforms: [linux, macos]
environments: [hermes-kanban]
metadata:
  hermes:
    tags: [kanban, multi-agent, gateway, dispatcher]
    related_skills: [kanban-orchestrator, kanban-worker, hermes-agent]
---

# Hermes Kanban 多角色流水线 — 实战避坑指南

## 核心发现：`-q` 模式不调用 Kanban 工具

**`hermes chat -q "prompt"`（单次查询模式）**：
- AI 作为"问答助手"运行，直接返回文字回答
- **不会**调用 `kanban_create()`、`kanban_complete()` 等工具
- 适合：快速提问、简单查询

**`hermes chat --profile <role>`（交互模式）**：
- AI 作为"Agent"运行，可以调用完整工具集
- **会**调用 `kanban_create()`、`delegate_task()` 等所有工具
- 适合：多角色任务分解、项目流水线

**验证方法**：查看 `proj-proj_4be81199`（stt-whisper）任务——CEO 任务由 `platform-ceo` profile 在交互 session 中创建，Board 上有完整的 CEO→PM→Dev→QA 依赖链。

## 架构组件

| 组件 | 命令 | 运行方式 |
|---|---|---|
| Gateway dispatcher | `hermes gateway run`（默认端口） | 持久后台进程，PID 327690 |
| CEO profile | `hermes chat --profile platform-ceo --skills kanban-orchestrator` | 按需触发 |
| Worker profiles | `proj-<board>-{pm,dev,qa}` | Gateway 自动分派 |
| Board | `hermes kanban boards create <name>` | 项目级隔离 |

## 正确的启动方式

### 方式 1（推荐）：CEO 交互模式

```bash
hermes chat --profile platform-ceo --skills kanban-orchestrator -s /path/to/project -q "\
项目目录：/path/to/project
请执行：
1. 读取 /path/to/project/USER_IDEA.md
2. 作为 CEO 在 Kanban Board 'proj-xxx' 上创建任务链
3. 生成 openspec/proposal.md
开始工作。"
```

**参数说明**：
- `--profile platform-ceo` → CEO SOUL（"只分解不执行"）
- `--skills kanban-orchestrator` → 加载分解剧本
- `-s <dir>` → 工作目录（AI 读取文件）
- `-q` → 抑制 banner，输出简洁（不影响工具调用）

### 方式 2：swarm（简单任务）

```bash
hermes kanban swarm "实现 X" \
  --worker "proj-x-dev:开发" \
  --verifier "proj-x-verifier:验收" \
  --synthesizer "proj-x-synthesizer:交付"
```

**限制**：只有 worker→verifier→synthesizer 三层，不支持 CEO/PM/Dev/QA 五角色。

### 方式 3：手动创建任务链

```bash
hermes kanban boards create proj-x
hermes kanban create "CEO: X 项目规划" --assignee platform-ceo --idempotency-key proj-x-root
hermes kanban create "PM: X 需求分析" --assignee proj-x-pm --parent <ceo-task-id>
hermes kanban create "Dev: X 开发" --assignee proj-x-dev --parent <pm-task-id>
hermes kanban create "QA: X 测试" --assignee proj-x-qa --parent <dev-task-id>
```

Gateway dispatcher 会自动分派给 workers。

## 依赖链（parent links）机制

- `kanban_create(..., parents=[parent_id])` 创建时指定依赖
- 子任务在父任务完成前自动保持 `todo`（Blocked）
- 父任务完成后，dispatcher 自动将子任务提升为 `ready`
- **不要**先创建任务再 link，应该在 `kanban_create` 时就用 `parents=` 指定

## ⚠️ 关键运营发现（2026-06 实测）

### 发现 1：Dispatcher 不自动分派新任务

**问题**：CEO 在 Flask 接口中创建任务后，任务停留在 `ready` 状态，Gateway dispatcher **不会**自动分派。

**现象**：
```
Board: project_1780702442019
▶ t_8a7cbfc3  ready     pm    PM: 济南中考志愿推荐系统 PRD   ← 一直 ready，不会自动 running
```

**解决方案**：每次创建任务后手动触发：
```bash
hermes kanban dispatch 2>&1
# 输出: Spawned: 1 — t_8a7cbfc3 -> pm
```

**在 Flask app.py 中补救**：在 `/start` 接口里，创建任务后同步调用 `dispatch`：
```python
# 先创建任务（CEO）
subprocess.Popen([... "hermes", "chat", "--profile", "platform-ceo", ...])

# 再触发 dispatcher
time.sleep(2)
subprocess.run(["hermes", "kanban", "dispatch"], capture_output=True)
```

### 发现 2：90 次迭代限制导致任务 blocked

**问题**：Dev/PM worker 单次运行最多 90 次迭代（`Iteration budget exhausted (90/90)`），耗尽后任务变成 `blocked`，最多重试 2 次。

**现象**：
```
⊘ t_d76a6896  blocked   dev   Dev: 济南中考志愿推荐系统开发
  ! Iteration budget exhausted (90/90)
  ! effective_limit: 2
  ! budget_used: 90, budget_max: 90
```

**原因**：复杂任务（如"开发完整推荐系统"）需要多次迭代调试，90 次不够用。

**解决方向**：
- 拆解大任务为小任务链（不要让 Dev 一个人干所有活）
- 在 prompt 中要求 Dev 先产出框架代码，再分批完成细节
- 或等待 Hermes 未来版本支持更高迭代限制

### 发现 3：用文件时间戳监控 worker 进度

**问题**：无法直接看到 worker 内部日志，但想知道任务是否还在活跃。

**解决方案**：监控 workspace 目录中文件的修改时间：
```bash
find /path/to/project/ -type f -printf '%T+ %p\n' | sort | tail -10
# 如果文件持续有新时间戳 → worker 还在工作
```

**实测**：Dev worker 在 PID 1990431 运行时，每 1-2 分钟有新文件产出（server.py、seed_data.py 等），时间戳持续更新说明任务在活跃执行。

### 发现 4：后台 Flask 服务端口不是 5000

**问题**：Dev 启动的 Flask 服务默认端口不是 5000，需要查 `server.py` 源码确认。

**解决方案**：
```bash
# 查找实际端口
grep -n "app.run\|port" server.py | tail -5

# Dev worker 启动的服务（实测）
# PID 1991945: /path/to/dev/backend/server.py → 端口 8765
```

## 常见错误

### 错误 1：在 Flask/Python 里用 `-q` 触发多角色

```python
# 错误 ❌ — AI 只返回文字，不创建 Kanban 任务
subprocess.Popen(["hermes", "chat", "-q", prompt])

# 正确 ✅ — 交互 Agent 模式，调用 kanban_create()
subprocess.Popen([
    "hermes", "chat",
    "--profile", "platform-ceo",
    "--skills", "kanban-orchestrator",
    "-s", base_dir, "-q", prompt
])
```

### 错误 2：给未知 profile 创建任务

```python
# 错误 ❌ — profile 不存在，任务永远在 ready 队列，dispatcher 静默失败
kanban_create(title="...", assignee="developer")

# 正确 ✅ — 先用 hermes profile list 确认 profile 存在
profiles = subprocess.run(["hermes", "profile", "list"], capture_output=True, text=True)
```

### 错误 3：Gateway dispatcher 未运行

```bash
# 检查 gateway 是否在跑
ps aux | grep "gateway run"

# 如果没跑，启动它
hermes gateway run &
```

## Dockerfile / 持久化

Gateway dispatcher 需要持久运行（systemd/service），不要用 `docker run --rm`。

## ⚠️ Workspace 生命周期：Dev→QA 工件传递问题

### 问题现象

Dev 任务 `done` 后，其 workspace（`workspaces/t_xxxxx/`）被系统清理，导致 QA 任务运行时发现：
- Dev 的源码不存在
- QA 无法验证 dev 的实际交付物
- QA 报 `blocked`（2026-06-06 实测）

### 根因

默认 workspace 模式是 `scratch`，任务完成后 workspace 被清空。

### 解决方案：用 `--workspace dir:<固定路径>`

创建任务时通过 `--workspace` 参数指定持久化目录：

```bash
hermes kanban create "PM: 需求分析" --assignee pm --board proj-x \
  --workspace dir:/home/zcxx/projects/proj-x/pm

hermes kanban create "Dev: 开发" --assignee dev --board proj-x \
  --workspace dir:/home/zcxx/projects/proj-x/dev

hermes kanban create "QA: 测试" --assignee qa --board proj-x \
  --workspace dir:/home/zcxx/projects/proj-x/qa
```

### 在 Flask app.py 中实现

```python
cmd = [
    "hermes", "chat",
    "--profile", "platform-ceo",
    "--skills", "kanban-orchestrator",
    "-t", "hermes-cli",
    "-q",
    f"项目 {project_name} 已创建在 {base_dir}。\n"
    f"创建任务时必须指定 --workspace：\n"
    f"PM：--workspace dir:{base_dir}/pm\n"
    f"Dev：--workspace dir:{base_dir}/dev\n"
    f"QA：--workspace dir:{base_dir}/qa\n"
]
```

### 验证方法

```bash
# 检查 workspace 配置
hermes kanban show <task_id> | grep workspace
# 应显示：workspace: dir @ /path/to/project/<role>

# 检查文件是否存在（Dev 完成后）
ls /path/to/project/dev/
# 应有：calculator.py, tests/, cli.py 等

# 验证 QA 能否读到 dev 代码
ls /path/to/project/qa/
# QA 运行时应创建 test_*.py 等文件
```

### 实测结果（2026-06-06）

| 指标 | 结果 |
|------|------|
| PM workspace 持久化 | ✅ `/proj/pm/` |
| Dev workspace 持久化 | ✅ `/proj/dev/`（calculator.py、cli.py、tests/）|
| QA workspace 持久化 | ✅ `/proj/qa/`（test_qa_acceptance.py）|
| Dev→QA 工件传递 | ✅ QA 成功读取 dev 代码，发现 2 个真实 bug |
| QA→Dev 反馈闭环 | ✅ QA 自动创建新 Dev 任务修复缺陷 |

## 参考项目

- Board `proj-proj_4be81199`（stt-whisper）有完整多角色验证数据
- Profile `platform-ceo` 的 SOUL.md 定义了"只分解不执行"原则
- Skill `kanban-orchestrator` 包含完整的任务分解剧本
- Skill `kanban-worker` 包含 worker 生命周期和 handoff 规范
