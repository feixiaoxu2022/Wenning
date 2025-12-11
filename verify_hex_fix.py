#!/usr/bin/env python3
"""验证修复后的hex解码"""

# 使用API返回的实际hex字符串（前100字符）
hex_string = "4944330400000000086a545858580000083d00000341494743007b224c6162656c223a2231222c22436f6e74656e7450726f"

print("="*60)
print("验证Hex解码修复")
print("="*60)

print(f"\nHex字符串（前100字符）:")
print(hex_string)

# 解码
audio_bytes = bytes.fromhex(hex_string)

print(f"\n解码后:")
print(f"  大小: {len(audio_bytes)} 字节")
print(f"  Hex: {audio_bytes.hex()}")
print(f"  Repr: {repr(audio_bytes)}")
print(f"  ASCII: {audio_bytes.decode('ascii', errors='ignore')}")

# 检查文件头
if audio_bytes[:3] == b'ID3':
    print(f"\n✓ 正确！这是ID3标签（MP3文件头）")
else:
    print(f"\n❌ 错误！不是ID3标签")
