"""更新现有index.json,添加output_dir字段并迁移outputs目录"""

import json
from pathlib import Path
import sys
import os

# 添加项目根目录到path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from src.utils.conversation_manager_v2 import ConversationManagerV2


def update_index_with_output_dir():
    """更新index.json,添加output_dir字段"""
    print("="*60)
    print("更新index.json - 添加output_dir字段")
    print("="*60 + "\n")

    index_path = Path("data/index.json")
    if not index_path.exists():
        print("❌ 未找到 data/index.json")
        return

    # 加载索引
    print("📖 加载索引...")
    with open(index_path, 'r', encoding='utf-8') as f:
        index = json.load(f)

    print(f"📊 共 {len(index)} 个对话\n")

    # 更新每个条目
    updated = 0
    for conv_id, meta in index.items():
        # 检查是否已有output_dir
        if "output_dir" in meta:
            continue

        created_at = meta.get("created_at", "")
        if not created_at:
            print(f"⚠️  跳过 {conv_id}: 缺少created_at")
            continue

        # 生成output_dir
        timestamp_prefix = created_at.replace("-", "").replace(":", "").replace(" ", "_")[:15]
        output_dir_name = f"{timestamp_prefix}_{conv_id}"

        meta["output_dir"] = output_dir_name
        updated += 1

    # 保存
    print(f"💾 保存更新后的索引...")
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"✅ 更新完成: {updated}/{len(index)} 个条目添加了output_dir字段\n")


def migrate_outputs_dirs():
    """迁移outputs目录,添加时间戳前缀"""
    print("="*60)
    print("迁移outputs目录")
    print("="*60 + "\n")

    outputs_root = Path("outputs")
    if not outputs_root.exists():
        print("ℹ️  outputs目录不存在,跳过")
        return

    # 加载manager
    manager = ConversationManagerV2()

    renamed = 0
    skipped = 0
    errors = []

    for old_dir in outputs_root.iterdir():
        if not old_dir.is_dir():
            continue

        conv_id = old_dir.name

        # 检查是否已经是新格式(包含下划线且长度>8)
        if "_" in conv_id and len(conv_id) > 8:
            skipped += 1
            continue

        # 从index获取输出目录名
        new_dir_name = manager.get_output_dir_name(conv_id)
        if new_dir_name == conv_id:
            # 没有对应的index条目,跳过
            print(f"⚠️  跳过 {conv_id}: 未在index中找到")
            skipped += 1
            continue

        new_path = outputs_root / new_dir_name

        try:
            # 重命名目录
            old_dir.rename(new_path)
            print(f"✓ {conv_id} -> {new_dir_name}")
            renamed += 1
        except Exception as e:
            errors.append((conv_id, str(e)))
            print(f"❌ 重命名失败: {conv_id} -> {new_dir_name}: {e}")

    print(f"\n✅ 重命名: {renamed} 个目录")
    print(f"⏭️  跳过: {skipped} 个目录")
    if errors:
        print(f"⚠️  失败: {len(errors)} 个目录")


if __name__ == "__main__":
    update_index_with_output_dir()
    print()
    migrate_outputs_dirs()
    print("\n" + "="*60)
    print("✅ 全部完成!")
    print("="*60)
