#!/usr/bin/env python
"""测试实际可用的图像生成模型"""

import requests
import json
import base64
from pathlib import Path

API_KEY = "sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF"
BASE_URL = "http://yy.dbh.baidu-int.com"

def test_gemini_flash_image():
    """测试 gemini-2.5-flash-image"""
    print("\n" + "="*60)
    print("测试 gemini-2.5-flash-image")
    print("="*60)

    # 测试两种格式
    formats = [
        {
            "name": "Gemini原生格式",
            "url": f"{BASE_URL}/v1/models/gemini-2.5-flash-image",
            "payload": {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": "Generate an image of a cute red panda eating bamboo"}
                        ]
                    }
                ]
            }
        },
        {
            "name": "OpenAI兼容格式",
            "url": f"{BASE_URL}/v1/chat/completions",
            "payload": {
                "model": "gemini-2.5-flash-image",
                "messages": [
                    {
                        "role": "user",
                        "content": "Generate an image of a cute red panda eating bamboo"
                    }
                ]
            }
        }
    ]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    for fmt in formats:
        print(f"\n--- {fmt['name']} ---")
        print(f"URL: {fmt['url']}")

        try:
            response = requests.post(fmt['url'], headers=headers, json=fmt['payload'], timeout=120)
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"✅ 成功!")

                # 保存完整响应以便分析
                with open(f"response_{fmt['name'].replace(' ', '_')}.json", "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"响应已保存到: response_{fmt['name'].replace(' ', '_')}.json")

                # 尝试提取图像
                saved = extract_and_save_image(result, f"{fmt['name']}_test")
                if saved:
                    print(f"✅ 图像已保存: {saved}")
                    return fmt  # 找到可用格式，返回
                else:
                    print("⚠️  未找到图像数据，查看响应结构:")
                    print(json.dumps(result, indent=2, ensure_ascii=False)[:500])
            else:
                print(f"❌ 失败: {response.text[:300]}")

        except Exception as e:
            print(f"❌ 异常: {e}")

    return None


def test_gpt_image_1():
    """测试 gpt-image-1"""
    print("\n" + "="*60)
    print("测试 gpt-image-1")
    print("="*60)

    # GPT图像生成可能使用不同的端点
    endpoints = [
        {
            "name": "image-generation端点",
            "url": f"{BASE_URL}/v1/images/generations",
            "payload": {
                "model": "gpt-image-1",
                "prompt": "A cute red panda eating bamboo in a forest",
                "n": 1,
                "size": "1024x1024"
            }
        },
        {
            "name": "chat/completions端点",
            "url": f"{BASE_URL}/v1/chat/completions",
            "payload": {
                "model": "gpt-image-1",
                "messages": [
                    {
                        "role": "user",
                        "content": "Generate an image of a cute red panda eating bamboo"
                    }
                ]
            }
        }
    ]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    for endpoint in endpoints:
        print(f"\n--- {endpoint['name']} ---")
        print(f"URL: {endpoint['url']}")

        try:
            response = requests.post(endpoint['url'], headers=headers, json=endpoint['payload'], timeout=120)
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"✅ 成功!")

                # 保存响应
                with open(f"response_gpt_image_{endpoint['name'].replace('/', '_')}.json", "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                # OpenAI格式通常返回URL而不是base64
                if "data" in result:
                    for i, item in enumerate(result["data"]):
                        if "url" in item:
                            print(f"  图像URL: {item['url']}")
                        if "b64_json" in item:
                            # 保存base64图像
                            filename = f"gpt_image_1_output_{i}.png"
                            with open(filename, "wb") as f:
                                f.write(base64.b64decode(item["b64_json"]))
                            print(f"  ✅ 图像已保存: {filename}")
                            return endpoint

                # 也尝试提取其他格式
                saved = extract_and_save_image(result, f"gpt_image_1_{endpoint['name']}")
                if saved:
                    return endpoint

                print("响应结构:")
                print(json.dumps(result, indent=2, ensure_ascii=False)[:500])

            else:
                print(f"❌ 失败: {response.text[:300]}")

        except Exception as e:
            print(f"❌ 异常: {e}")

    return None


def extract_and_save_image(response_json, prefix="image"):
    """从响应中提取并保存图像"""
    try:
        # 尝试Gemini格式
        if "candidates" in response_json:
            for i, candidate in enumerate(response_json["candidates"]):
                if "content" in candidate and "parts" in candidate["content"]:
                    for j, part in enumerate(candidate["content"]["parts"]):
                        if "inlineData" in part:
                            mime_type = part["inlineData"].get("mimeType", "image/png")
                            data = part["inlineData"]["data"]
                            ext = mime_type.split("/")[-1]
                            filename = f"{prefix}_{i}_{j}.{ext}"

                            with open(filename, "wb") as f:
                                f.write(base64.b64decode(data))
                            return filename

        # 尝试OpenAI格式（base64）
        if "choices" in response_json:
            for i, choice in enumerate(response_json["choices"]):
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                    # 检查是否是base64图像
                    if isinstance(content, str) and len(content) > 100:
                        try:
                            filename = f"{prefix}_{i}.png"
                            with open(filename, "wb") as f:
                                f.write(base64.b64decode(content))
                            return filename
                        except:
                            pass

    except Exception as e:
        print(f"提取图像时出错: {e}")

    return None


if __name__ == "__main__":
    print("="*60)
    print("测试实际可用的图像生成模型")
    print("="*60)

    working_format = None

    # 测试1：gemini-2.5-flash-image
    result = test_gemini_flash_image()
    if result:
        working_format = result
        print(f"\n✅ 找到可用格式: {result['name']}")
    else:
        # 测试2：gpt-image-1
        result = test_gpt_image_1()
        if result:
            working_format = result
            print(f"\n✅ 找到可用格式: {result['name']}")

    print("\n" + "="*60)
    if working_format:
        print("✅ 成功! 可用配置:")
        print(f"  模型: {working_format['payload'].get('model', 'gemini-2.5-flash-image')}")
        print(f"  端点: {working_format['url']}")
        print(f"  格式: {working_format['name']}")
    else:
        print("❌ 所有测试均失败")
        print("\n建议:")
        print("1. 查看保存的响应JSON文件，了解实际返回结构")
        print("2. 联系平台管理员确认图像生成的正确用法")
    print("="*60)
