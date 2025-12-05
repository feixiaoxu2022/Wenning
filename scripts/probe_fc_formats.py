#!/usr/bin/env python3
"""
Quickly probe a Chat Completions endpoint for Function-Calling compatibility
with different tool message encodings.

Reads .env in project root for AGENT_MODEL_BASE_URL / AGENT_MODEL_API_KEY.

Examples:
  python3 scripts/probe_fc_formats.py --model gemini-3-pro-preview
  python3 scripts/probe_fc_formats.py --model gpt-5 --stream
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import requests


def load_env():
    env_path = Path('.env')
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


def run(model: str, stream: bool = False):
    base = os.getenv('AGENT_MODEL_BASE_URL')
    key = os.getenv('AGENT_MODEL_API_KEY')
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}

    tools = [{
        "type": "function",
        "function": {
            "name": "code_executor",
            "description": "Execute Python code",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"]
            }
        }
    }]

    assistant_tc = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "code_executor", "arguments": json.dumps({"code": "print(1)"})}
        }]
    }

    variants = [
        ("tool(name+id) JSON content",
         [{"role": "tool", "tool_call_id": "call_1", "name": "code_executor", "content": json.dumps({"ok": True})}]),
        ("tool plain text",
         [{"role": "tool", "tool_call_id": "call_1", "name": "code_executor", "content": "ok"}]),
        ("function role",
         [{"role": "function", "name": "code_executor", "content": "ok"}]),
        ("tool(no name)",
         [{"role": "tool", "tool_call_id": "call_1", "content": "ok"}]),
    ]

    print(f"BASE={os.getenv('AGENT_MODEL_BASE_URL')}\nMODEL={model}\n")
    for i, (name, tail) in enumerate(variants, 1):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "probe"},
                {"role": "user", "content": "run"},
                assistant_tc,
                *tail,
            ],
            "tools": tools,
            "temperature": 0.1,
            "stream": bool(stream),
        }
        r = requests.post(base, headers=headers, json=payload, timeout=30)
        print(f"[{i}] {name}: status={r.status_code}")
        print(r.text[:600])
        print()


if __name__ == '__main__':
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--stream', action='store_true')
    args = ap.parse_args()
    run(args.model, args.stream)

