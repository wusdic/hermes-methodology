# 2026-06-07 多 Hermes 实例隔离实战记录

## 背景

用户要在同一台机器上跑**两个完全隔离的 Hermes 实例**：
- 旧 Hermes：在 `/home/zcxx/.hermes`（连着飞书机器人，跑了 stt-whisper、Jinan Zhongkao 等项目）
- 新 Hermes：用于测试新项目，**不能污染旧数据**

## 关键认知纠正

用户最初问题："我可能是不是需要再重新连一个飞书的智能体"——表明用户直觉是对的。然后问"`hermes profile create` 的方式和独立 HERMES_HOME 有什么区别"——这是关键问题。

**Profile 模式（错的隔离方式）**：
- 多 profile 共享 Kanban DB、session、memory、.env
- 旧 profile 创建的 board 会被新 profile 看见
- 共享同一个 Feishu 机器人

**HERMES_HOME 模式（对的隔离方式）**：
- 独立进程、独立 .env、独立 Kanban DB、独立 session
- 两个实例互不可见
- 必须用不同 Feishu 机器人（如果都要连飞书）

## 4 次启动失败的完整过程（CLI 模式）

| 次数 | 错误 | 根因 |
|---|---|---|
| 1 | `Another local Hermes gateway is already using this Feishu app_id` | 新 Hermes 误读旧 .env 里的 FEISHU_* |
| 2 | `Weixin bot token already in use` | 同上，但针对 Weixin |
| 3 | 同上 | 我在启动脚本里 `unset` 了 FEISHU_*，但**漏了 WEIXIN_* 完整列表**（拼写也错了 `WEXIN_*` 应为 `WEIXIN_*`）|
| 4 | 同上 | 即使脚本里 `unset` 成功，hermes 仍从 `$HERMES_HOME/.env` 读 |
| **5** | **✅ No messaging platforms enabled. Gateway will continue running for cron job execution.** | **新 .env 用 `grep -v` 过滤掉平台 key** |

## CLI 模式关键修复点

### 1. `unset` 在启动脚本里是必要的但**不够**

```bash
# 启动脚本里 unset
unset FEISHU_APP_ID WEIXIN_TOKEN
# ✅ 子进程（hermes）能继承清空环境
# ❌ 但 hermes 启动后会**重新读 $HERMES_HOME/.env**——里面如果有 FEISHU_APP_ID，就白 unset 了
```

**修复**：新 .env 必须用 `grep -v` 物理删除平台 key：

```bash
grep -viE "^(FEISHU|WEIXIN|TELEGRAM|DISCORD|SLACK|GATEWAY_ALLOW_ALL_USERS)" \
  /home/zcxx/.hermes/.env > /新home/.hermes/.env
```

### 2. Weixin env var 名字的正确拼写

- ✅ `WEIXIN_ACCOUNT_ID`（是 WEIXIN，不是 WEXIN）
- ✅ `WEIXIN_TOKEN`
- 完整列表见 `templates/env-cleanup.sh`

### 3. Gateway 不监听 TCP——不需要 --port

`hermes gateway run --help` 没有 `--port`。Gateway 默认只跑 WebSocket 长连接（连 Feishu/Weixin 服务器），不监听本地 TCP。

多个 Gateway 进程可以**同时跑、不会端口冲突**。新 Hermes 用**默认 WebSocket 模式**（不连飞书）就完全不需要管端口。

唯一例外：Feishu webhook 模式（`FEISHU_WEBHOOK_PORT`，默认 8765）才需要端口。

## 第二阶段：给新 Hermes 配独立飞书机器人

用户申请了新飞书机器人（独立 app_id），要把它装到新 Hermes 上。

### 关键步骤

1. **新 .env 必须含新机器人的 FEISHU_APP_ID + APP_SECRET**：
   ```bash
   cat >> /新home/.hermes/.env << 'EOF'
   FEISHU_APP_ID=cli_aaaf2ea22cb85cbc
   FEISHU_APP_SECRET=rjbOGl7UOYWsflawJf5nxcEPX8JJ5pBN
   FEISHU_DOMAIN=feishu
   FEISHU_CONNECTION_MODE=websocket
   FEISHU_ALLOW_ALL_USERS=true
   FEISHU_REQUIRE_MENTION=true
   FEISHU_GROUP_POLICY=allowlist
   EOF
   ```

2. **启动脚本必须显式 `source` 新 .env**——因为父 shell 继承了旧 Hermes 的 FEISHU_*，不 source 的话新 Hermes 还会读到旧值：
   ```bash
   unset WEIXIN_* TELEGRAM_* DISCORD_* SLACK_* HERMES_SESSION_*
   # 不要 unset FEISHU_*（因为我们要用新机器人的）
   if [ -f "$HERMES_HOME/.env" ]; then
     set -a
     source "$HERMES_HOME/.env"
     set +a
   fi
   ```

3. **启动日志成功标志**：
   ```
   [Lark] [INFO] connected to wss://msg-frontier.feishu.cn/ws/v2?...
   INFO gateway.run: Press Ctrl+C to stop
   INFO gateway.run: Cron ticker started (interval=60s)
   ```

### 飞书侧操作清单（给用户的步骤）

1. https://open.feishu.cn/app → 创建企业自建应用
2. 拿 App ID + App Secret
3. 启用"机器人能力"
4. 权限管理开通 `im:message` 系列（im:message, im:message.group_at_msg, im:message.p2p_msg, im:resource）
5. 事件订阅用 WebSocket（不用配置公网回调）
6. **发布版本**（未发布 = 收不到消息！）

### 安全教训

**用户经常在对话里直接贴 App Secret**——任何人看到这段对话的都能控制机器人。

**修复流程**：配置完成后立即建议用户去飞书开放平台**重置 App Secret**，把新 Secret 私聊传，不在群组/公开渠道出现。

### 飞书模式启动的额外坑

#### 坑 1：脚本里 `kill -0` 检查的 sleep 3 太短

CLI 模式启动只要 3 秒，飞书模式需要 5-8 秒（要连 WebSocket）。脚本会误报"启动失败"。

**症状**：
```
=== 启动新 Hermes ===
❌ 启动失败，查看日志：
[Lark] [INFO] connected to wss://msg-frontier.feishu.cn/ws/v2   ← 实际成功了
```

**修复**：`sleep 8` 而不是 `sleep 3`。

#### 坑 2：`hermes profile create` 不接受 `--model`

```bash
hermes profile create test-ceo --model MiniMax-M3
# error: unrecognized arguments: --model MiniMax-M3
```

模型用 `/model` 命令在交互模式里切换，或在 `config.yaml` 里写 `model.default`。

#### 坑 3：旧 Hermes systemd 服务的 env vars 会污染新 shell

旧 Hermes 由 systemd 启动时设了 `HERMES_HOME=/home/zcxx/.hermes`。当前 shell 登录时可能继承这些 env vars。

**症状**：在 shell 里直接 `hermes kanban boards list` 会用旧 home。

**修复**：用 `env -i` 清空环境变量：
```bash
/usr/bin/env -i HOME=/home/zcxx PATH=... \
  HERMES_HOME=/新home/.hermes \
  hermes kanban boards list
```

## 验证方法（已确认有效）

```bash
# 1. 看进程
ps aux | grep "gateway run" | grep -v grep
# 应看到 3 行：旧 default (3306) + 旧 autops (3305) + 新 (64832)

# 2. 验证新进程的 HERMES_HOME
tr '\0' '\n' < /proc/64832/environ | grep HERMES_HOME
# HERMES_HOME=/home/zcxx/hermes-test/.hermes

# 3. 验证 Kanban 独立（必须 env -i 清空当前 shell 的 HERMES_HOME）
/usr/bin/env -i HOME=/home/zcxx PATH=... \
  HERMES_HOME=/home/zcxx/hermes-test/.hermes \
  hermes kanban boards list
# 旧 Hermes 11 个 board，新 Hermes 1 个（default 空）

# 4. 飞书模式：看 WebSocket 连接
grep -i "feishu\|lark" /新home/.hermes/logs/gateway.log
# 应看到 connected to wss://msg-frontier.feishu.cn/ws/v2

# 5. 飞书模式：发消息测试
# 在飞书里给新机器人发 "hello"
# tail -f /新home/.hermes/logs/gateway.log 应看到 [Feishu] Inbound dm message
# 旧 Hermes 的 gateway.log 不会动
```

## 最终状态

| 维度 | 旧 Hermes | 新 Hermes |
|---|---|---|
| 进程 PID | 3305 (autops) + 3306 (default) | 65164 (default) |
| HERMES_HOME | /home/zcxx/.hermes | /home/zcxx/hermes-test/.hermes |
| Feishu | 启用（旧机器人）| **启用（新机器人 cli_aaaf2ea22cb85cbc）** |
| Weixin | 启用 | **未启用** |
| Kanban boards | 11 个 | 1 个（default 空） |
| systemd 服务 | 2 个 | 0 个（手动启动） |
| 飞书 WebSocket | connected | connected |

## 后续用户问题

1. 用户频繁用模型名词"m3"——说明用户对当前模型有意识（用 `MiniMax-M3`）
2. 用户问"重启系统"——说明对基础设施理解深入
3. 用户主动思考"我可能是不是需要再重新连一个飞书的智能体"——好习惯，主动考虑隔离
4. 用户在飞书里贴 App Secret——需要主动提醒安全重置
5. 用户问 "设置新项目飞书的步骤"——需要给清晰可执行的操作流程，不是只讲架构

## 用户偏好（可记忆）

- 用户会主动思考隔离（"是不是需要再重新连一个飞书的智能体"）——喜欢讨论架构而非盲目执行
- 用户说"重新启动本地系统"——敢于做大的破坏性操作
- 用户确认"hermes 现在的 model 是 m3"——会主动校验配置
- 用户会问"我可能需要再 X"——给完整操作步骤，而不是只确认需求
