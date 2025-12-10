# Wenning

Wenning是一个功能强大的AI Agent系统，专为内容创作者（如自媒体博主、产品运营人员）设计。通过灵活的工具组合和智能的任务规划，帮助用户自动化完成各类复杂创意任务。

## ✨ 核心特性

- 🤖 **Agentic Loop架构**：Master Agent + 工具注册表架构，支持复杂任务的自动化执行
- 🔧 **丰富的工具生态**：
  - 📝 内容生成：UGC分析、封面生成、文本创作
  - 🎨 多媒体创作：图像生成、视频生成、音乐生成
  - 🗣️ 语音合成：支持Google/Azure/本地/MiniMax多引擎TTS
  - 🌐 信息获取：Web搜索、URL抓取、网页预览
  - 💻 代码执行：Python代码沙箱、Shell命令执行
  - 📁 文件操作：文件读取、编辑、列表管理
- 🔄 **任务规划能力**：智能任务分解与步骤规划
- 🧠 **多模型支持**：兼容OpenAI/Claude/Gemini/EB5/GLM-4.5等
- 📦 **工作空间管理**：基于对话的文件组织和版本管理

## 🏗️ 项目架构

```
Wenning/
├── src/
│   ├── agent/              # Agent核心
│   │   ├── master_agent.py     # Master Agent主逻辑
│   │   └── context_manager.py  # 上下文管理
│   │
│   ├── tools/              # 工具层
│   │   ├── base.py             # 工具基类
│   │   ├── registry.py         # 工具注册表
│   │   ├── result.py           # 工具执行结果
│   │   │
│   │   ├── atomic/             # 原子工具（20+工具）
│   │   │   ├── web_search.py           # Web搜索
│   │   │   ├── url_fetch.py            # URL内容抓取
│   │   │   ├── code_executor.py        # Python代码执行
│   │   │   ├── shell_executor.py       # Shell命令执行
│   │   │   ├── file_reader.py          # 文件读取
│   │   │   ├── file_editor.py          # 文件编辑
│   │   │   ├── file_list.py            # 文件列表
│   │   │   ├── webpage_preview.py      # 网页预览
│   │   │   ├── media_ffmpeg.py         # 媒体处理
│   │   │   ├── plan.py                 # 任务规划
│   │   │   ├── tts_google.py           # Google TTS
│   │   │   ├── tts_azure.py            # Azure TTS
│   │   │   ├── tts_local.py            # 本地TTS
│   │   │   ├── tts_minimax.py          # MiniMax TTS
│   │   │   ├── text_to_image_minimax.py  # 文生图
│   │   │   ├── image_generation_minimax.py # 图像生成
│   │   │   ├── video_generation_minimax.py # 视频生成
│   │   │   └── music_generation_minimax.py # 音乐生成
│   │   │
│   │   └── workflow/           # 工作流工具
│   │       ├── ugc_analysis.py      # UGC分析工作流
│   │       └── cover_generation.py  # 封面生成工作流
│   │
│   ├── llm/                # LLM客户端
│   │   ├── client.py           # 统一LLM接口
│   │   └── prompts.py          # Prompt模板
│   │
│   └── utils/              # 工具函数
│       ├── config.py                # 配置管理
│       ├── logger.py                # 日志
│       ├── auth.py                  # 认证
│       ├── conversation_manager.py  # 对话管理
│       ├── workspace_manager.py     # 工作空间管理
│       └── workspace_store.py       # 工作空间存储
│
├── fastapi_app.py          # FastAPI启动入口
├── requirements.txt        # 依赖列表
├── .env.example            # 配置模板
└── README.md               # 项目文档
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/feixiaoxu2022/Wenning.git
cd Wenning

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

**可选安装**：

```bash
# HTML转图片功能（需要下载Chromium浏览器，约300MB）
playwright install chromium
```

### 2. 配置API密钥

复制 `.env.example` 为 `.env`，填入你的API密钥：

```bash
cp .env.example .env
# 编辑 .env 文件，配置以下内容：
# - LLM API密钥（OpenAI/Claude/Gemini等）
# - TTS服务密钥（Google/Azure等）
# - MiniMax API密钥（图像/视频/音乐生成）
# - Web搜索API密钥（Tavily/Serper等）
```

### 3. 启动服务

```bash
# 启动FastAPI服务
python fastapi_app.py

# 访问 http://localhost 开始使用
```

## 💡 使用场景

### 场景1: UGC内容分析

**用户输入**：

> "帮我分析小红书上关于'AI Agent'的最新评论，生成分析报告"

**系统执行**：

1. Web搜索相关内容
2. 情感分析与内容分类
3. 筛选高价值评论
4. 生成Excel分析报告

**交付物**：Excel报告（包含原始评论、情感分析、回复建议）

### 场景2: 多媒体内容创作

**用户输入**：

> "生成一首轻音乐背景音乐，同时制作一张'Python入门教程'的封面"

**系统执行**：

1. 调用音乐生成工具创建BGM
2. 调用图像生成工具创建封面
3. 可选：合成视频内容

**交付物**：音频文件(.mp3) + 图片文件(.png)

### 场景3: 自动化任务规划

**用户输入**：

> "帮我分析竞品的内容策略，写一份报告"

**系统执行**：

1. 使用plan工具分解任务
2. Web搜索收集竞品信息
3. URL抓取深度分析
4. 代码执行数据可视化
5. 生成Markdown报告

## 🔧 核心能力

### 1. 工具系统

- **Atomic Tools（原子工具）**：可独立执行的单一功能工具，如web_search、file_reader等
- **Workflow Tools（工作流工具）**：组合多个原子工具完成复杂任务的高级工具

### 2. 智能规划

Master Agent具备任务分解和步骤规划能力：

- 理解复杂任务需求
- 自动分解为可执行步骤
- 选择合适的工具组合
- 处理执行结果和异常

### 3. 工作空间管理

- 基于对话ID的文件隔离
- 自动文件版本管理
- 支持文件读取、编辑、列表查询
- 生成文件自动归档

## 🔑 技术栈

- **Web框架**：FastAPI + Uvicorn
- **LLM集成**：OpenAI SDK（兼容多种模型）
- **数据处理**：Pandas + openpyxl
- **图像处理**：Pillow + Playwright
- **媒体处理**：MoviePy + imageio + FFmpeg
- **语音合成**：Google Cloud TTS / Azure Speech / pyttsx3 / MiniMax
- **多媒体生成**：MiniMax API（图像/视频/音乐）
- **认证**：passlib + itsdangerous
- **日志**：loguru

## 📦 依赖说明

核心依赖：

- `fastapi` - Web API框架
- `openai` - LLM客户端
- `pandas` + `openpyxl` - 数据处理和Excel操作
- `Pillow` - 图像处理
- `requests` - HTTP请求

可选依赖：

- `playwright` - HTML转图片（需额外安装浏览器）
- `moviepy` - 视频处理
- `google-cloud-texttospeech` - Google TTS
- `azure-cognitiveservices-speech` - Azure TTS

## 🎯 项目定位

Wenning致力于成为：

1. **内容创作者的效率工具**：自动化内容分析、创作、发布流程
2. **产品运营的决策助手**：数据分析、竞品监控、用户洞察
3. **创意工作流的编排平台**：灵活组合各类AI能力，定制专属工作流

## 📄 许可证

MIT License

---

**开发者**：@feixiaoxu2022
**项目地址**：https://github.com/feixiaoxu2022/Wenning
