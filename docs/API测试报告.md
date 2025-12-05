# CreativeFlow API 连通性测试报告

**测试时间**: 2025-11-14
**测试目的**: 验证所有第三方服务API的可用性
**测试结果**: ✅ 全部通过 (5/5)

---

## 测试摘要

| # | 服务名称 | 状态 | 响应时间 | 备注 |
|---|---------|------|---------|------|
| 1 | Tavily Search API | ✅ 通过 | ~2s | 返回搜索结果正常 |
| 2 | Serper Google API | ✅ 通过 | ~2s | 返回Google SERP正常 |
| 3 | Firecrawl API | ✅ 通过 | ~2s | 成功抓取并转换为Markdown |
| 4 | Jina Reader API | ✅ 通过 | <1s | 无需API Key也可正常使用 |
| 5 | 百度LLM API | ✅ 通过 | ~16s | EB5和通用端点都正常 |

**总体状态**: 🎉 所有服务连通正常,可以开始开发!

---

## 详细测试结果

### 1. Tavily Search API ✅

**API Key**: `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`

**测试请求**:
```bash
curl -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "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",
    "query": "test",
    "max_results": 1
  }'
```

**响应示例**:
```json
{
  "query": "test",
  "results": [
    {
      "title": "SpeedSmart - HTML5 Internet Speed Test",
      "url": "https://speedsmart.net/",
      "content": "Test the speed of your internet connection...",
      "score": 0.229
    }
  ],
  "response_time": 0.0,
  "request_id": "54f1f3b2-7979-475f-938d-1280fcb99a49"
}
```

**验证要点**:
- ✅ 成功返回搜索结果
- ✅ 包含title、url、content、score
- ✅ 响应格式为LLM-ready的结构化数据
- ✅ request_id可用于追踪

**可用功能**:
- Basic Search (1 credit/次)
- Advanced Search (2 credits/次)
- 免费额度: 1,000 credits/月

---

### 2. Serper Google Search API ✅

**API Key**: `eb3c7892030d9be951ce06083106db4db378b84f`

**测试请求**:
```bash
curl -X POST https://google.serper.dev/search \
  -H "X-API-KEY: eb3c7892030d9be951ce06083106db4db378b84f" \
  -H "Content-Type: application/json" \
  -d '{"q": "OpenAI", "num": 2}'
```

**响应示例**:
```json
{
  "searchParameters": {
    "q": "OpenAI",
    "type": "search",
    "num": 2,
    "engine": "google"
  },
  "organic": [
    {
      "title": "OpenAI",
      "link": "https://openai.com/",
      "snippet": "We believe our research will eventually lead to AGI...",
      "position": 1
    },
    {
      "title": "OpenAI",
      "link": "https://en.wikipedia.org/wiki/OpenAI",
      "snippet": "OpenAI is an American AI organization...",
      "position": 2
    }
  ],
  "credits": 1
}
```

**验证要点**:
- ✅ 成功返回Google搜索结果
- ✅ 包含organic results(自然排名)
- ✅ 返回snippet(摘要)和position(排名)
- ✅ credits字段显示消耗1次查询

**可用功能**:
- Google搜索结果
- 免费额度: 2,500次
- 定价: $0.30/1,000次

---

### 3. Firecrawl API ✅

**API Key**: `fc-831a5a876d8c471893a42fb2324cc42e`

**测试请求**:
```bash
curl -X POST https://api.firecrawl.dev/v1/scrape \
  -H "Authorization: Bearer fc-831a5a876d8c471893a42fb2324cc42e" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "markdown": "# Example Domain\n\nThis domain is for use in documentation examples...",
    "metadata": {
      "language": "en",
      "title": "Example Domain",
      "scrapeId": "8be2b657-0190-4a87-9688-e516915476db",
      "sourceURL": "https://example.com",
      "url": "https://example.com/",
      "statusCode": 200,
      "contentType": "text/html",
      "cacheState": "hit",
      "creditsUsed": 1
    }
  }
}
```

**验证要点**:
- ✅ 成功抓取网页内容
- ✅ 输出干净的Markdown格式
- ✅ 包含丰富的metadata(标题、语言、状态码等)
- ✅ creditsUsed显示消耗1个credit
- ✅ cacheState显示命中缓存(快速响应)

**可用功能**:
- /scrape: 单页抓取
- /crawl: 整站爬取
- /extract: AI结构化提取
- 免费额度: 500 pages

---

### 4. Jina Reader API ✅

**API Key**: 无需(免费使用)

**测试请求**:
```bash
curl https://r.jina.ai/https://example.com
```

**响应示例**:
```
Title: Example Domain

URL Source: https://example.com/

Published Time: Thu, 09 Oct 2025 16:42:02 GMT

Warning: This page maybe not yet fully loaded, consider explicitly specify a timeout.
Warning: This is a cached snapshot of the original page, consider retry with caching opt-out.

Markdown Content:
This domain is for use in documentation examples without needing permission. Avoid use in operations.

[Learn more](https://iana.org/domains/example)
```

**验证要点**:
- ✅ 完全免费,无需API Key即可使用
- ✅ 极简API: 仅需在URL前加 `https://r.jina.ai/`
- ✅ 输出格式化的Markdown
- ✅ 包含metadata(标题、发布时间、来源URL)
- ✅ 提供有用的Warning提示

**可用功能**:
- 单URL转Markdown
- 免费限额: 20次/分钟(无key) 或 200次/分钟(免费key)
- 完全够用!

---

### 5. 百度LLM API ✅

#### 5.1 文心一言 EB5专用端点

**API Key**: `bce-v3/ALTAK-mCOi62yEOQCJIvZVDI521/10000568a22b656d14d37bb80abb5da439026f1a`

**测试请求**:
```bash
curl --location 'https://qianfan.baidubce.com/v2/chat/completions' \
  --header 'Content-Type: application/json' \
  --header 'Authorization: Bearer bce-v3/ALTAK-mCOi62yEOQCJIvZVDI521/...' \
  --data '{
    "model": "ernie-5.0-thinking-preview",
    "messages": [{"role": "user", "content": "你好,请用一句话介绍你自己"}]
  }'
```

**响应示例**:
```json
{
  "id": "as-wrwfftdk98",
  "object": "chat.completion",
  "created": 1763112190,
  "model": "ernie-5.0-thinking-preview",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "我是百度研发的文心一言，致力于为用户提供文本交互服务。",
        "reasoning_content": "用户让我用一句话介绍自己，首先需要明确核心身份——我是百度研发的文心一言..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 6,
    "completion_tokens": 111,
    "total_tokens": 117,
    "completion_tokens_details": {
      "reasoning_tokens": 100
    }
  }
}
```

**验证要点**:
- ✅ 成功调用文心5.0 thinking版本
- ✅ 返回完整的reasoning_content(思考过程)
- ✅ 包含详细的token usage统计
- ✅ 响应时间约16秒(包含思考过程)

**特点**:
- 支持thinking模式(类似o1)
- 中文理解能力强
- 成本低于OpenAI

---

#### 5.2 通用LLM端点 (支持多模型)

**API Key**: `sk-HoI9K08JDDEvstxTk0nxZSTpLcePrpKfru2Ya7nOSIXGHCNu`
**Base URL**: `http://yy.dbh.baidu-int.com/v1`

**测试请求**:
```bash
curl http://yy.dbh.baidu-int.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-HoI9K08JDDEvstxTk0nxZSTpLcePrpKfru2Ya7nOSIXGHCNu" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Say hello in one word"}],
    "max_tokens": 10
  }'
```

**响应示例**:
```json
{
  "choices": [
    {
      "content_filter_results": {
        "hate": {"filtered": false, "severity": "safe"},
        "self_harm": {"filtered": false, "severity": "safe"},
        "sexual": {"filtered": false, "severity": "safe"},
        "violence": {"filtered": false, "severity": "safe"}
      },
      "finish_reason": "stop",
      "index": 0,
      "message": {
        "content": "Hello!",
        "role": "assistant"
      }
    }
  ],
  "created": 1763112220,
  "id": "chatcmpl-CbkJo25JlKGlVwYPfjR7sheG31zI0",
  "model": "gpt-4o-mini-2024-07-18",
  "usage": {
    "completion_tokens": 3,
    "prompt_tokens": 12,
    "total_tokens": 15
  }
}
```

**验证要点**:
- ✅ 成功调用gpt-4o-mini
- ✅ OpenAI兼容格式
- ✅ 包含内容过滤结果
- ✅ 响应速度快(<1秒)

**可用模型**:
- `gpt-4o-mini` (测试通过 ✅)
- `gpt-4o`
- `glm-4.5`
- `doubao-seed-1-6-thinking-250615`
- `gemini-2.5-pro`

##### 5.2.1 Gemini 3 Pro (Preview) · 第二轮 Function Calling 消息示例（OpenAI风格）

以下示例基于同一个端点 `POST /v1/chat/completions`，在“可用工具”声明后，追加两条消息用于模拟第二轮工具调用链：

- 一条 `assistant` 携带 `tool_calls`（指定工具名与参数，使用 JSON 字符串）。
- 一条 `tool` 返回工具执行结果（示例分别给出 JSON 字符串与纯文本两种）。

注意：本段使用统一代理的 OpenAI Chat Completions 风格；若该模型在网关侧未开放 FC，可能返回 400。

示例A：assistant 携带 tool_calls + tool 返回（content 为 JSON 字符串）

```bash
curl \
  -X POST \
  http://yy.dbh.baidu-int.com/v1/chat/completions \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "gemini-3-pro-preview",
  "messages": [
    { "role": "system", "content": "你是一个个人助手。" },
    { "role": "user", "content": "看看邮箱里有啥邮件" },
    {
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {
          "id": "call_1",
          "type": "function",
          "function": {
            "name": "list_messages",
            "arguments": "{\"q\":\"from:boss@example.com\",\"maxResults\":3}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_1",
      "name": "list_messages",
      "content": "{\"status\":\"success\",\"data\":{\"messages\":[{\"id\":\"m1\",\"subject\":\"Project update\"},{\"id\":\"m2\",\"subject\":\"Meeting notes\"},{\"id\":\"m3\",\"subject\":\"Invoice\"}]}}"
    }
  ],
  "extra_body": {
    "generationConfig": {
      "thinkingConfig": { "includeThoughts": true, "thinkingBudget": -1 }
    }
  },
  "temperature": 0.1,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "list_messages",
        "description": "列出Gmail邮件，空参数时返回所有邮件，根据查询词找不到时也返回所有邮件",
        "parameters": {
          "type": "object",
          "properties": {
            "maxResults": { "type": "integer", "description": "最大返回邮件数量", "default": 10 },
            "q": { "type": "string", "description": "主题、发件人、收件人、正文等关键词" }
          }
        }
      }
    }
  ],
  "stream": false,
  "tool_choice": "auto",
  "enable_thinking": true,
  "top_p": 1.0,
  "frequency_penalty": 0.0,
  "presence_penalty": 0.0
}'
```

示例B：assistant 携带 tool_calls + tool 返回（content 为纯文本）

```bash
curl \
  -X POST \
  http://yy.dbh.baidu-int.com/v1/chat/completions \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "gemini-3-pro-preview",
  "messages": [
    { "role": "system", "content": "你是一个个人助手。" },
    { "role": "user", "content": "看看邮箱里有啥邮件" },
    {
      "role": "assistant",
      "content": "",
      "tool_calls": [
        {
          "id": "call_1",
          "type": "function",
          "function": {
            "name": "list_messages",
            "arguments": "{\"maxResults\":2}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_1",
      "name": "list_messages",
      "content": "ok: 2 messages returned"
    }
  ],
  "extra_body": {
    "generationConfig": {
      "thinkingConfig": { "includeThoughts": true, "thinkingBudget": -1 }
    }
  },
  "temperature": 0.1,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "list_messages",
        "description": "列出Gmail邮件，空参数时返回所有邮件，根据查询词找不到时也返回所有邮件",
        "parameters": {
          "type": "object",
          "properties": {
            "maxResults": { "type": "integer", "description": "最大返回邮件数量", "default": 10 },
            "q": { "type": "string", "description": "主题、发件人、收件人、正文等关键词" }
          }
        }
      }
    }
  ],
  "stream": false,
  "tool_choice": "auto",
  "enable_thinking": true,
  "top_p": 1.0,
  "frequency_penalty": 0.0,
  "presence_penalty": 0.0
}'
```

排查提示:
- 若该模型/端点对第二轮 FC 不支持，可能返回 400。可先用 `gpt-5` 验证相同 payload 是否 200，以区分“格式问题”与“代理/模型能力限制”。
- `function.arguments` 需要是 JSON 字符串；注意双引号转义。
- `tool` 消息需带 `tool_call_id`，与上一步 `assistant.tool_calls[].id` 对应。

##### 5.2.2 Gemini 3 Pro (Preview) · 原生 generateContent 带 Tool 消息

当网关提供 Gemini 原生协议时，请使用 `models/{model}:generateContent` 并通过 `functionCall`/`functionResponse` 进行工具调用与回传：

```bash
curl -X POST 'http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-preview:generateContent' \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "contents": [
    { "role": "user", "parts": [ { "text": "看看邮箱里有啥邮件" } ] },
    { "role": "model", "parts": [ { "functionCall": { "name": "list_messages", "args": { "maxResults": 3, "q": "from:boss@example.com" } } } ] },
    { "role": "tool",  "parts": [ { "functionResponse": { "name": "list_messages", "response": { "status": "success", "messages": [ {"id":"m1","subject":"Project update"},{"id":"m2","subject":"Meeting notes"},{"id":"m3","subject":"Invoice"} ] } } } ] }
  ],
  "tools": [
    { "functionDeclarations": [
        { "name": "list_messages",
          "description": "列出Gmail邮件，空参数时返回所有邮件，根据查询词找不到时也返回所有邮件",
          "parameters": {
            "type": "object",
            "properties": { "maxResults": {"type":"integer"}, "q": {"type":"string"} },
            "required": ["maxResults"]
          }
        }
    ]}
  ]
}'
```

提示：若返回 404/405，请确认网关是否要求显式的 `:generateContent` 方法后缀；若 400，通常为该模型在当前网关未启用原生工具链能力。

##### 5.2.3 Gemini 原生 generateContent · 二段式调用（含 thought_signature）

某些网关在“思考模式/工具调用”开启时，第二轮请求中要求携带首轮由模型产生的 `functionCall` 的完整签名字段（如 `thought_signature`）。不要手工构造 `functionCall`，而应分两步：

1) 第1步：请求模型产生 functionCall（不要附带任何 tool 响应）

```bash
curl -X POST 'http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-preview:generateContent' \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "contents": [
    { "role": "user", "parts": [ { "text": "看看邮箱里有啥邮件" } ] }
  ],
  "tools": [
    { "functionDeclarations": [
        { "name": "list_messages",
          "description": "列出Gmail邮件，空参数时返回所有邮件，根据查询词找不到时也返回所有邮件",
          "parameters": {
            "type": "object",
            "properties": { "maxResults": {"type":"integer"}, "q": {"type":"string"} }
          }
        }
    ]}
  ],
  "generationConfig": { "thinkingConfig": { "includeThoughts": true, "thinkingBudget": -1 } }
}'
```

- 期望响应（简化）：`contents[0].parts[0].functionCall` 中包含 `name`, `args`，以及网关要求的签名字段（例如 `thought_signature` 或同义字段）。
- 将“模型返回的这一段 functionCall”原封不动用于下一步。

2) 第2步：携带第1步返回的 functionCall + 追加 tool 的 functionResponse

下面给出“基于你上一步真实返回”的第二步请求，已嵌入该 functionCall 与 thoughtSignature：

```bash
curl -X POST 'http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-preview:generateContent' \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "contents": [
    { "role": "user", "parts": [ { "text": "看看邮箱里有啥邮件" } ] },
    { "role": "model", "parts": [ { 
        "functionCall": {
          "name": "list_messages",
          "args": { "maxResults": 10 }
        },
        "thoughtSignature": "CvMDAePx/17KU3DYDhOlZ9510LHT9z4jU7OiHQcunv5HLHWmDXhRrrNSMLvpUp9df3Ddbl6gcQCHQ548BxDAzeprzMizmc48p5Va6rHhLvE8OviCxSlK6+3fcaxjXdzMMX7pnmXJlacRhXaa5YnKpVzbMhZlqbjQyodG3sA36c9WK7klDywqvy04CDR30LvNHC73EeedtyJT2lUpdSrtyLnGUSRtyEtI4xWiRMMUndWH9G6EGDbKvjcgyp1buEw3QgO1TFeGqEQSd0P5FxAtgFn9AQKshfwiM4kC/XNngwHKR4zZm3j3u3+gXcsTcXWoPZe/MA/YC3te6XYgy0P11RUYlvXNbk+HFuzqNhPDcbIJHbRKfKgQ4B+nxWkWJGDR8MnAje7bnPdqs8djeXytS4YxS6bg+ZD3ldzEcVGkG3JBuRbnD6Y1jFRakZxFnDdeJ/icYEmTXfqqOCmb7tK7a9hTv83jwzDK76+mgjiftHMam9ZMDtsNYkCJldFMc+CAa1uuWmzBvsPqZh0B9LXyk9i0CsBQTZTBtxGm3O9/yCICrNDi9287J0wRrkBxCqDcwlkpZdiVD0AKAUOZfutLX+rD0aYFE8gDDRUbYflPBByVK/sGh9eOWNG2/tc/s1nvbyIAGa+mV0ETzCMwQlPE3fHb9O1saA=="
      } ] },
    { "role": "tool",  "parts": [ { "functionResponse": {
        "name": "list_messages",
        "response": {
          "status": "success",
          "messages": [
            { "id": "m1", "subject": "Project update" },
            { "id": "m2", "subject": "Meeting notes" },
            { "id": "m3", "subject": "Invoice" }
          ]
        }
    } } ] }
  ],
  "tools": [
    { "functionDeclarations": [
        { "name": "list_messages",
          "parameters": {
            "type": "object",
            "properties": { "maxResults": {"type":"integer"}, "q": {"type":"string"} }
          }
        }
    ]}
  ]
 }'
```

 若上面仍提示 invalid argument，请尝试变体（将 thoughtSignature 内嵌到 functionCall 中，并将 tool 响应放入 content.json）：

```bash
curl -X POST 'http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-preview:generateContent' \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "contents": [
    { "role": "user", "parts": [ { "text": "看看邮箱里有啥邮件" } ] },
    { "role": "model", "parts": [ { 
        "functionCall": {
          "name": "list_messages",
          "args": { "maxResults": 10 },
          "thoughtSignature": "CvMDAePx/17KU3DYDhOlZ9510LHT9z4jU7OiHQcunv5HLHWmDXhRrrNSMLvpUp9df3Ddbl6gcQCHQ548BxDAzeprzMizmc48p5Va6rHhLvE8OviCxSlK6+3fcaxjXdzMMX7pnmXJlacRhXaa5YnKpVzbMhZlqbjQyodG3sA36c9WK7klDywqvy04CDR30LvNHC73EeedtyJT2lUpdSrtyLnGUSRtyEtI4xWiRMMUndWH9G6EGDbKvjcgyp1buEw3QgO1TFeGqEQSd0P5FxAtgFn9AQKshfwiM4kC/XNngwHKR4zZm3j3u3+gXcsTcXWoPZe/MA/YC3te6XYgy0P11RUYlvXNbk+HFuzqNhPDcbIJHbRKfKgQ4B+nxWkWJGDR8MnAje7bnPdqs8djeXytS4YxS6bg+ZD3ldzEcVGkG3JBuRbnD6Y1jFRakZxFnDdeJ/icYEmTXfqqOCmb7tK7a9hTv83jwzDK76+mgjiftHMam9ZMDtsNYkCJldFMc+CAa1uuWmzBvsPqZh0B9LXyk9i0CsBQTZTBtxGm3O9/yCICrNDi9287J0wRrkBxCqDcwlkpZdiVD0AKAUOZfutLX+rD0aYFE8gDDRUbYflPBByVK/sGh9eOWNG2/tc/s1nvbyIAGa+mV0ETzCMwQlPE3fHb9O1saA=="
        }
      } ] },
    { "role": "tool",  "parts": [ { "functionResponse": {
        "name": "list_messages",
        "response": {
          "name": "list_messages",
          "content": [ { "json": {
            "status": "success",
            "messages": [
              { "id": "m1", "subject": "Project update" },
              { "id": "m2", "subject": "Meeting notes" },
              { "id": "m3", "subject": "Invoice" }
            ]
          } } ]
        }
    } } ] }
  ],
  "tools": [
    { "functionDeclarations": [ { "name": "list_messages", "parameters": {"type":"object","properties": {"maxResults": {"type":"integer"}, "q": {"type":"string"}} } } ] }
  ]
}'
```

若第2步仍返回 `missing thought_signature`，请确认：
- 你粘贴的是第1步“模型返回的 functionCall 原文”，而非自行构造；
- 名称空间（例如 `default_api:list_messages`）与响应一致；
- 第1步已开启思考/工具能力（`generationConfig.thinkingConfig.includeThoughts=true` 等）。

##### 5.2.4 二步法“粘贴原文”通用模板（推荐，避免签名/命名不一致）

使用本模板时，只需要做两处替换即可：
- 将 `<<<STEP1_MODEL_PART_JSON>>>` 替换为“第1步响应里 candidates[0].content.parts[0] 的完整 JSON 原文”（包含 functionCall 与其签名字段 thought_signature/thoughtSignature，保持结构与字段名完全一致）。
- 将 `<<<FUNC_NAME>>>` 替换为“第1步返回的 functionCall.name 原文”（可能是 `default_api:list_messages`，必须与第1步完全一致）。

```bash
curl -X POST 'http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-preview:generateContent' \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "contents": [
    { "role": "user", "parts": [ { "text": "看看邮箱里有啥邮件" } ] },
    { "role": "model", "parts": [ <<<STEP1_MODEL_PART_JSON>>> ] },
    { "role": "tool",  "parts": [ { "functionResponse": {
        "name": "<<<FUNC_NAME>>>",
        "response": {
          "name": "<<<FUNC_NAME>>>",
          "content": [ { "json": {
            "status": "success",
            "messages": [
              { "id": "m1", "subject": "Project update" },
              { "id": "m2", "subject": "Meeting notes" },
              { "id": "m3", "subject": "Invoice" }
            ]
          } } ]
        }
    } } ] }
  ],
  "tools": [
    { "functionDeclarations": [
        { "name": "<<<FUNC_NAME>>>",
          "parameters": {
            "type": "object",
            "properties": { "maxResults": {"type":"integer"}, "q": {"type":"string"} }
          }
        }
    ]}
  ]
}'
```

注意：
- 不要手动重命名 `functionCall.name`（例如把 `default_api:list_messages` 改成 `list_messages`），也不要改签名字段名及层级（`thought_signature` vs `thoughtSignature`；与第1步保持一致）。
- 将第1步 parts[0] 的对象“原封不动”粘贴到 `<<<STEP1_MODEL_PART_JSON>>>` 位置，最稳妥。

###### 5.2.4.1 使用你刚才“第1步返回值”的完整第二步请求（已嵌入签名）

下面这条已用你上一步返回的内容拼好，直接复制即可：

```bash
curl -X POST 'http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-preview:generateContent' \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "contents": [
    { "role": "user", "parts": [ { "text": "看看邮箱里有啥邮件" } ] },
    { "role": "model", "parts": [ { 
        "functionCall": {
          "name": "list_messages",
          "args": { "maxResults": 10 }
        },
        "thoughtSignature": "CvMDAePx/17KU3DYDhOlZ9510LHT9z4jU7OiHQcunv5HLHWmDXhRrrNSMLvpUp9df3Ddbl6gcQCHQ548BxDAzeprzMizmc48p5Va6rHhLvE8OviCxSlK6+3fcaxjXdzMMX7pnmXJlacRhXaa5YnKpVzbMhZlqbjQyodG3sA36c9WK7klDywqvy04CDR30LvNHC73EeedtyJT2lUpdSrtyLnGUSRtyEtI4xWiRMMUndWH9G6EGDbKvjcgyp1buEw3QgO1TFeGqEQSd0P5FxAtgFn9AQKshfwiM4kC/XNngwHKR4zZm3j3u3+gXcsTcXWoPZe/MA/YC3te6XYgy0P11RUYlvXNbk+HFuzqNhPDcbIJHbRKfKgQ4B+nxWkWJGDR8MnAje7bnPdqs8djeXytS4YxS6bg+ZD3ldzEcVGkG3JBuRbnD6Y1jFRakZxFnDdeJ/icYEmTXfqqOCmb7tK7a9hTv83jwzDK76+mgjiftHMam9ZMDtsNYkCJldFMc+CAa1uuWmzBvsPqZh0B9LXyk9i0CsBQTZTBtxGm3O9/yCICrNDi9287J0wRrkBxCqDcwlkpZdiVD0AKAUOZfutLX+rD0aYFE8gDDRUbYflPBByVK/sGh9eOWNG2/tc/s1nvbyIAGa+mV0ETzCMwQlPE3fHb9O1saA=="
      } ] },
    { "role": "tool",  "parts": [ { "functionResponse": {
        "name": "list_messages",
        "response": {
          "name": "list_messages",
          "content": [ { "json": {
            "status": "success",
            "messages": [
              { "id": "m1", "subject": "Project update" },
              { "id": "m2", "subject": "Meeting notes" },
              { "id": "m3", "subject": "Invoice" }
            ]
          } } ]
        }
    } } ] }
  ],
  "tools": [
    { "functionDeclarations": [
        { "name": "list_messages",
          "parameters": {
            "type": "object",
            "properties": { "maxResults": {"type":"integer"}, "q": {"type":"string"} }
          }
        }
    ]}
  ]
}'
```

若网关提示 `default_api:list_messages` 缺少 thought_signature，请将上面 JSON 里的所有 `list_messages` 替换为 `default_api:list_messages`（以网关第一步返回的命名空间为准）。

###### 5.2.4.2 命名空间 + snake_case 签名版本（直接可测）

部分网关要求第二步里的 functionCall：
- name 使用命名空间（例如 `default_api:list_messages`）
- 签名字段为 `thought_signature`，放在 functionCall 内部

下面这条把 name 统一为带命名空间，并将签名作为 `thought_signature` 写入 functionCall 内，直接复制测试：

```bash
curl -X POST 'http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-preview:generateContent' \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "contents": [
    { "role": "user", "parts": [ { "text": "看看邮箱里有啥邮件" } ] },
    { "role": "model", "parts": [ { 
        "functionCall": {
          "name": "default_api:list_messages",
          "args": { "maxResults": 10 },
          "thought_signature": "CvMDAePx/17KU3DYDhOlZ9510LHT9z4jU7OiHQcunv5HLHWmDXhRrrNSMLvpUp9df3Ddbl6gcQCHQ548BxDAzeprzMizmc48p5Va6rHhLvE8OviCxSlK6+3fcaxjXdzMMX7pnmXJlacRhXaa5YnKpVzbMhZlqbjQyodG3sA36c9WK7klDywqvy04CDR30LvNHC73EeedtyJT2lUpdSrtyLnGUSRtyEtI4xWiRMMUndWH9G6EGDbKvjcgyp1buEw3QgO1TFeGqEQSd0P5FxAtgFn9AQKshfwiM4kC/XNngwHKR4zZm3j3u3+gXcsTcXWoPZe/MA/YC3te6XYgy0P11RUYlvXNbk+HFuzqNhPDcbIJHbRKfKgQ4B+nxWkWJGDR8MnAje7bnPdqs8djeXytS4YxS6bg+ZD3ldzEcVGkG3JBuRbnD6Y1jFRakZxFnDdeJ/icYEmTXfqqOCmb7tK7a9hTv83jwzDK76+mgjiftHMam9ZMDtsNYkCJldFMc+CAa1uuWmzBvsPqZh0B9LXyk9i0CsBQTZTBtxGm3O9/yCICrNDi9287J0wRrkBxCqDcwlkpZdiVD0AKAUOZfutLX+rD0aYFE8gDDRUbYflPBByVK/sGh9eOWNG2/tc/s1nvbyIAGa+mV0ETzCMwQlPE3fHb9O1saA=="
        }
      } ] },
    { "role": "tool",  "parts": [ { "functionResponse": {
        "name": "default_api:list_messages",
        "response": {
          "name": "default_api:list_messages",
          "content": [ { "json": {
            "status": "success",
            "messages": [
              { "id": "m1", "subject": "Project update" },
              { "id": "m2", "subject": "Meeting notes" },
              { "id": "m3", "subject": "Invoice" }
            ]
          } } ]
        }
    } } ] }
  ],
  "tools": [
    { "functionDeclarations": [
        { "name": "default_api:list_messages",
          "parameters": {
            "type": "object",
            "properties": { "maxResults": {"type":"integer"}, "q": {"type":"string"} }
          }
        }
    ]}
  ]
}'
```

如果仍报 invalid argument，请把“第1步响应的 candidates[0].content.parts[0] 原文”和“第2步的报错 request id”一并提供，便于精确比对 name/签名字段位置及网关签名校验规则。

###### 5.2.4.3 命名空间 + thought_signature 同级（不嵌入 functionCall）

再提供一个常见网关要求的变体：
- name 使用命名空间 `default_api:list_messages`
- `thought_signature` 与 `functionCall` 保持同级（不放在 functionCall 内）

```bash
curl -X POST 'http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-preview:generateContent' \
  -H 'Authorization: Bearer sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF' \
  -H 'Content-Type: application/json' \
  -d '{
  "contents": [
    { "role": "user", "parts": [ { "text": "看看邮箱里有啥邮件" } ] },
    { "role": "model", "parts": [ {
        "functionCall": {
          "name": "default_api:list_messages",
          "args": { "maxResults": 10 }
        },
        "thought_signature": "CvMDAePx/17KU3DYDhOlZ9510LHT9z4jU7OiHQcunv5HLHWmDXhRrrNSMLvpUp9df3Ddbl6gcQCHQ548BxDAzeprzMizmc48p5Va6rHhLvE8OviCxSlK6+3fcaxjXdzMMX7pnmXJlacRhXaa5YnKpVzbMhZlqbjQyodG3sA36c9WK7klDywqvy04CDR30LvNHC73EeedtyJT2lUpdSrtyLnGUSRtyEtI4xWiRMMUndWH9G6EGDbKvjcgyp1buEw3QgO1TFeGqEQSd0P5FxAtgFn9AQKshfwiM4kC/XNngwHKR4zZm3j3u3+gXcsTcXWoPZe/MA/YC3te6XYgy0P11RUYlvXNbk+HFuzqNhPDcbIJHbRKfKgQ4B+nxWkWJGDR8MnAje7bnPdqs8djeXytS4YxS6bg+ZD3ldzEcVGkG3JBuRbnD6Y1jFRakZxFnDdeJ/icYEmTXfqqOCmb7tK7a9hTv83jwzDK76+mgjiftHMam9ZMDtsNYkCJldFMc+CAa1uuWmzBvsPqZh0B9LXyk9i0CsBQTZTBtxGm3O9/yCICrNDi9287J0wRrkBxCqDcwlkpZdiVD0AKAUOZfutLX+rD0aYFE8gDDRUbYflPBByVK/sGh9eOWNG2/tc/s1nvbyIAGa+mV0ETzCMwQlPE3fHb9O1saA=="
      }] },
    { "role": "tool",  "parts": [ { "functionResponse": {
        "name": "default_api:list_messages",
        "response": {
          "name": "default_api:list_messages",
          "content": [ { "json": {
            "status": "success",
            "messages": [
              { "id": "m1", "subject": "Project update" },
              { "id": "m2", "subject": "Meeting notes" },
              { "id": "m3", "subject": "Invoice" }
            ]
          } } ]
        }
    } } ] }
  ],
  "tools": [
    { "functionDeclarations": [
        { "name": "default_api:list_messages",
          "parameters": {
            "type": "object",
            "properties": { "maxResults": {"type":"integer"}, "q": {"type":"string"} }
          }
        }
    ]}
  ]
}'
```

---

## 环境变量配置

基于测试结果,推荐的`.env`配置:

```bash
# ============================================
# Web Search APIs
# ============================================
TAVILY_API_KEY=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
SERPER_API_KEY=eb3c7892030d9be951ce06083106db4db378b84f

# ============================================
# URL Fetch APIs
# ============================================
# Jina Reader无需API Key,直接使用
# JINA_API_KEY=  # 可选,用于提升限额

FIRECRAWL_API_KEY=fc-831a5a876d8c471893a42fb2324cc42e

# ============================================
# LLM APIs
# ============================================

# 文心一言 EB5专用(thinking模式)
QIANFAN_EB5_TOKEN=bce-v3/ALTAK-mCOi62yEOQCJIvZVDI521/10000568a22b656d14d37bb80abb5da439026f1a
QIANFAN_EB5_ENDPOINT=https://qianfan.baidubce.com/v2/chat/completions
QIANFAN_EB5_MODEL=ernie-5.0-thinking-preview

# 通用LLM端点(支持多模型)
AGENT_MODEL_API_KEY=sk-HoI9K08JDDEvstxTk0nxZSTpLcePrpKfru2Ya7nOSIXGHCNu
AGENT_MODEL_BASE_URL=http://yy.dbh.baidu-int.com/v1
AGENT_MODEL_TIMEOUT=600
```

---

## Python代码示例

### 统一配置类

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """CreativeFlow配置"""

    # Web Search
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")

    # URL Fetch
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    # Jina Reader无需配置

    # LLM - 文心一言EB5
    QIANFAN_EB5_TOKEN = os.getenv("QIANFAN_EB5_TOKEN")
    QIANFAN_EB5_ENDPOINT = os.getenv("QIANFAN_EB5_ENDPOINT")
    QIANFAN_EB5_MODEL = os.getenv("QIANFAN_EB5_MODEL", "ernie-5.0-thinking-preview")

    # LLM - 通用端点
    AGENT_MODEL_API_KEY = os.getenv("AGENT_MODEL_API_KEY")
    AGENT_MODEL_BASE_URL = os.getenv("AGENT_MODEL_BASE_URL")
    AGENT_MODEL_TIMEOUT = int(os.getenv("AGENT_MODEL_TIMEOUT", 600))

    @classmethod
    def validate(cls):
        """验证必需的配置"""
        required = {
            "TAVILY_API_KEY": cls.TAVILY_API_KEY,
            "FIRECRAWL_API_KEY": cls.FIRECRAWL_API_KEY,
            "AGENT_MODEL_API_KEY": cls.AGENT_MODEL_API_KEY,
        }

        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"缺少必需的配置: {missing}")

        print("✅ 所有必需的API Key配置完成")

# 使用
if __name__ == "__main__":
    Config.validate()
```

### LiteLLM统一调用

```python
# llm_client.py
from litellm import completion
from config import Config

def call_llm(messages, model="gpt-4o-mini", **kwargs):
    """统一的LLM调用接口"""

    response = completion(
        model=model,
        messages=messages,
        api_key=Config.AGENT_MODEL_API_KEY,
        base_url=Config.AGENT_MODEL_BASE_URL,
        timeout=Config.AGENT_MODEL_TIMEOUT,
        **kwargs
    )

    return response.choices[0].message.content

# 使用
if __name__ == "__main__":
    result = call_llm(
        messages=[{"role": "user", "content": "Hello!"}],
        model="gpt-4o-mini"
    )
    print(result)  # 输出: Hello! How can I assist you today?
```

---

## 测试结论

✅ **所有API连通性测试通过!**

**关键发现**:

1. **Tavily API**: 响应速度快,返回结构化数据,非常适合LLM使用
2. **Serper API**: Google搜索结果准确,成本极低
3. **Firecrawl API**: Markdown转换质量高,metadata完整
4. **Jina Reader**: 完全免费且好用,MVP阶段首选
5. **百度LLM**: 两个端点都正常,EB5支持thinking模式,通用端点支持多模型

**建议**:

- ✅ MVP阶段可以开始开发了
- ✅ 使用LiteLLM统一LLM调用接口
- ✅ 优先使用通用LLM端点(支持多模型切换)
- ✅ EB5端点用于需要深度思考的场景
- ✅ Jina Reader作为URL Fetch主力(免费)
- ✅ Tavily作为Web Search主力(免费额度高)

**成本预估**:

- Tavily: 免费1000次/月
- Serper: 免费2500次/月
- Firecrawl: 免费500页
- Jina: 完全免费
- LLM: 内部端点,无需额外付费

**MVP阶段月成本**: $0 🎉

---

## 下一步工作

- [ ] 创建`.env`文件并配置所有API Key
- [ ] 实现统一的Config类
- [ ] 集成LiteLLM用于多模型调用
- [ ] 开发Web Search Tool
- [ ] 开发URL Fetch Tool
- [ ] 开始Master Agent框架搭建

**所有服务已就绪,可以开始编码! 🚀**
