#!/usr/bin/env python3
"""测试MiniMax TTS API，查看原始返回"""

import os
import sys
import json
import base64
import requests

# 读取.env
from pathlib import Path
import re

env_file = Path('.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

API_KEY = os.getenv('MINIMAX_API_KEY', '')
API_URL = os.getenv('MINIMAX_TTS_API_URL', 'https://api.minimaxi.com/v1/t2a_v2')

if not API_KEY:
    print("❌ 缺少MINIMAX_API_KEY环境变量")
    sys.exit(1)

print("="*60)
print("MiniMax TTS API 原始响应测试")
print("="*60)
print(f"API Key: {API_KEY[:20]}...")
print(f"API URL: {API_URL}")

# 构建请求
payload = {
    "model": "speech-2.6-hd",
    "text": "这是测试",
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
        print(f"❌ HTTP错误")
        print(f"响应内容:\n{response.text}")
        sys.exit(1)

    result = response.json()
    print(f"\n响应结构:")
    print(f"  顶层keys: {list(result.keys())}")

    # 检查base_resp
    base_resp = result.get('base_resp', {})
    print(f"\nbase_resp:")
    print(f"  status_code: {base_resp.get('status_code')}")
    print(f"  status_msg: {base_resp.get('status_msg')}")

    if base_resp.get('status_code') != 0:
        print(f"❌ API返回错误")
        sys.exit(1)

    # 检查data
    if 'data' not in result:
        print("❌ 响应中缺少data字段")
        sys.exit(1)

    data = result['data']
    print(f"\ndata keys: {list(data.keys())}")

    if 'audio' not in data:
        print("❌ data中缺少audio字段")
        sys.exit(1)

    audio_b64 = data['audio']
    print(f"\naudio字段信息:")
    print(f"  类型: {type(audio_b64)}")
    print(f"  长度: {len(audio_b64)} 字符")
    print(f"  前100字符: {audio_b64[:100]}")
    print(f"  后100字符: {audio_b64[-100:]}")

    # 检查base64是否包含非法字符
    import string
    valid_chars = set(string.ascii_letters + string.digits + '+/=')
    invalid_chars = set(audio_b64) - valid_chars
    if invalid_chars:
        print(f"\n⚠️ Base64字符串包含非法字符: {invalid_chars}")

    # 修复padding
    missing_padding = len(audio_b64) % 4
    if missing_padding:
        audio_b64 += '=' * (4 - missing_padding)
        print(f"\n已补充padding: {4 - missing_padding}个'='")

    # 解码
    print(f"\n尝试解码base64...")
    try:
        audio_bytes = base64.b64decode(audio_b64)
        print(f"✓ 解码成功")
        print(f"  解码后大小: {len(audio_bytes)} 字节 ({len(audio_bytes)/1024:.2f} KB)")

        # 检查文件头
        header = audio_bytes[:50]
        print(f"\n文件头信息:")
        print(f"  Hex: {header.hex()}")
        print(f"  Repr: {repr(header)}")

        # 判断格式
        if header[:3] == b'ID3':
            print(f"\n✓ 这是标准MP3文件 (ID3标签)")
        elif header[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
            print(f"\n✓ 这是MP3文件 (MPEG sync)")
        elif header[:4] == b'RIFF':
            print(f"\n❌ 这是WAV文件，不是MP3")
        else:
            print(f"\n❌ 不是标准音频格式！")
            # 尝试作为文本
            try:
                text = audio_bytes[:200].decode('utf-8', errors='ignore')
                if text.isprintable():
                    print(f"\n可能是文本内容:\n{text}")
            except:
                pass

        # 保存文件
        output = Path('test_api_response.mp3')
        output.write_bytes(audio_bytes)
        print(f"\n文件已保存: {output}")
        print(f"测试播放: afplay {output}")

    except Exception as e:
        print(f"❌ Base64解码失败: {e}")
        print(f"  前200字符: {audio_b64[:200]}")

except Exception as e:
    print(f"❌ 请求失败: {e}")
    import traceback
    traceback.print_exc()
