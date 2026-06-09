#!/bin/bash
# 新 Hermes 实例启动脚本（已实测可用 2026-06-07）
# 用法: ./start-hermes.sh {start|stop|status|restart} [profile_name]
# 默认 profile: test-ceo
#
# 工作模式由 .env 中是否有 FEISHU_APP_ID 决定：
#   - 有 → 连飞书模式（保留 FEISHU_* env vars）
#   - 无 → CLI/测试模式（No messaging platforms enabled）

set -e

# ============ 配置区 ============
export HERMES_HOME="/home/zcxx/hermes-test/.hermes"
export HERMES_PROFILES_DIR="$HERMES_HOME/profiles"
export VENV="/home/zcxx/.hermes/hermes-agent/venv"

# 关键：清除 Weixin/Telegram/Discord/Slack 平台 env vars，
# 防止新 Hermes 误读父 shell 继承的旧 Hermes 凭证
# 注意：FEISHU_* 不在这里 unset —— 脚本末尾根据 .env 是否含 FEISHU_APP_ID 决定是否 source
unset WEIXIN_ACCOUNT_ID WEIXIN_TOKEN WEIXIN_BASE_URL WEIXIN_CDN_BASE_URL
unset WEIXIN_DM_POLICY WEIXIN_GROUP_POLICY WEIXIN_ALLOWED_USERS
unset WEIXIN_ALLOW_ALL_USERS WEIXIN_GROUP_ALLOWED_USERS WEIXIN_HOME_CHANNEL
unset WEIXIN_SEND_CHUNK_DELAY_SECONDS WEIXIN_SEND_CHUNK_RETRIES
unset WEIXIN_SEND_CHUNK_RETRY_DELAY_SECONDS
unset TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS
unset DISCORD_BOT_TOKEN DISCORD_ALLOWED_USERS
unset SLACK_BOT_TOKEN SLACK_ALLOWED_USERS
unset GATEWAY_ALLOW_ALL_USERS
unset HERMES_SESSION_PLATFORM HERMES_SESSION_KEY

# 显式从新 .env 加载（关键：覆盖父 shell 继承的旧 Hermes env vars）
if [ -f "$HERMES_HOME/.env" ]; then
  set -a  # 自动 export 所有赋值的变量
  source "$HERMES_HOME/.env"
  set +a
fi

# 第一个参数是动作，第二个是 profile
ACTION="${1:-start}"
PROFILE="${2:-test-ceo}"
HERMES_BIN="$VENV/bin/hermes"
LOG_DIR="$HERMES_HOME/logs"
LOG_FILE="$LOG_DIR/gateway.log"
PID_FILE="$HERMES_HOME/gateway.pid"

mkdir -p "$LOG_DIR" "$HERMES_PROFILES_DIR"

# ============ 函数 ============
start() {
  echo "=== 启动新 Hermes（HERMES_HOME=$HERMES_HOME，profile=$PROFILE）==="

  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "⚠️  已有进程在运行 (PID: $(cat "$PID_FILE"))，先 stop 再 start"
    exit 1
  fi

  nohup "$HERMES_BIN" --profile "$PROFILE" gateway run --replace \
    > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"

  # 关键：sleep 至少 8 秒——Gateway 加载模型 + 初始化 platform 需要时间
  sleep 8

  if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "✅ 新 Hermes 启动成功 (PID: $(cat "$PID_FILE"))"
    echo "📋 日志: $LOG_FILE"
    echo "🔍 查看: tail -f $LOG_FILE"
    echo ""
    echo "=== 验证两个 Hermes 都在跑 ==="
    ps aux | grep "gateway run" | grep -v grep
    echo ""
    echo "=== Feishu 连接状态 ==="
    if [ -n "$FEISHU_APP_ID" ]; then
      grep -i "feishu\|lark" "$LOG_FILE" | tail -3
    else
      echo "CLI 模式（未连飞书）"
    fi
  else
    echo "❌ 启动失败，查看日志："
    tail -20 "$LOG_FILE"
    exit 1
  fi
}

stop() {
  echo "=== 停止新 Hermes ==="
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      kill "$PID"
      sleep 2
      rm -f "$PID_FILE"
      echo "✅ 已停止 (PID: $PID)"
    else
      echo "⚠️  PID $PID 不存在，清理 PID 文件"
      rm -f "$PID_FILE"
    fi
  else
    echo "⚠️  未运行（无 PID 文件）"
  fi
}

status() {
  echo "=== 新 Hermes 状态 ==="
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "✅ 运行中 (PID: $(cat "$PID_FILE"))"
    echo "HOME: $HERMES_HOME"
    echo "PROFILE: $PROFILE"
  else
    echo "❌ 未运行"
  fi
  echo ""
  echo "=== 所有 Hermes 进程 ==="
  ps aux | grep "gateway run" | grep -v grep || echo "  (无)"
}

case "$ACTION" in
  start)   start ;;
  stop)    stop ;;
  status)  status ;;
  restart) stop; sleep 1; start ;;
  *)       echo "用法: $0 {start|stop|status|restart} [profile_name]"; exit 1 ;;
esac
