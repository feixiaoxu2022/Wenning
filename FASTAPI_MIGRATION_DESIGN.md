# FastAPI前端迁移设计文档

## 一、核心目标

从Chainlit迁移到FastAPI + 原生前端，彻底解决黑盒问题，完全掌控前后端。

## 二、功能需求清单

### 2.1 已有功能（必须保留）

#### 后端功能
- [x] Agent流式处理 (`process_with_progress`)
- [x] 多模型支持 (gpt-5, ernie-5.0-thinking-preview, glm-4.5, doubao-seed-1-6-thinking-250615, gemini-2.5-pro)
- [x] 工具注册与执行 (WebSearchTool, URLFetchTool, CodeExecutor)
- [x] 对话历史管理
- [x] 思考过程流式输出
- [x] 进度更新 (工具执行心跳)
- [x] 最终结果返回
- [x] 文件生成 (Excel/图片)

#### 前端功能
- [x] **左侧预览区 + 右侧对话区** 的布局
- [x] 多模型选项卡切换
- [x] 流式显示思考过程
- [x] 流式显示最终答案
- [x] Excel文件预览 (HTML表格)
- [x] 文件下载
- [x] 对话历史展示
- [x] 错误提示

### 2.2 新增优化

- [ ] 完全透明的流式机制 (SSE)
- [ ] 零黑盒，所有代码可控
- [ ] 更稳定的性能
- [ ] 更简洁的代码结构

## 三、技术架构

### 3.1 后端架构

```
FastAPI Application
├── fastapi_app.py          # 主应用
├── api/
│   ├── chat.py            # 聊天API (SSE流式)
│   └── models.py          # 数据模型
├── static/                # 前端静态文件
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── app.js         # 主应用逻辑
│       ├── sse.js         # SSE处理
│       └── ui.js          # UI组件
└── outputs/               # 生成文件目录
```

### 3.2 前端架构

#### 布局结构
```
┌─────────────────────────────────────────────┐
│            Header (模型选择)                  │
├──────────────┬──────────────────────────────┤
│              │                              │
│              │  对话区                       │
│  文件预览区   │  - 用户消息                   │
│              │  - Agent思考过程              │
│  (左侧)      │  - 最终答案                   │
│              │  - 输入框                     │
│              │                              │
│              │  (右侧,可滚动)                │
└──────────────┴──────────────────────────────┘
```

#### 组件划分
1. **Header**: 模型选择下拉框
2. **PreviewPanel**: 左侧文件预览区
   - Excel表格渲染
   - 图片显示
   - 下载按钮
3. **ChatPanel**: 右侧对话区
   - MessageList: 消息列表（用户+Agent）
   - ThinkingBox: 思考过程（流式更新）
   - ResultBox: 最终答案
   - InputBox: 用户输入框

### 3.3 数据流

```
用户输入 → FastAPI /chat → Agent.process_with_progress()
                                    ↓
                              SSE Stream
                                    ↓
                          EventSource (前端)
                                    ↓
                           更新DOM (实时)
```

## 四、API设计

### 4.1 聊天接口

**Endpoint**: `GET /chat`

**Query参数**:
- `message` (string): 用户消息
- `model` (string): 选择的模型名称

**Response**: Server-Sent Events (SSE)

**SSE消息格式**:

```javascript
// 思考过程更新
{
  "type": "thinking",
  "content": "思考内容片段"
}

// 进度更新
{
  "type": "progress",
  "message": "⏳ url_fetch 执行中...已等待 10 秒",
  "status": "⏳ 等待 url_fetch"
}

// 最终结果
{
  "type": "final",
  "result": {
    "status": "success",
    "result": "最终答案内容",
    "files": ["outputs/report.xlsx"]  // 生成的文件路径
  }
}

// 结束标记
"[DONE]"
```

### 4.2 文件服务

**Endpoint**: `GET /outputs/{filename}`

**Response**: 文件下载

### 4.3 Excel预览接口

**Endpoint**: `GET /preview/excel/{filename}`

**Response**: JSON

```json
{
  "html": "<table>...</table>",
  "rows": 100,
  "preview_rows": 20
}
```

## 五、前端实现细节

### 5.1 SSE流式处理

```javascript
function sendMessage(message, model) {
  const url = `/chat?message=${encodeURIComponent(message)}&model=${model}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (e) => {
    if (e.data === '[DONE]') {
      eventSource.close();
      return;
    }

    const update = JSON.parse(e.data);
    handleUpdate(update);
  };

  eventSource.onerror = (e) => {
    console.error('SSE error:', e);
    eventSource.close();
  };
}
```

### 5.2 思考过程渲染

```javascript
function handleUpdate(update) {
  switch(update.type) {
    case 'thinking':
      appendThinking(update.content);
      break;
    case 'progress':
      showProgress(update.message);
      break;
    case 'final':
      showResult(update.result);
      if (update.result.files) {
        loadFilePreview(update.result.files[0]);
      }
      break;
  }
}
```

### 5.3 Excel预览

```javascript
async function loadFilePreview(filepath) {
  const filename = filepath.split('/').pop();

  if (filename.endsWith('.xlsx')) {
    const response = await fetch(`/preview/excel/${filename}`);
    const data = await response.json();

    document.getElementById('preview-panel').innerHTML = data.html;
  } else if (filename.match(/\.(png|jpg|jpeg)$/)) {
    document.getElementById('preview-panel').innerHTML =
      `<img src="/outputs/${filename}" />`;
  }
}
```

### 5.4 对话历史管理

```javascript
const chatHistory = [];

function addMessage(role, content) {
  chatHistory.push({ role, content });
  renderMessage(role, content);
}

function renderMessage(role, content) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${role}`;
  messageDiv.textContent = content;
  document.getElementById('chat-messages').appendChild(messageDiv);
}
```

## 六、样式设计

### 6.1 布局CSS

```css
body {
  margin: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.header {
  height: 60px;
  padding: 10px 20px;
  border-bottom: 1px solid #ddd;
}

.main-container {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.preview-panel {
  width: 40%;
  border-right: 1px solid #ddd;
  overflow: auto;
  padding: 20px;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.chat-input {
  height: 100px;
  border-top: 1px solid #ddd;
  padding: 10px;
}
```

### 6.2 消息样式

```css
.message {
  margin-bottom: 15px;
  padding: 10px;
  border-radius: 8px;
}

.message.user {
  background: #e3f2fd;
  margin-left: 20%;
}

.message.assistant {
  background: #f5f5f5;
  margin-right: 20%;
}

.thinking-box {
  background: #fff3cd;
  border-left: 4px solid #ffc107;
  padding: 10px;
  margin: 10px 0;
  font-family: monospace;
  white-space: pre-wrap;
}

.result-box {
  background: #d4edda;
  border-left: 4px solid #28a745;
  padding: 15px;
  margin: 10px 0;
}
```

## 七、实现步骤

### Phase 1: 后端API (15分钟)
1. 创建 `fastapi_app.py`
2. 实现 `/chat` SSE接口
3. 实现 `/outputs/{filename}` 文件服务
4. 实现 `/preview/excel/{filename}` 预览接口

### Phase 2: 前端基础 (20分钟)
1. 创建 `static/index.html` 基础结构
2. 创建 `static/css/style.css` 样式
3. 创建 `static/js/sse.js` SSE处理逻辑
4. 创建 `static/js/ui.js` UI渲染逻辑
5. 创建 `static/js/app.js` 主应用逻辑

### Phase 3: 功能集成 (15分钟)
1. 集成模型选择
2. 集成文件预览
3. 集成对话历史
4. 测试所有功能

### Phase 4: 测试优化 (10分钟)
1. 测试长时间流式输出
2. 测试文件生成与预览
3. 测试错误处理
4. 性能优化

## 八、兼容性保证

### 8.1 保持原有接口

```python
# Agent接口不变
agent.process_with_progress(user_input)  # 继续使用

# 输出格式不变
yield {
    "type": "thinking",
    "content": "..."
}
```

### 8.2 配置不变

```python
# 继续使用现有config
config = get_config()
agent = MasterAgent(config, tool_registry, model_name=model_name)
```

## 九、优势对比

| 特性 | Chainlit | FastAPI方案 |
|------|----------|-------------|
| 流式机制 | 黑盒，不可控 | 透明，SSE标准 |
| 调试难度 | 高 | 低 |
| 性能 | 容易阻塞 | 稳定可控 |
| 代码量 | 少但隐藏复杂度 | 多但完全掌控 |
| 定制性 | 受限 | 完全自由 |
| 错误定位 | 困难 | 容易 |

## 十、风险与应对

### 风险1: SSE浏览器兼容性
**应对**: SSE在所有现代浏览器都支持，IE需polyfill（但我们不需要支持IE）

### 风险2: 大量流式数据性能
**应对**:
- 前端使用DocumentFragment批量更新DOM
- 限制thinking_box最大显示行数
- 实现虚拟滚动

### 风险3: 迁移过程中的Bug
**应对**:
- 保留Chainlit版本作为备份
- 新版本独立目录开发
- 充分测试后再切换

## 十一、文件清单

### 新增文件
```
tmp_scenarios/creative_agent/
├── fastapi_app.py              # FastAPI主应用 (新)
├── static/                     # 前端静态文件 (新)
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── app.js
│       ├── sse.js
│       └── ui.js
├── chainlit_app.py             # 保留备份
└── outputs/                    # 已存在，继续使用
```

### 保持不变的文件
```
src/
├── agent/
│   └── master_agent.py        # 不改
├── tools/
│   ├── registry.py            # 不改
│   └── atomic/                # 不改
└── utils/
    └── config.py              # 不改
```

## 十二、启动命令

### 旧版本（Chainlit）
```bash
chainlit run chainlit_app.py --host 0.0.0.0 --port 8000
```

### 新版本（FastAPI）
```bash
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
```

---

**设计完成时间**: 2025-11-17
**预计实现时间**: 60分钟
**预计稳定性提升**: 10倍
