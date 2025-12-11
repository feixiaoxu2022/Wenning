#!/usr/bin/env python3
"""检查音频文件内容"""

from pathlib import Path

filepath = Path('outputs/20251210_195938_09e80835/rl_narration.mp3')

print(f'文件存在: {filepath.exists()}')
if filepath.exists():
    size = filepath.stat().st_size
    print(f'文件大小: {size} 字节 ({size/1024:.2f} KB)')

    with open(filepath, 'rb') as f:
        content = f.read(500)

    print(f'\n文件头 (hex): {content[:50].hex()}')
    print(f'\n文件头 (repr): {repr(content[:50])}')

    # 检查是否是MP3
    if content[:3] == b'ID3':
        print('\n✓ 这是标准MP3文件 (ID3标签)')
    elif content[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
        print('\n✓ 这是MP3文件 (MPEG audio)')
    elif content[:4] == b'RIFF':
        print('\n❌ 这是WAV文件')
    else:
        print('\n❌ 不是标准音频格式')
        # 尝试解码为文本
        try:
            text = content.decode('utf-8', errors='ignore')
            if text.isprintable():
                print(f'\n这是文本内容:\n{text}')
        except:
            pass

print('\n' + '='*60)
print('同样检查第二个文件')
print('='*60)

filepath2 = Path('outputs/20251210_195938_09e80835/rl_bgm.mp3')
print(f'\n文件存在: {filepath2.exists()}')
if filepath2.exists():
    size = filepath2.stat().st_size
    print(f'文件大小: {size} 字节 ({size/1024:.2f} KB)')

    with open(filepath2, 'rb') as f:
        content = f.read(500)

    print(f'\n文件头 (hex): {content[:50].hex()}')
    print(f'\n文件头 (repr): {repr(content[:50])}')

    # 检查是否是MP3
    if content[:3] == b'ID3':
        print('\n✓ 这是标准MP3文件 (ID3标签)')
    elif content[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
        print('\n✓ 这是MP3文件 (MPEG audio)')
    elif content[:4] == b'RIFF':
        print('\n❌ 这是WAV文件')
    else:
        print('\n❌ 不是标准音频格式')
        # 尝试解码为文本
        try:
            text = content.decode('utf-8', errors='ignore')
            if text.isprintable():
                print(f'\n这是文本内容:\n{text}')
        except:
            pass
