"""
LLM Judge

使用LLM进行语义层面的评估：
- 相关性分析
- 完整性检查
- 质量评估
- 组织方式评估
等
"""

import json
import re
from typing import Dict, Any, Optional
import requests


class LLMJudge:
    """基于LLM的评测器"""

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.3
    ):
        """
        Args:
            model: LLM模型名称
            base_url: API base URL
            api_key: API密钥
            temperature: 温度参数（默认0.3，保证稳定性）
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature

    def evaluate(
        self,
        check_item: Dict[str, Any],
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行LLM评测

        Args:
            check_item: 检查项定义（包含prompt、score_range等）
            execution_result: Agent执行结果

        Returns:
            CheckResult
        """
        params = check_item["params"]
        prompt = params["prompt"]
        score_range = params["score_range"]  # [min, max]
        temperature = params.get("temperature", self.temperature)

        # 构造上下文
        context = self._build_context(execution_result)

        # 完整prompt = 上下文 + 评测prompt
        full_prompt = f"""【Agent执行结果】
{context}

{prompt}
"""

        # 调用LLM
        llm_response = self._call_llm(full_prompt, temperature)

        # 解析LLM返回
        score, reason = self._parse_response(llm_response, score_range)

        # 归一化到0-1
        normalized_score = (score - score_range[0]) / (score_range[1] - score_range[0])

        # 判断是否通过（得分>=中间值）
        mid_point = (score_range[0] + score_range[1]) / 2
        passed = score >= mid_point

        return {
            "check_type": check_item["check_type"],
            "description": check_item.get("description", "LLM Judge评估"),
            "score": normalized_score,
            "passed": passed,
            "details": reason,
            "weight": check_item.get("weight", 1.0),
            "raw_data": {
                "llm_response": llm_response,
                "raw_score": score,
                "score_range": score_range
            }
        }

    def _build_context(self, execution_result: Dict) -> str:
        """构造评测上下文"""
        final_state = execution_result.get("final_state", {})
        files = final_state.get("files", [])

        # 文件列表
        file_list = "\n".join([
            f"- {f['path']} ({f['type']}, {f['size']} bytes)"
            for f in files
        ])

        # 对话历史（简化版，只看关键信息）
        conversation = execution_result.get("conversation_history", [])
        # 取前3轮和后3轮
        conv_summary = ""
        if len(conversation) > 6:
            conv_summary = "【前3轮对话】\n"
            for msg in conversation[:3]:
                role = msg.get("role", "")
                content = msg.get("content", "")[:200]  # 截断过长内容
                conv_summary += f"{role}: {content}\n"
            conv_summary += "\n...(中间省略)...\n\n"
            conv_summary += "【后3轮对话】\n"
            for msg in conversation[-3:]:
                role = msg.get("role", "")
                content = msg.get("content", "")[:200]
                conv_summary += f"{role}: {content}\n"
        else:
            conv_summary = "【完整对话】\n"
            for msg in conversation:
                role = msg.get("role", "")
                content = msg.get("content", "")[:200]
                conv_summary += f"{role}: {content}\n"

        context = f"""
生成的文件（共{len(files)}个）：
{file_list}

{conv_summary}
"""
        return context

    def _call_llm(self, prompt: str, temperature: float) -> str:
        """调用LLM API"""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"LLM调用失败: {e}")

    def _parse_response(self, response: str, score_range: tuple) -> tuple[int, str]:
        """
        解析LLM返回的评分

        期望格式：
        【评分】X/5
        【理由】...

        或：
        分数：X
        理由：...
        """
        # 提取分数
        score_patterns = [
            r'【评分】\s*(\d+)',
            r'分数[：:]\s*(\d+)',
            r'得分[：:]\s*(\d+)',
            r'\b(\d+)\s*/\s*\d+',  # X/5格式
        ]

        score = score_range[0]  # 默认最低分
        for pattern in score_patterns:
            match = re.search(pattern, response)
            if match:
                score = int(match.group(1))
                break

        # 确保分数在范围内
        score = max(score_range[0], min(score, score_range[1]))

        # 提取理由
        reason_patterns = [
            r'【理由】\s*[：:]?\s*(.+?)(?=【|$)',
            r'理由[：:]\s*(.+?)(?=\n\n|$)',
        ]

        reason = response[:300]  # 默认取前300字符
        for pattern in reason_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                reason = match.group(1).strip()
                break

        return score, reason
