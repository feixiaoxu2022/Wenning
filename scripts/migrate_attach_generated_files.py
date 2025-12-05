#!/usr/bin/env python3
"""
为历史对话补充 generated_files 字段的迁移脚本。

背景:
- 早期对话未保存 generated_files，前端曾通过正则从文本里匹配文件名。
- 为避免运行时正则，我们迁移为: 离线扫描消息内容 → 匹配文件名 → 验证文件存在 → 写回 generated_files。

用法:
  python scripts/migrate_attach_generated_files.py

效果:
- data/conversations.json 将备份到 data/conversations_backup_YYYYmmdd_HHMMSS.json
- 对每条 assistant 消息, 若无 generated_files, 将根据内容填充存在的文件名
"""

from pathlib import Path
from datetime import datetime
import json
import re


DATA_PATH = Path("data/conversations.json")
OUTPUTS_DIR = Path("outputs")


def extract_filenames(text: str) -> list[str]:
    if not text:
        return []
    patterns = [
        r"([\u4e00-\u9fa5\w\-]+\.xlsx)",
        r"([\u4e00-\u9fa5\w\-]+\.xls)",
        r"([\u4e00-\u9fa5\w\-]+\.png)",
        r"([\u4e00-\u9fa5\w\-]+\.jpg)",
        r"([\u4e00-\u9fa5\w\-]+\.jpeg)",
    ]
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            name = m.group(1)
            # 过滤掉带路径的
            if "/" in name or "\\" in name:
                continue
            found.append(name)
    # 去重，保留顺序
    seen = set()
    unique = []
    for f in found:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def main():
    if not DATA_PATH.exists():
        print("[migrate] conversations.json 不存在")
        return

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    # 备份
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DATA_PATH.parent / f"conversations_backup_{ts}.json"
    backup.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[migrate] 已备份到: {backup}")

    updated_msgs = 0
    updated_convs = 0

    for conv_id, conv in data.items():
        msgs = conv.get("messages", [])
        changed = False
        for msg in msgs:
            if msg.get("role") != "assistant":
                continue
            if msg.get("generated_files"):
                continue
            names = extract_filenames(msg.get("content", ""))
            if not names:
                continue
            # 只保留真实存在的文件
            existing = [n for n in names if (OUTPUTS_DIR / n).exists()]
            if existing:
                msg["generated_files"] = existing
                updated_msgs += 1
                changed = True
        if changed:
            updated_convs += 1

    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[migrate] 完成: 更新 {updated_convs} 个对话, 补充 {updated_msgs} 条消息的 generated_files")


if __name__ == "__main__":
    main()

