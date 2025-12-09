#!/usr/bin/env python3
"""
测试Agent执行并生成文件

正确消费生成器,确保Agent真正执行任务
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import get_config
from src.agent.master_agent import MasterAgent
from src.tools.registry import ToolRegistry
from src.tools.atomic.web_search import WebSearchTool
from src.tools.atomic.url_fetch import URLFetchTool
from src.tools.atomic.code_executor import CodeExecutor

def test_agent():
    print("=" * 60)
    print("测试Agent执行")
    print("=" * 60)

    # 初始化Agent
    config = get_config()
    registry = ToolRegistry()
    registry.register_atomic_tool(WebSearchTool(config))
    registry.register_atomic_tool(URLFetchTool(config))
    registry.register_atomic_tool(CodeExecutor(config))

    agent = MasterAgent(config, registry, 'gpt-5')
    print(f"✓ Agent初始化完成,工具数: {len(registry.list_tools())}")

    # 测试简单任务
    query = "帮我搜索一下Python入门教程"
    print(f"\n📝 Query: {query}")
    print("\n开始执行...")

    result = agent.process(query)
    print(f"\n返回结果类型: {type(result['result'])}")

    # 检查是否是生成器
    if hasattr(result['result'], '__iter__') and hasattr(result['result'], '__next__'):
        print("⚠️  检测到生成器,需要消费它")

        # 消费生成器
        final_output = None
        for item in result['result']:
            print(f"  生成器输出: {type(item)}")
            if isinstance(item, str):
                final_output = item

        print(f"\n✓ 最终输出: {final_output[:200] if final_output else 'None'}...")
    else:
        print(f"✓ 最终结果: {result['result'][:200] if result['result'] else 'None'}...")

    # 检查conversation_history
    print(f"\n对话历史长度: {len(agent.conversation_history)}")
    if agent.conversation_history:
        print("✓ 有对话历史")
    else:
        print("❌ 对话历史为空!")

if __name__ == "__main__":
    test_agent()
