#!/usr/bin/env python3
"""测试Claude Function Calling参数传递问题"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.llm.client import LLMClient
from src.utils.config import Config

def test_tool_call_parsing():
    """测试tool call解析"""
    print("=" * 60)
    print("测试Claude Function Calling")
    print("=" * 60)

    config = Config()
    llm = LLMClient(config, model_name="claude-sonnet-4-5-20250929")

    # 模拟tool schema
    tools = [{
        "type": "function",
        "function": {
            "name": "code_executor",
            "description": "在安全沙箱中执行Python代码",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的Python代码（必须）"
                    }
                },
                "required": ["code"]
            }
        }
    }]

    # 简单的测试消息
    messages = [
        {"role": "system", "content": "你是一个助手，可以执行Python代码。"},
        {"role": "user", "content": "生成一个简单的视频，显示文字'Hello World'"}
    ]

    print("\n发送请求...")
    print(f"Model: {llm.model_name}")
    print(f"Tools: {len(tools)} 个")

    try:
        response = llm.chat(messages, tools=tools, stream=False, temperature=0.7)

        print("\n✅ 收到响应")
        print(f"Content: {response.get('content')[:100] if response.get('content') else '(无文本内容)'}...")

        if "tool_calls" in response:
            print(f"\n工具调用: {len(response['tool_calls'])} 个")
            for i, tc in enumerate(response['tool_calls']):
                print(f"\n--- Tool Call #{i+1} ---")
                print(f"ID: {tc.get('id')}")
                print(f"Name: {tc.get('function', {}).get('name')}")
                args_str = tc.get('function', {}).get('arguments')
                print(f"Arguments (type={type(args_str).__name__}): {args_str!r}")

                # 尝试解析
                try:
                    if isinstance(args_str, str):
                        args = json.loads(args_str) if args_str.strip() else {}
                    elif isinstance(args_str, dict):
                        args = args_str
                    else:
                        args = {}

                    print(f"解析后: {json.dumps(args, ensure_ascii=False, indent=2)}")

                    if "code" in args:
                        print(f"✅ code参数存在 ({len(args['code'])} 字符)")
                    else:
                        print(f"❌ code参数缺失！")
                        print(f"   可用键: {list(args.keys())}")

                except Exception as e:
                    print(f"❌ 解析失败: {e}")
        else:
            print("\n❌ 响应中没有tool_calls")

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == '__main__':
    print("\n🔍 Claude Function Calling 参数传递测试\n")
    success = test_tool_call_parsing()
    print("\n" + "=" * 60)
    print(f"测试{'成功' if success else '失败'}")
    print("=" * 60)
    sys.exit(0 if success else 1)
