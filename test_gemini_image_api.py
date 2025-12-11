#!/usr/bin/env python3
"""测试 Gemini 3 Pro Image Preview API"""

import requests
import json
import base64
from pathlib import Path

# API配置
API_URL = "http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-image-preview:generateContent"
API_KEY = "sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF"

def test_text_to_image_basic():
    """测试1：基础文生图"""
    print("\n=== 测试1：基础文生图 ===")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "Generate an image of a serene mountain landscape at sunset with a lake in the foreground"
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
            "maxOutputTokens": 8192
        }
    }

    try:
        print(f"请求URL: {API_URL}")
        print(f"请求payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)

        print(f"\n状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 成功!")
            print(f"响应结构: {json.dumps(result, indent=2, ensure_ascii=False)[:1000]}...")

            # 尝试提取图片数据
            if "candidates" in result:
                for i, candidate in enumerate(result["candidates"]):
                    if "content" in candidate and "parts" in candidate["content"]:
                        for j, part in enumerate(candidate["content"]["parts"]):
                            if "inlineData" in part:
                                # 保存图片
                                mime_type = part["inlineData"].get("mimeType", "image/png")
                                data = part["inlineData"]["data"]

                                ext = mime_type.split("/")[-1]
                                filename = f"test_output_{i}_{j}.{ext}"

                                with open(filename, "wb") as f:
                                    f.write(base64.b64decode(data))

                                print(f"  ✅ 图片已保存: {filename}")

        else:
            print(f"\n❌ 失败!")
            print(f"错误响应: {response.text}")

    except Exception as e:
        print(f"\n❌ 异常: {e}")


def test_text_to_image_chinese():
    """测试2：中文提示词生图"""
    print("\n=== 测试2：中文提示词生图 ===")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": "生成一张图片：中国传统水墨画风格，描绘一座古老的寺庙坐落在云雾缭绕的山顶，前景有一棵松树"
                    }
                ]
            }
        ]
    }

    try:
        print(f"请求URL: {API_URL}")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)

        print(f"\n状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 成功! 响应结构: {list(result.keys())}")

            # 尝试提取图片
            if "candidates" in result:
                for i, candidate in enumerate(result["candidates"]):
                    if "content" in candidate and "parts" in candidate["content"]:
                        for j, part in enumerate(candidate["content"]["parts"]):
                            if "inlineData" in part:
                                mime_type = part["inlineData"].get("mimeType", "image/png")
                                data = part["inlineData"]["data"]
                                ext = mime_type.split("/")[-1]
                                filename = f"test_chinese_{i}_{j}.{ext}"

                                with open(filename, "wb") as f:
                                    f.write(base64.b64decode(data))

                                print(f"  ✅ 图片已保存: {filename}")
        else:
            print(f"❌ 失败: {response.text}")

    except Exception as e:
        print(f"❌ 异常: {e}")


def test_check_endpoint_variants():
    """测试3：尝试不同的端点格式"""
    print("\n=== 测试3：检查端点格式 ===")

    endpoints = [
        "http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-image-preview:generateContent",
        "http://yy.dbh.baidu-int.com/v1/models/gemini-3-pro-image-preview",
        "http://yy.dbh.baidu-int.com/v1/chat/completions",  # 标准格式
    ]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    simple_payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Generate a simple red circle"}]
            }
        ]
    }

    for endpoint in endpoints:
        print(f"\n尝试端点: {endpoint}")
        try:
            response = requests.post(endpoint, headers=headers, json=simple_payload, timeout=30)
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✅ 可用!")
                print(f"  响应keys: {list(response.json().keys())}")
            else:
                print(f"  ❌ 响应: {response.text[:200]}")
        except Exception as e:
            print(f"  ❌ 异常: {e}")


def test_standard_openai_format():
    """测试4：尝试标准OpenAI兼容格式"""
    print("\n=== 测试4：OpenAI兼容格式 ===")

    url = "http://yy.dbh.baidu-int.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gemini-3-pro-image-preview",
        "messages": [
            {
                "role": "user",
                "content": "Generate an image of a cute cat"
            }
        ]
    }

    try:
        print(f"请求URL: {url}")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 成功!")
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}...")
        else:
            print(f"❌ 失败: {response.text}")

    except Exception as e:
        print(f"❌ 异常: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Gemini 3 Pro Image Preview API 调试脚本")
    print("=" * 60)

    # 运行测试
    test_check_endpoint_variants()
    test_text_to_image_basic()
    test_text_to_image_chinese()
    test_standard_openai_format()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
