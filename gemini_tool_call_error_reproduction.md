# Gemini Tool Call 错误复现文档

## 问题概述

**模型**: gemini-3-pro-preview
**服务端**: http://yy.dbh.baidu-int.com/v1/chat/completions
**问题**: 模型返回的tool call参数格式不符合schema，导致后续请求返回500错误

---

## 第一轮请求（成功，但返回了畸形的tool call）

```bash
curl -X POST \
  http://yy.dbh.baidu-int.com/v1/chat/completions \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "gemini-3-pro-preview",
  "messages": [
    {
      "role": "system",
      "content": "你是一个AI助手，帮助用户完成创意任务。"
    },
    {
      "role": "user",
      "content": "帮我搜索Anthropic官网的engineer板块内容"
    }
  ],
  "temperature": 0.3,
  "max_tokens": 16384,
  "stream": false,
  "tool_choice": "auto",
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "web_search",
        "description": "搜索互联网获取实时信息和最新内容。适用于需要网络资料、新闻、博客文章、用户评论等场景。",
        "parameters": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "搜索关键词或查询语句"
            },
            "max_results": {
              "type": "integer",
              "description": "返回的最大结果数量,默认5",
              "default": 5
            }
          },
          "required": ["query"]
        }
      }
    }
  ]
}'
```

### 第一轮响应（问题所在）

模型返回了**畸形的arguments字符串**：

```json
{
  "id": "chatcmpl-xxx",
  "model": "gemini-3-pro-preview",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_55ef7b4a40c844b198050f3ad37c4982",
            "type": "function",
            "function": {
              "name": "web_search",
              "arguments": "{\"steps\":[{\"action\":\"搜索Anthropic官网，确认\\\"engineer\\\"板块的具体位置（可能是工程博客、开发者文档或招聘页面），并获取相关URL。\",\"status\":\"pending\",\"step\":1},{\"action\":\"抓取确认的页面内容，提取关键文章或文档链接。\",\"status\":\"pending\",\"step\":2},{\"action\":\"深入抓取核心文章或文档的具体内容。\",\"status\":\"pending\",\"step\":3},{\"action\":\"整理、分析抓取到的信息，汇总成一份结构化的Markdown文档。\",\"status\":\"pending\",\"step\":4}],\"task_description\":\"查找、理解并汇总Anthropic官网Engineer板块（或工程相关内容）的关键信息。\"}{\"query\":\"Anthropic website engineer section\"}{\"query\":\"Anthropic engineering blog\"}{\"query\":\"Anthropic prompt engineering guide\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

**问题分析**：
1. **期望的arguments格式**（符合schema）:
   ```json
   {"query": "Anthropic engineer", "max_results": 5}
   ```

2. **实际返回的arguments**（多个JSON对象拼接）:
   ```
   {"steps":[...],"task_description":"..."}{"query":"..."}{"query":"..."}{"query":"..."}
   ```

3. **违规点**：
   - ❌ 包含未定义的参数：`steps`, `task_description`
   - ❌ 缺少必填参数：`query`
   - ❌ JSON格式错误：多个对象拼接，不是有效JSON
   - ❌ 模型进行了multi-step planning，而非简单传递搜索关键词

---

## 第二轮请求（失败，服务端返回500）

客户端尝试执行工具 → JSON解析失败 → 构造tool message → 发送第二轮请求

```bash
curl -X POST \
  http://yy.dbh.baidu-int.com/v1/chat/completions \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "gemini-3-pro-preview",
  "messages": [
    {
      "role": "system",
      "content": "你是一个AI助手，帮助用户完成创意任务。"
    },
    {
      "role": "user",
      "content": "帮我搜索Anthropic官网的engineer板块内容"
    },
    {
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {
          "id": "call_55ef7b4a40c844b198050f3ad37c4982",
          "type": "function",
          "function": {
            "name": "web_search",
            "arguments": "{\"steps\":[{\"action\":\"搜索Anthropic官网，确认\\\"engineer\\\"板块的具体位置（可能是工程博客、开发者文档或招聘页面），并获取相关URL。\",\"status\":\"pending\",\"step\":1},{\"action\":\"抓取确认的页面内容，提取关键文章或文档链接。\",\"status\":\"pending\",\"step\":2},{\"action\":\"深入抓取核心文章或文档的具体内容。\",\"status\":\"pending\",\"step\":3},{\"action\":\"整理、分析抓取到的信息，汇总成一份结构化的Markdown文档。\",\"status\":\"pending\",\"step\":4}],\"task_description\":\"查找、理解并汇总Anthropic官网Engineer板块（或工程相关内容）的关键信息。\"}{\"query\":\"Anthropic website engineer section\"}{\"query\":\"Anthropic engineering blog\"}{\"query\":\"Anthropic prompt engineering guide\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_55ef7b4a40c844b198050f3ad37c4982",
      "name": "web_search",
      "content": "工具执行失败: Extra data: line 1 column 382 (char 381)"
    }
  ],
  "temperature": 0.3,
  "max_tokens": 16384,
  "stream": true,
  "tool_choice": "auto",
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "web_search",
        "description": "搜索互联网获取实时信息和最新内容。适用于需要网络资料、新闻、博客文章、用户评论等场景。",
        "parameters": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "搜索关键词或查询语句"
            },
            "max_results": {
              "type": "integer",
              "description": "返回的最大结果数量,默认5",
              "default": 5
            }
          },
          "required": ["query"]
        }
      }
    }
  ]
}'
```

### 第二轮响应（500错误）

```json
{
  "error": {
    "message": "invalid arguments for function web_search, args: {\"steps\":[{\"action\":\"搜索Anthropic官网，确认\\\"engineer\\\"板块的具体位置（可能是工程博客、开发者文档或招聘页面），并获取相关URL。\",\"status\":\"pending\",\"step\":1}...省略...]",
    "type": "invalid_request_error",
    "code": 500
  }
}
```

---

## 对比：正常工作的案例

同样使用Gemini模型，以下请求**正常工作**：

```bash
curl -X POST \
  http://yy.dbh.baidu-int.com/v1/chat/completions \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "gemini-3-pro-preview",
  "messages": [
    {
      "role": "system",
      "content": "你是一个个人助手。"
    },
    {
      "role": "user",
      "content": "看看邮箱里有啥邮件"
    }
  ],
  "temperature": 0.1,
  "stream": false,
  "tool_choice": "auto",
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "list_messages",
        "description": "列出Gmail邮件，空参数时返回所有邮件，根据查询词找不到时也返回所有邮件",
        "parameters": {
          "type": "object",
          "properties": {
            "maxResults": {
              "type": "integer",
              "description": "最大返回邮件数量",
              "default": 10
            },
            "q": {
              "type": "string",
              "description": "主题、发件人、收件人、正文等关键词"
            }
          }
        }
      }
    }
  ]
}'
```

**成功响应**：
```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "tool_calls": [
          {
            "function": {
              "name": "list_messages",
              "arguments": "{}"
            }
          }
        ]
      }
    }
  ]
}
```

**工作原因对比**：
- ✅ 工具描述简单直接："列出Gmail邮件"
- ✅ 参数全部可选，无required字段
- ✅ 任务语义明确，不易引发multi-step planning

---

## 问题根因分析

### 🔴 关键发现：服务端是格式转换网关

**重要**：`yy.dbh.baidu-int.com` 不是Gemini原生API，而是一个**格式转换网关**。

#### Gemini原生API格式
根据 [Google官方文档](https://ai.google.dev/api/generate-content)：

```json
{
  "contents": [
    {
      "role": "user",
      "parts": [{"text": "The weather in Chicago"}]
    }
  ],
  "tools": [
    {"googleSearch": {}}  // ← Gemini原生工具格式
  ]
}
```

#### 网关转换流程

```
客户端请求（OpenAI格式）
    ↓
[网关层：OpenAI → Gemini转换]
    ↓
Gemini原生格式请求
    ↓
Google Gemini API
    ↓
Gemini原生响应
    ↓
[网关层：Gemini → OpenAI转换] ← 问题可能在这里！
    ↓
OpenAI格式响应（含畸形tool call）
    ↓
返回给客户端
```

### 1. 可能的问题层级

#### Level 1: Gemini原生响应异常
- Gemini模型本身返回了multi-step planning的结构
- 原生格式可能包含Gemini特有的`functionCall`结构
- 参考：https://ai.google.dev/gemini-api/docs/function-calling

#### Level 2: 网关转换逻辑有bug（最可能）
- **Schema转换丢失信息**：OpenAI的`parameters.required`可能没正确转换到Gemini格式
- **响应转换错误**：Gemini原生响应 → OpenAI格式时，tool call参数拼接出错
- **验证时机错误**：网关在转换后验证，发现不符合原始schema → 返回500

示例问题场景：
```python
# Gemini可能返回多个function call
gemini_response = {
  "functionCalls": [
    {"name": "web_search", "args": {"steps": [...]}},
    {"name": "web_search", "args": {"query": "..."}},
    {"name": "web_search", "args": {"query": "..."}}
  ]
}

# 网关转换时错误地拼接了arguments
openai_format = {
  "tool_calls": [{
    "function": {
      "name": "web_search",
      "arguments": '{"steps":[...]}{"query":"..."}{"query":"..."}'  # ← 拼接错误
    }
  }]
}
```

#### Level 3: Schema不兼容
- OpenAI的`additionalProperties`等约束可能在Gemini中无法表达
- `required`字段的语义可能不同
- Gemini对function calling的理解与OpenAI有差异

### 2. 服务端验证机制
- 网关在转换**之后**进行了参数验证
- 发现转换后的tool call参数不符合原始OpenAI schema → 返回500
- 这个验证发生在**流式响应过程中**，导致连接中断

### 3. 触发条件
- 工具描述包含"搜索互联网"、"实时信息"等可能引发planning的关键词
- 必填参数（`required: ["query"]`）在Gemini中可能被理解为"需要复杂参数结构"
- 用户输入涉及"查找"、"汇总"等多步骤语义
- **对比成功案例**：`list_messages`工具没有required字段，且描述简单，不触发planning

---

## 期望的服务端行为

### 选项1：放宽验证（推荐）
- 允许tool call参数不符合schema
- 将验证责任交给客户端
- 客户端可以根据实际情况处理（重试、fallback等）

### 选项2：优化错误信息
如果必须保留验证，至少返回更友好的错误：
```json
{
  "error": {
    "message": "Tool call validation failed for 'web_search': Expected parameters: {query: string, max_results?: number}, but received: {steps: array, task_description: string, ...}. Please ensure the model's tool call strictly follows the schema definition.",
    "type": "tool_call_validation_error",
    "code": 400,
    "details": {
      "tool_name": "web_search",
      "expected_params": ["query", "max_results"],
      "received_params": ["steps", "task_description"],
      "missing_required": ["query"]
    }
  }
}
```

### 选项3：针对Gemini的特殊处理
- 检测到Gemini模型时，自动对tool call参数进行清洗
- 或者在schema中加入更强的约束提示
- 或者对特定工具禁用multi-step planning

---

## 临时解决方案（客户端）

1. **优化工具描述**：参考`list_messages`的成功案例，使用更简单直接的描述
2. **去除必填约束**：将`required: ["query"]`改为全部可选，由客户端补充默认值
3. **添加schema约束**：`"additionalProperties": false` 明确禁止额外参数
4. **模型切换**：对该工具使用GPT-4等更"听话"的模型

---

## 附录：完整日志片段

```
2025-12-09 11:55:55 | INFO | src.agent.master_agent:_react_loop_with_progress:688 -
原始tool_call: {"id": "call_55ef7b4a40c844b198050f3ad37c4982", "type": "function", "function": {"name": "web_search", "arguments": "{\"steps\":[...]..."}}

2025-12-09 11:55:55 | INFO | src.agent.master_agent:_react_loop_with_progress:693 -
arguments字符串: '{"steps":[...]...}{"query":"..."}{"query":"..."}{"query":"..."}' (类型: str)

2025-12-09 11:55:55 | ERROR | src.agent.master_agent:_react_loop_with_progress:819 -
工具执行异常: web_search, error=Extra data: line 1 column 382 (char 381)

2025-12-09 11:55:55 | ERROR | src.llm.client:_chat_stream:629 -
LLM流式请求失败: status=500, detail={"error":{"message":"invalid arguments for function web_search, args: {\"steps\":[...]..."}}
```

---

**联系信息**：
如需更多信息或复现细节，请联系 [你的联系方式]
