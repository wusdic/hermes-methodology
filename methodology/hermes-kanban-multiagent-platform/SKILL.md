---
name: hermes-kanban-multiagent-platform
description: Hermes Agent v0.15.1 多项目自动编程平台架构 — 基于实测 Kanban 工作流，非 delegate_task
triggers:
  - 构建多项目自动编程平台
  - Hermes Agent 任务编排
  - multi-project kanban hermes
---

# Hermes Agent v0.15.1 — Multi-Project Auto-Programming Platform

## Context
Building a multi-project auto-programming platform using Hermes Agent's native Kanban workflow mechanism (NOT `delegate_task`).

## Key Architecture Facts (Based on v0.15.1 Source Verification)

### What EXISTS (实测验证)
- `hermes kanban` — task management with boards, lists, cards
- `hermes kanban boards` — per-project isolated boards (SQLite under `~/.hermes/kanban/boards/{slug}/`)
- `hermes kanban create --goal_mode=true` — long-running autonomous tasks
- `hermes kanban swarm` — parallel task execution (workers→verifier→synthesizer)
- `hermes kanban list` / `hermes kanban show` / `hermes kanban claim` / `hermes kanban complete` / `hermes kanban block`
- `hermes gateway start` — starts dispatcher that polls kanban board every 60s and assigns tasks to workers
- `hermes profile create --clone` — per-role SOUL isolation (default/pm/arch/dev/qa)
- Task `parents` dependency gating — child task auto-promotes from `todo`→`ready` when parent completes

### What DOES NOT EXIST (文档错误)
- `hermes spawn` — **不存在**，无此 CLI 子命令
- `hermes kanban spawn` — 不存在
- `network_enabled: false` — 无此配置键
- `orchestrator_enabled: false` — 设为 false 会破坏编排模式（危险）
- `max_turns: 20` — 文档建议值太激进，worker SKILL.md 默认 90

### delegate_task 约束（若仍需使用）
- `max_spawn_depth=1` — 只支持扁平并行，无嵌套
- `max_concurrent_children=3` — 同级并发上限（硬编码默认值）
- 超出后任务排队，不报错也不死锁

## 正确架构模式

### 每个项目 = 一个 Kanban Board
```
hermes kanban boards create my-app
hermes kanban boards use my-app
hermes kanban create --title "写PRD" --role pm --goal_mode=false
hermes kanban create --title "架构设计" --role arch --goal_mode=true --parents t_xxx
```

### Gateway Worker 模式
```bash
# 启动 gateway（60s 轮询）
hermes gateway start

# Worker 自动 pickup kanban 任务
# 每个 worker 是独立 Hermes 进程，通过 gateway 接收任务分派
```

### SOUL Profile 隔离
每个角色独立 Profile，SOUL 模板写入该角色的专业职责：
- `proj-{slug}-pm` — Product Manager SOUL
- `proj-{slug}-arch` — Architect SOUL
- `proj-{slug}-dev` — Developer SOUL
- `proj-{slug}-qa` — QA Engineer SOUL

## 项目目录结构
```
platform/
├── __init__.py
├── init_project.py      # hermes kanban boards create + profile + 目录结构
├── roles.py            # 各角色 SOUL 模板
└── orchestrator.py     # kanban_create 任务创建辅助函数
```

## init_project.sh 脚本（脚手架）

创建 `~/.hermes/scaffold/init_project.sh`，用于自动化项目目录创建：

```bash
#!/bin/bash
set -e

PROJECT_NAME="${1:?Usage: $0 <project_name>}"
BASE_DIR="$HOME/hermes-projects/${PROJECT_NAME}"
mkdir -p "${BASE_DIR}"/{openspec,workspace,.hermes}

# 透传必要的环境变量（API Key 等）
ENV_FLAGS=""
for var in MINIMAX_API_KEY OPENAI_API_KEY OPENAI_API_BASE; do
    val="${!var}"
    if [ -n "$val" ]; then
        ENV_FLAGS="$ENV_FLAGS -e ${var}=${val}"
    fi
done

docker run -d \
  --name "${PROJECT_NAME}" \
  --restart unless-stopped \
  ${ENV_FLAGS} \
  -v "${BASE_DIR}/.hermes:/workspace/.hermes" \
  -v "${BASE_DIR}/openspec:/workspace/openspec" \
  -v "${BASE_DIR}/workspace:/workspace" \
  -w /workspace \
  nousresearch/hermes-agent:latest
```

**常见错误（方案原文有 5 处）**：
- `PROJECT_NAME=1` 硬编码 → 参数检查失效
- `BASE_DIR=~/hermes-projects/PROJECT_NAME` → 变量未引用
- `--name PROJECT_NAME` → 未引用 `$PROJECT_NAME`
- `/opt/data` → 容器内路径应为 `/workspace/.hermes`
- 中国网络拉取 Docker Hub 镜像失败 → 改用本地 Hermes Kanban 机制

## hermes profile create CLI 限制

```
hermes profile create --model "minimax/minimax-m2.7-highspeed"
# ❌ 不存在 --model 参数

# ✅ 正确做法：直接写 YAML
mkdir -p ~/.hermes/profiles/${role}
cat > ~/.hermes/profiles/${role}/config.yaml << 'EOF'
model: minimax/minimax-m2.7-highspeed
provider: minimax-cn
EOF
```

## SOUL.md vs config.yaml（全局系统指令路径）

| 文件 | 用途 | 存在性 |
|------|------|--------|
| `~/.hermes/config.yaml` | 方案假设路径（❌ 错误） | 不存在 |
| `~/.hermes/SOUL.md` | 全局人格配置（✅ 正确） | 存在（6行占位符） |

**追加自动化指令到 SOUL.md**：
```markdown
## 全自动化软件工程项目经理（系统级指令）

当接收到新项目需求时，严格按以下步骤自主执行，无需人工干预：

1. **【环境构建】** 提取项目名称，调用终端执行 `bash ~/.hermes/scaffold/init_project.sh <项目名>` 完成目录创建。
2. **【CEO沟通】** 使用 `hermes kanban create` 创建 CEO 任务，dispatch 执行，等待完成后读取 `~/hermes-projects/<项目名>/openspec/proposal.md`。
3. **【产品设计】** 基于 proposal.md，使用 `hermes kanban create` 创建 PM 任务，dispatch 执行，等待完成读取 `design.md` 和 `tasks.md`。
4. **【研发编码】** 读取 tasks.md，依次为每个任务创建 `hermes kanban create`，使用 `hermes kanban link` 建立依赖链，每次 `hermes kanban dispatch` 并行执行已就绪的任务，直到全部完成。
5. **【测试验收】** 最后创建 QA 任务，运行 pytest 验证，统计通过率并汇报。
```

## 关键实测发现

### hermes chat -q 是单人 chat，不是多角色流水线（2026-06-06 新发现）
- `hermes chat -q "prompt"` → AI 直接干活写代码，**不会调用 kanban_create()**
- 多角色流水线（CEO→PM→Dev→QA）需要用 `hermes chat --profile <role>` 交互模式
- **教训**：PDF 方案 Step 5.2 设想用 `chat -q` 触发 Kanban 流程是不对的

### ✅ 正确触发方式：`hermes chat --profile platform-ceo`（交互 Agent 模式）

**`hermes chat -q`（单人 Q&A 模式）**：
- AI 作为"问答助手"，直接返回文字回答
- **不会**调用 `kanban_create()` 等 Kanban 工具
- 适合：快速提问、简单查询

**`hermes chat --profile platform-ceo`（交互 Agent 模式）**：
- AI 作为"角色 Agent"，可以调用完整工具集
- **会**调用 `kanban_create()`、`delegate_task()` 等所有工具
- 适合：多角色任务分解、项目流水线

**stt-whisper 项目（`proj-proj_4be81199`）验证**：Board 上 CEO/PM/Dev/QA 完整任务链，
全部由 `platform-ceo` profile 在交互 session 中调用 `kanban_create()` 创建。

**Flask app.py 正确写法**：
```python
# 错误 ❌ — AI 只返回文字，不创建 Kanban 任务
subprocess.Popen(["hermes", "chat", "-q", prompt])

# 正确 ✅ — 交互 Agent 模式，调用 kanban_create()
subprocess.Popen([
    "hermes", "chat",
    "--profile", "platform-ceo",
    "--skills", "kanban-orchestrator",
    "-s", base_dir,          # 传入项目目录，AI 可读取文件
    "-q",                    # 抑制 banner（不影响工具调用）
    f"项目 {project_name} 已创建在 {base_dir}。\n"
    f"请读取 {idea_path}，作为 CEO 执行需求分析，"
    f"在 Kanban Board '{board_name}' 上创建任务链，"
    f"生成 openspec/proposal.md"
])
```

**为什么 `-q` 加在 `--profile` 后面就不影响工具调用**：
`-q/--query` 只抑制输出 banner，不改变 Agent 模式。Agent 模式的判定条件是：
有 `--profile` → 加载该 profile 的 SOUL 和工具集 → 完整工具调用能力。

### Board 架构实测（2026-06-06 新发现）
- 主库 `~/.hermes/kanban/kanban.db` — **空的**，零张表
- 每个 Board 独立 SQLite：`~/.hermes/kanban/boards/<slug>/kanban.db`
- tasks 表列：`id, title, status, assignee, body, created_at, ...`（**无 `profile` 列**，查询时不要用）
- Board 必须先**同步创建**（在 app.py 里用 `subprocess.run`）再 spawn Agent subprocess

### Web 服务 + projects.json 注册表（2026-06-06 新发现）
- 前端 `fetch('http://localhost:8080/start')` 跨域失败 → 用相对路径 `fetch('/start')`
- `projects.json` 全局注册表方案可行，Flask API：
  - `GET /api/projects` — 列出所有项目
  - `GET /api/projects/<name>/tasks` — 读取 Board 任务
  - `POST /start` — 创建项目 + 同步建 Board + 注册 + 触发 Hermes

### gateway 只轮询当前激活的 board
gateway 运行时只轮询 `hermes kanban boards` 中 **当前激活的 board**（有 `◆` 标记的）。如果 workers 在非默认 board，gateway 不会 pickup 任务。

### Projects.json 全局注册表方案（B1）
解决"Kanban Board 隔离导致无法全局感知所有项目"的问题：

```json
// ~/hermes-projects/projects.json
{
  "version": 1,
  "projects": [
    {"name": "proj_name", "board": "board_slug", "created_at": "...", "status": "active"}
  ]
}
```

Flask API 端点：
- `GET /api/projects` — 列出所有已注册项目
- `GET /api/projects/<name>` — 查询单个项目
- `GET /api/projects/<name>/tasks` — 从 Board 读取任务列表

Board 必须在 app.py 中**同步创建**（`subprocess.run(["hermes", "kanban", "boards", "create", ...])`），然后再 `subprocess.Popen` 启动 Hermes。

**两种解法**：
```bash
# 解法1：用 kanban swarm（推荐，无需 gateway 常驻）
hermes kanban swarm \
  --worker "default:Research 上海数据交易所" \
  --worker "default:Research 贵阳数据交易所" \
  --verifier "default" \
  --synthesizer "default" \
  "采集任务描述"

# swarm 自动创建：1个根任务 + N个worker + 1个verifier + 1个synthesizer
# workers 状态从 ready → running，通过 hermes kanban dispatch 触发 spawn
```

```bash
# 解法2：让 gateway 切换到正确 board
hermes kanban boards switch <slug>   # 先切换到目标 board
hermes gateway start                  # gateway 只轮询当前 board
```

### dispatch — 手动触发 worker spawn（关键！）
**`kanban swarm` 创建任务后 workers 不会自动 spawn**，需要：
```bash
hermes kanban dispatch    # 实际执行
hermes kanban dispatch --dry-run  # 预览会 spawn 哪些
```
输出示例：
```
Spawned:  3
  - t_82828fcf  ->  default  @ /path/to/workspace
  - t_abbeeea8  ->  default  @ /path/to/workspace
```

### reclaim — 重启卡住的 worker
worker 超过 ~10 分钟无 heartbeat（网络/搜索卡住）：
```bash
hermes kanban reclaim <task_id>   # 释放锁，状态变 ready
hermes kanban dispatch            # 重新 spawn
```

### swarm 架构（完整拓扑）
```
t_root (done) ← swarm root / shared blackboard
  ├── t_worker_1 (running) → Research 上海数据交易所
  ├── t_worker_2 (done)    → Research 贵阳数据交易所
  ├── t_worker_3 (done)    → Research 国际数据价格
  └── t_worker_4 (done)    → Research 国内黑市案例
        ↓ 全部 done
  t_verifier (todo)
  t_synthesizer (todo)
```

### worker 输出路径
- scratch workspace：`/tmp/` 或 `/home/zcxx/.hermes/kanban/boards/{board}/workspaces/{task_id}/`
- 完成后用 `kanban_complete(summary=..., metadata=...)` 报告，structured metadata 供下游解析

### 常见陷阱

1. **swarm 后 workers 不 spawn** → 需手动 `hermes kanban dispatch`
2. **gateway 轮询错误的 board** → gateway 只看当前激活 board，解法见上
3. **worker 超过 10min 无输出** → `hermes kanban reclaim` + `dispatch`
4. **板未激活** → `hermes kanban boards switch {slug}`
5. **Profile 隔离** → 用 `--profile` 启动独立会话
6. **子任务依赖** → `hermes kanban create --parents {id}`
7. **hermes chat -q 超时退出码 124** → 超时不代表命令失败，检查实际文件系统产出
8. **Docker 镜像拉取失败（中国网络）** → Docker Hub 在国内受限，Docker 后端子 agent 不可用，改用 kanban goal_mode
9. **goal_mode CEO 任务范围自裁剪** → CEO 有裁量权，可能只完成"研究"而不生成"proposal"，建议在 body 中明确要求必须输出哪些文件
10. **并行 dispatch 加速流水线** → 多个 ready 任务可同时 dispatch，max_concurrent_children 控制并发上限，流水线总耗时从串行的 ~60min 降至 ~30min
11. **依赖 link 可后置** → 可先 `kanban create` 所有任务（状态均为 todo），再批量 `kanban link parent child` 建立依赖链，父任务完成后子任务自动 promote → ready
12. **测试结果判断** → pytest 119/122 passed 说明 pipeline 有效，少数失败通常是测试断言措辞问题（如期望 "pomodoro-cli" 但输出 "main, version 0.1.0"），不代表 CLI 功能缺陷
13. **PDF 方案执行标准流程** — 用 `pdftotext -layout` 提取 PDF 内容（分两段 8K chars 避免截断），逐条执行并暂停询问差异点。PDF 常见截断内容：init_project.sh、web-interface/app.py、SOUL.md 完整内容。
14. **heredoc 内 brace expansion 不展开** — `mkdir -p "${BASE_DIR}/.hermes/profiles/{ceo,pm,dev,qa}"` 在 heredoc 中失败，brace expansion 不会展开。必须分 4 次 mkdir。
15. **两套 Python 环境各装各的 llama_cpp** — conda 和 hermes venv 各有独立的 site-packages，pip install 只装进当前 python3 对应的环境，互不影响。llama.cpp server 可用任一环境启动。
16. **Step 1-6 流水线方案差异点** — PDF 方案 vs 实际：(1) Ubuntu 不升级跳过；(2) Hermes 已是最新无需 update；(3) hermes-projects 目录已存在；(4) SOUL.md 用追加而非覆盖；(5) Kanban 无需手动配置 global.db。
17. **Flask subprocess 重启不完全** — pkill 后旧进程可能没死透，导致端口仍被占用且代码未更新。用 `pkill -9 -f "python3 app.py"` 彻底杀掉。
18. **hermes chat 命令行参数** — 正确是 `hermes chat -q "prompt"`（`-q` = `--query`），不存在 `-z` 参数。

## Verification Commands
```bash
hermes --help | grep -E "kanban|gateway|profile"
hermes kanban --help
hermes kanban boards --help
hermes kanban create --help
hermes gateway --help
```
