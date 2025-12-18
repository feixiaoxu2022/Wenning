#!/usr/bin/env python3
"""纯Python标准库实现的日志查看服务

无需任何第三方依赖！

功能：
1. 查看日志文件列表
2. 查看最新N行日志
3. 搜索关键字

启动方式：
    python log_viewer_simple.py

访问方式：
    http://your-server:9000/
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import json
import os

# 配置日志文件目录
LOG_DIR = Path(__file__).parent / "logs"

# 首页HTML
INDEX_HTML = """<!DOCTYPE html>
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
        button:disabled { background: #ccc; cursor: not-allowed; }
        .log-container {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            max-height: 80vh;
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
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .stats {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 10px 15px;
            border-radius: 4px;
            margin-bottom: 10px;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Wenning日志查看器 (标准库版)</h1>

        <div class="controls">
            <div class="control-row">
                <label>日志文件:</label>
                <select id="logFile">
                    <option value="">-- 加载中 --</option>
                </select>

                <label>显示行数:</label>
                <select id="lines">
                    <option value="50">50行</option>
                    <option value="100" selected>100行</option>
                    <option value="200">200行</option>
                    <option value="500">500行</option>
                    <option value="1000">1000行</option>
                    <option value="all">全部</option>
                </select>
            </div>

            <div class="control-row">
                <label>搜索关键字:</label>
                <input type="text" id="search" placeholder="输入关键字，如: manage_images_view">
                <button onclick="loadLogs()" id="loadBtn">📊 查看日志</button>
                <button onclick="autoRefresh()" id="refreshBtn">🔄 自动刷新(5s)</button>
            </div>
        </div>

        <div id="statsDiv"></div>
        <div class="log-container" id="logContainer">
            <div class="loading">正在加载日志文件列表...</div>
        </div>
    </div>

    <script>
        let autoRefreshInterval = null;

        // 页面加载时获取日志文件列表
        window.onload = function() {
            loadFileList();
        };

        function loadFileList() {
            fetch('/api/files')
                .then(r => r.json())
                .then(data => {
                    const select = document.getElementById('logFile');
                    select.innerHTML = '';

                    if (data.files.length === 0) {
                        select.innerHTML = '<option value="">-- 无日志文件 --</option>';
                        document.getElementById('logContainer').innerHTML =
                            '<div class="loading">logs/目录下没有.log文件</div>';
                        return;
                    }

                    data.files.forEach(f => {
                        const option = document.createElement('option');
                        option.value = f.name;
                        option.textContent = `${f.name} (${formatSize(f.size)})`;
                        select.appendChild(option);
                    });

                    document.getElementById('logContainer').innerHTML =
                        '<div class="loading">选择日志文件并点击"查看日志"</div>';
                })
                .catch(err => {
                    document.getElementById('logContainer').innerHTML =
                        `<div class="loading">加载文件列表失败: ${err.message}</div>`;
                });
        }

        function loadLogs() {
            const logFile = document.getElementById('logFile').value;
            const lines = document.getElementById('lines').value;
            const search = document.getElementById('search').value;

            if (!logFile) {
                alert('请选择日志文件');
                return;
            }

            let url = `/api/logs/${logFile}?lines=${lines}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;

            document.getElementById('logContainer').innerHTML = '<div class="loading">加载中...</div>';
            document.getElementById('statsDiv').innerHTML = '';

            fetch(url)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        throw new Error(data.error);
                    }

                    // 显示统计信息
                    let stats = `📊 总行数: ${data.total_lines}`;
                    if (data.filtered_lines !== data.total_lines) {
                        stats += ` | 🔍 匹配行数: ${data.filtered_lines}`;
                    }
                    stats += ` | 📄 显示行数: ${data.shown_lines}`;

                    document.getElementById('statsDiv').innerHTML =
                        `<div class="stats">${stats}</div>`;

                    // 显示日志内容
                    const content = data.content || '（空）';
                    document.getElementById('logContainer').innerHTML =
                        `<pre>${escapeHtml(content)}</pre>`;
                })
                .catch(err => {
                    document.getElementById('logContainer').innerHTML =
                        `<div class="loading" style="color: #f44336;">加载失败: ${err.message}</div>`;
                });
        }

        function autoRefresh() {
            const btn = document.getElementById('refreshBtn');

            if (autoRefreshInterval) {
                // 停止自动刷新
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
                btn.textContent = '🔄 自动刷新(5s)';
                btn.style.background = '#007bff';
            } else {
                // 启动自动刷新
                loadLogs();  // 立即刷新一次
                autoRefreshInterval = setInterval(loadLogs, 5000);
                btn.textContent = '⏹️ 停止刷新';
                btn.style.background = '#dc3545';
            }
        }

        function formatSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
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

        // 页面关闭时停止自动刷新
        window.onbeforeunload = function() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
            }
        };
    </script>
</body>
</html>
"""


class LogViewerHandler(BaseHTTPRequestHandler):
    """日志查看请求处理器"""

    def do_GET(self):
        """处理GET请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        # 路由分发
        if path == '/':
            self.serve_index()
        elif path == '/api/files':
            self.serve_file_list()
        elif path.startswith('/api/logs/'):
            filename = path.replace('/api/logs/', '')
            self.serve_log(filename, query)
        else:
            self.send_error(404, "Not Found")

    def serve_index(self):
        """返回首页"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(INDEX_HTML.encode('utf-8'))

    def serve_file_list(self):
        """返回日志文件列表"""
        files = []
        if LOG_DIR.exists():
            for f in sorted(LOG_DIR.glob('*.log')):
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime
                })

        self.send_json_response({"files": files})

    def serve_log(self, filename, query):
        """返回日志内容"""
        log_path = LOG_DIR / filename

        if not log_path.exists():
            self.send_json_response({"error": f"日志文件不存在: {filename}"}, 404)
            return

        try:
            # 获取参数
            lines_param = query.get('lines', ['100'])[0]
            search = query.get('search', [''])[0].strip()

            # 读取文件
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()

            total_lines = len(all_lines)
            filtered_lines = all_lines

            # 如果有搜索关键字，先过滤
            if search:
                filtered_lines = [line for line in all_lines if search in line]

            # 取最后N行
            if lines_param == 'all':
                shown_lines = filtered_lines
            else:
                lines_count = int(lines_param)
                shown_lines = filtered_lines[-lines_count:]

            content = ''.join(shown_lines)

            self.send_json_response({
                "total_lines": total_lines,
                "filtered_lines": len(filtered_lines),
                "shown_lines": len(shown_lines),
                "content": content
            })

        except Exception as e:
            self.send_json_response({"error": f"读取日志失败: {str(e)}"}, 500)

    def send_json_response(self, data, status_code=200):
        """发送JSON响应"""
        json_data = json.dumps(data, ensure_ascii=False)
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json_data.encode('utf-8'))

    def log_message(self, format, *args):
        """禁用默认日志输出（避免干扰）"""
        pass


def run_server(port=9000):
    """启动HTTP服务器"""
    server = HTTPServer(('0.0.0.0', port), LogViewerHandler)

    print(f"📋 日志查看器启动成功！")
    print(f"📁 日志目录: {LOG_DIR.absolute()}")
    print(f"🌐 访问地址: http://0.0.0.0:{port}")
    print(f"")
    print(f"💡 使用说明:")
    print(f"  1. 浏览器访问: http://your-server-ip:{port}")
    print(f"  2. 选择日志文件和显示行数")
    print(f"  3. 输入搜索关键字（如: manage_images_view）")
    print(f"  4. 点击'查看日志'查看，或点击'自动刷新'开启5秒刷新")
    print(f"")
    print(f"按 Ctrl+C 停止服务")
    print(f"")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == '__main__':
    run_server()
