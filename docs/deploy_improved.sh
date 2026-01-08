#!/usr/bin/env bash
set -e

TARGET_DIR="/home/work/Wenning"

cd $TARGET_DIR/output
PID_FILE="app.pid"

# 创建本地环境配置文件（不提交到git）
# 用于配置Playwright等工具的代理设置
echo "🔧 Creating local environment config..."
cat > .env.local << 'ENVEOF'
# Playwright代理配置（用于访问外网）
PLAYWRIGHT_PROXY_SERVER=http://agent.baidu.com:8891
ENVEOF
echo "✅ Local config created: .env.local"

# 停止服务
stop_app() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
      echo "🛑 Stopping running app (PID=$PID)"
      kill "$PID"
      sleep 2
    fi
    rm -f "$PID_FILE"
  fi
}

# 清理 Python 缓存（重要！避免加载旧代码）
echo "🧹 Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Cache cleaned"

# 安装中文字体（matplotlib绘图需要）
echo "🔤 Installing Chinese fonts for matplotlib..."
if ! fc-list | grep -qi "wqy\|noto.*cjk\|droid.*sans"; then
    echo "  Installing WenQuanYi fonts..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq fonts-wqy-zenhei fonts-wqy-microhei fonts-noto-cjk 2>/dev/null || {
        echo "  ⚠️  Font installation requires sudo, skipping..."
    }
else
    echo "  ✅ Chinese fonts already installed"
fi

# 清理matplotlib字体缓存（让新字体生效）
rm -rf ~/.cache/matplotlib ~/.matplotlib 2>/dev/null || true
echo "✅ Font setup complete"

# 创建虚拟环境（如果不存在）
if [ ! -d "$TARGET_DIR/output/.venv" ]; then
  echo "📦 Creating virtualenv"
  python3 -m venv .venv
fi

# 升级 pip（使用代理）
echo "⬆️  Upgrading pip..."
(export https_proxy=http://agent.baidu.com:8891; .venv/bin/pip3 install --upgrade pip setuptools wheel build)

# 安装依赖（使用代理）
if [ -f "requirements.txt" ]; then
    echo "📥 Installing requirements"
    (export https_proxy=http://agent.baidu.com:8891; .venv/bin/pip3 install -r requirements.txt)

    # 安装Playwright浏览器及系统依赖（如果playwright在requirements中）
    if .venv/bin/pip3 show playwright > /dev/null 2>&1; then
        echo "🎭 Installing Playwright browsers and system dependencies..."
        (export https_proxy=http://agent.baidu.com:8891; .venv/bin/playwright install chromium)
        # 注意：install-deps需要sudo权限，如果没有权限会跳过
        .venv/bin/playwright install-deps chromium 2>/dev/null || {
            echo "⚠️  Playwright system dependencies installation requires sudo"
            echo "   Please run manually: sudo .venv/bin/playwright install-deps chromium"
        }
    fi
else
    echo "⚠️  requirements.txt not found, skip"
fi

# 停止旧服务
stop_app

# 启动服务（使用代理访问外网如Tavily，但排除百度内网域名如千帆API）
echo "▶️  Starting app on port 8081"
export https_proxy=http://agent.baidu.com:8891
export http_proxy=http://agent.baidu.com:8891
export no_proxy="baidu.com,.baidu.com,baidubce.com,.baidubce.com,baidu-int.com,.baidu-int.com,localhost,127.0.0.1,10.0.0.0/8,192.168.0.0/16"
export WENNING_PORT=8081
nohup .venv/bin/python3 fastapi_app.py > app.log 2>&1 &
echo $! > "$PID_FILE"

# 等待服务启动
sleep 2

# 检查服务状态
if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    echo "✅ Deploy finished successfully!"
    echo "   PID: $(cat $PID_FILE)"
    echo "   URL: http://10.25.70.163:8081"
    echo ""
    echo "📋 Check logs:"
    echo "   tail -f app.log"
    echo "   tail -f logs/wenning_$(date +%Y-%m-%d).log"
else
    echo "❌ Service failed to start, check app.log for details"
    tail -20 app.log
    exit 1
fi
