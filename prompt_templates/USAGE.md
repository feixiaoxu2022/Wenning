# Prompt模板库使用指南

## 🎯 设计理念

**简洁优于复杂**：使用enum参数明确列出所有可用模板，Agent直接选择，无需模糊检索。

## 📋 快速开始

### 1. 查看可用模板

在tool的enum参数中可以看到所有可用模板：

```json
{
  "template_type": {
    "enum": ["tech_demo_video"],
    "description": "tech_demo_video: 技术演示视频制作指南(知识教学、产品演示、技术讲解、带旁白的视频)"
  }
}
```

### 2. AI Agent自动调用

当用户需求匹配某个模板时，Agent会自动调用：

```
用户: "帮我制作一个讲解Context Engineering的视频，需要有旁白"

Agent: [看到enum中有tech_demo_video适合这个需求]
{
  "name": "retrieve_prompt_template",
  "arguments": {
    "template_type": "tech_demo_video"
  }
}

返回: 完整的32KB专业prompt模板
```

### 3. 测试工具

```bash
python test_prompt_tool.py
```

## 📁 文件结构

```
prompt_templates/
├── templates.json              # 模板索引（简单的key-value映射）
├── video_production/
│   └── tech_demo_video.md     # 技术演示视频制作指南（32KB）
└── README.md                   # 本文档
```

## ✨ 当前可用模板

| Enum Key | 模板名称 | 适用场景 | 大小 |
|----------|----------|----------|------|
| `tech_demo_video` | 技术演示视频制作指南 | 知识教学视频、产品演示、技术讲解、带旁白的视频 | 32KB |

## 🔧 添加新模板

### Step 1: 创建模板markdown文件

```bash
# 选择合适的分类目录
mkdir -p prompt_templates/data_analysis
vim prompt_templates/data_analysis/data_report.md
```

### Step 2: 更新templates.json

```json
{
  "templates": {
    "tech_demo_video": { ... },
    "data_report": {
      "title": "数据分析报告生成指南",
      "description": "...",
      "file_path": "data_analysis/data_report.md",
      "category": "data_analysis"
    }
  }
}
```

### Step 3: 更新tool的enum参数

编辑 `src/tools/atomic/prompt_template_tool.py`:

```python
parameters_schema = {
    "properties": {
        "template_type": {
            "enum": ["tech_demo_video", "data_report"],  # 添加新模板
            "description": "tech_demo_video: ...； data_report: ..."
        }
    }
}
```

### Step 4: 更新tool的description

```python
description = (
    "..."
    "当前可用模板：tech_demo_video(...), data_report(...)。"
    "..."
)
```

### Step 5: 重启服务

```bash
# 需要重启以加载新的enum定义
python fastapi_app.py
```

## 🎯 模板编写规范

好的prompt模板应包含：

1. **明确的角色定义** - 定义AI的专业身份
2. **详细的规范说明** - 技术标准、设计规范
3. **执行Checklist** - 步骤化的操作指南
4. **质量标准** - 明确的验收标准
5. **常见问题解决** - 已知问题和解决方案
6. **代码示例** - 具体的实现参考

参考 `tech_demo_video.md` 的结构。

## 📊 工具返回格式

```json
{
  "status": "success",
  "template": {
    "type": "tech_demo_video",
    "title": "技术演示视频制作指南",
    "description": "...",
    "category": "video_production",
    "content": "# 完整的32KB模板内容..."
  }
}
```

## ⚠️ 重要约束

1. **不做模糊检索** - Agent必须从enum中精确选择
2. **显式列举** - 所有可用模板都在enum中明确列出
3. **简单映射** - 模板索引采用简单的key-value结构
4. **无自动推断** - 如果enum中没有合适的模板，Agent不应调用此tool

## 🔍 调试

```bash
# 查看模板索引
cat prompt_templates/templates.json

# 测试工具
python test_prompt_tool.py

# 查看日志
# 启动服务时会输出: PromptTemplateRetriever 初始化完成, 可用模板: ['tech_demo_video']
```

## 📝 变更日志

### 2024-12-12 v1.0
- ✅ 简化设计：使用enum参数替代模糊检索
- ✅ 添加第一个模板：tech_demo_video
- ✅ 完成工具集成和测试

---

**简洁、明确、可控**
