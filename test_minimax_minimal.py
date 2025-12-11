#!/usr/bin/env python3
"""最小化测试 - 直接调用MiniMax API"""

import os
import base64
import requests
from pathlib import Path

# 从环境变量读取API Key
API_KEY = os.getenv("MINIMAX_API_KEY", "")

if not API_KEY:
    print("❌ 请设置 MINIMAX_API_KEY 环境变量")
    exit(1)

print("=" * 60)
print("MiniMax TTS API 最小化测试")
print("=" * 60)
print(f"API Key: {API_KEY[:20]}...")

# API配置
API_URL = "https://api.minimaxi.com/v1/t2a_v2"

# 请求体
payload = {
    "model": "speech-2.6-hd",
    "text": "这是一个测试",
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
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

print("\n发送请求...")
try:
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    print(f"状态码: {response.status_code}")

    if response.status_code != 200:
        print(f"❌ HTTP错误:\n{response.text}")
        exit(1)

    result = response.json()

    # 检查base_resp
    base_resp = result.get("base_resp", {})
    print(f"\nbase_resp:")
    print(f"  status_code: {base_resp.get('status_code')}")
    print(f"  status_msg: {base_resp.get('status_msg')}")

    if base_resp.get("status_code") != 0:
        print(f"❌ API错误: {base_resp.get('status_msg')}")
        exit(1)

    # 检查data
    if "data" not in result:
        print("❌ 响应中缺少 'data'字段")
        print(f"响应keys: {list(result.keys())}")
        exit(1)

    data = result["data"]
    print(f"\ndata keys: {list(data.keys())}")

    if "audio" not in data:
        print("❌ data中缺少 'audio'字段")
        exit(1)

    audio_base64 = data["audio"]
    print(f"\naudio字段:")
    print(f"  类型: {type(audio_base64)}")
    print(f"  长度: {len(audio_base64)} 字符")
    print(f"  前100字符: {audio_base64[:100]}")

    # 修复padding
    missing_padding = len(audio_base64) % 4
    if missing_padding:
        audio_base64 += '=' * (4 - missing_padding)
        print(f"  已补充padding: {4 - missing_padding}个'='")

    # 解码
    try:
        audio_bytes = base64.b64decode(audio_base64)
        print(f"\n✓ Base64解码成功")
        print(f"  解码后大小: {len(audio_bytes)} 字节")

        # 检查文件头
        header = audio_bytes[:10]
        print(f"  文件头 (hex): {header.hex()}")
        print(f"  文件头 (repr): {repr(header)}")

        # 判断文件类型
        if header[:3] == b'ID3':
            print(f"  ✓ 检测到ID3标签，这是标准MP3文件")
        elif header[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
            print(f"  ✓ 检测到MP3同步字，这是有效的MP3文件")
        elif header[:4] == b'RIFF':
            print(f"  ⚠️ 这是WAV文件，不是MP3")
        else:
            # 检查是否是文本
            try:
                text = header.decode('utf-8', errors='ignore')
                if text.isprintable():
                    print(f"  ❌ 文件内容是文本，不是音频")
                    print(f"     文本内容: {audio_bytes[:200].decode('utf-8', errors='ignore')}")
                else:
                    print(f"  ⚠️ 未识别的文件格式")
            except:
                print(f"  ⚠️ 未识别的文件格式")

        # 保存文件
        output_file = Path("test_minimal_tts.mp3")
        output_file.write_bytes(audio_bytes)
        print(f"\n✓ 文件已保存: {output_file}")
        print(f"  播放命令: afplay {output_file}")

    except Exception as e:
        print(f"\n❌ Base64解码失败: {e}")
        print(f"  base64前200字符: {audio_base64[:200]}")

except Exception as e:
    print(f"❌ 请求失败: {e}")
    import traceback
    traceback.print_exc()
