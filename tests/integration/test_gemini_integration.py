#!/usr/bin/env python
"""测试Gemini原生API集成"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import Config
from src.llm.client import LLMClient

def test_gemini_basic():
    """测试基础对话"""
    print("=" * 60)
    print("测试1: Gemini基础对话")
    print("=" * 60)

    config = Config()
    client = LLMClient(config, model_name="gemini-3-pro-preview")

    messages = [
        {"role": "user", "content": "Hello, what is 2+2?"}
    ]

    try:
        stream = client.chat(
            messages=messages,
            temperature=0.7,
            stream=True
        )

        print("\n响应:")
        for chunk in stream:
            if chunk.get("type") == "content":
                print(chunk.get("delta", ""), end="", flush=True)
            elif chunk.get("type") == "done":
                print("\n\n✅ 测试通过!")
                response = chunk.get("response", {})
                print(f"模型: {response.get('model')}")
                print(f"Token使用: {response.get('usage')}")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_gemini_with_tools():
    """测试Function Calling"""
    print("\n" + "=" * 60)
    print("测试2: Gemini Function Calling")
    print("=" * 60)

    config = Config()
    client = LLMClient(config, model_name="gemini-3-pro-preview")

    messages = [
        {"role": "user", "content": "帮我搜索Anthropic官网的engineer板块内容"}
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "搜索互联网。只需要提供搜索关键词query参数。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    try:
        stream = client.chat(
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.3,
            stream=True
        )

        print("\n响应:")
        for chunk in stream:
            if chunk.get("type") == "content":
                print(chunk.get("delta", ""), end="", flush=True)
            elif chunk.get("type") == "done":
                response = chunk.get("response", {})
                tool_calls = response.get("tool_calls")

                if tool_calls:
                    print("\n\n✅ Tool Call 成功!")
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        print(f"  工具: {fn.get('name')}")
                        print(f"  参数: {fn.get('arguments')}")
                else:
                    print("\n\n⚠️ 没有tool call")

                print(f"\n模型: {response.get('model')}")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gemini_basic()
    test_gemini_with_tools()

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
