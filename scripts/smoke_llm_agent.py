#!/usr/bin/env python3
"""
后端真实 LLM 冒烟测试（依赖已在 .env / 环境变量中配置）：
- 预期服务已在本机运行: http://127.0.0.1:8000
- 流程：创建对话 → 通过SSE请求 /chat → 收集 files_generated → 校验文件可访问

用法：
  python3 scripts/smoke_llm_agent.py \
      --host 127.0.0.1 --port 8000 \
      --model gpt-5 \
      --message "用PIL生成 real_llm_a.png 和 real_llm_b.png，再用openpyxl生成 real_llm.xlsx，必须只用文件名保存"
"""

import argparse
import json
import sys
import time
import requests
from urllib.parse import quote


def sse_lines(resp):
    buff = b""
    for chunk in resp.iter_lines():
        if not chunk:
            continue
        try:
            line = chunk.decode("utf-8", errors="ignore")
        except Exception:
            continue
        yield line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--model", default="gpt-5")
    ap.add_argument("--message", required=True)
    args = ap.parse_args()

    base = f"http://{args.host}:{args.port}"
    sess = requests.Session()

    # 1) 创建对话
    r = sess.post(f"{base}/conversations", params={"model": args.model})
    r.raise_for_status()
    conv_id = r.json()["conversation_id"]
    print("[SMOKE] conversation_id:", conv_id)

    # 2) 发送SSE请求
    url = (
        f"{base}/chat?message={quote(args.message)}&model={quote(args.model)}&conversation_id={quote(conv_id)}"
    )
    print("[SMOKE] SSE:", url)
    resp = sess.get(url, stream=True, timeout=600)
    resp.raise_for_status()

    files = []
    final_ok = False
    for line in sse_lines(resp):
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data.strip() == "[DONE]":
            break
        try:
            evt = json.loads(data)
        except Exception:
            continue
        t = evt.get("type")
        if t == "files_generated":
            files.extend(evt.get("files", []))
            print("[files_generated]", evt.get("files"))
        elif t == "final":
            print("[final]", evt.get("result"))
            final_ok = evt.get("result", {}).get("status") == "success"

    if not final_ok:
        print("[SMOKE] 最终未成功，退出", file=sys.stderr)
        sys.exit(2)

    # 过滤只验证前端可预览的扩展名
    files = [f for f in files if any(f.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".xlsx"))]
    files = list(dict.fromkeys(files))  # 去重，保序
    if not files:
        print("[SMOKE] 未收到可预览文件名 (png/jpg/xlsx)")
    else:
        print("[SMOKE] 收到文件:", files)

    # 3) HEAD/GET 校验
    for f in files:
        head = sess.head(f"{base}/outputs/{quote(conv_id)}/{quote(f)}")
        print("HEAD", f, head.status_code, head.headers.get("X-File-Scope"))
        get = sess.get(f"{base}/outputs/{quote(conv_id)}/{quote(f)}")
        print("GET", f, get.status_code, get.headers.get("Content-Type"), len(get.content))

    print("[SMOKE] done.")


if __name__ == "__main__":
    main()

