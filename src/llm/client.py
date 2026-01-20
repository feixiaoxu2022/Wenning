"""LLM客户端模块

提供统一的LLM调用接口，支持多种模型切换。
"""

import requests
import time
import random
from typing import List, Dict, Optional, Any
from src.utils.config import Config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """统一LLM客户端

    支持通过model_name参数切换不同的LLM模型。
    """

    def __init__(self, config: Config, model_name: str = "ernie-5.0-thinking-preview"):
        """初始化LLM客户端

        Args:
            config: 配置对象
            model_name: 模型名称，默认为EB5
        """
        self.config = config
        self.model_name = model_name
        self.model_config = config.get_model_config(model_name)
        # 简单的重试策略：最多5次，指数退避基础间隔0.5s
        self.max_retries = 5
        self.retry_base_delay = 0.5

        logger.info(f"初始化LLMClient: model={model_name}, base_url={self.model_config['base_url']}")

    # ===== Claude native helpers =====
    def _is_claude(self) -> bool:
        return str(self.model_name).lower().startswith("claude")

    def _is_gemini(self) -> bool:
        """判断是否为Gemini模型"""
        return "gemini" in str(self.model_name).lower()

    def _build_claude_native_url(self) -> str:
        """构造Claude原生messages端点。
        优先使用配置CLAUDE_API_BASE_URL，否则从统一网关base_url替换成/v1/messages。
        """
        import urllib.parse
        base = self.model_config.get("base_url") or ""
        if getattr(self.config, 'claude_api_base_url', None):
            return self.config.claude_api_base_url
        try:
            u = urllib.parse.urlparse(base)
            return f"{u.scheme}://{u.netloc}/v1/messages"
        except Exception:
            return base

    def _convert_tools_to_anthropic(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        out = []
        for t in tools:
            fn = (t or {}).get("function") or {}
            out.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object"})
            })
        return out

    # ===== Gemini native helpers =====
    def _convert_tools_to_gemini(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """将OpenAI格式的tools转换为Gemini格式

        OpenAI: {"type": "function", "function": {"name": "...", "parameters": {...}}}
        Gemini: {"functionDeclarations": [{"name": "...", "parameters": {...}}]}
        """
        if not tools:
            return None

        declarations = []
        for t in tools:
            fn = (t or {}).get("function") or {}
            params = fn.get("parameters", {})

            # 转换参数类型为大写（Gemini要求）
            gemini_params = self._convert_schema_types_to_uppercase(params)

            declarations.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": gemini_params
            })

        return [{"functionDeclarations": declarations}]

    def _convert_schema_types_to_uppercase(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """递归转换schema中的type字段为大写（Gemini格式要求）

        object -> OBJECT, string -> STRING, integer -> INTEGER, array -> ARRAY
        """
        if not isinstance(schema, dict):
            return schema

        result = {}
        for key, value in schema.items():
            if key == "type" and isinstance(value, str):
                # 类型映射
                type_mapping = {
                    "object": "OBJECT",
                    "string": "STRING",
                    "integer": "INTEGER",
                    "number": "NUMBER",
                    "boolean": "BOOLEAN",
                    "array": "ARRAY"
                }
                result[key] = type_mapping.get(value.lower(), value.upper())
            elif isinstance(value, dict):
                result[key] = self._convert_schema_types_to_uppercase(value)
            elif isinstance(value, list):
                result[key] = [self._convert_schema_types_to_uppercase(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value

        return result

    def _convert_messages_to_contents(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将OpenAI格式的messages转换为Gemini格式的contents

        OpenAI: [{"role": "user/assistant/system", "content": "..."}]
        Gemini: [{"role": "user/model", "parts": [{"text": "..."}]}]

        注意：
        - system消息会被合并到第一个user消息前
        - assistant -> model
        - tool消息转换为functionResponse格式
        """
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")

            if role == "system":
                # Gemini将system作为独立配置，暂存
                system_instruction = content
                continue

            if role == "assistant":
                # assistant -> model
                gemini_role = "model"

                # 优先检查是否有Gemini原生parts（即使tool_calls被移除，也要使用）
                gemini_parts = msg.get("_gemini_original_parts")
                if gemini_parts:
                    # 直接使用原始parts，保留thoughtSignature等Gemini特有字段
                    contents.append({"role": gemini_role, "parts": gemini_parts})
                    continue  # 跳过后续处理

                # 检查是否有tool_calls（兼容非Gemini来源）
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    # 🔧 安全检查：Gemini模型的tool_calls必须有_gemini_original_parts
                    # 如果没有（旧版本消息），转换会缺少thoughtSignature导致400错误
                    # 解决方案：直接跳过这条消息，不拼接到contents里
                    if self._is_gemini() and not gemini_parts:
                        logger.warning(f"检测到旧版本assistant消息（有{len(tool_calls)}个tool_calls但无_gemini_original_parts），直接跳过不拼接")
                        continue  # 跳过这条消息
                    else:
                        # 转换为functionCall格式（兼容非Gemini来源的tool_calls）
                        parts = []
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            import json
                            try:
                                args = json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {})
                            except:
                                args = {}

                            parts.append({
                                "functionCall": {
                                    "name": fn.get("name", ""),
                                    "args": args
                                }
                            })

                        contents.append({"role": gemini_role, "parts": parts})
                else:
                    # 普通文本消息
                    if content:
                        contents.append({
                            "role": gemini_role,
                            "parts": [{"text": str(content)}]
                        })

            elif role == "user":
                # User消息：支持纯文本和multimodal
                if isinstance(content, str):
                    # 纯文本
                    contents.append({
                        "role": "user",
                        "parts": [{"text": str(content)}]
                    })
                elif isinstance(content, list):
                    # Multimodal消息
                    parts = []
                    for part in content:
                        if not isinstance(part, dict):
                            continue

                        part_type = part.get("type")
                        if part_type == "text":
                            # 文本部分
                            parts.append({"text": part.get("text", "")})
                        elif part_type == "image_url":
                            # 图片部分：转换OpenAI格式到Gemini格式
                            # OpenAI: {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
                            # Gemini: {"inline_data": {"mime_type": "image/jpeg", "data": "..."}}
                            image_url_obj = part.get("image_url", {})
                            data_url = image_url_obj.get("url", "")

                            # 解析data URL
                            if data_url.startswith("data:"):
                                try:
                                    header, base64_data = data_url.split(",", 1)
                                    mime_type = header.split(":")[1].split(";")[0]

                                    parts.append({
                                        "inline_data": {
                                            "mime_type": mime_type,
                                            "data": base64_data
                                        }
                                    })
                                except Exception as e:
                                    logger.warning(f"解析Gemini图片data URL失败: {e}")

                    if parts:
                        contents.append({"role": "user", "parts": parts})
                else:
                    # 其他类型，转为文本
                    contents.append({
                        "role": "user",
                        "parts": [{"text": str(content)}]
                    })

            elif role == "tool":
                # tool结果转换为functionResponse
                # 注意：Gemini要求functionResponse必须在user消息中，以保持user/model交替
                tool_name = msg.get("name", "unknown")
                tool_response = {
                    "functionResponse": {
                        "name": tool_name,
                        "response": {
                            "content": str(content)
                        }
                    }
                }
                contents.append({
                    "role": "user",  # functionResponse必须使用user role
                    "parts": [tool_response]
                })

        # 如果有system instruction，插入到开头（或作为配置返回）
        # 这里简化处理：如果有system，添加到第一个user消息前
        if system_instruction and contents:
            # 查找第一个user消息
            for i, c in enumerate(contents):
                if c.get("role") == "user":
                    # 将system instruction添加到该user消息的开头
                    parts = c.get("parts", [])
                    parts.insert(0, {"text": f"[System Instructions: {system_instruction}]\n\n"})
                    break

        # Gemini要求：必须user/model交替，且以user开始
        # 合并连续的相同role消息
        merged_contents = []
        for content_msg in contents:
            if not merged_contents:
                merged_contents.append(content_msg)
            elif merged_contents[-1]["role"] == content_msg["role"]:
                # 相同role，合并parts
                last_parts = merged_contents[-1]["parts"]
                current_parts = content_msg["parts"]

                # 智能合并：如果都是text，合并文本内容；否则直接extend
                if (len(last_parts) == 1 and "text" in last_parts[0] and
                    len(current_parts) == 1 and "text" in current_parts[0]):
                    # 合并两个text parts为一个
                    last_parts[0]["text"] += "\n\n" + current_parts[0]["text"]
                else:
                    # 其他情况（functionCall、functionResponse等）直接extend
                    merged_contents[-1]["parts"].extend(content_msg["parts"])
            else:
                merged_contents.append(content_msg)

        # 确保以user开始
        if merged_contents and merged_contents[0]["role"] != "user":
            merged_contents.insert(0, {
                "role": "user",
                "parts": [{"text": "Continue."}]
            })

        return merged_contents

    def _sanitize_inf_values(self, obj):
        """递归清理对象中的inf/-inf值，替换为None

        JSON标准不支持inf值，需要清理掉
        """
        import math

        if isinstance(obj, float):
            if math.isinf(obj) or math.isnan(obj):
                logger.warning(f"发现非法浮点数值: {obj}，替换为None")
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize_inf_values(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_inf_values(item) for item in obj]
        else:
            return obj

    def _remove_orphaned_tool_messages(self, msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """移除孤立的tool消息（没有对应tool_use的tool_result）

        Claude/Bedrock严格要求：tool消息必须紧跟在包含对应tool_use的assistant消息之后
        """
        cleaned = []
        last_assistant_tool_ids = set()

        for m in msgs:
            role = (m.get("role") or "").lower()

            if role == "assistant":
                # 重置并记录新的tool_use IDs
                last_assistant_tool_ids.clear()
                tcs = m.get("tool_calls") or []
                for tc in tcs:
                    tid = (tc or {}).get("id")
                    if tid:
                        last_assistant_tool_ids.add(tid)
                cleaned.append(m)

            elif role == "tool":
                # 验证tool_call_id
                tool_call_id = m.get("tool_call_id") or m.get("id") or ""
                if tool_call_id in last_assistant_tool_ids:
                    cleaned.append(m)
                    last_assistant_tool_ids.discard(tool_call_id)
                else:
                    logger.warning(f"[消息清理] 跳过孤立的tool消息: tool_call_id={tool_call_id}, last_assistant_tool_ids={last_assistant_tool_ids}")

            elif role == "user":
                # user消息打断序列，清空tool_ids
                last_assistant_tool_ids.clear()
                cleaned.append(m)

            else:
                # system等其他消息直接保留
                cleaned.append(m)

        removed_count = len(msgs) - len(cleaned)
        if removed_count > 0:
            logger.info(f"[消息清理] 移除了 {removed_count} 条孤立的tool消息")

        return cleaned

    def _build_anthropic_messages_payload(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]], temperature: float, max_tokens: Optional[int]) -> Dict[str, Any]:
        import json as _json
        system_parts: List[str] = []
        anth_msgs: List[Dict[str, Any]] = []

        # 跟踪最后一条assistant消息中的tool_use IDs（Claude要求tool_result必须在previous message中有对应tool_use）
        last_assistant_tool_ids: set = set()

        for m in messages:
            role = (m.get("role") or "user").lower()
            content = m.get("content")
            if role == "system":
                if isinstance(content, str):
                    system_parts.append(content)
                else:
                    system_parts.append(str(content))
                continue

            if role == "tool":
                # 工具结果 → user消息中的tool_result块
                tool_use_id = m.get("tool_call_id") or m.get("id") or ""

                # 验证：只有当tool_use_id在最后一条assistant消息中时才添加tool_result
                if tool_use_id not in last_assistant_tool_ids:
                    logger.warning(f"跳过孤立的tool消息: tool_call_id={tool_use_id} 没有在previous assistant消息中找到对应的tool_use")
                    logger.warning(f"  last_assistant_tool_ids={last_assistant_tool_ids}")
                    # 清空，因为序列已断
                    last_assistant_tool_ids.clear()
                    continue

                result_text = str(m.get("content") or "")
                anth_msgs.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": [{"type": "text", "text": result_text or "(empty)"}]
                        }
                    ]
                })
                # 工具结果添加后，从集合中移除这个ID
                # 防止重复的tool_result引用同一个tool_use_id
                last_assistant_tool_ids.discard(tool_use_id)
                continue

            if role == "assistant":
                # 重置：每次遇到新的assistant消息时，清空并记录新的tool_use IDs
                last_assistant_tool_ids.clear()

                blocks: List[Dict[str, Any]] = []
                if isinstance(content, str) and content.strip() and content != "(tool call)":
                    blocks.append({"type": "text", "text": content})
                tcs = m.get("tool_calls") or []
                for i, tc in enumerate(tcs):
                    fn = (tc or {}).get("function") or {}
                    name = fn.get("name", "")
                    args = fn.get("arguments")
                    try:
                        args_obj = _json.loads(args) if isinstance(args, str) else (args or {})
                    except Exception:
                        args_obj = {}
                    tid = (tc or {}).get("id") or f"tu_{int(time.time()*1000)}_{i}"

                    # 记录这个tool_use_id
                    last_assistant_tool_ids.add(tid)

                    blocks.append({
                        "type": "tool_use",
                        "id": tid,
                        "name": name,
                        "input": args_obj,
                    })
                if not blocks:
                    blocks = [{"type": "text", "text": content or "…"}]
                anth_msgs.append({"role": "assistant", "content": blocks})
                continue

            # 默认按user处理
            # 重要：遇到user消息时，清空last_assistant_tool_ids
            # 因为Claude要求tool_result必须在previous message中有对应tool_use
            # 一旦插入user消息，之后的tool_result就无法再引用前面的tool_use了
            last_assistant_tool_ids.clear()

            if isinstance(content, str):
                # 纯文本消息
                text = content if content.strip() else "…"
                anth_msgs.append({"role": "user", "content": [{"type": "text", "text": text}]})
            elif isinstance(content, list):
                # Multimodal消息（包含文本和图片）
                blocks: List[Dict[str, Any]] = []
                for part in content:
                    if not isinstance(part, dict):
                        continue

                    part_type = part.get("type")
                    if part_type == "text":
                        # 文本部分
                        blocks.append({"type": "text", "text": part.get("text", "")})
                    elif part_type == "image_url":
                        # 图片部分：转换OpenAI格式到Claude格式
                        # OpenAI: {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
                        # Claude: {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "..."}}
                        image_url_obj = part.get("image_url", {})
                        data_url = image_url_obj.get("url", "")

                        # 解析data URL: data:image/jpeg;base64,<base64_data>
                        if data_url.startswith("data:"):
                            try:
                                # 提取media_type和base64数据
                                header, base64_data = data_url.split(",", 1)
                                media_type = header.split(":")[1].split(";")[0]  # image/jpeg

                                blocks.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": base64_data
                                    }
                                })
                            except Exception as e:
                                logger.warning(f"解析图片data URL失败: {e}")

                if not blocks:
                    blocks = [{"type": "text", "text": "…"}]
                anth_msgs.append({"role": "user", "content": blocks})
            else:
                # 其他类型，转为文本
                text = str(content) if content else "…"
                anth_msgs.append({"role": "user", "content": [{"type": "text", "text": text}]})

        payload = {
            "model": self.model_config["model"],
            "messages": anth_msgs,
            "temperature": temperature,
            "max_tokens": int(max_tokens or 2048),
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        ant_tools = self._convert_tools_to_anthropic(tools)
        if ant_tools:
            payload["tools"] = ant_tools
            payload["tool_choice"] = {"type": "auto"}
        return payload

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ):
        """发送聊天请求

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 温度参数（0-1）
            max_tokens: 最大token数
            stream: 是否流式输出
            tools: Function Calling工具列表
            tool_choice: 工具选择策略 ("auto", "none", 或指定工具名)

        Returns:
            如果stream=True，返回生成器；否则返回响应字典

        Raises:
            requests.exceptions.RequestException: 请求失败
        """
        if stream:
            return self._chat_stream(messages, temperature, max_tokens, tools, tool_choice)
        else:
            return self._chat_non_stream(messages, temperature, max_tokens, tools, tool_choice)

    def _chat_non_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """非流式聊天请求

        Returns:
            响应字典，包含content、usage、tool_calls等信息
        """
        # 构建请求体
        # Claude(Bedrock)适配：不允许空content；最小化兼容（仍使用OAI样式，由网关转换）
        def _sanitize_msgs_for_claude(msgs: List[Dict[str, Any]]):
            out = []
            for m in msgs:
                c = m.get("content")
                if isinstance(c, str) and (c.strip() == "" or c is None):
                    m = dict(m)
                    m["content"] = "…"
                out.append(m)
            return out

        used_messages = messages
        used_tools = tools
        if str(self.model_name).lower().startswith("claude"):
            used_messages = _sanitize_msgs_for_claude(messages)
            # 清理孤立的tool消息（Bedrock后端严格要求）
            used_messages = self._remove_orphaned_tool_messages(used_messages)

        payload = {
            "model": self.model_config["model"],
            "messages": used_messages,
            "temperature": temperature,
            "stream": False
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Reasoning effort参数（仅OpenAI模型支持）
        if not str(self.model_name).lower().startswith("claude"):
            payload["reasoning_effort"] = "high"

        # Function Calling参数
        if used_tools:
            payload["tools"] = used_tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        # 构建headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.model_config['api_key']}"
        }
        if str(self.model_name).lower().startswith("claude"):
            headers["anthropic-version"] = headers.get("anthropic-version", "2023-06-01")

        # 记录请求日志（脱敏）
        if self.config.agent_enable_request_logging:
            try:
                msg_preview = [
                    {"role": m.get("role"), "len": len(m.get("content", ""))}
                    for m in (messages or [])
                ]
                logger.debug(
                    f"LLM请求: model={self.model_name}, stream=False, messages={msg_preview}, tools={len(tools) if tools else 0}, tool_choice={tool_choice}"
                )
            except Exception:
                pass

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self.model_config["base_url"],
                    headers=headers,
                    json=payload,
                    timeout=self.model_config["timeout"]
                )
                if response.status_code >= 400:
                    detail = None
                    try:
                        detail = response.text[:500]
                    except Exception:
                        detail = None
                    logger.error(
                        f"LLM非流式请求失败: status={response.status_code}, detail={detail}"
                    )
                    # 4xx(非429)不再重试，直接抛出
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        response.raise_for_status()
                response.raise_for_status()

                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0]["message"]
                    response_dict = {
                        "content": message.get("content"),
                        "model": self.model_name,
                        "usage": result.get("usage", {}),
                        "raw_response": result
                    }
                    if "tool_calls" in message:
                        response_dict["tool_calls"] = message["tool_calls"]
                    return response_dict
                else:
                    raise ValueError(f"无效的LLM响应格式: {result}")

            except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
                last_error = e
                # 若是4xx且非429，不重试
                try:
                    status = getattr(e.response, "status_code", None)
                except Exception:
                    status = None
                if status is not None and 400 <= status < 500 and status != 429:
                    logger.error(f"LLM请求失败(4xx,不重试): {e}")
                    raise
                if attempt >= self.max_retries:
                    logger.error(f"LLM请求失败且重试耗尽({attempt}/{self.max_retries}): {e}")
                    raise

                # 针对429速率限制使用更激进的退避策略
                if status == 429:
                    # 429错误：使用更长的指数退避，从2秒开始
                    delay = 2.0 * (2 ** (attempt - 1))  # 2s, 4s, 8s, 16s, 32s
                    delay += random.uniform(0, 1.0)  # 添加抖动避免雷鸣群效应
                    logger.warning(f"遇到速率限制(429)，使用长退避策略，重试第{attempt}/{self.max_retries}次，等待{delay:.2f}s: {e}")
                else:
                    # 其他错误：使用标准指数退避
                    delay = self.retry_base_delay * (2 ** (attempt - 1))
                    delay += random.uniform(0, self.retry_base_delay)
                    logger.warning(f"LLM请求失败，重试第{attempt}/{self.max_retries}次后重试，等待{delay:.2f}s: {e}")

                time.sleep(delay)

    def generate_code(
        self,
        task_description: str,
        context: Optional[str] = None,
        language: str = "python"
    ) -> str:
        """生成代码

        Args:
            task_description: 任务描述
            context: 上下文信息（如数据示例）
            language: 编程语言

        Returns:
            生成的代码字符串
        """
        system_prompt = f"""你是一个专业的{language}程序员。
根据用户的需求，生成简洁、可执行的代码。

要求：
1. 代码必须完整可执行
2. 包含必要的错误处理
3. 只输出代码，不要任何解释
4. 代码用```{language}包裹"""

        user_prompt = f"任务：{task_description}"
        if context:
            user_prompt += f"\n\n上下文：\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = self.chat(messages, temperature=0.2)  # 代码生成用低温度
        content = response["content"]

        # 提取代码块
        code = self._extract_code_block(content, language)

        logger.info(f"代码生成成功: {len(code)} characters")
        return code

    def analyze_text(
        self,
        text: str,
        analysis_type: str,
        instructions: Optional[str] = None
    ) -> str:
        """文本分析（情感、主题、摘要等）

        Args:
            text: 待分析文本
            analysis_type: 分析类型（sentiment/topic/summary）
            instructions: 额外指令

        Returns:
            分析结果
        """
        analysis_prompts = {
            "sentiment": "分析以下文本的情感倾向（正面/负面/中性），并给出理由。",
            "topic": "提取以下文本的核心主题和关键词。",
            "summary": "对以下文本进行简洁的摘要。"
        }

        system_prompt = analysis_prompts.get(analysis_type, "分析以下文本。")
        if instructions:
            system_prompt += f"\n\n额外要求：{instructions}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]

        response = self.chat(messages, temperature=0.3)
        return response["content"]

    def _extract_code_block(self, content: str, language: str) -> str:
        """从LLM响应中提取代码块

        Args:
            content: LLM响应内容
            language: 编程语言

        Returns:
            提取的代码
        """
        # 尝试提取```language code ```格式
        import re

        pattern = f"```{language}\\s*\\n(.*?)\\n```"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 尝试提取```code```格式
        pattern = "```\\s*\\n(.*?)\\n```"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            return match.group(1).strip()

        # 如果没有代码块标记，返回全部内容
        logger.warning("LLM响应中未找到代码块标记，返回全部内容")
        return content.strip()

    def switch_model(self, model_name: str):
        """切换模型

        Args:
            model_name: 新模型名称
        """
        self.model_name = model_name
        self.model_config = self.config.get_model_config(model_name)
        logger.info(f"切换模型: {model_name}")

    def _chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ):
        """流式聊天请求（生成器）

        Yields:
            流式响应块，包含delta内容
        """
        import json

        # 构建请求体
        # Claude(Bedrock)适配：不允许空content；最小化兼容（仍使用OAI样式，由网关转换）
        def _sanitize_msgs_for_claude(msgs: List[Dict[str, Any]]):
            out = []
            for m in msgs:
                c = m.get("content")
                if isinstance(c, str) and (c.strip() == "" or c is None):
                    m = dict(m)
                    m["content"] = "…"
                out.append(m)
            return out

        used_messages = messages
        used_tools = tools
        is_claude = self._is_claude()
        is_gemini = self._is_gemini()

        if is_claude:
            used_messages = _sanitize_msgs_for_claude(messages)
            # 清理孤立的tool消息（Bedrock后端严格要求）
            used_messages = self._remove_orphaned_tool_messages(used_messages)
            # 清理inf/nan值
            used_messages = self._sanitize_inf_values(used_messages)

        # ===== Gemini原生API =====
        if is_gemini:
            # 从base_url中提取主机名，构建Gemini原生API端点
            import urllib.parse
            parsed = urllib.parse.urlparse(self.model_config['base_url'])
            gemini_url = f"{parsed.scheme}://{parsed.netloc}/v1/models/{self.model_name}"
            headers_gemini = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.model_config['api_key']}"
            }

            # 构建Gemini格式payload
            gemini_contents = self._convert_messages_to_contents(messages)

            # 调试: 打印原始tools参数
            logger.info(f"[Gemini Debug] 接收到的tools参数: {tools is not None}, 数量: {len(tools) if tools else 0}")

            gemini_tools = self._convert_tools_to_gemini(tools)

            # 调试: 打印转换后的gemini_tools
            logger.info(f"[Gemini Debug] 转换后的gemini_tools: {gemini_tools is not None}, 内容: {gemini_tools if gemini_tools else 'None'}")

            payload_gemini = {
                "contents": gemini_contents
            }
            if gemini_tools:
                payload_gemini["tools"] = gemini_tools
                logger.info(f"[Gemini Debug] tools字段已添加到payload")
            else:
                logger.warning(f"[Gemini Debug] gemini_tools为空,未添加tools字段到payload")
            if temperature is not None:
                payload_gemini["generationConfig"] = {"temperature": temperature}
            if max_tokens:
                payload_gemini["generationConfig"] = payload_gemini.get("generationConfig", {})
                payload_gemini["generationConfig"]["maxOutputTokens"] = max_tokens

            logger.info(f"[Gemini] 使用原生API: {gemini_url}")
            logger.info(f"[Gemini] Payload: {json.dumps(payload_gemini, ensure_ascii=False)}")

            try:
                response = requests.post(
                    gemini_url,
                    headers=headers_gemini,
                    json=payload_gemini,
                    timeout=self.model_config["timeout"]
                )
                if response.status_code >= 400:
                    try:
                        error_detail = response.json()
                        logger.error(f"[Gemini] 请求失败详情: status={response.status_code}, error={json.dumps(error_detail, ensure_ascii=False)}")
                    except:
                        logger.error(f"[Gemini] 请求失败详情: status={response.status_code}, text={response.text[:500]}")
                response.raise_for_status()
                gemini_response = response.json()

                logger.info(f"[Gemini] 响应: {json.dumps(gemini_response, ensure_ascii=False)[:500]}")

                # 解析Gemini响应
                full_content = ""
                tool_calls_list = []
                gemini_parts_with_tool_calls = []  # 保存包含functionCall的原始parts

                candidates = gemini_response.get("candidates", [])
                if candidates:
                    candidate = candidates[0]
                    content_data = candidate.get("content", {})
                    parts = content_data.get("parts", [])

                    for part in parts:
                        # 调试：记录每个part的结构（用于发现新的思考字段）
                        logger.debug(f"[Gemini] Part keys: {list(part.keys())}")

                        # 思考过程（Gemini 2.0 Flash Thinking）
                        # Gemini将思考过程放在单独的part中，检查多种可能的字段名
                        thought_text = None
                        if "thought" in part:
                            thought_text = part.get("thought")
                        elif "thoughtText" in part:
                            thought_text = part.get("thoughtText")
                        elif "thinking" in part:
                            thought_text = part.get("thinking")

                        if thought_text:
                            logger.info(f"[Gemini] 发现思考过程: {len(thought_text)} 字符")
                            yield {"type": "reasoning", "delta": thought_text, "full_reasoning": thought_text}

                        # 文本内容
                        if "text" in part:
                            text = part["text"]
                            full_content += text
                            yield {"type": "content", "delta": text, "full_content": full_content}

                        # Function call
                        if "functionCall" in part:
                            # 保存原始part（包含thoughtSignature等所有字段）
                            gemini_parts_with_tool_calls.append(part)

                            fc = part["functionCall"]
                            tool_call_id = f"call_{int(time.time()*1000)}_{len(tool_calls_list)}"
                            tool_calls_list.append({
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": fc.get("name", ""),
                                    "arguments": json.dumps(fc.get("args", {}), ensure_ascii=False)
                                }
                            })

                # 构建最终响应
                final_response = {
                    "content": full_content or None,
                    "model": self.model_name,
                    "usage": gemini_response.get("usageMetadata", {}),
                    "raw_response": gemini_response
                }

                if tool_calls_list:
                    final_response["tool_calls"] = tool_calls_list
                    # 保存Gemini原生parts供下一轮使用
                    final_response["_gemini_original_parts"] = gemini_parts_with_tool_calls

                yield {"type": "done", "response": final_response}
                return

            except Exception as e:
                logger.error(f"[Gemini] 请求失败: {e}")
                # Gemini失败不fallback，直接抛出
                raise

        # 优先尝试Claude原生messages协议
        if is_claude and getattr(self.config, 'claude_force_native', True):
            native_url = self._build_claude_native_url()
            headers_native = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.model_config['api_key']}",
                "anthropic-version": "2023-06-01"
            }
            # 使用清理过的messages（包含inf/nan清理和孤立tool消息移除）
            payload_native = self._build_anthropic_messages_payload(used_messages, tools, temperature, max_tokens)
            payload_native["stream"] = True

            # 清理inf/nan值（JSON不支持）
            payload_native = self._sanitize_inf_values(payload_native)

            try:
                response = requests.post(
                    native_url,
                    headers=headers_native,
                    json=payload_native,
                    timeout=self.model_config["timeout"],
                    stream=True
                )
                if response.status_code < 400:
                    # 解析Anthropic流式
                    full_content = ""
                    tool_uses: Dict[str, Dict[str, Any]] = {}
                    last_tool_id: Optional[str] = None
                    for raw in response.iter_lines():
                        if not raw:
                            continue
                        line = raw.decode('utf-8', errors='ignore')
                        if not line.startswith('data: '):
                            continue
                        data_str = line[6:]
                        if not data_str.strip() or data_str.strip() == "[DONE]":
                            continue
                        try:
                            evt = json.loads(data_str)
                        except Exception:
                            continue

                        et = evt.get("type")
                        # 关键调试：打印所有事件
                        logger.info(f"[Claude流式事件] type={et}, event={json.dumps(evt, ensure_ascii=False)[:300]}")

                        if et == "content_block_start":
                            block = evt.get("content_block", {})
                            if block.get("type") == "tool_use":
                                tid = block.get("id") or f"tu_{int(time.time()*1000)}"
                                tool_uses[tid] = {"name": block.get("name", ""), "input_str": "", "input": block.get("input")}
                                last_tool_id = tid
                                logger.debug(f"流式tool_use开始: id={tid}, name={block.get('name')}, input={block.get('input')}")
                        elif et == "content_block_delta":
                            delta = evt.get("delta", {})
                            delta_type = delta.get("type")
                            logger.debug(f"流式delta: type={delta_type}, keys={list(delta.keys())}")
                            if delta_type == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    full_content += text
                                    yield {"type": "content", "delta": text, "full_content": full_content}
                            elif delta_type == "input_json_delta":
                                # Claude流式tool_use的正确类型是input_json_delta，不是其他
                                partial = delta.get("partial_json")
                                if partial and last_tool_id and last_tool_id in tool_uses:
                                    tool_uses[last_tool_id]["input_str"] += partial
                                    logger.debug(f"累积tool input: {len(tool_uses[last_tool_id]['input_str'])} 字符")
                            else:
                                # 旧逻辑兼容：如果不是text_delta，尝试提取partial_json
                                partial = delta.get("partial_json")
                                if partial and last_tool_id and last_tool_id in tool_uses:
                                    tool_uses[last_tool_id]["input_str"] += partial
                                    logger.debug(f"累积tool input(fallback): {len(tool_uses[last_tool_id]['input_str'])} 字符")
                        elif et == "content_block_stop":
                            if last_tool_id and last_tool_id in tool_uses:
                                info = tool_uses[last_tool_id]
                                if info.get("input") is None and info.get("input_str"):
                                    try:
                                        info["input"] = json.loads(info["input_str"]) or {}
                                    except Exception:
                                        info["input"] = {}
                            last_tool_id = None
                        elif et == "message_stop":
                            break
                        else:
                            # 其它事件忽略（message_start, ping, ...）
                            pass

                    final_response = {
                        "content": full_content or None,
                        "model": self.model_name,
                        "usage": {},
                        "raw_response": {}
                    }
                    tool_calls = []
                    for tid, info in tool_uses.items():
                        name = info.get("name") or ""
                        args_obj = info.get("input")
                        input_str = info.get("input_str") or ""

                        logger.info(f"流式tool_use完成: id={tid}, name={name}, input={args_obj}, input_str_len={len(input_str)}")

                        # 修复：如果input为空或None，尝试从input_str解析
                        if not args_obj or args_obj is None:
                            s = input_str
                            try:
                                args_obj = json.loads(s) if s else {}
                                logger.info(f"从input_str解析参数成功: {len(str(args_obj))} 字符")
                            except Exception as e:
                                logger.error(f"从input_str解析参数失败: {e}, input_str={s[:200]}")
                                args_obj = {}
                        tool_calls.append({
                            "id": tid,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args_obj, ensure_ascii=False)}
                        })
                    if tool_calls:
                        final_response["tool_calls"] = tool_calls
                    yield {"type": "done", "response": final_response}
                    return
                else:
                    # Claude native API返回非200，直接报错（不再fallback）
                    error_msg = f"Claude原生API失败: status={response.status_code}"
                    try:
                        error_detail = response.json()
                        error_msg += f", detail={error_detail}"
                    except:
                        error_msg += f", text={response.text[:500]}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            except Exception as e:
                # Claude native API异常，直接抛出（不再fallback）
                logger.error(f"Claude原生messages请求失败: {e}")
                raise

        # —— OAI ChatCompletions 常规流式 ——
        payload = {
            "model": self.model_config["model"],
            "messages": used_messages,
            "temperature": temperature,
            "stream": True
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Reasoning effort参数（仅OpenAI模型支持）
        if not is_claude:
            payload["reasoning_effort"] = "high"

        if used_tools:
            payload["tools"] = used_tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.model_config['api_key']}"
        }
        if is_claude:
            headers["anthropic-version"] = headers.get("anthropic-version", "2023-06-01")

        # 记录请求日志（脱敏）
        if self.config.agent_enable_request_logging:
            try:
                msg_preview = []
                for m in (used_messages or []):
                    role = m.get("role")
                    content = m.get("content", "")

                    # 详细记录multimodal消息结构
                    if isinstance(content, list):
                        # Multimodal消息：记录每个part的类型和大小
                        parts_info = []
                        for part in content:
                            if isinstance(part, dict):
                                part_type = part.get("type")
                                if part_type == "text":
                                    text_len = len(part.get("text", ""))
                                    parts_info.append(f"text({text_len}chars)")
                                elif part_type == "image_url":
                                    image_url = part.get("image_url", {}).get("url", "")
                                    if image_url.startswith("data:"):
                                        # 提取mime type和base64长度
                                        try:
                                            header, base64_data = image_url.split(",", 1)
                                            mime = header.split(":")[1].split(";")[0]
                                            base64_len = len(base64_data)
                                            parts_info.append(f"image({mime},{base64_len}chars_base64)")
                                        except:
                                            parts_info.append("image(unknown)")
                                    else:
                                        parts_info.append(f"image({image_url[:50]}...)")
                        msg_preview.append({"role": role, "content": parts_info})
                    elif isinstance(content, str):
                        msg_preview.append({"role": role, "content_len": len(content)})
                    else:
                        msg_preview.append({"role": role, "content_type": type(content).__name__})

                logger.debug(
                    f"LLM流式请求: model={self.model_name}, stream=True, messages={msg_preview}, tools={len(tools) if tools else 0}, tool_choice={tool_choice}"
                )
            except Exception as e:
                logger.warning(f"记录请求日志失败: {e}")

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                # 发送流式请求
                response = requests.post(
                    self.model_config["base_url"],
                    headers=headers,
                    json=payload,
                    timeout=self.model_config["timeout"],
                    stream=True
                )
                if response.status_code >= 400:
                    detail = None
                    try:
                        detail = response.text[:500]
                    except Exception:
                        detail = None
                    logger.error(
                        f"LLM流式请求失败: status={response.status_code}, detail={detail}"
                    )
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        response.raise_for_status()
                response.raise_for_status()

                # 累积完整响应用于最终返回
                full_content = ""
                full_reasoning = ""
                full_tool_calls = []
                current_tool_call = None

                # 逐块处理SSE流
                for line in response.iter_lines():
                    if not line:
                        continue

                    line = line.decode('utf-8')

                    # SSE格式：data: {...}
                    if line.startswith('data: '):
                        data_str = line[6:]  # 移除 "data: " 前缀

                        # 检查是否为流结束标记
                        if data_str.strip() == '[DONE]':
                            break

                        try:
                            chunk = json.loads(data_str)

                            # 记录原始chunk用于调试
                            logger.debug(f"原始chunk: {json.dumps(chunk, ensure_ascii=False)[:500]}")

                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})

                                # 🔍 调试日志：查看delta中的所有字段
                                if delta:
                                    logger.info(f"[Thinking Debug] Delta keys: {list(delta.keys())}, model={self.model_name}")
                                    # 打印可能的thinking相关字段
                                    for key in ["reasoning", "reasoning_content", "thoughts", "thinking", "internal_thoughts"]:
                                        if key in delta:
                                            logger.info(f"[Thinking Debug] Found {key}: {delta[key][:100] if delta[key] else '(empty)'}")

                                # 处理reasoning字段（思考过程）
                                # 兼容多种协议：reasoning（ERNIE-5等）、reasoning_content（OpenAI O系列、Deepseek等）
                                reasoning_delta = delta.get("reasoning") or delta.get("reasoning_content")
                                if reasoning_delta:
                                    full_reasoning += reasoning_delta

                                    # yield思考过程增量
                                    yield {
                                        "type": "reasoning",
                                        "delta": reasoning_delta,
                                        "full_reasoning": full_reasoning
                                    }

                                # 处理内容增量
                                if "content" in delta and delta["content"]:
                                    content_delta = delta["content"]
                                    full_content += content_delta

                                    # yield内容增量
                                    yield {
                                        "type": "content",
                                        "delta": content_delta,
                                        "full_content": full_content
                                    }

                                # 处理tool_calls增量
                                if "tool_calls" in delta:
                                    # 🔍 GLM-4.7调试：记录每个tool_call delta
                                    if self.model_name == "glm-4.7":
                                        logger.info(f"[GLM-4.7 Debug] tool_calls delta: {json.dumps(delta['tool_calls'], ensure_ascii=False)}")

                                    for tc_delta in delta["tool_calls"]:
                                        index = tc_delta.get("index", 0)

                                        # 确保有足够的tool_call槽位
                                        while len(full_tool_calls) <= index:
                                            full_tool_calls.append({
                                                "id": "",
                                                "type": "function",
                                                "function": {"name": "", "arguments": ""}
                                            })

                                        # 更新tool_call
                                        if "id" in tc_delta:
                                            full_tool_calls[index]["id"] = tc_delta["id"]
                                        if "function" in tc_delta:
                                            if "name" in tc_delta["function"]:
                                                full_tool_calls[index]["function"]["name"] = tc_delta["function"]["name"]
                                            if "arguments" in tc_delta["function"]:
                                                full_tool_calls[index]["function"]["arguments"] += tc_delta["function"]["arguments"]

                        except json.JSONDecodeError:
                            logger.warning(f"无法解析流式响应块: {data_str}")
                            continue

                # 流结束后返回完整响应
                final_response = {
                    "content": full_content if full_content else None,
                    "model": self.model_name,
                    "usage": {},
                    "raw_response": {}
                }
                if full_tool_calls:
                    final_response["tool_calls"] = full_tool_calls
                yield {"type": "done", "response": final_response}
                return

            except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
                last_error = e
                try:
                    status = getattr(e.response, "status_code", None)
                except Exception:
                    status = None

                # 尝试解析错误响应体，提取详细错误信息
                error_detail = None
                error_type = None
                user_friendly_message = None

                if hasattr(e, 'response') and e.response is not None:
                    try:
                        response_text = e.response.text
                        error_data = json.loads(response_text)

                        # Azure OpenAI错误格式: {"error": {"message": "...", "code": "..."}}
                        if isinstance(error_data, dict) and "error" in error_data:
                            error_obj = error_data["error"]
                            error_detail = error_obj.get("message", "")
                            error_code = error_obj.get("code", "")

                            # 识别content_filter错误
                            if "content" in error_detail.lower() and ("filter" in error_detail.lower() or "policy" in error_detail.lower() or "management" in error_detail.lower()):
                                error_type = "content_filter"
                                user_friendly_message = "您的请求触发了内容安全策略，请修改后重试。如果您认为这是误判，请尝试换一种表达方式。"
                            # 识别deployment被封禁（通常是content_filter的副作用）
                            elif "deployment" in error_detail.lower() and ("not exist" in error_detail.lower() or "not found" in error_detail.lower()):
                                error_type = "deployment_blocked"
                                user_friendly_message = "⚠️ API服务暂时不可用\n\n可能原因：\n• 之前的请求触发了内容审核，API已被临时封禁\n• 服务正在维护或重启\n\n建议：\n1. 等待5-10分钟后重试\n2. 切换到其他模型（如GPT/Claude）\n3. 简化问题描述，避免敏感内容"
                            # 识别配额错误
                            elif "quota" in error_detail.lower() or "insufficient" in error_detail.lower():
                                error_type = "quota_exceeded"
                                user_friendly_message = "API配额已用尽，请联系管理员"
                            # 识别参数错误
                            elif "invalid" in error_detail.lower() or "parameter" in error_detail.lower():
                                error_type = "invalid_parameter"
                                user_friendly_message = "请求参数无效，请检查输入内容"
                            else:
                                # 其他4xx错误，使用原始错误消息（截断）
                                user_friendly_message = error_detail[:200] if len(error_detail) > 200 else error_detail
                    except Exception as parse_error:
                        logger.debug(f"无法解析错误响应体: {parse_error}")

                # 可读的失败原因（不暴露敏感信息）
                reason = "请求失败"
                if isinstance(e, requests.exceptions.Timeout):
                    reason = "超时"
                elif status == 429:
                    reason = "速率限制"
                elif status is not None and status >= 500:
                    reason = "服务异常"
                elif status is not None and 400 <= status < 500:
                    if error_type:
                        reason = error_type
                    else:
                        reason = "客户端错误"
                else:
                    reason = "网络异常"

                # 4xx(非429)错误处理：区分可恢复错误和不可恢复错误
                if status is not None and 400 <= status < 500 and status != 429:
                    logger.error(f"LLM流式请求失败(4xx,不重试): {e}, error_type={error_type}, detail={error_detail[:200] if error_detail else None}")

                    # content_filter错误：Agent可以调整策略，优雅恢复
                    if error_type == "content_filter":
                        logger.info("检测到content_filter错误，将作为系统消息返回给Agent，让其调整策略")

                        # 返回系统提示给Agent（不暴露给用户）
                        system_message = (
                            "[系统提示] 您的上一次回复触发了内容安全策略。"
                            "请调整表达方式，避免敏感内容，然后重新回答用户的问题。"
                        )

                        yield {
                            "type": "done",
                            "response": {
                                "role": "assistant",
                                "content": system_message,
                                "finish_reason": "content_filter"
                            }
                        }
                        return  # 不raise，让Agent继续循环

                    # 其他4xx错误：Agent无法自己解决，终止流程
                    else:
                        final_message = user_friendly_message if user_friendly_message else f"LLM请求失败({reason})"

                        yield {
                            "type": "error",
                            "message": final_message,
                            "status_code": status,
                            "error_type": error_type
                        }
                        raise

                if attempt >= self.max_retries:
                    logger.error(f"LLM流式请求失败且重试耗尽({attempt}/{self.max_retries}): {e}")
                    yield {"type": "retry_exhausted", "attempt": attempt, "max_retries": self.max_retries, "reason": reason}
                    raise

                # 针对429速率限制使用更激进的退避策略
                if status == 429:
                    # 429错误：使用更长的指数退避，从2秒开始
                    delay = 2.0 * (2 ** (attempt - 1))  # 2s, 4s, 8s, 16s, 32s
                    delay += random.uniform(0, 1.0)  # 添加抖动避免雷鸣群效应
                    logger.warning(f"遇到速率限制(429)，使用长退避策略，重试第{attempt}/{self.max_retries}次，等待{delay:.2f}s: {e}")
                else:
                    # 其他错误：使用标准指数退避
                    delay = self.retry_base_delay * (2 ** (attempt - 1))
                    delay += random.uniform(0, self.retry_base_delay)
                    logger.warning(f"LLM流式请求失败，重试第{attempt}/{self.max_retries}次后重连，等待{delay:.2f}s: {e}")

                # 将重试计划告知上层（供前端展示），不包含URL等敏感信息
                yield {"type": "retry", "attempt": attempt, "max_retries": self.max_retries, "delay": round(delay, 2), "reason": reason}
                time.sleep(delay)
