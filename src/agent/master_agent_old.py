"""Master Agent核心模块

负责意图识别、Workflow匹配和任务执行调度。
采用自研轻量级状态机，具备错误反思和自动恢复能力。
"""

import json
from typing import Dict, Any, Optional
from enum import Enum
from src.utils.config import Config
from src.llm.client import LLMClient
from src.llm.prompts import INTENT_RECOGNITION_SYSTEM_PROMPT
from src.tools.workflow.ugc_analysis import UGCAnalysisWorkflow
from src.tools.workflow.cover_generation import CoverGenerationWorkflow
from src.tools.result import ToolResult, ErrorType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentState(Enum):
    """Agent状态枚举"""
    IDLE = "idle"
    INTENT_ANALYSIS = "intent_analysis"
    WORKFLOW_EXECUTION = "workflow_execution"
    COMPLETED = "completed"
    FAILED = "failed"


class MasterAgent:
    """Master Agent

    核心职责：
    1. 意图识别 - 理解用户想做什么
    2. Workflow匹配 - 选择合适的工作流
    3. 执行调度 - 调用Workflow并返回结果
    4. 错误反思 - Tool失败时反思并尝试恢复
    """

    def __init__(self, config: Config, model_name: str = "ernie-5.0-thinking-preview"):
        """初始化Master Agent

        Args:
            config: 全局配置
            model_name: 使用的LLM模型
        """
        self.config = config
        self.llm = LLMClient(config, model_name)
        self.state = AgentState.IDLE
        self.max_reflection_attempts = 2  # 最多反思尝试次数

        # 注册Workflow Tools
        self.workflows = {
            "UGC分析": UGCAnalysisWorkflow(config, self.llm),
            "封面生成": CoverGenerationWorkflow(config, self.llm)
        }

        logger.info(f"MasterAgent初始化完成: model={model_name}")

    def process(self, user_input: str) -> Dict[str, Any]:
        """处理用户输入（主入口）

        Args:
            user_input: 用户输入文本

        Returns:
            执行结果
        """
        logger.info(f"收到用户请求: {user_input[:100]}...")

        try:
            # 状态1: 意图识别
            self.state = AgentState.INTENT_ANALYSIS
            intent_result = self._recognize_intent(user_input)

            logger.info(f"意图识别: type={intent_result['intent_type']}, confidence={intent_result['confidence']}")

            # 状态2: Workflow执行（带反思能力）
            self.state = AgentState.WORKFLOW_EXECUTION
            execution_result = self._execute_workflow_with_reflection(intent_result, user_input)

            # 状态3: 完成
            self.state = AgentState.COMPLETED

            return {
                "status": "success",
                "intent": intent_result,
                "result": execution_result,
                "message": "任务执行成功"
            }

        except Exception as e:
            self.state = AgentState.FAILED
            logger.error(f"任务执行失败: {str(e)}")

            return {
                "status": "failed",
                "error": str(e),
                "message": f"任务执行失败: {str(e)}"
            }

    def _recognize_intent(self, user_input: str) -> Dict[str, Any]:
        """意图识别

        Args:
            user_input: 用户输入

        Returns:
            意图识别结果
        """
        messages = [
            {"role": "system", "content": INTENT_RECOGNITION_SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]

        response = self.llm.chat(messages, temperature=0.3)

        # 解析JSON（多重容错策略）
        import re
        content = response["content"]
        intent_data = None

        # 策略1: 直接解析
        try:
            intent_data = json.loads(content)
        except json.JSONDecodeError:
            # 策略2: 清理空白后解析
            try:
                intent_data = json.loads(content.strip())
            except:
                # 策略3: 提取JSON代码块
                json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    try:
                        intent_data = json.loads(json_match.group(1).strip())
                    except:
                        pass

                # 策略4: 提取{}内容
                if not intent_data:
                    json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                    if json_match:
                        try:
                            intent_data = json.loads(json_match.group(1).strip())
                        except:
                            pass

        # 如果所有解析策略都失败,使用规则式fallback（带参数提取）
        if not intent_data:
            logger.warning("意图识别返回非标准JSON，使用规则式fallback")

            # 简单的关键词匹配+参数提取
            if any(kw in user_input for kw in ["评论", "分析", "UGC", "用户反馈"]):
                # 提取平台和关键词
                platform = ""
                keyword = ""

                # 提取平台
                for p in ["小红书", "抖音", "微博", "知乎", "B站"]:
                    if p in user_input:
                        platform = p
                        break

                # 提取关键词（引号内的内容）
                keyword_match = re.search(r'["""](.*?)["""]', user_input)
                if keyword_match:
                    keyword = keyword_match.group(1)

                intent_data = {
                    "intent_type": "UGC分析",
                    "confidence": 0.7,
                    "extracted_params": {
                        "platform": platform,
                        "keyword": keyword
                    }
                }
            elif any(kw in user_input for kw in ["封面", "图片", "生成图"]):
                intent_data = {
                    "intent_type": "封面生成",
                    "confidence": 0.7,
                    "extracted_params": {}
                }
            else:
                intent_data = {
                    "intent_type": "其他",
                    "confidence": 0.5,
                    "extracted_params": {}
                }

        return intent_data

    def _execute_workflow_with_reflection(
        self,
        intent: Dict[str, Any],
        user_input: str
    ) -> Dict[str, Any]:
        """执行Workflow（带反思和恢复能力）

        Args:
            intent: 意图识别结果
            user_input: 原始用户输入

        Returns:
            执行结果
        """
        intent_type = intent["intent_type"]

        # 匹配Workflow
        if intent_type not in self.workflows:
            raise ValueError(f"暂不支持的任务类型: {intent_type}")

        workflow = self.workflows[intent_type]
        params = self._build_workflow_params(intent, user_input)

        logger.info(f"执行Workflow: {workflow.name}")

        # 反思循环
        for attempt in range(self.max_reflection_attempts + 1):
            # 执行Workflow（返回ToolResult，永不抛异常）
            result: ToolResult = workflow.execute(params)

            if result.success:
                # 成功，直接返回数据
                logger.info(f"Workflow执行成功")
                return result.data

            else:
                # 失败，进入反思流程
                logger.warning(f"Workflow执行失败 (尝试 {attempt + 1}/{self.max_reflection_attempts + 1})")
                logger.info(f"失败信息:\n{result.to_agent_message()}")

                # 最后一次尝试失败，抛出异常
                if attempt >= self.max_reflection_attempts:
                    logger.error("达到最大反思次数，任务失败")
                    raise RuntimeError(result.to_agent_message())

                # 反思并决策
                reflection = self._reflect_on_failure(result, params, user_input)
                logger.info(f"反思结果: {reflection['action']} - {reflection.get('reasoning', '')}")

                # 根据反思结果采取行动
                if reflection["action"] == "retry_with_adjusted_params":
                    params.update(reflection.get("adjusted_params", {}))
                    logger.info(f"调整参数后重试")

                elif reflection["action"] == "retry_with_enhanced_prompt":
                    params["_prompt_enhancement"] = reflection.get("prompt_enhancement", "")
                    logger.info(f"增强Prompt后重试")

                elif reflection["action"] == "skip_and_use_partial":
                    logger.info("使用部分结果作为最终输出")
                    return {
                        "status": "partial_success",
                        "partial_results": result.partial_results,
                        "message": "任务部分完成"
                    }

                elif reflection["action"] == "give_up":
                    logger.error(f"反思后决定放弃")
                    raise RuntimeError(result.to_agent_message())

        # 不应该到这里
        raise RuntimeError("Workflow执行异常")

    def _reflect_on_failure(
        self,
        result: ToolResult,
        current_params: Dict[str, Any],
        user_input: str
    ) -> Dict[str, Any]:
        """对失败进行反思

        Args:
            result: Workflow执行失败的ToolResult
            current_params: 当前使用的参数
            user_input: 用户原始输入

        Returns:
            反思结果，包含下一步行动
        """
        # 构建反思Prompt
        reflection_prompt = f"""你是一个具备反思能力的AI Agent。任务执行失败，需要分析原因并决定下一步行动。

**用户请求**: {user_input}

**执行的工具**: {result.tool_name}

**失败信息**:
{result.to_agent_message()}

**可能的恢复建议**:
{json.dumps(result.recovery_suggestions, ensure_ascii=False, indent=2)}

请分析并返回JSON格式：
{{
    "root_cause": "根本原因分析",
    "action": "retry_with_adjusted_params / retry_with_enhanced_prompt / skip_and_use_partial / give_up",
    "reasoning": "决策理由",
    "adjusted_params": {{}},
    "prompt_enhancement": ""
}}
"""

        # 调用LLM反思
        try:
            response = self.llm.chat([
                {"role": "user", "content": reflection_prompt}
            ], temperature=0.3)

            # 解析反思结果
            return self._parse_reflection_response(response["content"])

        except Exception as e:
            logger.error(f"反思过程失败: {str(e)}，使用规则式fallback")
            return self._rule_based_reflection(result)

    def _parse_reflection_response(self, response: str) -> Dict[str, Any]:
        """解析反思响应"""
        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            # 尝试提取JSON代码块
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except:
                    pass

            # 解析失败，返回默认策略
            return {
                "action": "retry_with_adjusted_params",
                "reasoning": "解析失败，默认重试",
                "adjusted_params": {}
            }

    def _rule_based_reflection(self, result: ToolResult) -> Dict[str, Any]:
        """基于规则的反思（LLM反思失败时的fallback）"""
        if result.error_type == ErrorType.LLM_RESPONSE_PARSE_ERROR:
            return {
                "action": "retry_with_enhanced_prompt",
                "reasoning": "LLM返回格式错误，增强Prompt要求标准JSON",
                "prompt_enhancement": "请严格返回标准JSON格式，不要包含任何代码块标记。"
            }
        elif result.error_type == ErrorType.LLM_TIMEOUT:
            return {
                "action": "retry_with_adjusted_params",
                "reasoning": "LLM超时，减少数据量",
                "adjusted_params": {"max_results": 5}
            }
        elif result.partial_results:
            return {
                "action": "skip_and_use_partial",
                "reasoning": "有部分结果可用"
            }
        else:
            return {
                "action": "give_up",
                "reasoning": "无法恢复的错误"
            }

    def _build_workflow_params(self, intent: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """构建Workflow执行参数

        Args:
            intent: 意图识别结果
            user_input: 原始用户输入

        Returns:
            Workflow参数字典
        """
        # 基础参数
        params = {
            "user_input": user_input,
            **intent.get("extracted_params", {})
        }

        # 根据意图类型添加特定参数
        intent_type = intent["intent_type"]

        if intent_type == "UGC分析":
            # 为UGC分析补充默认参数
            if "max_results" not in params:
                params["max_results"] = 10

        elif intent_type == "封面生成":
            # 为封面生成补充默认参数
            if "title" not in params:
                # 从用户输入中提取标题
                params["title"] = user_input
            if "style" not in params:
                params["style"] = "简洁现代"

        return params

    def switch_model(self, model_name: str):
        """切换LLM模型

        Args:
            model_name: 新模型名称
        """
        self.llm.switch_model(model_name)
        logger.info(f"MasterAgent切换模型: {model_name}")

        # 同步更新所有Workflow的LLM客户端
        for workflow in self.workflows.values():
            workflow.llm = self.llm

    def get_available_workflows(self) -> list[str]:
        """获取可用的Workflow列表

        Returns:
            Workflow名称列表
        """
        return list(self.workflows.keys())

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态

        Returns:
            状态信息
        """
        return {
            "state": self.state.value,
            "model": self.llm.model_name,
            "available_workflows": self.get_available_workflows()
        }
