#!/usr/bin/env python3
"""直接调用TTS和音乐生成工具进行测试"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import Config
from src.utils.conversation_manager_v2 import ConversationManagerV2
from src.tools.atomic.tts_minimax import TTSMiniMax
from src.tools.atomic.music_generation_minimax import MusicGenerationMiniMax


def check_audio_file(filepath):
    """检查音频文件是否有效"""
    path = Path(filepath)
    if not path.exists():
        print(f"  ❌ 文件不存在: {filepath}")
        return False

    file_size = path.stat().st_size
    print(f"  文件大小: {file_size} 字节")

    if file_size == 0:
        print(f"  ❌ 文件为空")
        return False

    # 读取文件头
    with open(path, 'rb') as f:
        header = f.read(20)

    print(f"  文件头 (hex): {header[:10].hex()}")

    # 检查MP3文件头
    if header[:3] == b'ID3':
        print(f"  ✓ 有效的MP3文件 (ID3v2标签)")
        return True
    elif header[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
        print(f"  ✓ 有效的MP3文件 (MPEG audio)")
        return True
    elif header[:4] == b'RIFF':
        print(f"  ⚠️ 这是WAV文件，不是MP3")
        return False
    else:
        # 检查是否是文本
        try:
            text = header[:50].decode('utf-8', errors='ignore')
            if text.isprintable():
                print(f"  ❌ 文件内容是文本而非二进制音频")
                print(f"     内容: {text}")
                return False
        except:
            pass
        print(f"  ❌ 未识别的文件格式")
        return False


def test_tts_tool():
    """测试TTS工具"""
    print("=" * 60)
    print("测试 TTS MiniMax 工具")
    print("=" * 60)

    config = Config()
    conv_manager = ConversationManagerV2(config)

    # 创建工具实例
    tool = TTSMiniMax(config, conv_manager)

    print(f"API Key: {config.minimax_api_key[:20] if config.minimax_api_key else 'NOT SET'}...")
    print(f"API URL: {config.minimax_tts_api_url}")

    # 创建测试会话
    test_conv_id = "test_audio_debug"

    print(f"\n调用工具生成测试音频...")
    print(f"  conversation_id: {test_conv_id}")
    print(f"  text: 这是一个测试")

    result = tool.run(
        text="这是一个测试",
        conversation_id=test_conv_id,
        filename="test_tts.mp3"
    )

    print(f"\n工具返回:")
    print(f"  status: {result.get('status')}")

    if result.get('status') == 'failed':
        print(f"  ❌ 工具执行失败")
        print(f"  error: {result.get('error')}")
        return None

    print(f"  ✓ 工具执行成功")

    # 检查生成的文件
    data = result.get('data', {})
    file_path = data.get('file_path')

    if file_path:
        print(f"\n检查生成的文件: {file_path}")
        if check_audio_file(file_path):
            print(f"\n✓ 文件有效，可以播放")
            print(f"  播放命令: afplay {file_path}")
            return file_path
        else:
            print(f"\n✗ 文件无效，无法播放")
            return None
    else:
        print(f"  ❌ 工具未返回文件路径")
        return None


def test_music_tool():
    """测试音乐生成工具"""
    print("\n" + "=" * 60)
    print("测试 Music Generation MiniMax 工具")
    print("=" * 60)

    config = Config()
    conv_manager = ConversationManagerV2(config)

    # 创建工具实例
    tool = MusicGenerationMiniMax(config, conv_manager)

    print(f"API Key: {config.minimax_api_key[:20] if config.minimax_api_key else 'NOT SET'}...")
    print(f"API URL: {config.minimax_music_api_url}")

    # 创建测试会话
    test_conv_id = "test_audio_debug"

    print(f"\n调用工具生成测试音乐...")
    print(f"  conversation_id: {test_conv_id}")
    print(f"  prompt: 轻快的背景音乐")

    result = tool.run(
        prompt="轻快的背景音乐",
        conversation_id=test_conv_id,
        filename="test_music.mp3"
    )

    print(f"\n工具返回:")
    print(f"  status: {result.get('status')}")

    if result.get('status') == 'failed':
        print(f"  ❌ 工具执行失败")
        print(f"  error: {result.get('error')}")
        return None

    print(f"  ✓ 工具执行成功")

    # 检查生成的文件
    data = result.get('data', {})
    file_path = data.get('file_path')

    if file_path:
        print(f"\n检查生成的文件: {file_path}")
        if check_audio_file(file_path):
            print(f"\n✓ 文件有效，可以播放")
            print(f"  播放命令: afplay {file_path}")
            return file_path
        else:
            print(f"\n✗ 文件无效，无法播放")
            return None
    else:
        print(f"  ❌ 工具未返回文件路径")
        return None


if __name__ == "__main__":
    print("\n直接调用工具测试\n")

    # 测试TTS
    tts_file = test_tts_tool()

    # 测试Music (这个比较慢，如果TTS失败就不测了)
    music_file = None
    if tts_file:
        music_file = test_music_tool()

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if tts_file:
        print(f"✓ TTS测试成功: {tts_file}")
    else:
        print("✗ TTS测试失败")

    if music_file:
        print(f"✓ Music测试成功: {music_file}")
    else:
        print("✗ Music测试失败或未执行")
