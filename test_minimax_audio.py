#!/usr/bin/env python3
"""测试MiniMax音频生成API，验证返回格式和文件有效性"""

import os
import sys
import json
import base64
import requests
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import Config


def test_tts_api():
    """测试TTS API"""
    print("=" * 60)
    print("测试 MiniMax TTS API")
    print("=" * 60)

    config = Config()
    api_key = config.minimax_api_key
    api_url = config.minimax_tts_api_url

    if not api_key:
        print("❌ 缺少 MINIMAX_API_KEY 环境变量")
        return None

    print(f"API URL: {api_url}")
    print(f"API Key: {api_key[:10]}...")

    # 简单的测试文本
    payload = {
        "model": "speech-2.6-hd",
        "text": "这是一个测试。",
        "stream": False,
        "voice_setting": {
            "voice_id": "male-qn-qingse",
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 0
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1
        },
        "subtitle_enable": False
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print("\n发送请求...")
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        print(f"状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ HTTP错误: {response.text}")
            return None

        result = response.json()
        print("\n响应结构:")
        print(f"  Keys: {list(result.keys())}")

        # 检查base_resp
        base_resp = result.get("base_resp", {})
        print(f"  base_resp.status_code: {base_resp.get('status_code')}")
        print(f"  base_resp.status_msg: {base_resp.get('status_msg')}")

        if base_resp.get("status_code") != 0:
            print(f"❌ API返回错误: {base_resp.get('status_msg')}")
            return None

        # 检查data
        if "data" not in result:
            print("❌ 响应中缺少 'data' 字段")
            return None

        data = result["data"]
        print(f"  data Keys: {list(data.keys())}")

        if "audio" not in data:
            print("❌ data中缺少 'audio' 字段")
            return None

        audio_base64 = data["audio"]
        print(f"\n音频数据:")
        print(f"  Base64长度: {len(audio_base64)} 字符")
        print(f"  Base64前100字符: {audio_base64[:100]}")

        # 尝试解码
        # 修复padding
        missing_padding = len(audio_base64) % 4
        if missing_padding:
            audio_base64 += '=' * (4 - missing_padding)
            print(f"  已补充padding: {4 - missing_padding}个'='")

        try:
            audio_bytes = base64.b64decode(audio_base64)
            print(f"  解码成功! 音频大小: {len(audio_bytes)} 字节")

            # 检查文件头（MP3 magic bytes）
            if len(audio_bytes) >= 3:
                header = audio_bytes[:3]
                print(f"  文件头 (hex): {header.hex()}")
                # MP3文件应该以 ID3 (0x494433) 或 0xFFFB/0xFFFA 开头
                if header == b'ID3':
                    print("  ✓ 检测到ID3标签 (标准MP3)")
                elif audio_bytes[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
                    print("  ✓ 检测到MP3同步字 (无ID3标签)")
                else:
                    print(f"  ⚠️ 未检测到MP3文件头，可能不是有效的MP3")

            # 保存测试文件
            test_file = Path("test_tts_output.mp3")
            test_file.write_bytes(audio_bytes)
            print(f"\n✓ 测试文件已保存: {test_file}")
            print(f"  可以用 'afplay {test_file}' 测试播放 (macOS)")

            return test_file

        except Exception as e:
            print(f"❌ Base64解码失败: {e}")
            return None

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_music_api():
    """测试Music Generation API"""
    print("\n" + "=" * 60)
    print("测试 MiniMax Music Generation API")
    print("=" * 60)

    config = Config()
    api_key = config.minimax_api_key
    api_url = config.minimax_music_api_url

    if not api_key:
        print("❌ 缺少 MINIMAX_API_KEY 环境变量")
        return None

    print(f"API URL: {api_url}")
    print(f"API Key: {api_key[:10]}...")

    # 简单的测试提示词
    payload = {
        "model": "music-2.0",
        "prompt": "轻快的背景音乐",
        "audio_setting": {
            "sample_rate": 44100,
            "bitrate": 256000,
            "format": "mp3"
        }
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print("\n发送请求... (音乐生成可能需要较长时间)")
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=180)
        print(f"状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ HTTP错误: {response.text}")
            return None

        result = response.json()
        print("\n响应结构:")
        print(f"  Keys: {list(result.keys())}")

        # 检查base_resp
        base_resp = result.get("base_resp", {})
        print(f"  base_resp.status_code: {base_resp.get('status_code')}")
        print(f"  base_resp.status_msg: {base_resp.get('status_msg')}")

        if base_resp.get("status_code") != 0:
            print(f"❌ API返回错误: {base_resp.get('status_msg')}")
            return None

        # 检查data
        if "data" not in result:
            print("❌ 响应中缺少 'data' 字段")
            return None

        data = result["data"]
        print(f"  data Keys: {list(data.keys())}")

        if "audio" not in data:
            print("❌ data中缺少 'audio' 字段")
            return None

        audio_base64 = data["audio"]
        print(f"\n音频数据:")
        print(f"  Base64长度: {len(audio_base64)} 字符")
        print(f"  Base64前100字符: {audio_base64[:100]}")

        # 尝试解码
        missing_padding = len(audio_base64) % 4
        if missing_padding:
            audio_base64 += '=' * (4 - missing_padding)
            print(f"  已补充padding: {4 - missing_padding}个'='")

        try:
            audio_bytes = base64.b64decode(audio_base64)
            print(f"  解码成功! 音频大小: {len(audio_bytes)} 字节")

            # 检查文件头
            if len(audio_bytes) >= 3:
                header = audio_bytes[:3]
                print(f"  文件头 (hex): {header.hex()}")
                if header == b'ID3':
                    print("  ✓ 检测到ID3标签 (标准MP3)")
                elif audio_bytes[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
                    print("  ✓ 检测到MP3同步字 (无ID3标签)")
                else:
                    print(f"  ⚠️ 未检测到MP3文件头，可能不是有效的MP3")

            # 保存测试文件
            test_file = Path("test_music_output.mp3")
            test_file.write_bytes(audio_bytes)
            print(f"\n✓ 测试文件已保存: {test_file}")
            print(f"  可以用 'afplay {test_file}' 测试播放 (macOS)")

            return test_file

        except Exception as e:
            print(f"❌ Base64解码失败: {e}")
            return None

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("\nMiniMax 音频生成API测试工具\n")

    # 测试TTS
    tts_file = test_tts_api()

    # 测试Music Generation
    music_file = test_music_api()

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if tts_file and tts_file.exists():
        print(f"✓ TTS测试成功: {tts_file}")
        print(f"  播放命令: afplay {tts_file}")
    else:
        print("✗ TTS测试失败")

    if music_file and music_file.exists():
        print(f"✓ Music测试成功: {music_file}")
        print(f"  播放命令: afplay {music_file}")
    else:
        print("✗ Music测试失败")
