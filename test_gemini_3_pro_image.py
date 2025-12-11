#!/usr/bin/env python
"""测试 gemini-3-pro-image-preview 模型"""

import requests
import json
import base64

API_KEY = "sk-3AYbtGCuXtiVmCDd8nfJoKwNibOagcDswEJiJLwJnOjwPVVF"
BASE_URL = "http://yy.dbh.baidu-int.com"

print("\n" + "="*60)
print("测试 gemini-3-pro-image-preview")
print("="*60)

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {"text": "Generate an image of a blue butterfly on a flower"}
            ]
        }
    ]
}

url = f"{BASE_URL}/v1/models/gemini-3-pro-image-preview"
print(f"\n请求URL: {url}")
print(f"提示词: Generate an image of a blue butterfly on a flower")

try:
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    print(f"\n状态码: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print("✅ 成功!")

        # 检查响应结构
        if "candidates" in result:
            print(f"\n候选数: {len(result['candidates'])}")

            image_saved = False
            for i, candidate in enumerate(result["candidates"]):
                if "content" in candidate and "parts" in candidate["content"]:
                    print(f"\n候选 {i}: {len(candidate['content']['parts'])} 个parts")

                    for j, part in enumerate(candidate["content"]["parts"]):
                        if "inlineData" in part:
                            mime_type = part["inlineData"].get("mimeType", "image/png")
                            data = part["inlineData"].get("data", "")
                            print(f"  Part {j}: 图像数据")
                            print(f"    MIME类型: {mime_type}")
                            print(f"    Base64长度: {len(data)} chars")

                            # 保存图像
                            ext = mime_type.split("/")[-1]
                            filename = f"gemini_3_pro_image_preview_test.{ext}"

                            with open(filename, "wb") as f:
                                f.write(base64.b64decode(data))

                            import os
                            size = os.path.getsize(filename)
                            print(f"    ✅ 图像已保存: {filename} ({size/1024:.1f} KB)")
                            image_saved = True

                        elif "text" in part:
                            text = part["text"]
                            print(f"  Part {j}: 文本响应")
                            print(f"    内容: {text[:150]}")

            if not image_saved:
                print("\n⚠️  响应中没有找到图像数据")
                print("响应结构:")
                # 显示简化的响应结构
                for i, candidate in enumerate(result["candidates"]):
                    print(f"\n候选 {i}:")
                    if "content" in candidate:
                        for j, part in enumerate(candidate["content"]["parts"]):
                            print(f"  Part {j} keys: {list(part.keys())}")
        else:
            print("⚠️  响应中没有 'candidates' 字段")
            print(f"响应keys: {list(result.keys())}")

    elif response.status_code == 503:
        print("❌ 模型不可用 (503)")
        error = response.json()
        print(f"错误信息: {error.get('error', {}).get('message', response.text)}")
    else:
        print(f"❌ 失败 (状态码: {response.status_code})")
        print(f"错误: {response.text[:500]}")

except Exception as e:
    print(f"❌ 异常: {type(e).__name__}: {e}")

print("\n" + "="*60)
