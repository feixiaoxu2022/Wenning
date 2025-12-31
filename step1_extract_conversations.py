#!/usr/bin/env python3
"""
步骤1: 提取所有对话的基本信息
输出一个JSON文件，包含每个对话的关键信息，供LLM进行语义分析
"""

import json
from pathlib import Path

DATA_DIR = Path("data/conversations")
OUTPUT_FILE = Path("all_conversations_summary.json")

def extract_first_user_query(messages):
    """提取第一条用户消息"""
    for msg in messages:
        if msg.get("role") == "user":
            return msg.get("content", "").strip()
    return ""

def count_agent_turns(messages):
    """统计agent执行轮次"""
    return sum(1 for msg in messages if msg.get("role") == "assistant")

def main():
    print("正在读取所有对话...")

    conversations = []
    json_files = list(DATA_DIR.rglob("*.json"))
    print(f"找到 {len(json_files)} 个对话文件")

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            messages = data.get("messages", [])
            query = extract_first_user_query(messages)

            if not query or len(query) < 5:
                continue

            # 提取附件信息
            has_attachment = "本次输入包含附件" in query

            conv_info = {
                "conversation_id": data.get("id", ""),
                "title": data.get("title", "")[:100],
                "user": data.get("user", ""),
                "model": data.get("model", ""),
                "created_at": data.get("created_at", ""),
                "first_query": query,
                "query_length": len(query),
                "agent_turns": count_agent_turns(messages),
                "total_messages": len(messages),
                "has_attachment": has_attachment,
                "file_path": str(json_file)
            }

            conversations.append(conv_info)

        except Exception as e:
            print(f"警告: 无法读取 {json_file}: {e}")

    # 按创建时间排序
    conversations.sort(key=lambda x: x["created_at"])

    # 保存
    output = {
        "total_conversations": len(conversations),
        "conversations": conversations
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 提取完成！")
    print(f"  有效对话数: {len(conversations)}")
    print(f"  输出文件: {OUTPUT_FILE}")
    print(f"\n统计信息:")
    print(f"  平均query长度: {sum(c['query_length'] for c in conversations) / len(conversations):.0f} 字符")
    print(f"  平均agent执行轮次: {sum(c['agent_turns'] for c in conversations) / len(conversations):.1f} 轮")
    print(f"  包含附件的对话: {sum(1 for c in conversations if c['has_attachment'])} 个")

if __name__ == "__main__":
    main()
