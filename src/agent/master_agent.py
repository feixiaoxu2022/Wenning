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

    def __init__(self, config: Config, tool_registry: ToolRegistry, model_name: str = "glm-4.7", conv_manager=None):
        """初始化Master Agent

        Args:
            config: 全局配置
            tool_registry: 工具注册中心
            model_name: 使用的LLM模型
            conv_manager: 对话管理器（用于路径转换）
        """
        self.config = config
        self.llm = LLMClient(config, model_name)
        self.tool_registry = tool_registry
        self.state = AgentState.IDLE
        self.max_iterations = 100  # 最大ReAct迭代次数
        self.conversation_history = []  # 多轮对话历史
        self.current_conversation_id = None
        self.message_callback = None  # 消息保存回调函数
        self.conv_manager = conv_manager  # 对话管理器

        # 初始化Context Manager（自动识别模型context window大小）
        self.context_manager = ContextManager(
            model_name=model_name
            # max_tokens参数已移除，将自动根据模型名称推断：
            # - Claude系列: 200K
            # - Gemini 1.5: 1M
            # - GPT-4 Turbo/4o: 128K
            # - GLM-4/Deepseek: 128K
        )

        logger.info(f"MasterAgent初始化完成: model={model_name}, tools={len(tool_registry.list_tools())}")

    def _filter_existing_files(self, files):
        """过滤文件列表，保留在线URL和本地文件

        注意：不再检查文件是否真实存在，直接信任工具返回的generated_files，
        避免因文件写入延迟导致的文件被过滤问题。
        """
        try:
            root_dir = Path(self.config.output_dir)
        except Exception:
            root_dir = Path("outputs")

        existing = []
        for name in files:
            try:
                # 如果是在线URL，直接保留
                if isinstance(name, str) and name.startswith(('http://', 'https://')):
                    existing.append(name)
                    continue

                # 本地文件：直接信任工具返回，不检查文件是否存在
                # （避免因文件写入延迟导致检查失败）
                if self.current_conversation_id:
                    existing.append(name)
            except Exception:
                continue
        return existing

    def _filter_previewable(self, files):
        """过滤可预览文件，与前端ui.js的支持类型保持一致"""
        allowed = {
            # 图片
            '.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp', '.avif',
            # 表格与演示
            '.xlsx', '.pptx',
            # 音频
            '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac',
            # 视频
            '.mp4', '.webm', '.mov',
            # 文档
            '.html', '.pdf', '.jsonl', '.json', '.md',
            # 文本/代码（前端支持语法高亮预览）
            '.txt', '.log', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.xml',
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs',
            '.c', '.cpp', '.h', '.cs', '.rb', '.php', '.sh', '.bash', '.zsh', '.sql'
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
                        # 移除tool_calls字段，但保留其他字段（特别是_gemini_original_parts）
                        logger.info(f"[消息验证] 消息#{i}: 移除不完整的tool_calls")
                        fixed_msg = dict(msg)  # 复制所有字段
                        fixed_msg.pop('tool_calls', None)  # 移除tool_calls
                        # 确保有content
                        if not fixed_msg.get('content'):
                            fixed_msg['content'] = '(工具调用进行中...)'
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

    def _inject_pending_images_to_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将待注入的图片添加到消息列表（从conversation state读取）

        Args:
            messages: 原始消息列表

        Returns:
            添加了图片的消息列表
        """
        if not self.conv_manager or not self.current_conversation_id:
            return messages

        # 从conversation state读取图片列表
        pending_images = self.conv_manager.get_images_to_view(self.current_conversation_id)

        if not pending_images:
            return messages

        from src.utils.image_processor import ImageProcessor
        from pathlib import Path as _Path

        # 构造multimodal content
        content_parts = []

        for img_data in pending_images:
            try:
                img_path = img_data["path"]
                detail_level = img_data.get("detail", "auto")

                # 构造完整路径
                output_dir_name = self.conv_manager.get_output_dir_name(self.current_conversation_id)
                full_path = _Path("outputs") / output_dir_name / img_path

                if not full_path.exists():
                    logger.warning(f"待注入图片不存在: {full_path}")
                    continue

                # 根据当前使用的模型选择合适的格式
                model_name = self.llm.model_name.lower()

                if 'claude' in model_name or 'anthropic' in model_name:
                    # Anthropic格式
                    img_content = ImageProcessor.build_anthropic_content([str(full_path)], detail_level)
                    content_parts.extend(img_content)
                    logger.info(f"  - 已转换图片(Anthropic格式): {img_path} (detail={detail_level})")
                elif 'gemini' in model_name:
                    # Gemini格式
                    img_content = ImageProcessor.build_gemini_content([str(full_path)], detail_level)
                    content_parts.extend(img_content)
                    logger.info(f"  - 已转换图片(Gemini格式): {img_path} (detail={detail_level})")
                else:
                    # OpenAI格式（默认）
                    img_content = ImageProcessor.build_openai_content([str(full_path)], detail_level)
                    content_parts.extend(img_content)
                    logger.info(f"  - 已转换图片(OpenAI格式): {img_path} (detail={detail_level})")

            except Exception as e:
                logger.error(f"处理待注入图片失败: {img_data}, error={e}")
                import traceback
                traceback.print_exc()

        if content_parts:
            # 在最后一条tool消息之后插入图片消息
            # 策略：如果最后一条消息是tool，在后面插入；否则在最后插入
            last_tool_idx = -1
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get('role') == 'tool':
                    last_tool_idx = i
                    break

            # 构造图片消息（作为user消息）
            image_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"以下是待查看的{len(content_parts)}张图片，请查看并分析："}
                ] + content_parts
            }

            # 插入到合适的位置
            if last_tool_idx >= 0:
                messages.insert(last_tool_idx + 1, image_message)
                logger.info(f"已在tool消息#{last_tool_idx}后插入图片消息")
            else:
                messages.append(image_message)
                logger.info(f"已在消息列表末尾添加图片消息")

            # ⭐ 关键：注入后递减查看次数并移除已消耗的图片
            removed_count = self.conv_manager.decrement_views_and_cleanup(self.current_conversation_id)
            if removed_count > 0:
                logger.info(f"✓ 已自动移除 {removed_count} 张查看次数用尽的图片")

            remaining_count = len(pending_images) - removed_count
            logger.info(f"图片已注入，剩余 {remaining_count} 张图片在列表中（待下次查看）")
        else:
            logger.info(f"图片列表非空（{len(pending_images)}张），但无有效内容可注入")

        return messages

    def _react_loop(self, user_input: str) -> str:
        """ReAct循环: Reason → Act → Observe

        注意：此方法为非流式简化版本，不使用对话历史和压缩功能。
        主要用于测试或特殊场景。生产环境请使用 _react_loop_with_progress 方法。

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

        # 调试日志：打印传递给LLM的工具列表
        tool_names = [t['function']['name'] for t in tools]
        logger.info(f"ReAct循环开始: 可用工具数量={len(tools)}")
        logger.info(f"ReAct循环开始: 可用工具={tool_names}")
        logger.info(f"manage_images_view在tools中: {'manage_images_view' in tool_names}")

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

                    # 发送工具执行开始状态
                    tool_emoji = {"web_search": "🔎", "url_fetch": "🌐", "code_executor": "🛠"}.get(tool_name, "•")
                    args_preview = str(arguments)[:80] + "..." if len(str(arguments)) > 80 else str(arguments)
                    tool_start_time = time.time()
                    yield {
                        "type": "exec",
                        "iter": iteration + 1,
                        "phase": "start",
                        "tool": tool_name,
                        "args_preview": args_preview,
                        "ts": tool_start_time
                    }

                    # 执行工具
                    tool_result: ToolResult = self.tool_registry.execute(tool_name, arguments)

                    # 发送工具执行完成状态
                    tool_end_time = time.time()
                    yield {
                        "type": "exec",
                        "iter": iteration + 1,
                        "phase": "done",
                        "tool": tool_name,
                        "success": tool_result.success,
                        "elapsed_sec": int(tool_end_time - tool_start_time),
                        "ts": tool_end_time
                    }

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

        # 调试日志：检查即将使用的历史
        logger.info("=== Agent历史使用调试 ===")
        logger.info(f"self.conversation_history长度: {len(self.conversation_history)}")
        logger.info(f"conversation_to_use长度: {len(conversation_to_use)}")
        if conversation_to_use:
            logger.info(f"历史最后3条roles: {[msg.get('role') for msg in conversation_to_use[-3:]]}")
        else:
            logger.info("对话历史为空（这是第一条消息或历史已清空）")

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
            old_history_len = len(conversation_to_use)
            compressed_history = self.context_manager.compress_conversation_history(
                conversation_history=conversation_to_use,
                llm_client=self.llm
            )

            # 检查压缩是否成功
            if compressed_history == conversation_to_use:
                logger.warning("压缩未生效，保持原始历史")
                # 通知前端压缩失败
                yield {
                    "type": "compression_failed",
                    "message": "⚠️  压缩未生效，继续使用原始对话历史",
                    "stats": context_stats
                }
            else:
                # 更新对话历史
                self.conversation_history = compressed_history
                conversation_to_use = compressed_history

                # 重新计算压缩后的使用率
                temp_messages = messages + conversation_to_use + [{"role": "user", "content": user_input}]
                new_stats = self.context_manager.calculate_usage(temp_messages)

                logger.info(f"压缩完成: {old_history_len}条 → {len(compressed_history)}条消息, 使用率: {context_stats['usage_percent']}% → {new_stats['usage_percent']}%")

                # 通知前端压缩完成
                yield {
                    "type": "compression_done",
                    "message": f"✓ 压缩完成 · 使用率 {context_stats['usage_percent']}% → {new_stats['usage_percent']}%",
                    "old_stats": context_stats,
                    "new_stats": new_stats
                }

        # 添加对话历史到messages
        messages.extend(conversation_to_use)

        # 记录历史消息数量（用于后续追加新消息）
        history_message_count = len(conversation_to_use)

        # 检查是否有待附加的图片
        user_content = user_input  # 默认纯文本
        if self.conv_manager and self.current_conversation_id:
            images_data = self.conv_manager.get_images_to_view(self.current_conversation_id)
            pending_images = [img["path"] for img in images_data] if images_data else []
            if pending_images:
                logger.info(f"检测到{len(pending_images)}张待附加图片，构造multimodal消息")

                # 构造multimodal content
                import base64
                from pathlib import Path as _Path

                content_parts = [{"type": "text", "text": user_input}]

                for img_path in pending_images:
                    try:
                        # 读取图片文件
                        full_path = _Path("outputs") / img_path
                        if not full_path.exists():
                            logger.warning(f"图片文件不存在: {full_path}")
                            continue

                        # 读取并转base64
                        with open(full_path, "rb") as f:
                            image_bytes = f.read()

                        # 检测图片类型
                        ext = full_path.suffix.lower()
                        mime_types = {
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.png': 'image/png',
                            '.gif': 'image/gif',
                            '.webp': 'image/webp',
                            '.bmp': 'image/bmp'
                        }
                        mime_type = mime_types.get(ext, 'image/jpeg')

                        # 压缩大图片（避免token超限）
                        if len(image_bytes) > 2 * 1024 * 1024:  # 大于2MB
                            try:
                                from PIL import Image
                                import io
                                img = Image.open(full_path)
                                # 压缩到最大1024px
                                img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                                buffer = io.BytesIO()
                                img.save(buffer, format='JPEG', quality=85)
                                image_bytes = buffer.getvalue()
                                mime_type = 'image/jpeg'
                                logger.info(f"图片已压缩: {full_path.name} ({len(image_bytes)/1024:.1f}KB)")
                            except Exception as e:
                                logger.warning(f"图片压缩失败，使用原图: {e}")

                        # 转base64
                        base64_str = base64.b64encode(image_bytes).decode('utf-8')

                        # 添加图片到content（OpenAI格式）
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_str}"
                            }
                        })
                        logger.info(f"图片已添加: {full_path.name} ({len(image_bytes)/1024:.1f}KB, {mime_type})")

                    except Exception as e:
                        logger.error(f"处理图片失败: {img_path}, error={e}")
                        import traceback
                        traceback.print_exc()

                # 使用multimodal content
                if len(content_parts) > 1:
                    user_content = content_parts
                    logger.info(f"Multimodal消息构造完成: {len(content_parts)-1}张图片")

                # 清空pending_images
                self.conv_manager.clear_images_to_view(self.current_conversation_id)

        # 添加当前用户输入
        messages.append({
            "role": "user",
            "content": user_content
        })

        # 最终确认日志：检查即将发送给LLM的完整messages
        logger.info(f"=== 即将发送给LLM的messages ===")
        logger.info(f"总消息数: {len(messages)} (system=1, history={history_message_count}, current_user=1)")
        logger.info(f"messages结构: {[m.get('role') for m in messages]}")
        if len(messages) > 5:
            logger.info(f"最后5条消息roles: {[m.get('role') for m in messages[-5:]]}")

        # 获取所有可用工具的schema
        tools = self.tool_registry.get_function_calling_schemas()

        # 调试日志：打印传递给LLM的工具列表
        tool_names = [t['function']['name'] for t in tools]
        logger.info(f"ReAct循环开始(streaming): 可用工具数量={len(tools)}")
        logger.info(f"ReAct循环开始(streaming): 可用工具={tool_names}")
        logger.info(f"manage_images_view在tools中(streaming): {'manage_images_view' in tool_names}")

        # 追踪连续content_filter次数，防止无限循环
        consecutive_content_filter_count = 0
        max_content_filter_retries = 3

        # ReAct迭代
        for iteration in range(self.max_iterations):
            logger.info(f"ReAct迭代 {iteration + 1}/{self.max_iterations}")

            # 本轮开始
            yield {"type": "iter_start", "iter": iteration + 1, "ts": time.time()}

            # Reason: LLM决策（流式）
            self.state = AgentState.REASONING

            # 验证并修复消息格式（防止tool_calls没有对应响应导致API错误）
            messages = self._validate_and_fix_messages(messages)

            # === 视觉控制：从conversation state读取并注入图片 ===
            messages = self._inject_pending_images_to_messages(messages)

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
                            "full_content": thinking_content,
                            "iter": iteration + 1,
                            "ts": time.time()
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
                            "type": "note",
                            "delta": f"⚠️ LLM请求失败（{reason}），{delay}s后进行第{att + 1}次重试...",
                            "iter": iteration + 1,
                            "ts": time.time()
                        }
                    elif chunk.get("type") == "retry_exhausted":
                        rsn = chunk.get("reason") or "请求失败"
                        # 同步messages到conversation_history（只追加本轮新消息）
                        new_messages_start_idx = 1 + history_message_count
                        new_messages = [msg for msg in messages[new_messages_start_idx:] if msg.get("role") != "system"]
                        self.conversation_history.extend(new_messages)
                        yield {
                            "type": "final",
                            "result": {"status": "failed", "error": f"LLM请求失败（{rsn}），重试已达上限，请稍后重试"}
                        }
                        return
                    elif chunk.get("type") == "error":
                        msg = chunk.get("message") or "LLM请求失败"
                        # 同步messages到conversation_history（只追加本轮新消息）
                        new_messages_start_idx = 1 + history_message_count
                        new_messages = [msg for msg in messages[new_messages_start_idx:] if msg.get("role") != "system"]
                        self.conversation_history.extend(new_messages)
                        yield {"type": "final", "result": {"status": "failed", "error": msg}}
                        return
                    elif chunk.get("type") == "done":
                        response = chunk.get("response")
                        break
            except Exception as e:
                logger.error(f"处理LLM流异常: {e}")
                # 同步messages到conversation_history（只追加本轮新消息）
                new_messages_start_idx = 1 + history_message_count
                new_messages = [msg for msg in messages[new_messages_start_idx:] if msg.get("role") != "system"]
                self.conversation_history.extend(new_messages)
                yield {"type": "final", "result": {"status": "failed", "error": "LLM连接异常，请稍后重试"}}
                return

            # 记录LLM响应
            logger.info(f"LLM响应: content={response.get('content')[:200] if response.get('content') else 'None'}...")

            # 检查是否为content_filter响应
            finish_reason = response.get("finish_reason")
            if finish_reason == "content_filter":
                logger.warning(f"检测到content_filter响应，直接终止对话")

                # 第一次触发就终止，不再重试（避免历史污染导致后续请求失败）
                self.conversation_history = [msg for msg in messages if msg.get("role") != "system"]
                yield {
                    "type": "final",
                    "result": {
                        "status": "content_filter",  # 特殊状态，前端用温和样式显示
                        "error": "您的请求触发了内容审核\n\n为了遵守平台内容安全规范，当前对话已终止。\n\n💡 建议：\n• 开启新对话，换一种表达方式\n• 切换到其他模型（GPT/Claude）\n• 简化问题描述，避免敏感词汇"
                    }
                }
                return
            else:
                # 正常响应，重置计数器
                consecutive_content_filter_count = 0

            if response.get("tool_calls"):
                logger.info(f"LLM决策: 调用{len(response['tool_calls'])}个工具")
                for tc in response["tool_calls"]:
                    logger.info(f"  - {tc['function']['name']}({tc['function']['arguments'][:100]}...)")

                # 🔧 FIX: Claude不会stream content当有tool_calls时，而是作为完整块返回
                # 优先使用content_buffer（如果有streaming），否则使用response.get("content")
                accompanying_text = content_buffer or response.get("content", "")

                if accompanying_text:
                    yield {
                        "type": "note",
                        "delta": accompanying_text,
                        "iter": iteration + 1,
                        "ts": time.time()
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

                # 同步messages到conversation_history
                # 注意：如果本轮做了压缩，self.conversation_history已经是压缩后的版本
                # 只需追加本轮新增的消息（从user_input开始的所有消息）
                # messages结构：[0]=system, [1:1+history_message_count]=历史, [1+history_message_count:]=本轮新增
                new_messages_start_idx = 1 + history_message_count
                new_messages = [msg for msg in messages[new_messages_start_idx:] if msg.get("role") != "system"]

                # 追加新消息到对话历史（保持压缩后的历史不变）
                self.conversation_history.extend(new_messages)
                logger.info(f"同步对话历史: 追加{len(new_messages)}条新消息, 总计{len(self.conversation_history)}条")

                # 最后一轮结束
                yield {"type": "iter_done", "iter": iteration + 1, "status": "success", "ts": time.time()}
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
                    if tool_name in ("code_executor", "shell_executor", "file_reader", "file_list", "tts_local", "media_ffmpeg", "tts_google", "tts_azure", "file_writer", "file_editor", "create_plan"):
                        try:
                            arguments["conversation_id"] = self.current_conversation_id
                            # 统一注入完整目录名，避免每个工具重复转换
                            if hasattr(self, 'conv_manager') and self.conv_manager:
                                arguments["_output_dir_name"] = self.conv_manager.get_output_dir_name(self.current_conversation_id)
                        except Exception:
                            pass
                    logger.info(f"执行工具: {tool_name}, 参数: {arguments}")

                    # 发送工具执行进度（更现代的图标映射）
                    tool_emoji = {"web_search": "🔎", "url_fetch": "🌐", "code_executor": "🛠"}.get(tool_name, "•")
                    args_preview = str(arguments)[:80] + "..." if len(str(arguments)) > 80 else str(arguments)
                    tool_start_time = time.time()  # 记录工具开始时间
                    logger.info(f"⏱️ [工具执行] {tool_name} 开始执行 (ts={tool_start_time})")
                    yield {
                        "type": "exec",
                        "iter": iteration + 1,
                        "phase": "start",
                        "tool": tool_name,
                        "args_preview": args_preview,
                        "ts": tool_start_time
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
                                "type": "exec",
                                "iter": iteration + 1,
                                "phase": "heartbeat",
                                "tool": tool_name,
                                "elapsed_sec": elapsed,
                                "ts": time.time()
                            }
                            last_heartbeat = elapsed

                        time.sleep(1)

                    tool_result = result_container["result"]

                    # 记录工具执行结果
                    if tool_result.success:
                        tool_end_time = time.time()
                        elapsed_time = tool_end_time - tool_start_time
                        logger.info(f"⏱️ [工具执行] {tool_name} 执行成功 (耗时={elapsed_time:.3f}s)")
                        logger.info(f"  返回数据预览: {str(tool_result.data)[:300]}...")
                        result_message = self._format_tool_success_message(tool_result)

                        # 发送成功进度（使用更简洁现代的勾号符号）
                        yield {
                            "type": "exec",
                            "iter": iteration + 1,
                            "phase": "done",
                            "tool": tool_name,
                            "message": "执行完成",
                            "success": True,
                            "ts": tool_end_time,
                            "elapsed": elapsed_time  # 添加耗时信息
                        }

                        # 如果工具生成了文件,发送文件列表给前端
                        if hasattr(tool_result, 'generated_files') and tool_result.generated_files:
                            # 仅发送真实存在且可预览的文件，避免前端出现无用标签
                            existing = self._filter_existing_files(tool_result.generated_files)
                            previewable = self._filter_previewable(existing)
                            if previewable:
                                yield {
                                    "type": "files_generated",
                                    "iter": iteration + 1,
                                    "files": previewable,
                                    "ts": time.time()
                                }

                        # === 兼容性支持：工具返回inject_images时自动添加到conversation state ===
                        if hasattr(tool_result, 'inject_images') and tool_result.inject_images:
                            image_detail = getattr(tool_result, 'image_detail', 'auto')
                            logger.info(f"工具请求注入{len(tool_result.inject_images)}张图片 (detail={image_detail})")

                            # 自动添加到conversation state（默认查看1次）
                            if self.conv_manager and self.current_conversation_id:
                                success = self.conv_manager.add_images_to_view(
                                    self.current_conversation_id,
                                    tool_result.inject_images,
                                    image_detail,
                                    view_count=1  # 默认1次后自动移除
                                )
                                if success:
                                    logger.info(f"  - 已自动添加{len(tool_result.inject_images)}张图片到查看列表（查看1次后移除）")
                                else:
                                    logger.warning(f"  - 自动添加图片到查看列表失败")

                            # 发送files事件，让前端知道这些图片会被LLM查看
                            yield {
                                "type": "exec",
                                "iter": iteration + 1,
                                "phase": "files",
                                "files": tool_result.inject_images,
                                "message": f"已准备{len(tool_result.inject_images)}张图片供LLM查看",
                                "ts": time.time()
                            }
                    else:
                        tool_end_time = time.time()
                        elapsed_time = tool_end_time - tool_start_time
                        logger.warning(f"⏱️ [工具执行] {tool_name} 执行失败 (耗时={elapsed_time:.3f}s)")
                        logger.warning(f"  错误类型: {tool_result.error_type}")
                        logger.warning(f"  错误信息: {tool_result.error_message}")
                        result_message = self._format_tool_failure_message(tool_result)

                        # 发送失败进度（使用警示符号 !）
                        yield {
                            "type": "exec",
                            "iter": iteration + 1,
                            "phase": "error",
                            "tool": tool_name,
                            "message": tool_result.error_message[:200] if tool_result.error_message else "执行失败",
                            "success": False,
                            "ts": tool_end_time,
                            "elapsed": elapsed_time  # 添加耗时信息
                        }

                except Exception as e:
                    logger.error(f"工具执行异常: {tool_name}, error={str(e)}")
                    result_message = f"工具执行失败: {str(e)}"

                    # 发送异常进度（使用警示符号 !）
                    yield {
                        "type": "exec",
                        "iter": iteration + 1,
                        "phase": "error",
                        "tool": tool_name,
                        "message": str(e)[:200],
                        "success": False,
                        "ts": time.time()
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

            # 本轮结束（工具已执行），等待下一轮
            yield {"type": "iter_done", "iter": iteration + 1, "status": "success", "ts": time.time()}
            # 继续下一轮循环,让LLM看到工具结果后决定下一步

        # 达到最大迭代次数
        logger.warning(f"达到最大迭代次数 {self.max_iterations},强制结束")
        self.state = AgentState.FAILED

        # 同步messages到conversation_history
        # 注意：如果本轮做了压缩，self.conversation_history已经是压缩后的版本
        # 只需追加本轮新增的消息
        new_messages_start_idx = 1 + history_message_count
        new_messages = [msg for msg in messages[new_messages_start_idx:] if msg.get("role") != "system"]
        self.conversation_history.extend(new_messages)
        logger.info(f"同步对话历史(超时): 追加{len(new_messages)}条新消息, 总计{len(self.conversation_history)}条")

        yield {
            "type": "final",
            "result": {
                "status": "failed",
                "result": "抱歉,任务执行超时,请简化你的请求后重试。",
                "message": "达到最大迭代次数"
            }
        }

    def _get_python_env_info(self) -> str:
        """获取Python环境关键库的版本信息

        Returns:
            格式化的环境信息字符串
        """
        # 定义需要检测的常用库
        common_libraries = [
            'pandas', 'numpy', 'matplotlib', 'PIL', 'moviepy',
            'requests', 'openpyxl', 'playwright', 'pptx'
        ]

        versions = []
        for lib_name in common_libraries:
            try:
                # 特殊处理：PIL实际包名是Pillow
                if lib_name == 'PIL':
                    lib = __import__(lib_name)
                    from PIL import __version__
                    version = __version__
                else:
                    lib = __import__(lib_name)
                    version = lib.__version__

                versions.append(f"{lib_name}={version}")
            except ImportError:
                pass  # 库未安装，跳过
            except AttributeError:
                pass  # 没有__version__属性，跳过
            except Exception:
                pass  # 其他异常，跳过

        if versions:
            return f"- **已安装库版本**: {', '.join(versions)}"
        else:
            return ""

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

        # 获取Python环境信息
        python_env_info = self._get_python_env_info()

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
**会话ID**: {conv_id or '[会话ID]'}
**工作目录**: outputs/{conv_id or '[会话ID]'}/
**现有文件**（最近20个）:
{workspace_files}

**重要**: 调用需要conversation_id参数的工具（如tts_minimax、image_generation_minimax等）时，只传递会话ID本身（如 "{conv_id or '[会话ID]'}"），不要包含"outputs/"路径前缀

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
- **支持格式**: 图片（.png/.jpg）、表格（.xlsx）、PPT演示文稿（.pptx）、网页（.html）、视频（.mp4）、音频（.mp3/.wav）

### 代码执行
- **环境**: Python 3.x
{python_env_info}
- **执行模式**:
  - 短代码（<50行）：使用code_executor的code参数直接执行
  - 长代码（≥50行）：建议先用file_writer保存为.py文件，再用code_executor的script_file参数执行（便于调试和迭代修改）
- **导入规范**:
  - moviepy必须使用 `from moviepy.editor import ...` 或 `import moviepy.editor`（注意是editor不是edit）
  - 其他常用库已安装：pandas, numpy, matplotlib, PIL, openpyxl, requests等
- **视频兼容性**: 生成mp4时使用yuv420p像素格式和libx264编码确保兼容性
- **中文显示**:
  - matplotlib包含中文时必须先设置字体避免乱码：`matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'Microsoft YaHei']`
  - moviepy的TextClip使用中文时需指定font参数，如：`TextClip("中文", font='/System/Library/Fonts/PingFang.ttc', fontsize=40)`
- **限制**: 不能使用subprocess/os.system，网络操作通过工具完成

### 信息获取
- **时效性**: 搜索时在query中包含年份（如"{current_year}年"）确保结果时效性
- **多源验证**: 重要信息通过多次搜索或不同来源验证

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
        """格式化工具成功消息（优化版：压缩冗余信息）

        Args:
            result: 工具执行结果

        Returns:
            格式化的消息
        """
        data = result.data
        tool_name = result.tool_name

        # 🔧 针对不同工具做精简优化
        if tool_name == "code_executor":
            # Code Executor：只保留关键信息，删除冗长的stdout/stderr
            optimized_data = {
                "status": "success",
                "generated_files": data.get("generated_files", [])
            }
            # 只在有stderr时才保留（通常是警告）
            if data.get("stderr") and data["stderr"].strip():
                # 只保留最后5行stderr（通常是最关键的错误信息）
                stderr_lines = data["stderr"].strip().split('\n')
                optimized_data["stderr_summary"] = '\n'.join(stderr_lines[-5:]) if len(stderr_lines) > 5 else data["stderr"]

            # 如果stdout很短（<200字符），可以保留；否则只保留最后3行
            stdout = data.get("stdout", "")
            if stdout and len(stdout) < 200:
                optimized_data["stdout"] = stdout
            elif stdout:
                stdout_lines = stdout.strip().split('\n')
                if len(stdout_lines) > 3:
                    optimized_data["stdout_summary"] = '\n'.join(stdout_lines[-3:]) + f"\n[前{len(stdout_lines)-3}行已省略]"
                else:
                    optimized_data["stdout"] = stdout

            return json.dumps({"status": "success", "data": optimized_data}, ensure_ascii=False)

        elif tool_name == "web_search":
            # Web Search：限制每个结果的snippet长度
            optimized_data = dict(data)
            if "results" in optimized_data:
                for result in optimized_data["results"]:
                    if "snippet" in result and len(result["snippet"]) > 300:
                        result["snippet"] = result["snippet"][:300] + "..."
            return json.dumps({"status": "success", "data": optimized_data}, ensure_ascii=False)

        elif tool_name == "url_fetch":
            # URL Fetch：限制内容长度
            optimized_data = dict(data)
            if "content" in optimized_data and len(optimized_data["content"]) > 2000:
                optimized_data["content"] = optimized_data["content"][:2000] + "\n[内容过长已截断，共" + str(len(data.get("content", ""))) + "字符]"
            return json.dumps({"status": "success", "data": optimized_data}, ensure_ascii=False)

        else:
            # 其他工具：保持原样
            return json.dumps({"status": "success", "data": data}, ensure_ascii=False)

    def _format_tool_failure_message(self, result: ToolResult) -> str:
        """格式化工具失败消息（优化版：只保留关键错误信息）

        Args:
            result: 工具执行结果

        Returns:
            格式化的消息
        """
        # 🔧 失败消息精简：只保留error_message，删除冗余字段
        # partial_results和recovery_suggestions在对话历史中价值不大
        return json.dumps({
            "status": "failed",
            "error_type": result.error_type.value if result.error_type else "unknown",
            "error_message": result.error_message
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
