---
name: hermes-multiple-instances
description: 在同一台机器上运行多个完全隔离的 Hermes Agent 实例——多团队 / 多环境 / 新项目测试 / A/B 测试。Profile 只是同一 Hermes 内的角色（共享数据），HERMES_HOME 才是隔离的关键（物理隔离所有 state）。
version: 1.0.0
platforms: [linux, macos]
environments: [hermes]
metadata:
  hermes:
    tags: [hermes, multi-instance, isolation, hermes-home, parallel]
    related_skills: [hermes-kanban-multiagent-setup, hermes-agent, hermes-kanban-architecture]
---

# Hermes 多实例隔离 — Profile vs HERMES_HOME

## ⚠️ 最常见的误解

很多用户（包括第一次接触 Hermes 的）以为：

> "我要跑一个新项目？用 `hermes profile create <name>` 加个 profile 不就行了吗？"

**错。** Profile 只是同一个 Hermes 进程内的"角色"——多个 profile **共享**：
- 同一个 Kanban DB 和所有 board
- 同一个 Session DB
- 同一个 .env 和 config.yaml
- 同一个 Feishu/Weixin/Telegram 机器人 token
- 同一个 hermes-agent 进程

如果用 `profile create` 创建新项目，**会污染旧项目的 board/session/memory**。

## 真正的隔离方式：HERMES_HOME 环境变量

```bash
# 这是创建完全隔离新实例的唯一正确方式
export HERMES_HOME=/path/to/new/.hermes
hermes gateway run
```

HERMES_HOME 改变后，**所有** hermes 内部路径（profile、Kanban、session、memory、logs、state）都从新目录读——和旧实例**物理隔离**。

## 三个关键认知

| 维度 | 同一个 Hermes（多 profile） | 多个 Hermes（多 HERMES_HOME） |
|---|---|---|
| 进程数 | 1 个 | N 个独立进程 |
| 共享数据 | Kanban、session、memory、.env | **无**——物理隔离 |
| Feishu 机器人 | 同一个机器人（同一 app_id） | 必须用**不同机器人** |
| Gateway 端口 | 同一 WebSocket（无 TCP 冲突） | 各自 WebSocket（也不冲突） |
| systemd 服务 | 一个 service | N 个 service（或手动启动） |
| 典型用途 | 一人多角色（CEO/PM/Dev/QA） | 多团队 / 多环境 / 测试 vs 生产 / A/B |
| 类比 | Linux 同用户多 shell | **两台独立服务器** |

## ⚠️ 启动新实例的 3 个真实陷阱（2026-06-07 实测）

### 陷阱 0（前置）：新实例要不要连自己的飞书机器人？

**两种模式**：
- **纯 CLI/测试模式**（新 Hermes 不连飞书）—— `unset` 所有平台 env vars + 新 .env 不含平台 key，新 Hermes 跑 `gateway run` 即可，自动 fallback 到 `No messaging platforms enabled. Gateway will continue running for cron job execution.`
- **连飞书模式**（新 Hermes 配独立机器人）—— 见下方 "陷阱 4"

### 陷阱 1：只 `unset` 平台 env vars 不够

新 Hermes 启动时会**重新读 `$HERMES_HOME/.env`**。如果新 .env 是从旧 .env 复制而来，里面残留了 `FEISHU_APP_ID`、`WEIXIN_TOKEN` 等 key，**`unset` 这些 shell env vars 完全无效**——hermes 启动后还是会读到。

**修复**：新 `.env` 必须用 `grep -v` 删除所有平台 key 行：

```bash
# 复制除 Feishu/Weixin/Telegram/Discord/Slack 之外的所有 key
grep -viE "^(FEISHU|WEIXIN|TELEGRAM|DISCORD|SLACK|GATEWAY_ALLOW_ALL_USERS)" \
  /home/zcxx/.hermes/.env > /home/zcxx/hermes-test/.hermes/.env
```

### 陷阱 2：Weixin env var 名字容易拼错

是 **`WEIXIN_ACCOUNT_ID` / `WEIXIN_TOKEN`**（不是 `WEXIN_*` 或 `WECHAT_*`）。从源码确认：

```python
# gateway/platforms/weixin.py
self._account_id = str(... or os.getenv("WEIXIN_ACCOUNT_ID", ""))
self._token = str(... or os.getenv("WEIXIN_TOKEN", ""))
```

### 陷阱 3：Gateway 不监听 TCP 端口

`hermes gateway run --help` **没有 `--port` 选项**。Gateway 默认只跑 WebSocket 长连接（连 Feishu/Weixin 服务器），不监听本地 TCP。

这意味着 **多个 Gateway 进程可以同时跑、不会端口冲突**。用户问"新 Hermes 用什么端口"——答案是**不需要端口**。

唯一可能端口冲突的是 Feishu webhook 模式（`FEISHU_WEBHOOK_PORT`），默认 8765。如果两个实例都用 webhook 才需要改。

### 陷阱 4：给新实例配独立飞书机器人

如果新 Hermes 也要连飞书（**必须**是新机器人 app_id，不能和旧 Hermes 共享）：

1. 在 https://open.feishu.cn/app 创建企业自建应用 → 拿 App ID + App Secret
2. 启用"机器人能力" → 权限管理开 `im:message` 系列 → 事件订阅用 WebSocket → **发布版本**（未发布收不到消息）
3. 把凭证写进新 .env：
   ```bash
   cat >> $HERMES_HOME/.env << EOF
   FEISHU_APP_ID=cli_xxx
   FEISHU_APP_SECRET=xxx
   FEISHU_DOMAIN=feishu
   FEISHU_CONNECTION_MODE=websocket
   FEISHU_ALLOW_ALL_USERS=true   # 测试阶段放开
   FEISHU_REQUIRE_MENTION=true
   FEISHU_GROUP_POLICY=allowlist
   EOF
   ```
4. **修改启动脚本**——只 `unset` Weixin/Telegram/Discord/Slack，**不能 unset FEISHU_***。同时显式 `source` 新 .env 覆盖父 shell 继承的旧 Hermes 凭证：
   ```bash
   unset WEIXIN_* TELEGRAM_* DISCORD_* SLACK_* GATEWAY_ALLOW_ALL_USERS HERMES_SESSION_*
   if [ -f "$HERMES_HOME/.env" ]; then
     set -a
     source "$HERMES_HOME/.env"
     set +a
   fi
   ```
5. 启动后日志应看到 `connected to wss://msg-frontier.feishu.cn/ws/v2`

**安全提示**：用户经常直接在对话里贴 App Secret。配置完成后**立即建议去飞书开放平台重置 App Secret**，把新 Secret 私聊传，不要在群组/公开渠道。

### 陷阱 5：启动脚本的 `kill -0` 检查太快

`start()` 里的 `sleep 3; kill -0 ...` 在加载模型 + 初始化 platform 时**不够**。Gateway 实际需要 5-10 秒才能进入稳定状态。

**症状**：脚本打印 "❌ 启动失败"，但 `ps aux | grep gateway` 实际能看见新进程在跑。

**修复**：要么 `sleep 8`，要么把检查逻辑改成"扫描所有 gateway 进程，匹配新 HERMES_HOME"。

### 陷阱 6：`hermes profile create` 不接受 `--model`

```bash
hermes profile create test-ceo --model MiniMax-M3
# error: unrecognized arguments: --model MiniMax-M3
```

`profile create` 接受 `--clone`, `--description`, `--no-skills` 等，**不接受模型参数**。模型用 `/model` 命令在交互模式里切换，或在 `config.yaml` 里写 `model.default`。

## 启动脚本模板

参考 `templates/start-hermes.sh`——已通过实测验证可用，关键点：
1. 顶部 `unset` 所有平台 env vars（防御性）
2. `export HERMES_HOME=/新路径`
3. 复制旧 .env 时**过滤**平台 key（关键）
4. 写 PID 文件方便 `stop`/`status`
5. 后台 `nohup` 启动

## 验证隔离的 4 个命令

```bash
# 1. 看两个进程都跑
ps aux | grep "gateway run" | grep -v grep

# 2. 看新进程 HERMES_HOME 是新路径
tr '\0' '\n' < /proc/<新PID>/environ | grep HERMES_HOME

# 3. 看 Kanban 完全独立（必须用 env -i 清空当前 shell 的 HERMES_HOME）
/usr/bin/env -i HOME=/home/zcxx PATH=... \
  HERMES_HOME=/home/zcxx/hermes-test/.hermes \
  hermes kanban boards list   # 旧 Hermes 才有 11 个 board

# 4. 看 Feishu 没启用
tail -20 /新home/logs/gateway.log
# 应看到 "No messaging platforms enabled"
```

## 何时用哪种方案

| 需求 | 方案 |
|---|---|
| 一个人跑 CEO + PM + Dev + QA | 多 profile（同一个 Hermes） |
| 跑两个不相关的项目 | **多 HERMES_HOME**（隔离） |
| 旧项目稳定运行 + 测试新项目 | **多 HERMES_HOME** |
| A/B 测试两个不同 prompt/模型 | 多 profile（共享 Kanban 即可） |
| 多团队共用一台机器 | **多 HERMES_HOME**（数据物理隔离） |
| 跨项目复用 skill/memory | 多 profile（共享） |
| 老 Hermes 跑 Feishu，新 Hermes 不跑 | **多 HERMES_HOME + 启动脚本 unset** |

## 关联文档

- `references/parallel-hermes-session.md` — 2026-06-07 完整会话记录（4 次启动失败 → 第 5 次成功）
- `templates/start-hermes.sh` — 已知好的启动脚本
- `templates/env-cleanup.sh` — 平台 env vars 清理 snippet
