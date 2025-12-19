#!/usr/bin/env bash
set -e

export https_proxy=http://agent.baidu.com:8891

TARGET_DIR="/home/work/Wenning"
cd $TARGET_DIR/output
PID_FILE="app.pid"

# 改进的停止函数
stop_app() {
  echo "🛑 Stopping existing app..."

  # 1. 先尝试从PID文件停止
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
      echo "  Killing process (PID=$PID)"
      kill -9 "$PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi

  # 2. 强制清理所有可能残留的进程
  pkill -9 -f "python3.*fastapi_app.py" 2>/dev/null || true

  # 3. 等待确认所有进程已停止
  for i in {1..5}; do
    if pgrep -f "fastapi_app.py" > /dev/null; then
      echo "  Waiting for processes to stop... ($i/5)"
      sleep 1
    else
      echo "  ✅ All processes stopped"
      break
    fi
  done

  # 4. 清理Python缓存
  echo "🧹 Cleaning Python cache..."
  find ./src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  find ./src -type f -name "*.pyc" -delete 2>/dev/null || true
}

# 虚拟环境设置
if [ ! -d "$TARGET_DIR/output/.venv" ]; then
  echo "Creating virtualenv"
  python3 -m venv .venv
fi

.venv/bin/pip3 install --upgrade pip setuptools wheel build

if [ -f "requirements.txt" ]; then
    echo "📦 Installing requirements"
    .venv/bin/pip3 install -r requirements.txt
else
    echo "⚠️ requirements.txt not found, skip"
fi

# 停止旧服务
stop_app

echo "▶️ Starting app"
sed -i 's/port=80/port=8081/g' fastapi_app.py
nohup .venv/bin/python3 fastapi_app.py > app.log 2>&1 &
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"

# 验证启动成功
sleep 2
if ps -p $NEW_PID > /dev/null; then
  echo "✅ Deploy finished, PID=$NEW_PID  http://10.25.70.163:8081"
else
  echo "❌ Failed to start app, check app.log"
  tail -50 app.log
  exit 1
fi
