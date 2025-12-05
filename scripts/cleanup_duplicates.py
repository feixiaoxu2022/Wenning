"""
清理conversations.json中的重复消息
"""
import json
import shutil
from pathlib import Path
from datetime import datetime


def cleanup_duplicate_messages(conversations_file: Path):
    """清理对话历史中的重复消息

    Args:
        conversations_file: conversations.json文件路径
    """
    # 创建备份
    backup_file = conversations_file.parent / f"conversations_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy(conversations_file, backup_file)
    print(f"✅ 已创建备份: {backup_file.name}")

    # 读取对话数据
    with open(conversations_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_removed = 0

    # 遍历每个对话
    for conv_id, conv_data in data.items():
        messages = conv_data.get('messages', [])
        if not messages:
            continue

        # 去重逻辑:连续的重复消息(role和content完全相同)
        cleaned_messages = []
        prev_msg = None

        for msg in messages:
            # 如果当前消息与上一条消息完全相同(role和content都相同),跳过
            if prev_msg and prev_msg['role'] == msg['role'] and prev_msg['content'] == msg['content']:
                total_removed += 1
                print(f"  [对话 {conv_id}] 跳过重复消息 (role={msg['role']}, length={len(msg['content'])})")
                continue

            cleaned_messages.append(msg)
            prev_msg = msg

        # 更新消息列表
        conv_data['messages'] = cleaned_messages

        removed_count = len(messages) - len(cleaned_messages)
        if removed_count > 0:
            print(f"✅ 对话 {conv_id}: 移除了 {removed_count} 条重复消息 ({len(messages)} → {len(cleaned_messages)})")

    # 写回文件
    with open(conversations_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 清理完成! 总共移除 {total_removed} 条重复消息")
    print(f"📁 备份文件: {backup_file}")
    print(f"📁 已更新文件: {conversations_file}")


if __name__ == '__main__':
    conversations_file = Path(__file__).parent.parent / 'data' / 'conversations.json'

    if not conversations_file.exists():
        print(f"❌ 文件不存在: {conversations_file}")
        exit(1)

    print(f"开始清理重复消息: {conversations_file}\n")
    cleanup_duplicate_messages(conversations_file)
