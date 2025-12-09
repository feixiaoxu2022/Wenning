#!/usr/bin/env python
"""测试Gemini多轮对话（验证thoughtSignature保留）"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import Config
from src.llm.client import LLMClient

def test_multiround_with_tool_call():
    """测试多轮对话（包含tool call）"""
    print("=" * 60)
    print("测试：Gemini多轮对话 + Tool Call")
    print("=" * 60)

    config = Config()
    client = LLMClient(config, model_name="gemini-3-pro-preview")

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

    # 第一轮：用户请求
    messages = [
        {"role": "user", "content": "搜索一下Python教程"}
    ]

    print("\n--- 第一轮请求 ---")
    print(f"Messages: {messages}")

    try:
        stream = client.chat(
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.3,
            stream=True
        )

        response = None
        for chunk in stream:
            if chunk.get("type") == "content":
                print(chunk.get("delta", ""), end="", flush=True)
            elif chunk.get("type") == "done":
                response = chunk.get("response", {})

        if not response:
            print("\n❌ 第一轮失败: 没有获得响应")
            return

        print("\n\n✅ 第一轮成功")
        tool_calls = response.get("tool_calls", [])
        print(f"Tool calls: {len(tool_calls)}")

        if not tool_calls:
            print("⚠️ 没有tool call，无法测试多轮")
            return

        # 检查是否保存了_gemini_original_parts
        if "_gemini_original_parts" in response:
            print(f"✅ 保存了 _gemini_original_parts: {len(response['_gemini_original_parts'])} parts")
            # 打印第一个part的keys（包含thoughtSignature）
            if response['_gemini_original_parts']:
                part_keys = list(response['_gemini_original_parts'][0].keys())
                print(f"   Part keys: {part_keys}")
        else:
            print("❌ 未保存 _gemini_original_parts")
            return

        # 构造第二轮消息（模拟tool执行结果）
        assistant_message = {
            "role": "assistant",
            "content": response.get("content") or "",
            "tool_calls": tool_calls
        }
        # 传递_gemini_original_parts
        if "_gemini_original_parts" in response:
            assistant_message["_gemini_original_parts"] = response["_gemini_original_parts"]

        messages.append(assistant_message)

        # 添加tool响应
        for tc in tool_calls:
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": tc["function"]["name"],
                "content": "搜索结果：找到5个Python教程链接..."
            })

        # 第二轮：发送tool结果
        print("\n--- 第二轮请求 ---")
        print(f"Messages数量: {len(messages)}")

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
                print("\n\n✅ 第二轮成功! thoughtSignature保留方案有效!")
                response2 = chunk.get("response", {})
                print(f"模型: {response2.get('model')}")
                return

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_multiround_with_tool_call()

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
