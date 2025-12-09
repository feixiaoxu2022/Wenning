#!/bin/bash

# Gemini原生API测试脚本
# 绕过OpenAI格式网关，直接使用Gemini原生格式

# 配置
API_KEY="sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF"
BASE_URL="http://yy.dbh.baidu-int.com"

echo "=== 测试Gemini原生API格式 ==="
echo ""

# 测试1：基础对话（无工具）
echo "📝 测试1：基础对话"
curl -X POST \
  "${BASE_URL}/v1/models/gemini-3-pro-preview" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "Hello, what is 2+2?"
          }
        ]
      }
    ]
  }' | jq .

echo ""
echo "---"
echo ""

# 测试2：Function Calling（Gemini原生格式）
echo "📝 测试2：Function Calling - Gemini原生格式"
curl -X POST \
  "${BASE_URL}/v1/models/gemini-3-pro-preview" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "帮我搜索Anthropic官网的engineer板块内容"
          }
        ]
      }
    ],
    "tools": [
      {
        "functionDeclarations": [
          {
            "name": "web_search",
            "description": "搜索互联网。只需要提供搜索关键词query参数，不要添加其他参数。",
            "parameters": {
              "type": "OBJECT",
              "properties": {
                "query": {
                  "type": "STRING",
                  "description": "搜索关键词"
                }
              },
              "required": ["query"]
            }
          }
        ]
      }
    ]
  }' | jq .

echo ""
echo "---"
echo ""

# 测试3：Google Search工具（Gemini内置）
echo "📝 测试3：使用Gemini内置的Google Search"
curl -X POST \
  "${BASE_URL}/v1/models/gemini-3-pro-preview" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "The weather in Chicago this weekend"
          }
        ]
      }
    ],
    "tools": [
      {
        "googleSearch": {}
      }
    ]
  }' | jq .

echo ""
echo "=== 测试完成 ==="
