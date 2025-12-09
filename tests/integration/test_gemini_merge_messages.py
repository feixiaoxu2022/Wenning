#!/usr/bin/env python
"""测试Gemini消息合并（连续相同role）"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import Config
from src.llm.client import LLMClient

def test_consecutive_user_messages():
    """测试连续user消息合并"""
    print("=" * 60)
    print("测试：连续user消息合并")
    print("=" * 60)

    config = Config()
    client = LLMClient(config, model_name="gemini-3-pro-preview")

    # 模拟连续的user消息
    messages = [
        {"role": "system", "content": "你是一个AI助手"},
        {"role": "user", "content": "第一条用户消息"},
        {"role": "user", "content": "第二条用户消息"},
        {"role": "user", "content": "第三条用户消息，请回答：2+2等于多少？"}
    ]

    print("\n--- 原始消息序列 ---")
    for i, msg in enumerate(messages):
        print(f"{i+1}. {msg['role']}: {msg['content'][:50]}...")

    print("\n--- 发送请求 ---")

    try:
        stream = client.chat(
            messages=messages,
            temperature=0.3,
            stream=True
        )

        print("\n--- Gemini响应 ---")
        for chunk in stream:
            if chunk.get("type") == "content":
                print(chunk.get("delta", ""), end="", flush=True)
            elif chunk.get("type") == "done":
                print("\n\n✅ 测试成功! 连续user消息合并正常工作")
                response = chunk.get("response", {})
                print(f"模型: {response.get('model')}")
                return

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_consecutive_tool_messages():
    """测试连续tool消息合并（模拟多个tool响应）"""
    print("\n" + "=" * 60)
    print("测试：连续tool消息合并")
    print("=" * 60)

    config = Config()
    client = LLMClient(config, model_name="gemini-3-pro-preview")

    # 模拟一个完整的tool call流程，但tool响应是连续的
    messages = [
        {"role": "user", "content": "搜索Python和JavaScript的区别"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query": "Python vs JavaScript"}'
                    }
                }
            ],
            "_gemini_original_parts": [
                {
                    "functionCall": {
                        "name": "web_search",
                        "args": {"query": "Python vs JavaScript"}
                    },
                    "thoughtSignature": "fake_signature_123"
                }
            ]
        },
        {"role": "tool", "tool_call_id": "call_1", "name": "web_search", "content": "搜索结果1：Python是解释型语言"},
        {"role": "tool", "tool_call_id": "call_1", "name": "web_search", "content": "搜索结果2：JavaScript是浏览器语言"}
    ]

    print("\n--- 原始消息序列 ---")
    for i, msg in enumerate(messages):
        role = msg['role']
        if role == "tool":
            print(f"{i+1}. {role}: {msg.get('name')} - {msg.get('content')[:50]}...")
        else:
            print(f"{i+1}. {role}: {msg.get('content', '(tool call)')[:50]}...")

    print("\n--- 发送请求 ---")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "搜索互联网",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
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
            temperature=0.3,
            stream=True
        )

        print("\n--- Gemini响应 ---")
        for chunk in stream:
            if chunk.get("type") == "content":
                print(chunk.get("delta", ""), end="", flush=True)
            elif chunk.get("type") == "done":
                print("\n\n✅ 测试成功! 连续tool消息合并正常工作")
                response = chunk.get("response", {})
                print(f"模型: {response.get('model')}")
                return

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_consecutive_user_messages()
    test_consecutive_tool_messages()

    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)
