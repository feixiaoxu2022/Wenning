#!/usr/bin/env python3
"""
将根目录 outputs 下仍被会话引用的文件复制到各自的 outputs/{conversation_id}/ 目录。

用途：切换到严格会话隔离模式后，历史对话若引用了根目录文件，前端访问将 404。
执行本脚本可将这些文件复制到对应会话目录，便于回放历史对话。

安全性：默认复制，不移动；不会覆盖已有同名文件。
"""

from pathlib import Path
import json
import shutil

DATA = Path("data/conversations.json")
OUT_ROOT = Path("outputs")


def main():
    if not DATA.exists():
        print("[migrate] conversations.json 不存在")
        return
    if not OUT_ROOT.exists():
        print("[migrate] outputs 不存在，无需处理")
        return

    data = json.loads(DATA.read_text(encoding="utf-8"))
    copied = 0
    touched_convs = 0

    for conv_id, conv in data.items():
        msgs = conv.get("messages", [])
        conv_dir = OUT_ROOT / conv_id
        conv_dir.mkdir(exist_ok=True)
        changed = False

        for m in msgs:
            if m.get("role") != "assistant":
                continue
            files = m.get("generated_files") or []
            for name in files:
                src = OUT_ROOT / name
                dst = conv_dir / name
                if src.exists() and not dst.exists():
                    try:
                        shutil.copy2(src, dst)
                        copied += 1
                        changed = True
                        print(f"[migrate] {name}: {src} -> {dst}")
                    except Exception as e:
                        print(f"[migrate] 复制失败 {name}: {e}")

        if changed:
            touched_convs += 1

    print(f"[migrate] 完成: 复制 {copied} 个文件，涉及 {touched_convs} 个对话。")


if __name__ == "__main__":
    main()

