#!/usr/bin/env python3
"""
去重历史对话中的相邻重复消息脚本

规则:
- 仅删除“相邻且完全相同”的重复消息(相同 role、content、generated_files)
- 对 generated_files 进行无序比较
- 自动生成备份文件 data/conversations_backup_YYYYmmdd_HHMMSS.json

使用:
  python scripts/dedupe_conversations.py
"""

import json
from pathlib import Path
from datetime import datetime


DATA_PATH = Path("data/conversations.json")


def files_equal(a, b):
    a = a or []
    b = b or []
    try:
        return sorted(a) == sorted(b)
    except Exception:
        return a == b


def dedupe_messages(msgs):
    deduped = []
    removed = 0
    for m in msgs:
        if deduped:
            prev = deduped[-1]
            if (
                prev.get("role") == m.get("role")
                and prev.get("content") == m.get("content")
                and files_equal(prev.get("generated_files"), m.get("generated_files"))
            ):
                removed += 1
                continue
        deduped.append(m)
    return deduped, removed


def main():
    if not DATA_PATH.exists():
        print("[dedupe] data/conversations.json 不存在，无需处理")
        return

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    # 备份
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DATA_PATH.parent / f"conversations_backup_{ts}.json"
    backup.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[dedupe] 已创建备份: {backup}")

    total_removed = 0
    conv_changed = 0
    for conv_id, conv in data.items():
        msgs = conv.get("messages", [])
        deduped, removed = dedupe_messages(msgs)
        if removed:
            conv_changed += 1
            total_removed += removed
            conv["messages"] = deduped
            # 不改 updated_at，保持对话时间线稳定

    # 写回
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[dedupe] 去重完成: {conv_changed} 个对话发生变更, 删除 {total_removed} 条重复消息")


if __name__ == "__main__":
    main()

