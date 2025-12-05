# CreativeFlow - 创意工作流Agent系统

CreativeFlow是一个面向内容创作者和产品运营人员的AI Agent系统，通过双层架构（Master Agent + Workflow Tools + Atomic Tools）实现复杂创意任务的自动化处理。

## 核心特性

- 🎯 **双场景支持**：UGC分析（运营场景）+ 封面生成（创作场景）
- 🔧 **工具分层架构**：Workflow Tools（高频场景） + Atomic Tools（原子能力）
- 🤖 **多模型支持**：用户可选择多种LLM模型（默认Ernie-5.0-Thinking-Preview）
- 💻 **代码生成能力**：LLM生成Python代码自动执行（数据分析、图像处理）
- 🌐 **Web搜索集成**：Tavily/Serper双引擎
- 📄 **URL内容抓取**：Jina Reader/Firecrawl双引擎

## 项目结构

```
creative_agent/
├── .env                    # API配置（不提交git）
├── .env.example            # 配置模板
├── .gitignore
├── README.md
├── requirements.txt
│
├── docs/                   # 设计文档
│   ├── 00_架构设计总览.md
│   ├── 技术方案设计.md
│   └── ...
│
├── src/
│   ├── agent/              # Master Agent
│   │   ├── master_agent.py     # 核心Agent类
│   │   ├── state_machine.py    # 自研状态机
│   │   └── intent_router.py    # 意图识别
│   │
│   ├── tools/              # 工具层
│   │   ├── base.py             # 基类定义
│   │   ├── atomic/             # 原子工具
│   │   │   ├── web_search.py
│   │   │   ├── url_fetch.py
│   │   │   └── code_executor.py
│   │   └── workflow/           # 工作流工具
│   │       ├── ugc_analysis.py
│   │       └── cover_generation.py
│   │
│   ├── llm/                # LLM客户端
│   │   ├── client.py           # 统一LLM接口
│   │   └── prompts.py          # Prompt模板
│   │
│   ├── ui/                 # 用户界面
│   │   └── gradio_app.py       # Web UI
│   │
│   └── utils/              # 工具函数
│       ├── config.py           # 配置加载
│       └── logger.py           # 日志
│
├── tests/                  # 测试
├── scripts/                # 脚本
└── outputs/                # 输出文件
```

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装Playwright浏览器（用于HTML转图片功能）
playwright install chromium
```

**注意**：
- Playwright需要额外下载浏览器二进制文件（约300MB），首次安装需要一些时间
- 如果不需要HTML转图片功能，可以跳过`playwright install`步骤

### 2. 配置API密钥

复制 `.env.example` 为 `.env`，填入你的API密钥：

```bash
cp .env.example .env
# 编辑 .env 文件，填入API密钥
```

### 3. 启动Web UI

```bash
python -m src.ui.gradio_app
```

访问 `http://localhost:7860` 开始使用。

## MVP场景

### 场景1: UGC分析工作流

**用户输入**：
> "帮我分析一下小红书上关于'新疆旅游'的最新评论，生成一份分析报告"

**系统执行**：
1. 数据采集 - Web搜索小红书相关内容
2. 情感分析 - LLM直接处理评论情感
3. 内容筛选 - 筛选高价值评论
4. 回复生成 - 生成回复建议
5. 报告生成 - 生成Excel分析报告

**交付物**：Excel文件（包含原始评论、情感分析、回复建议）

### 场景2: 封面生成工作流

**用户输入**：
> "帮我生成一张'Python入门教程'的封面图，蓝色科技风"

**系统执行**：
1. 风格理解 - 解析用户期望风格
2. 文字图生成 - LLM生成PIL代码创建文字图
3. 代码执行 - 安全沙箱执行代码

**交付物**：PNG封面图片

## 技术架构

### 双层Agent架构

```
Master Agent (意图识别 + 调度)
    ↓
┌────────────┬────────────┐
↓            ↓            ↓
Workflow    Atomic       LLM直接处理
Tools       Tools        (无tool_call)
```

### 关键技术决策

- ✅ 自研轻量级状态机（非LangGraph）
- ✅ 用户可选择LLM模型（默认EB5）
- ✅ subprocess代码沙箱（MVP阶段）
- ✅ 无数据库（Gradio会话 + 本地文件）

## 开发状态

- [x] 调研阶段：Web Search/URL Fetch服务选型
- [x] 设计阶段：技术方案、架构设计
- [ ] Week 1: 基础设施（Config + LLMClient + Logger）
- [ ] Week 2: Atomic Tools（Web搜索 + URL抓取 + 代码执行）
- [ ] Week 3: Workflow Tools（UGC分析 + 封面生成）
- [ ] Week 4: Master Agent + Gradio UI

## 参考文档

- [00_架构设计总览](docs/00_架构设计总览.md) - 系统架构和能力矩阵
- [技术方案设计](docs/技术方案设计.md) - 完整技术实现方案
- [MCP协议集成方案分析](docs/MCP协议集成方案分析.md) - 为什么不用MCP
- [API测试报告](docs/API测试报告.md) - 外部API验证结果

## 许可证

MIT License
