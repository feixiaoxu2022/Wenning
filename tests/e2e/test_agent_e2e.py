#!/usr/bin/env python3
"""
Agent 端到端(本地无网络)回归：
- 伪造 LLM 返回，第一轮返回 tool_calls=code_executor；第二轮返回最终答案
- 验证 code_executor 收到 conversation_id，并在 outputs/{conversation_id} 下落盘
- 打印 agent 流中的 files_generated 事件
"""

import os
import json
from pathlib import Path

# 必要的环境变量，避免 Config 校验失败
os.environ.setdefault("TAVILY_API_KEY", "dummy")
os.environ.setdefault("AGENT_MODEL_API_KEY", "dummy")
os.environ.setdefault("EB5_API_KEY", "dummy")

from src.utils.config import get_config
from src.tools.registry import ToolRegistry
from src.tools.atomic.web_search import WebSearchTool
from src.tools.atomic.url_fetch import URLFetchTool
from src.tools.atomic.code_executor import CodeExecutor
from src.tools.atomic.plan import PlanTool
from src.agent.master_agent import MasterAgent


class FakeLLM:
    """最小可用 LLM 模拟器，满足 MasterAgent._react_loop_with_progress 的调用。

    第一次流式调用 -> 返回 tool_calls 调用 code_executor；
    第二次流式调用 -> 返回最终 content。
    """

    def __init__(self):
        self._counter = 0
        self.model_name = "fake-model"

    def chat(self, messages, tools=None, tool_choice=None, temperature=0.3, stream=False, **kwargs):
        assert stream is True, "Agent 流程使用 stream=True"

        self._counter += 1
        if self._counter == 1:
            # 第一次：要求执行 code_executor，生成 2 个文件
            code = (
                "from PIL import Image\n"
                "img = Image.new('RGB', (32, 32), (200, 120, 50))\n"
                "img.save('agent_e2e.png')\n"
                "import openpyxl\n"
                "wb = openpyxl.Workbook()\n"
                "ws = wb.active\n"
                "ws['A1'] = 'ok'\n"
                "wb.save('agent_e2e.xlsx')\n"
            )

            response = {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "code_executor",
                            "arguments": json.dumps({
                                "code": code,
                                "output_filename": "agent_e2e.png"
                            }, ensure_ascii=False)
                        }
                    }
                ]
            }

        else:
            # 第二次：返回最终答案
            response = {
                "content": "生成完成"
            }

        def gen():
            # 直接给一个 done 块即可
            yield {"type": "done", "response": response}

        return gen()


def main():
    cfg = get_config()

    # 注册原子工具（与 fastapi_app 一致）
    reg = ToolRegistry()
    reg.register_atomic_tool(WebSearchTool(cfg))
    reg.register_atomic_tool(URLFetchTool(cfg))
    reg.register_atomic_tool(CodeExecutor(cfg))
    reg.register_atomic_tool(PlanTool(cfg))

    agent = MasterAgent(cfg, reg, model_name="gpt-5")
    agent.llm = FakeLLM()

    conv_id = "conv_e2e_agent"
    agent.current_conversation_id = conv_id
    agent.conversation_history = []

    print("[TEST] start agent process_with_progress ...")
    files = []
    for evt in agent.process_with_progress("生成两个文件测试"):
        if evt.get("type") == "files_generated":
            files.extend(evt.get("files", []))
            print("[files_generated]", evt.get("files"))
        if evt.get("type") == "final":
            print("[final]", evt.get("result", {}))

    base = Path(cfg.output_dir) / conv_id
    print("[check exists] dir:", base)
    for name in files:
        p = base / name
        print(str(p), "exists=", p.exists())


if __name__ == "__main__":
    main()

