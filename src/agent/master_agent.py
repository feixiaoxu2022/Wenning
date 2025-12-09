"""Master Agent核心模块 (Function Calling版本)

基于ReAct模式,LLM作为主控者自主选择和调用工具。
"""

import json
import time
import threading
from typing import Dict, Any, List, Callable, Generator
from enum import Enum
from src.utils.config import Config
from src.llm.client import LLMClient
from src.tools.registry import ToolRegistry
from src.tools.result import ToolResult
from src.utils.logger import get_logger
from src.agent.context_manager import ContextManager
from pathlib import Path

logger = get_logger(__name__)


class AgentState(Enum):
    """Agent状态枚举"""
    IDLE = "idle"
    REASONING = "reasoning"
    TOOL_EXECUTION = "tool_execution"
    COMPLETED = "completed"
    FAILED = "failed"


class MasterAgent:
    """Master Agent (Function Calling模式)

    核心职责:
    1. 作为调度中心,LLM主控决策
    2. 维护Tool Registry,提供所有可用工具
    3. 执行ReAct循环: Reason → Act → Observe
    4. 处理工具调用结果,反馈给LLM继续决策
    """

    def __init__(self, config: Config, tool_registry: ToolRegistry, model_name: str = "glm-4.5"):
        """初始化Master Agent

        Args:
            config: 全局配置
            tool_registry: 工具注册中心
            model_name: 使用的LLM模型
        """
        self.config = config
        self.llm = LLMClient(config, model_name)
        self.tool_registry = tool_registry
        self.state = AgentState.IDLE
        self.max_iterations = 30  # 最大ReAct迭代次数
        self.conversation_history = []  # 多轮对话历史
        self.current_conversation_id = None
        self.message_callback = None  # 消息保存回调函数

        # 初始化Context Manager
        self.context_manager = ContextManager(
            model_name=model_name,
            max_tokens=128000  # 默认128K上下文窗口
        )

        logger.info(f"MasterAgent初始化完成: model={model_name}, tools={len(tool_registry.list_tools())}")

    def _filter_existing_files(self, files):
        try:
            root_dir = Path(self.config.output_dir)
        except Exception:
            root_dir = Path("outputs")

        existing = []
        for name in files:
            try:
                # 如果是在线URL，直接保留（不需要检查本地文件是否存在）
                if isinstance(name, str) and name.startswith(('http://', 'https://')):
                    existing.append(name)
                    continue

                if not self.current_conversation_id:
                    continue
                p_conv = root_dir / self.current_conversation_id / name
                if p_conv.exists() and p_conv.is_file():
                    existing.append(name)
            except Exception:
                continue
        return existing

    def _filter_previewable(self, files):
        allowed = {
            '.png', '.jpg', '.jpeg', '.xlsx', '.html',
            '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac',
            '.mp4', '.webm', '.mov'
        }
        result = []
        for f in files:
            try:
                # 如果是在线URL，视为可预览（前端会用iframe加载）
                if isinstance(f, str) and f.startswith(('http://', 'https://')):
                    result.append(f)
                elif Path(f).suffix.lower() in allowed:
                    result.append(f)
            except Exception:
                continue
        return result

    def process(self, user_input: str) -> Dict[str, Any]:
        """处理用户输入（主入口）

        Args:
            user_input: 用户输入文本

        Returns:
            执行结果
        """
        logger.info(f"收到用户请求: {user_input[:100]}...")

        try:
            # 执行ReAct循环
            self.state = AgentState.REASONING
            result = self._react_loop(user_input)

            # 完成
            self.state = AgentState.COMPLETED

            return {
                "status": "success",
                "result": result,
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

    def process_with_progress(self, user_input: str, progress_callback=None):
        """处理用户输入（带进度反馈的生成器版本）

        Args:
            user_input: 用户输入文本
            progress_callback: 可选的进度回调函数

        Yields:
            进度更新字典
        """
        logger.info(f"收到用户请求(流式): {user_input[:100]}...")

        try:
            # 初始化
            self.state = AgentState.REASONING

            # 执行ReAct循环（流式版本）
            for update in self._react_loop_with_progress(user_input):
                yield update

        except Exception as e:
            self.state = AgentState.FAILED
            logger.error(f"任务执行失败: {str(e)}")
            yield {
                "type": "final",
                "result": {
                    "status": "failed",
                    "error": str(e),
                    "message": f"任务执行失败: {str(e)}"
                }
            }

    def _validate_and_fix_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证并修复消息格式，确保tool_calls有对应的tool消息

        核心原理：
        OpenAI要求有tool_calls的assistant消息后，必须紧跟所有对应的tool响应（在下一个user/assistant之前）。
        当用户在工具执行中途发送新消息时，会导致部分tool响应缺失，需要清理整个不完整的序列。

        两遍扫描策略：
        第一遍：识别所有不完整的tool_calls组（有缺失响应的）
        第二遍：构建干净的消息列表，同时检测孤儿tool消息

        Args:
            messages: 原始消息列表

        Returns:
            修复后的消息列表
        """
        if not messages:
            logger.info("[消息验证] 消息列表为空，跳过验证")
            return messages

        logger.info(f"[消息验证] 开始验证 {len(messages)} 条消息")

        # ========== 第一遍扫描：识别不完整的tool_calls组 ==========
        incomplete_tool_call_ids = set()  # 需要被移除的tool_call_id集合

        for i, msg in enumerate(messages):
            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                tool_calls = msg['tool_calls']
                tool_call_ids = {tc['id'] for tc in tool_calls}

                logger.info(f"[消息验证] 消息#{i}: assistant with {len(tool_calls)} tool_calls")
                logger.info(f"[消息验证]   tool_call_ids: {tool_call_ids}")

                # 向后查找所有对应的tool响应
                found_responses = set()
                for j in range(i + 1, len(messages)):
                    next_msg = messages[j]
                    if next_msg.get('role') == 'tool':
                        tool_call_id = next_msg.get('tool_call_id')
                        if tool_call_id in tool_call_ids:
                            found_responses.add(tool_call_id)
                    elif next_msg.get('role') in ['user', 'assistant']:
                        # 遇到user/assistant消息，序列结束
                        logger.info(f"[消息验证]   在消息#{j}遇到{next_msg.get('role')}，序列结束")
                        break

                missing_responses = tool_call_ids - found_responses

                if missing_responses:
                    # 这组tool_calls不完整，需要被移除
                    logger.warning(f"[消息验证]   ⚠️ 不完整! 缺失响应: {missing_responses}")
                    logger.warning(f"[消息验证]   将移除整组tool_calls({len(tool_call_ids)}个)及其所有响应({len(found_responses)}个)")
                    incomplete_tool_call_ids.update(tool_call_ids)
                else:
                    logger.info(f"[消息验证]   ✓ 完整，找到所有{len(tool_call_ids)}个响应")

        # ========== 第二遍扫描：构建干净的消息列表 ==========
        fixed = []
        current_expected_tool_calls = set()  # 当前期望的tool_call_ids（用于检测孤儿tool消息）

        for i, msg in enumerate(messages):
            role = msg.get('role')

            if role == 'assistant':
                if msg.get('tool_calls'):
                    tool_calls = msg['tool_calls']
                    tool_call_ids = {tc['id'] for tc in tool_calls}

                    # 检查是否为不完整的组
                    if tool_call_ids & incomplete_tool_call_ids:
                        # 移除tool_calls字段，保留content
                        logger.info(f"[消息验证] 消息#{i}: 移除不完整的tool_calls")
                        fixed_msg = {
                            'role': 'assistant',
                            'content': msg.get('content') or '(工具调用进行中...)'
                        }
                        fixed.append(fixed_msg)
                        current_expected_tool_calls = set()  # 清空期望
                    else:
                        # 保留完整的tool_calls
                        logger.info(f"[消息验证] 消息#{i}: 保留完整的tool_calls")
                        fixed.append(msg)
                        current_expected_tool_calls = tool_call_ids  # 更新期望
                else:
                    # assistant without tool_calls
                    fixed.append(msg)
                    current_expected_tool_calls = set()  # 清空期望

            elif role == 'tool':
                tool_call_id = msg.get('tool_call_id')

                # 检查tool消息的合法性
                if tool_call_id in incomplete_tool_call_ids:
                    # 属于被移除的不完整组
                    logger.info(f"[消息验证] 消息#{i}: 跳过 (属于不完整组, id={tool_call_id})")
                elif tool_call_id not in current_expected_tool_calls:
                    # 孤儿tool消息（不在当前期望中）
                    logger.warning(f"[消息验证] 消息#{i}: 跳过孤儿tool (id={tool_call_id}, 期望={current_expected_tool_calls})")
                else:
                    # 合法的tool响应
                    logger.info(f"[消息验证] 消息#{i}: 保留合法的tool响应 (id={tool_call_id})")
                    fixed.append(msg)
                    current_expected_tool_calls.discard(tool_call_id)  # 从期望中移除

            elif role == 'user':
                # user消息中断tool_calls序列
                fixed.append(msg)
                current_expected_tool_calls = set()  # 清空期望

            else:
                # 其他消息类型（如system）
                fixed.append(msg)

        logger.info(f"[消息验证] 验证完成: 原始{len(messages)}条 → 修复后{len(fixed)}条 (移除{len(messages)-len(fixed)}条)")
        return fixed

    def _react_loop(self, user_input: str) -> str:
        """ReAct循环: Reason → Act → Observe

        Args:
            user_input: 用户输入

        Returns:
            最终答案
        """
        # 初始化对话历史
        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt()
            },
            {
                "role": "user",
                "content": user_input
            }
        ]

        # 获取所有可用工具的schema
        tools = self.tool_registry.get_function_calling_schemas()

        logger.info(f"ReAct循环开始: 可用工具={[t['function']['name'] for t in tools]}")

        # ReAct迭代
        for iteration in range(self.max_iterations):
            logger.info(f"ReAct迭代 {iteration + 1}/{self.max_iterations}")

            # Reason: LLM决策
            self.state = AgentState.REASONING

            # 验证并修复消息格式（防止tool_calls没有对应响应导致API错误）
            messages = self._validate_and_fix_messages(messages)

            response = self.llm.chat(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3
            )

            # 记录LLM响应
            logger.info(f"LLM响应: content={response.get('content')[:200] if response.get('content') else 'None'}...")
            if response.get("tool_calls"):
                logger.info(f"LLM决策: 调用{len(response['tool_calls'])}个工具")
                for tc in response["tool_calls"]:
                    logger.info(f"  - {tc['function']['name']}({tc['function']['arguments'][:100]}...)")

            # 检查是否返回最终答案
            if not response.get("tool_calls"):
                # LLM决定不调用工具,返回最终答案
                final_answer = response.get("content")
                logger.info(f"ReAct循环结束: 获得最终答案 (长度: {len(final_answer) if final_answer else 0}字符)")

                # 保存对话历史
                messages.append({
                    "role": "assistant",
                    "content": final_answer
                })
                self.conversation_history = messages[1:]  # 排除system prompt

                return final_answer

            # Act: 执行工具调用
            self.state = AgentState.TOOL_EXECUTION

            # 将LLM的响应添加到消息历史
            assistant_message = {
                "role": "assistant",
                # Claude(Bedrock) 不允许空文本块，这里给出占位，避免下游网关报校验错误
                "content": response.get("content") or "(tool call)",
                "tool_calls": response["tool_calls"]
            }
            # 保留Gemini原生parts（如果有），用于下一轮请求
            if "_gemini_original_parts" in response:
                assistant_message["_gemini_original_parts"] = response["_gemini_original_parts"]
            messages.append(assistant_message)

            # 执行所有工具调用
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_call_id = tool_call["id"]

                # 调试日志：打印完整的tool_call结构
                logger.info(f"原始tool_call: {json.dumps(tool_call, ensure_ascii=False)}")

                try:
                    # 解析参数
                    arguments_str = tool_call["function"]["arguments"]
                    logger.info(f"arguments字符串: {arguments_str!r} (类型: {type(arguments_str).__name__})")

                    if isinstance(arguments_str, str):
                        arguments = json.loads(arguments_str) if arguments_str.strip() else {}
                    elif isinstance(arguments_str, dict):
                        arguments = arguments_str
                    else:
                        logger.warning(f"未知的arguments类型: {type(arguments_str)}, 使用空字典")
                        arguments = {}
                    # 只对需要文件隔离的工具注入conversation_id
                    # web_search、url_fetch等工具不需要conversation_id
                    if tool_name in ("code_executor", "shell_executor", "file_reader", "file_list"):
                        try:
                            if self.current_conversation_id:
                                arguments["conversation_id"] = self.current_conversation_id
                        except Exception:
                            pass
                    logger.info(f"执行工具: {tool_name}, 参数: {arguments}")

                    # 执行工具
                    tool_result: ToolResult = self.tool_registry.execute(tool_name, arguments)

                    # 记录工具执行结果
                    if tool_result.success:
                        logger.info(f"工具执行成功: {tool_name}")
                        logger.info(f"  返回数据预览: {str(tool_result.data)[:300]}...")
                        result_message = self._format_tool_success_message(tool_result)

                        # 如果是计划工具，推送结构化plan更新，便于前端渲染特有样式
                        if tool_name == 'create_plan':
                            try:
                                plan_dict = None
                                if isinstance(tool_result.data, dict):
                                    plan_dict = tool_result.data.get('plan') or tool_result.data
                                if plan_dict:
                                    yield {
                                        "type": "plan_update",
                                        "plan": plan_dict,
                                        "summary": tool_result.data.get('summary') if isinstance(tool_result.data, dict) else None
                                    }
                            except Exception as _:
                                pass
                    else:
                        logger.warning(f"工具执行失败: {tool_name}")
                        logger.warning(f"  错误类型: {tool_result.error_type}")
                        logger.warning(f"  错误信息: {tool_result.error_message}")
                        result_message = self._format_tool_failure_message(tool_result)

                except Exception as e:
                    logger.error(f"工具执行异常: {tool_name}, error={str(e)}")
                    result_message = f"工具执行失败: {str(e)}"

                # 添加工具结果到消息历史
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": result_message
                }
                # 保存tool消息
                if self.message_callback:
                    self.message_callback(tool_message)
                    logger.info(f"已通过回调保存tool消息: {tool_name}")

                messages.append(tool_message)

                logger.info(f"工具结果已反馈给LLM: {tool_name} (消息长度: {len(result_message)}字符)")

            # 继续下一轮循环,让LLM看到工具结果后决定下一步

        # 达到最大迭代次数
        logger.warning(f"达到最大迭代次数 {self.max_iterations},强制结束")
        return "抱歉,任务执行超时,请简化你的请求后重试。"

    def _react_loop_with_progress(self, user_input: str):
        """ReAct循环（流式进度版本）: Reason → Act → Observe

        Args:
            user_input: 用户输入

        Yields:
            进度更新或最终结果
        """
        # 构建包含历史的消息列表
        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt()
            }
        ]

        # 添加历史对话 (可能需要压缩)
        conversation_to_use = self.conversation_history

        # 计算context使用情况
        temp_messages = messages + conversation_to_use + [{"role": "user", "content": user_input}]
        context_stats = self.context_manager.calculate_usage(temp_messages)

        logger.info(f"Context使用情况: {context_stats['usage_percent']}% ({context_stats['total_tokens']}/{context_stats['max_tokens']})")

        # 返回context统计信息
        yield {
            "type": "context_stats",
            "stats": context_stats
        }

        # 检查是否需要压缩
        if context_stats["should_compress"] and len(conversation_to_use) > 2:
            logger.info("触发context压缩...")

            # 通知前端开始压缩
            yield {
                "type": "compression_start",
                "message": "💾 对话历史即将超出上下文窗口,正在智能压缩...",
                "stats": context_stats
            }

            # 执行压缩
            compressed_history = self.context_manager.compress_conversation_history(
                conversation_history=conversation_to_use,
                llm_client=self.llm
            )

            # 更新对话历史
            self.conversation_history = compressed_history
            conversation_to_use = compressed_history

            # 重新计算压缩后的使用率
            temp_messages = messages + conversation_to_use + [{"role": "user", "content": user_input}]
            new_stats = self.context_manager.calculate_usage(temp_messages)

            logger.info(f"压缩完成: {len(self.conversation_history)}条消息, 新使用率: {new_stats['usage_percent']}%")

            # 通知前端压缩完成
            yield {
                "type": "compression_done",
                "message": f"✓ 压缩完成 · 使用率 {context_stats['usage_percent']}% → {new_stats['usage_percent']}%",
                "old_stats": context_stats,
                "new_stats": new_stats
            }

        # 添加对话历史到messages
        messages.extend(conversation_to_use)

        # 添加当前用户输入
        messages.append({
            "role": "user",
            "content": user_input
        })

        # 获取所有可用工具的schema
        tools = self.tool_registry.get_function_calling_schemas()

        logger.info(f"ReAct循环开始: 可用工具={[t['function']['name'] for t in tools]}")

        # ReAct迭代
        for iteration in range(self.max_iterations):
            logger.info(f"ReAct迭代 {iteration + 1}/{self.max_iterations}")

            # 发送迭代进度
            yield {
                "type": "progress",
                "message": f"💭 第{iteration + 1}轮思考...",
                "status": f"🔄 迭代 {iteration + 1}/{self.max_iterations}"
            }

            # Reason: LLM决策（流式）
            self.state = AgentState.REASONING

            # 验证并修复消息格式（防止tool_calls没有对应响应导致API错误）
            messages = self._validate_and_fix_messages(messages)

            stream = self.llm.chat(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=16384,  # 16K，足够生成复杂视频代码
                stream=True  # 启用流式
            )

            # 处理流式响应
            response = None
            thinking_content = ""
            content_buffer = ""  # 缓存content，等确定是否有tool_calls再决定如何展示

            try:
                for chunk in stream:
                    logger.info(f"收到流式chunk: type={chunk.get('type')}, keys={list(chunk.keys())}")

                    if chunk.get("type") == "reasoning":
                        # 思考过程（打字机效果）
                        thinking_content = chunk.get("full_reasoning", "")
                        yield {
                            "type": "thinking",
                            "content": chunk.get("delta", ""),
                            "full_content": thinking_content
                        }
                    elif chunk.get("type") == "content":
                        # 普通内容 - 先缓存，等确定是否有tool_calls再决定展示方式
                        content_buffer = chunk.get("full_content", "")
                        # 不在这里yield，避免重复展示
                    elif chunk.get("type") == "retry":
                        # LLM重试提示 → 转为progress供前端展示
                        att = chunk.get("attempt") or 0
                        mx = chunk.get("max_retries") or 0
                        delay = chunk.get("delay") or 0
                        reason = chunk.get("reason") or "请求失败"
                        yield {
                            "type": "progress",
                            "message": f"⚠️ LLM请求失败（{reason}），{delay}s后进行第{att + 1}次重试...",
                            "status": f"重试 {att}/{mx}"
                        }
                    elif chunk.get("type") == "retry_exhausted":
                        rsn = chunk.get("reason") or "请求失败"
                        # 同步messages到conversation_history
                        self.conversation_history = [msg for msg in messages if msg.get("role") != "system"]
                        yield {
                            "type": "final",
                            "result": {"status": "failed", "error": f"LLM请求失败（{rsn}），重试已达上限，请稍后重试"}
                        }
                        return
                    elif chunk.get("type") == "error":
                        msg = chunk.get("message") or "LLM请求失败"
                        # 同步messages到conversation_history
                        self.conversation_history = [msg for msg in messages if msg.get("role") != "system"]
                        yield {"type": "final", "result": {"status": "failed", "error": msg}}
                        return
                    elif chunk.get("type") == "done":
                        response = chunk.get("response")
                        break
            except Exception as e:
                logger.error(f"处理LLM流异常: {e}")
                # 同步messages到conversation_history
                self.conversation_history = [msg for msg in messages if msg.get("role") != "system"]
                yield {"type": "final", "result": {"status": "failed", "error": "LLM连接异常，请稍后重试"}}
                return

            # 记录LLM响应
            logger.info(f"LLM响应: content={response.get('content')[:200] if response.get('content') else 'None'}...")
            if response.get("tool_calls"):
                logger.info(f"LLM决策: 调用{len(response['tool_calls'])}个工具")
                for tc in response["tool_calls"]:
                    logger.info(f"  - {tc['function']['name']}({tc['function']['arguments'][:100]}...)")

                # 有tool_calls时，如果有content_buffer，展示为accompanying text
                if content_buffer:
                    yield {
                        "type": "tool_call_text",
                        "content": content_buffer,
                        "full_content": content_buffer
                    }

            # 检查是否返回最终答案
            if not response.get("tool_calls"):
                # LLM决定不调用工具,返回最终答案
                final_answer = response.get("content")
                logger.info(f"ReAct循环结束: 获得最终答案 (长度: {len(final_answer) if final_answer else 0}字符)")

                # 保存assistant最终答案消息
                assistant_message = {
                    "role": "assistant",
                    "content": final_answer
                }
                if self.message_callback:
                    self.message_callback(assistant_message)
                    logger.info("已通过回调保存assistant最终答案")

                messages.append(assistant_message)

                # 完成
                self.state = AgentState.COMPLETED

                # 同步messages到conversation_history（排除system prompt）
                self.conversation_history = [msg for msg in messages if msg.get("role") != "system"]
                logger.info(f"同步对话历史: {len(self.conversation_history)}条消息")

                yield {
                    "type": "final",
                    "result": {
                        "status": "success",
                        "result": final_answer,
                        "message": "任务执行成功"
                    }
                }
                return

            # Act: 执行工具调用
            self.state = AgentState.TOOL_EXECUTION

            # 将LLM的响应添加到消息历史
            assistant_message = {
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": response["tool_calls"]
            }
            # 保留Gemini原生parts（如果有），用于下一轮请求
            if "_gemini_original_parts" in response:
                assistant_message["_gemini_original_parts"] = response["_gemini_original_parts"]
            # 保存assistant消息（带tool_calls）
            if self.message_callback:
                self.message_callback(assistant_message)
                logger.info(f"已通过回调保存assistant消息(带{len(response['tool_calls'])}个tool_calls)")

            messages.append(assistant_message)

            # 执行所有工具调用
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_call_id = tool_call["id"]

                # 调试日志：打印完整的tool_call结构
                logger.info(f"原始tool_call: {json.dumps(tool_call, ensure_ascii=False)}")

                try:
                    # 解析参数
                    arguments_str = tool_call["function"]["arguments"]
                    logger.info(f"arguments字符串: {arguments_str!r} (类型: {type(arguments_str).__name__})")

                    if isinstance(arguments_str, str):
                        arguments = json.loads(arguments_str) if arguments_str.strip() else {}
                    elif isinstance(arguments_str, dict):
                        arguments = arguments_str
                    else:
                        logger.warning(f"未知的arguments类型: {type(arguments_str)}, 使用空字典")
                        arguments = {}

                    # 🔧 Fallback: 如果code_executor缺少code参数，尝试从content中提取
                    if tool_name == "code_executor" and "code" not in arguments:
                        content = response.get("content") or ""
                        if content:
                            import re
                            # 尝试提取python代码块
                            code_match = re.search(r'```python\s*\n(.*?)\n```', content, re.DOTALL)
                            if code_match:
                                arguments["code"] = code_match.group(1).strip()
                                logger.warning(f"⚠️ code参数缺失，从content中提取了 {len(arguments['code'])} 字符的代码（fallback）")
                            else:
                                # 尝试提取任意代码块
                                code_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
                                if code_match:
                                    arguments["code"] = code_match.group(1).strip()
                                    logger.warning(f"⚠️ code参数缺失，从content提取了通用代码块 {len(arguments['code'])} 字符（fallback）")

                    # 对code_executor强制注入conversation_id，避免LLM参数覆盖/缺失
                    # 强制对需要会话上下文的工具注入正确的 conversation_id
                    if tool_name in ("code_executor", "shell_executor", "file_reader", "file_list", "tts_local", "media_ffmpeg", "tts_google", "tts_azure"):
                        try:
                            arguments["conversation_id"] = self.current_conversation_id
                        except Exception:
                            pass
                    logger.info(f"执行工具: {tool_name}, 参数: {arguments}")

                    # 发送工具执行进度（更现代的图标映射）
                    tool_emoji = {"web_search": "🔎", "url_fetch": "🌐", "code_executor": "🛠"}.get(tool_name, "•")
                    args_preview = str(arguments)[:80] + "..." if len(str(arguments)) > 80 else str(arguments)
                    yield {
                        "type": "progress",
                        "message": f"{tool_emoji} 执行工具: {tool_name}\n参数: {args_preview}",
                        "status": f"⚙️ 调用 {tool_name}"
                    }

                    # 执行工具 (带心跳)
                    # 启动工具执行线程
                    result_container = {"result": None, "completed": False}

                    def execute_tool_thread():
                        try:
                            result_container["result"] = self.tool_registry.execute(tool_name, arguments)
                        except Exception as e:
                            logger.error(f"工具执行线程异常: {e}")
                            from src.tools.result import create_failure_result, ErrorType
                            # 线程内异常时，返回规范化的失败结果
                            result_container["result"] = create_failure_result(
                                tool_name=tool_name,
                                tool_type="atomic",
                                error_type=ErrorType.TOOL_EXECUTION_ERROR,
                                error_message=str(e)
                            )
                        finally:
                            result_container["completed"] = True

                    execute_thread = threading.Thread(target=execute_tool_thread, daemon=True)
                    execute_thread.start()

                    # 等待完成,期间yield心跳
                    start_time = time.time()
                    last_heartbeat = 0
                    heartbeat_interval = 10

                    while not result_container["completed"]:
                        elapsed = int(time.time() - start_time)

                        # 每隔10秒yield心跳
                        if elapsed >= last_heartbeat + heartbeat_interval and elapsed > 0:
                            yield {
                                "type": "progress",
                                "message": f"⏳ {tool_name} 执行中...已等待 {elapsed} 秒",
                                "status": f"⏳ 等待 {tool_name}"
                            }
                            last_heartbeat = elapsed

                        time.sleep(1)

                    tool_result = result_container["result"]

                    # 记录工具执行结果
                    if tool_result.success:
                        logger.info(f"工具执行成功: {tool_name}")
                        logger.info(f"  返回数据预览: {str(tool_result.data)[:300]}...")
                        result_message = self._format_tool_success_message(tool_result)

                        # 发送成功进度（使用更简洁现代的勾号符号）
                        yield {
                            "type": "progress",
                            "message": f"✓ {tool_name} 执行完成",
                            "status": f"📊 处理 {tool_name} 结果"
                        }

                        # 如果工具生成了文件,发送文件列表给前端
                        if hasattr(tool_result, 'generated_files') and tool_result.generated_files:
                            # 仅发送真实存在且可预览的文件，避免前端出现无用标签
                            existing = self._filter_existing_files(tool_result.generated_files)
                            previewable = self._filter_previewable(existing)
                            if previewable:
                                yield {
                                    "type": "files_generated",
                                    "files": previewable
                                }
                    else:
                        logger.warning(f"工具执行失败: {tool_name}")
                        logger.warning(f"  错误类型: {tool_result.error_type}")
                        logger.warning(f"  错误信息: {tool_result.error_message}")
                        result_message = self._format_tool_failure_message(tool_result)

                        # 发送失败进度（使用警示符号 !）
                        yield {
                            "type": "progress",
                            "message": f"! {tool_name} 执行失败: {tool_result.error_message[:100]}",
                            "status": f"⚠️ {tool_name} 失败"
                        }

                except Exception as e:
                    logger.error(f"工具执行异常: {tool_name}, error={str(e)}")
                    result_message = f"工具执行失败: {str(e)}"

                    # 发送异常进度（使用警示符号 !）
                    yield {
                        "type": "progress",
                        "message": f"✗ {tool_name} 执行异常: {str(e)[:100]}",
                        "status": f"❌ {tool_name} 异常"
                    }

                # 添加工具结果到消息历史
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": result_message
                }
                # 保存tool消息
                if self.message_callback:
                    self.message_callback(tool_message)
                    logger.info(f"已通过回调保存tool消息: {tool_name}")

                messages.append(tool_message)

                logger.info(f"工具结果已反馈给LLM: {tool_name} (消息长度: {len(result_message)}字符)")

            # 继续下一轮循环,让LLM看到工具结果后决定下一步

        # 达到最大迭代次数
        logger.warning(f"达到最大迭代次数 {self.max_iterations},强制结束")
        self.state = AgentState.FAILED

        # 同步messages到conversation_history
        self.conversation_history = [msg for msg in messages if msg.get("role") != "system"]
        logger.info(f"同步对话历史(超时): {len(self.conversation_history)}条消息")

        yield {
            "type": "final",
            "result": {
                "status": "failed",
                "result": "抱歉,任务执行超时,请简化你的请求后重试。",
                "message": "达到最大迭代次数"
            }
        }

    def _build_system_prompt(self) -> str:
        """构建系统提示词（优化版 - Just Right原则）

        Returns:
            系统提示词
        """
        from datetime import datetime
        import pytz

        # 获取当前时间 (中国时区)
        china_tz = pytz.timezone('Asia/Shanghai')
        current_time = datetime.now(china_tz)
        current_datetime = current_time.strftime("%Y年%m月%d日 %H:%M")
        current_year = current_time.year
        current_month = current_time.month

        # 获取工具列表（分组展示）
        tool_names = self.tool_registry.list_tools()

        # 按功能分组工具
        tts_tools = [t for t in tool_names if 'tts' in t.lower()]
        image_tools = [t for t in tool_names if 'image' in t.lower()]
        video_tools = [t for t in tool_names if 'video' in t.lower()]
        music_tools = [t for t in tool_names if 'music' in t.lower()]
        core_tools = [t for t in tool_names if t in ['web_search', 'url_fetch', 'code_executor', 'file_reader', 'file_list', 'file_editor', 'plan']]
        other_tools = [t for t in tool_names if t not in tts_tools + image_tools + video_tools + music_tools + core_tools]

        # 获取当前工作目录文件列表（简化版 - 只显示最近20个）
        try:
            conv_id = getattr(self, 'current_conversation_id', None)
            root_dir = Path(self.config.output_dir)
            conv_dir = root_dir / conv_id if conv_id else None
            if conv_dir and conv_dir.exists():
                files = sorted(
                    [(p.stat().st_mtime, p.name) for p in conv_dir.iterdir() if p.is_file()],
                    reverse=True
                )
                workspace_files = "\n".join(f"- {name}" for _, name in files[:20]) if files else "- (empty)"
            else:
                workspace_files = "- (empty)"
        except Exception:
            workspace_files = "- (empty)"

        return f"""你是Wenning，一个专业的创意工作流自动化助手。

## 核心能力

你可以帮助用户完成：
- 信息检索与整理（搜索热点、查询资料、获取最新信息）
- 数据分析与可视化（数据统计、生成报告和图表）
- 多模态内容生成（图像、视频、音频、音乐）
- 文件管理与编辑

## 环境信息

**当前时间**: {current_datetime} (北京时间)
**当前年份**: {current_year}年
**工作目录**: outputs/{conv_id or '[会话ID]'}
**现有文件**（最近20个）:
{workspace_files}

## 可用工具

### 核心工具
{chr(10).join(f'- {t}' for t in core_tools)}

### 多模态生成工具

#### 语音合成（TTS）
{chr(10).join(f'- {t}' for t in tts_tools)}

**选择建议**: 中文内容且需要情感表达 → tts_minimax；多语言/标准应用 → tts_google/tts_azure；快速原型 → tts_local

#### 图像生成
{chr(10).join(f'- {t}' for t in image_tools)}

**选择建议**:
- 艺术创作/创意设计 → image_generation_minimax（支持宽高比16:9等和prompt优化）
- 精确尺寸需求 → text_to_image_minimax（支持width×height精确控制）
- 数据图表/技术图形 → code_executor（PIL/matplotlib完全可控）

#### 视频生成
{chr(10).join(f'- {t}' for t in video_tools)}

**选择建议**:
- 自然场景短视频 → video_generation_minimax（AI生成6秒视频）
- 数据动画/算法演示 → code_executor + matplotlib.animation
- 视频剪辑/字幕特效 → code_executor + moviepy

#### 音乐生成
{chr(10).join(f'- {t}' for t in music_tools)}

### 其他工具
{chr(10).join(f'- {t}' for t in other_tools)}

## 工作原则

### 文件处理
- **输出路径**: 所有生成的文件使用简单文件名（如 `chart.png`, `report.xlsx`），不使用绝对路径或相对路径，系统会自动处理存储位置
- **文件引用**: 在回复内容中引用文件时，必须只使用文件名（如 `ai_trend_1.png`），不要使用任何路径前缀（如 `/mnt/data/`, `sandbox:/`, 等）
- **读取文件**: 使用 `file_reader` 工具，列出文件使用 `file_list` 工具
- **支持格式**: 图片（.png/.jpg）、表格（.xlsx）、网页（.html）、视频（.mp4）、音频（.mp3/.wav）

### 代码执行
- **环境**: Python 3.x，已安装pandas/numpy/matplotlib/PIL/moviepy/playwright等常用库
- **视频兼容性**: 生成mp4时使用yuv420p像素格式和libx264编码确保兼容性
- **中文支持**: matplotlib中文会自动显示，moviepy使用系统注入的 `_MOVIEPY_FONT_CONFIG` 变量
- **限制**: 不能使用subprocess/os.system，网络操作通过工具完成

### 信息获取
- **时效性**: 搜索时在query中包含年份（如"{current_year}年"）确保结果时效性
- **多源验证**: 重要信息通过多次搜索或不同来源验证

### 多轮对话
- 保持上下文连贯性，理解用户的指代关系（如"继续"、"那个文件"）
- 主动理解上下文，避免重复询问

## 任务执行框架

遵循 ReAct 循环（Reason → Act → Observe）：

1. **理解需求**: 分析用户意图，识别任务类型，制定执行计划
2. **选择工具**: 根据任务特点选择最合适的工具
3. **评估结果**: 检查返回数据质量，判断是否需要补充信息
4. **迭代优化**: 根据结果调整策略，必要时重试或补充操作
5. **生成答案**: 整合结果，提供结构化且有洞察的回答

## 质量标准

好的工作成果：
- 基于真实数据，不编造信息
- 结构清晰，有具体数据支撑
- 提供洞察和建议，不只罗列事实
- 文件生成成功并可访问

当搜索结果不理想、代码执行失败、信息不完整时，应该主动调整策略并重试。
"""

    def _format_tool_success_message(self, result: ToolResult) -> str:
        """格式化工具成功消息

        Args:
            result: 工具执行结果

        Returns:
            格式化的消息
        """
        # 将data转为JSON字符串
        return json.dumps({
            "status": "success",
            "data": result.data
        }, ensure_ascii=False)

    def _format_tool_failure_message(self, result: ToolResult) -> str:
        """格式化工具失败消息

        Args:
            result: 工具执行结果

        Returns:
            格式化的消息
        """
        # 提供详细的错误信息,帮助LLM理解问题
        return json.dumps({
            "status": "failed",
            "error_type": result.error_type.value if result.error_type else "unknown",
            "error_message": result.error_message,
            "partial_results": result.partial_results,
            "recovery_suggestions": result.recovery_suggestions
        }, ensure_ascii=False)

    def switch_model(self, model_name: str):
        """切换LLM模型

        Args:
            model_name: 新模型名称
        """
        self.llm.switch_model(model_name)
        logger.info(f"MasterAgent切换模型: {model_name}")

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态

        Returns:
            状态信息
        """
        return {
            "state": self.state.value,
            "model": self.llm.model_name,
            "available_tools": self.tool_registry.list_tools(),
            "conversation_turns": len(self.conversation_history) // 2
        }

    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history = []
        logger.info("对话历史已清空")
