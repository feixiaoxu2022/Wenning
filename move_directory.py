#!/usr/bin/env python3
"""临时脚本：将outputs/5eed325c中的文件移动到outputs/20251209_155004_5eed325c"""

from pathlib import Path
import shutil

source = Path("outputs/5eed325c")
target = Path("outputs/20251209_155004_5eed325c")

if not source.exists():
    print(f"❌ 源目录不存在: {source}")
    exit(1)

if not target.exists():
    print(f"❌ 目标目录不存在: {target}")
    exit(1)

print(f"正在移动文件...")
print(f"  从: {source}")
print(f"  到: {target}")
print()

# 获取源目录中的所有文件
source_files = list(source.iterdir())
print(f"源目录包含 {len(source_files)} 个文件/目录")

moved_count = 0
skipped_count = 0

for item in source_files:
    target_path = target / item.name

    if target_path.exists():
        print(f"  ⏭️  跳过（已存在）: {item.name}")
        skipped_count += 1
    else:
        try:
            shutil.move(str(item), str(target_path))
            print(f"  ✅ 移动: {item.name}")
            moved_count += 1
        except Exception as e:
            print(f"  ❌ 失败: {item.name} - {e}")

print()
print(f"完成！移动 {moved_count} 个文件，跳过 {skipped_count} 个")

# 如果源目录为空，删除它
remaining = list(source.iterdir())
if not remaining:
    print(f"✅ 源目录已空，删除: {source}")
    source.rmdir()
else:
    print(f"⚠️  源目录还有 {len(remaining)} 个文件，保留目录")

# 验证
mp4_files = list(target.glob("*.mp4"))
print(f"✅ 最终验证: 目标目录包含 {len(mp4_files)} 个mp4文件")
