"""数据迁移脚本: conversations.json -> 分片存储

将单个大文件迁移到按用户和日期分片的目录结构
"""

import json
from pathlib import Path
from datetime import datetime
import sys
import os

# 添加项目根目录到path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from src.utils.conversation_manager_v2 import ConversationManagerV2


def migrate_outputs(manager: ConversationManagerV2):
    """迁移outputs目录,添加时间戳前缀

    Args:
        manager: ConversationManager实例
    """
    outputs_root = Path("outputs")
    if not outputs_root.exists():
        print("  ℹ️  outputs目录不存在,跳过")
        return

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
            skipped += 1
            continue

        new_path = outputs_root / new_dir_name

        try:
            # 重命名目录
            old_dir.rename(new_path)
            renamed += 1
            if renamed % 10 == 0:
                print(f"  ⏳ 进度: {renamed} 个目录已重命名")
        except Exception as e:
            errors.append((conv_id, str(e)))
            print(f"  ❌ 重命名失败: {conv_id} -> {new_dir_name}: {e}")

    print(f"  ✅ 重命名: {renamed} 个目录")
    print(f"  ⏭️  跳过: {skipped} 个目录")
    if errors:
        print(f"  ⚠️  失败: {len(errors)} 个目录")


def migrate_conversations():
    """迁移对话数据"""
    # 旧数据路径
    old_path = Path("data/conversations.json")

    if not old_path.exists():
        print("❌ 未找到 data/conversations.json,无需迁移")
        return

    # 备份旧数据
    backup_path = old_path.with_suffix(".json.backup")
    print(f"📦 备份旧数据: {backup_path}")
    import shutil
    shutil.copy(old_path, backup_path)

    # 加载旧数据
    print(f"📖 加载旧数据: {old_path}")
    with open(old_path, 'r', encoding='utf-8') as f:
        old_data = json.load(f)

    total = len(old_data)
    print(f"📊 共 {total} 个对话需要迁移")

    # 创建新的管理器
    print("🔨 初始化新的存储系统...")
    new_manager = ConversationManagerV2()

    # 迁移每个对话
    migrated = 0
    errors = []

    for conv_id, conv in old_data.items():
        try:
            # 提取元数据
            username = conv.get("user") or "anonymous"
            created_at = conv.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            # 获取目标路径
            conv_path = new_manager._get_conv_path(conv_id, username, created_at)

            # 保存对话文件
            new_manager._save_conversation_file(conv_path, conv)

            # 生成输出目录名
            timestamp_prefix = created_at.replace("-", "").replace(":", "").replace(" ", "_")[:15] if created_at else datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir_name = f"{timestamp_prefix}_{conv_id}"

            # 更新索引
            new_manager.index[conv_id] = {
                "id": conv_id,
                "title": conv.get("title", "新对话"),
                "model": conv.get("model", "gpt-5"),
                "created_at": created_at,
                "updated_at": conv.get("updated_at", created_at),
                "user": username,
                "output_dir": output_dir_name  # 添加输出目录名
            }

            migrated += 1
            if migrated % 10 == 0:
                print(f"⏳ 进度: {migrated}/{total}")

        except Exception as e:
            errors.append((conv_id, str(e)))
            print(f"❌ 迁移失败: {conv_id} - {e}")

    # 保存索引
    print("💾 保存索引文件...")
    new_manager._save_index()

    # 迁移outputs目录
    print("\n🔄 迁移outputs目录...")
    migrate_outputs(new_manager)

    # 报告结果
    print("\n" + "="*60)
    print(f"✅ 迁移完成!")
    print(f"📊 成功迁移: {migrated}/{total} 个对话")

    if errors:
        print(f"⚠️  失败: {len(errors)} 个对话")
        for conv_id, err in errors[:5]:  # 只显示前5个错误
            print(f"  - {conv_id}: {err}")

    print(f"\n📁 新的存储位置: data/conversations/")
    print(f"📋 索引文件: data/index.json")
    print(f"💾 备份文件: {backup_path}")
    print("="*60)

    # 询问是否删除旧文件(仅在交互模式下)
    try:
        response = input("\n是否删除旧的 conversations.json? (保留备份) [y/N]: ")
        if response.lower() == 'y':
            old_path.unlink()
            print(f"🗑️  已删除: {old_path}")
            print(f"💾 备份保留在: {backup_path}")
        else:
            print("✅ 保留旧文件")
    except (EOFError, KeyboardInterrupt):
        print("\n✅ 保留旧文件 (非交互模式)")


if __name__ == "__main__":
    print("="*60)
    print("对话数据迁移工具")
    print("conversations.json -> 分片存储")
    print("="*60 + "\n")

    migrate_conversations()
