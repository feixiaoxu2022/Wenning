#!/usr/bin/env python
"""测试Gemini图像生成能力 - V2"""

import requests
import json

API_KEY = "sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF"
BASE_URL = "http://yy.dbh.baidu-int.com"

def test_1_list_models():
    """测试1：列出可用模型"""
    print("\n=== 测试1：查询可用模型 ===")

    endpoints = [
        f"{BASE_URL}/v1/models",
        f"{BASE_URL}/v1/models/list",
    ]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    for endpoint in endpoints:
        print(f"\n尝试: {endpoint}")
        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 成功!")
                print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])

                # 查找图像相关模型
                if isinstance(result, dict) and "data" in result:
                    models = result["data"]
                    image_models = [m for m in models if "image" in str(m).lower() or "vision" in str(m).lower()]
                    if image_models:
                        print(f"\n找到图像相关模型: {image_models}")
            else:
                print(f"失败: {response.text[:200]}")
        except Exception as e:
            print(f"异常: {e}")


def test_2_gemini_pro_with_image_instruction():
    """测试2：gemini-3-pro-preview + 明确的图像生成指令"""
    print("\n=== 测试2：使用gemini-3-pro-preview生成图像 ===")

    url = f"{BASE_URL}/v1/models/gemini-3-pro-preview"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 尝试不同的提示词格式
    test_prompts = [
        # 格式1：直接要求生成图像
        "Please generate an image of a red apple on a white background.",

        # 格式2：更明确的指令
        "Create a visual image showing a cute cat sitting on a windowsill. Return the image data in base64 format.",

        # 格式3：中文
        "请生成一张图片：一只可爱的小猫坐在窗台上"
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n--- 提示词 {i} ---")
        print(f"提示词: {prompt}")

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ]
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()

                # 检查响应内容
                if "candidates" in result:
                    for candidate in result["candidates"]:
                        if "content" in candidate and "parts" in candidate["content"]:
                            for part in candidate["content"]["parts"]:
                                if "text" in part:
                                    text = part["text"]
                                    print(f"文本响应: {text[:200]}...")

                                    # 检查是否包含图像相关关键词
                                    if any(kw in text.lower() for kw in ["image", "picture", "图", "图像", "图片"]):
                                        print("⚠️  返回文本提到了图像，但没有实际图像数据")

                                if "inlineData" in part:
                                    print("✅ 找到图像数据!")
                                    print(f"  mimeType: {part['inlineData'].get('mimeType')}")
                                    print(f"  数据长度: {len(part['inlineData'].get('data', ''))} bytes")
                                    return  # 成功，退出
            else:
                print(f"失败: {response.text[:200]}")

        except Exception as e:
            print(f"异常: {e}")


def test_3_check_imagen_models():
    """测试3：尝试Imagen相关模型名称"""
    print("\n=== 测试3：尝试Imagen模型 ===")

    model_names = [
        "imagen-3",
        "imagen-3.0",
        "imagen-3-fast",
        "gemini-3-imagen",
        "gemini-imagen",
        "gemini-3-pro-vision",
        "gemini-pro-vision",
    ]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    simple_payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Generate an image of a red circle"}]
            }
        ]
    }

    for model_name in model_names:
        print(f"\n尝试模型: {model_name}")
        url = f"{BASE_URL}/v1/models/{model_name}"

        try:
            response = requests.post(url, headers=headers, json=simple_payload, timeout=30)
            print(f"  状态码: {response.status_code}")

            if response.status_code == 200:
                print(f"  ✅ 模型可用!")
                result = response.json()
                print(f"  响应keys: {list(result.keys())}")
                return model_name
            elif response.status_code == 503:
                error = response.json().get("error", {})
                if "model_not_found" in error.get("code", ""):
                    print(f"  ❌ 模型不存在")
            else:
                print(f"  ❌ 其他错误: {response.text[:100]}")

        except Exception as e:
            print(f"  ❌ 异常: {e}")

    return None


if __name__ == "__main__":
    print("=" * 60)
    print("Gemini 图像生成能力测试 V2")
    print("=" * 60)

    # 测试1：列出模型
    test_1_list_models()

    # 测试2：gemini-3-pro-preview是否支持图像生成
    test_2_gemini_pro_with_image_instruction()

    # 测试3：尝试其他可能的图像模型
    working_model = test_3_check_imagen_models()

    print("\n" + "=" * 60)
    if working_model:
        print(f"✅ 找到可用的图像模型: {working_model}")
    else:
        print("❌ 未找到可用的图像生成模型")
        print("\n建议：")
        print("1. 联系平台管理员确认图像生成模型的正确名称")
        print("2. 检查是否需要特殊权限访问图像生成功能")
        print("3. 确认平台是否支持Imagen或其他图像生成模型")
    print("=" * 60)
