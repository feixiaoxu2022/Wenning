#!/usr/bin/env python3
"""诊断生成的音频文件是否有效"""

import sys
from pathlib import Path

def check_mp3_file(filepath):
    """检查MP3文件是否有效"""
    print(f"\n检查文件: {filepath}")

    path = Path(filepath)
    if not path.exists():
        print("  ❌ 文件不存在")
        return False

    file_size = path.stat().st_size
    print(f"  文件大小: {file_size} 字节")

    if file_size == 0:
        print("  ❌ 文件为空")
        return False

    # 读取文件头
    with open(path, 'rb') as f:
        header = f.read(10)

    print(f"  文件头 (hex): {header[:10].hex()}")
    print(f"  文件头 (ascii): {repr(header[:10])}")

    # 检查MP3文件头
    # MP3文件可能以以下方式开头:
    # 1. ID3v2: 49 44 33 (ID3)
    # 2. MP3 sync word: FF FB/FA/F3/F2
    # 3. RIFF (WAV): 52 49 46 46

    if header[:3] == b'ID3':
        print("  ✓ 检测到ID3v2标签 (标准MP3)")
        return True
    elif header[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
        print("  ✓ 检测到MP3同步字 (无ID3标签的MP3)")
        return True
    elif header[:4] == b'RIFF':
        print("  ⚠️ 检测到RIFF头，这是WAV文件而不是MP3")
        return False
    elif header[:4] == b'ftyp':
        print("  ⚠️ 检测到ftyp，这是M4A文件而不是MP3")
        return False
    else:
        # 可能是纯文本或其他格式
        if all(32 <= b < 127 or b in [9, 10, 13] for b in header[:10]):
            print("  ❌ 文件内容似乎是文本，而不是二进制音频")
            print(f"     前50字符: {header[:50]}")
        else:
            print("  ⚠️ 未识别的文件格式")
        return False

def main():
    if len(sys.argv) < 2:
        print("用法: python diagnose_audio_files.py <file1.mp3> [file2.mp3] ...")
        print("\n示例:")
        print("  python diagnose_audio_files.py outputs/20251210_195938_09e80835/rl_narration.mp3")
        return

    print("=" * 60)
    print("音频文件诊断工具")
    print("=" * 60)

    all_valid = True
    for filepath in sys.argv[1:]:
        if not check_mp3_file(filepath):
            all_valid = False

    print("\n" + "=" * 60)
    if all_valid:
        print("✓ 所有文件检查通过")
    else:
        print("✗ 部分文件存在问题")
    print("=" * 60)

if __name__ == "__main__":
    main()
