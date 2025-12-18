#!/usr/bin/env python3
"""简单的日志查看HTTP服务

功能：
1. 查看最新N行日志
2. 搜索关键字
3. 实时tail日志流
4. 支持多个日志文件

启动方式：
    python log_viewer.py

访问方式：
    http://your-server:9000/
    http://your-server:9000/logs/app.log?lines=100
    http://your-server:9000/logs/app.log?search=manage_images_view
    http://your-server:9000/tail/app.log  (实时流)
"""

from flask import Flask, Response, request, render_template_string
import os
import time
from pathlib import Path

app = Flask(__name__)

# 配置日志文件目录
LOG_DIR = Path(__file__).parent / "logs"

# 首页HTML模板
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Wenning日志查看器</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .control-row {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            align-items: center;
        }
        label { font-weight: 600; min-width: 80px; }
        select, input, button {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        input { flex: 1; }
        button {
            background: #007bff;
            color: white;
            border: none;
            cursor: pointer;
            font-weight: 600;
        }
        button:hover { background: #0056b3; }
        .log-container {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        pre {
            margin: 0;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 13px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .highlight { background: #ffd700; color: #000; padding: 2px 4px; }
        .error { color: #f44336; }
        .warning { color: #ff9800; }
        .info { color: #4caf50; }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Wenning日志查看器</h1>

        <div class="controls">
            <div class="control-row">
                <label>日志文件:</label>
                <select id="logFile">
                    {% for log in log_files %}
                    <option value="{{ log }}">{{ log }}</option>
                    {% endfor %}
                </select>

                <label>显示行数:</label>
                <select id="lines">
                    <option value="50">50行</option>
                    <option value="100" selected>100行</option>
                    <option value="200">200行</option>
                    <option value="500">500行</option>
                    <option value="1000">1000行</option>
                </select>
            </div>

            <div class="control-row">
                <label>搜索关键字:</label>
                <input type="text" id="search" placeholder="输入关键字，如: manage_images_view">
                <button onclick="loadLogs()">📊 查看日志</button>
                <button onclick="startTail()">🔄 实时监控</button>
                <button onclick="stopTail()">⏹️ 停止</button>
            </div>
        </div>

        <div class="log-container" id="logContainer">
            <div class="loading">选择日志文件并点击"查看日志"</div>
        </div>
    </div>

    <script>
        let tailStream = null;

        function loadLogs() {
            const logFile = document.getElementById('logFile').value;
            const lines = document.getElementById('lines').value;
            const search = document.getElementById('search').value;

            let url = `/logs/${logFile}?lines=${lines}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;

            document.getElementById('logContainer').innerHTML = '<div class="loading">加载中...</div>';

            fetch(url)
                .then(r => r.text())
                .then(data => {
                    document.getElementById('logContainer').innerHTML = `<pre>${escapeHtml(data)}</pre>`;
                })
                .catch(err => {
                    document.getElementById('logContainer').innerHTML =
                        `<div class="error">加载失败: ${err.message}</div>`;
                });
        }

        function startTail() {
            stopTail();

            const logFile = document.getElementById('logFile').value;
            const search = document.getElementById('search').value;

            let url = `/tail/${logFile}`;
            if (search) url += `?search=${encodeURIComponent(search)}`;

            document.getElementById('logContainer').innerHTML = '<pre id="tailContent"></pre>';
            const container = document.getElementById('tailContent');

            tailStream = new EventSource(url);

            tailStream.onmessage = function(event) {
                container.textContent += event.data + '\\n';
                container.parentElement.scrollTop = container.parentElement.scrollHeight;
            };

            tailStream.onerror = function() {
                container.textContent += '\\n[连接断开]\\n';
                stopTail();
            };
        }

        function stopTail() {
            if (tailStream) {
                tailStream.close();
                tailStream = null;
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 回车键触发搜索
        document.getElementById('search').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') loadLogs();
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """首页 - 日志查看器界面"""
    log_files = []
    if LOG_DIR.exists():
        log_files = sorted([f.name for f in LOG_DIR.glob('*.log')])

    return render_template_string(INDEX_HTML, log_files=log_files)


@app.route('/logs/<filename>')
def view_log(filename):
    """查看日志文件（最新N行，支持搜索）"""
    log_path = LOG_DIR / filename

    if not log_path.exists():
        return f"日志文件不存在: {filename}", 404

    # 获取参数
    lines = int(request.args.get('lines', 100))
    search = request.args.get('search', '').strip()

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        # 如果有搜索关键字，先过滤
        if search:
            all_lines = [line for line in all_lines if search in line]

        # 取最后N行
        recent_lines = all_lines[-lines:]

        return ''.join(recent_lines), 200, {'Content-Type': 'text/plain; charset=utf-8'}

    except Exception as e:
        return f"读取日志失败: {str(e)}", 500


@app.route('/tail/<filename>')
def tail_log(filename):
    """实时tail日志（Server-Sent Events）"""
    log_path = LOG_DIR / filename

    if not log_path.exists():
        return f"日志文件不存在: {filename}", 404

    search = request.args.get('search', '').strip()

    def generate():
        """生成器：持续读取日志新内容"""
        with open(log_path, 'r', encoding='utf-8') as f:
            # 先跳到文件末尾
            f.seek(0, 2)

            while True:
                line = f.readline()
                if line:
                    # 如果有搜索关键字，只发送匹配的行
                    if not search or search in line:
                        yield f"data: {line.rstrip()}\n\n"
                else:
                    time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')


@app.route('/files')
def list_files():
    """列出所有日志文件"""
    if not LOG_DIR.exists():
        return {"files": []}

    files = []
    for f in LOG_DIR.glob('*.log'):
        stat = f.stat()
        files.append({
            "name": f.name,
            "size": stat.st_size,
            "modified": time.ctime(stat.st_mtime)
        })

    return {"files": files}


if __name__ == '__main__':
    print(f"📋 日志查看器启动中...")
    print(f"📁 日志目录: {LOG_DIR}")
    print(f"🌐 访问地址: http://0.0.0.0:9000")
    print(f"")
    print(f"使用说明:")
    print(f"  1. 浏览器访问: http://your-server-ip:9000")
    print(f"  2. 选择日志文件和显示行数")
    print(f"  3. 输入搜索关键字（如: manage_images_view）")
    print(f"  4. 点击'查看日志'或'实时监控'")
    print(f"")

    # 启动服务
    app.run(host='0.0.0.0', port=9000, debug=False, threaded=True)
