"""调试 MiniMax Image Generation API 响应格式"""

import os
import requests
import json

API_KEY = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLotLnmmZPml60iLCJVc2VyTmFtZSI6Iui0ueaZk-aXrSIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTk4MDg2MDMwMzM0MzcwMDMyIiwiUGhvbmUiOiIxMzMyMTEwNTQ0MiIsIkdyb3VwSUQiOiIxOTk4MDg2MDMwMzMwMTc1NzI4IiwiUGFnZU5hbWUiOiIiLCJNYWlsIjoiIiwiQ3JlYXRlVGltZSI6IjIwMjUtMTItMDkgMTQ6NDU6MDgiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.Cduc9i-LTFkGZqXPTjE2O0bUlSNtM914e8889FxBCYyTOgM2GUWKSG0WmnmUlHajA7tEI_HoSQQusNuOpxun7GGEChsEE3moOYSWmYM43mRk3Vw4lp_L4DBTwSS14KlrO75O6FkiCIgiSIemxvPdb7iRZbLoT0DT5KK32qoXCgiZcyGnjsGKS0XLz8i0LA6oWIU0VNwJkp8AGjGp5Ul3UchqZNfqHsi71If-oPCEBfjekiib9kYtnr250zyomOwD1h9HDXw_-la68pY-a82fHBDXbEp9t3jF_cn1kR9YC4putmkoMnCxbIfHGIEEU5wGA2SQod1qlQLgtM5oT7VOBA"

url = "https://api.minimaxi.com/v1/image_generation"

payload = {
    "model": "image-01",
    "prompt": "A cute cat sitting on a table",
    "aspect_ratio": "16:9",
    "response_format": "url",
    "n": 1,
    "prompt_optimizer": True
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

print("发送请求...")
response = requests.post(url, json=payload, headers=headers, timeout=60)

print(f"\n状态码: {response.status_code}")
print(f"\n完整响应:\n{json.dumps(response.json(), indent=2, ensure_ascii=False)}")
