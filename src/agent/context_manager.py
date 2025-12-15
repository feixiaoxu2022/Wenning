"""Context Manager - 对话上下文管理和压缩

负责:
1. Token计数和使用率监控
2. 自动压缩历史对话
3. 智能保留关键信息
"""

from typing import List, Dict, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager:
    """对话上下文管理器"""

    def __init__(self, model_name: str = "gpt-4", max_tokens: int = None):
        """初始化Context Manager

        Args:
            model_name: 模型名称,用于token计数
            max_tokens: 最大context window大小（None则自动根据模型推断）
        """
        self.model_name = model_name

        # 自动识别模型的context window大小
        if max_tokens is None:
            max_tokens = self._infer_max_tokens(model_name)

        self.max_tokens = max_tokens
        self.compression_threshold = 0.85  # 85%触发压缩（充分利用200K context）
        self.recent_turns_to_keep = 3  # 保留最近3轮不压缩（参考Anthropic建议）

        logger.info(f"ContextManager初始化: model={model_name}, max_tokens={max_tokens}, threshold={self.compression_threshold}")

    def _infer_max_tokens(self, model_name: str) -> int:
        """根据模型名称推断context window大小

        Args:
            model_name: 模型名称

        Returns:
            推断的max_tokens大小
        """
        model_lower = model_name.lower()

        # Claude 系列（3.x, 4.5, Opus, Sonnet, Haiku等）- 200K tokens
        if 'claude' in model_lower:
            return 200000

        # Gemini 1.5/3.0 系列 - 1M tokens
        if 'gemini' in model_lower and (any(x in model_lower for x in ['1.5', '3', 'pro', 'flash'])):
            return 1000000

        # GPT-5 - 请确认具体的context window大小
        if 'gpt-5' in model_lower:
            # TODO: 确认GPT-5的实际context window大小
            return 200000  # 临时使用200K，需要根据官方文档调整

        # GPT-4 Turbo / GPT-4o - 128K tokens
        if any(x in model_lower for x in ['gpt-4-turbo', 'gpt-4o', 'gpt-4-0125', 'gpt-4-1106']):
            return 128000

        # GPT-4-32K - 32K tokens
        if 'gpt-4-32k' in model_lower:
            return 32000

        # GPT-4 基础版 - 8K tokens
        if 'gpt-4' in model_lower:
            return 8000

        # GLM-4 系列 - 128K tokens
        if 'glm-4' in model_lower:
            return 128000

        # Deepseek 系列 - 128K tokens
        if 'deepseek' in model_lower:
            return 128000

        # 默认128K（保守估计，对未知模型如GPT-5可手动指定max_tokens）
        logger.warning(f"未识别的模型 {model_name}，使用默认128K context window。如需自定义，请在初始化时指定max_tokens参数")
        return 128000

    def calculate_usage(self, messages: List[Dict]) -> Dict[str, Any]:
        """计算context使用情况

        Args:
            messages: 消息列表

        Returns:
            使用情况统计
        """
        try:
            # 方案1：尝试使用tiktoken（仅当已缓存时）
            total_tokens = self._calculate_tokens_tiktoken(messages)

            if total_tokens is None:
                # 方案2：降级到简单估算（避免网络超时）
                total_tokens = self._calculate_tokens_simple(messages)

            usage_percent = (total_tokens / self.max_tokens) * 100
            should_compress = usage_percent >= (self.compression_threshold * 100)

            stats = {
                "total_tokens": total_tokens,
                "max_tokens": self.max_tokens,
                "usage_percent": round(usage_percent, 2),
                "available_tokens": self.max_tokens - total_tokens,
                "should_compress": should_compress,
                "compression_threshold": self.compression_threshold * 100
            }

            logger.info(f"Context使用率: {stats['usage_percent']}% ({total_tokens}/{self.max_tokens})")

            return stats

        except Exception as e:
            logger.error(f"计算context使用率失败: {str(e)}")
            # 返回默认值
            return {
                "total_tokens": 0,
                "max_tokens": self.max_tokens,
                "usage_percent": 0.0,
                "available_tokens": self.max_tokens,
                "should_compress": False,
                "compression_threshold": self.compression_threshold * 100
            }

    def _calculate_tokens_tiktoken(self, messages: List[Dict]) -> int:
        """使用tiktoken计算token数（使用项目本地缓存，避免网络下载）

        Args:
            messages: 消息列表

        Returns:
            token总数，如果失败返回None
        """
        try:
            import tiktoken
            import socket
            import os

            # 优先使用项目本地缓存目录（从.env加载）
            tiktoken_cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR")
            if tiktoken_cache_dir:
                # 相对路径转绝对路径
                if not os.path.isabs(tiktoken_cache_dir):
                    from pathlib import Path
                    tiktoken_cache_dir = str(Path.cwd() / tiktoken_cache_dir)
                os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
                logger.debug(f"使用tiktoken缓存目录: {tiktoken_cache_dir}")
            else:
                # 回退到默认用户目录
                tiktoken_cache_dir = os.path.expanduser("~/.cache/tiktoken")

            # 检查缓存是否存在
            cache_exists = os.path.exists(tiktoken_cache_dir) and any(
                os.path.isfile(os.path.join(tiktoken_cache_dir, f))
                for f in os.listdir(tiktoken_cache_dir)
            ) if os.path.exists(tiktoken_cache_dir) else False

            if not cache_exists:
                logger.info(f"tiktoken缓存不存在({tiktoken_cache_dir})，使用简单估算")
                logger.info("提示: 运行 'python scripts/download_tiktoken_cache.py' 下载编码文件")
                return None

            # 设置更短的超时时间（防止意外网络请求）
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(2.0)  # 2秒超时

            try:
                try:
                    encoder = tiktoken.encoding_for_model(self.model_name)
                    logger.debug(f"使用模型专属编码: {self.model_name}")
                except KeyError:
                    # 模型不在tiktoken中，使用默认编码（静默处理，这是正常情况）
                    encoder = tiktoken.get_encoding("cl100k_base")
                    logger.debug(f"模型{self.model_name}使用cl100k_base编码")
            finally:
                socket.setdefaulttimeout(original_timeout)

            # 计算总token数
            total_tokens = 0
            for msg in messages:
                content = str(msg.get("content", ""))
                # Function calling相关的也要计算
                if msg.get("tool_calls"):
                    content += str(msg["tool_calls"])
                if msg.get("name"):
                    content += msg["name"]

                total_tokens += len(encoder.encode(content))

            logger.debug(f"使用tiktoken计算: {total_tokens} tokens")
            return total_tokens

        except Exception as e:
            logger.warning(f"tiktoken计算失败，降级到简单估算: {str(e)}")
            return None

    def _calculate_tokens_simple(self, messages: List[Dict]) -> int:
        """简单token估算（不依赖tiktoken）

        使用经验公式：英文约4字符=1token，中文约1.5字符=1token

        Args:
            messages: 消息列表

        Returns:
            估算的token总数
        """
        total_chars = 0
        chinese_chars = 0

        for msg in messages:
            content = str(msg.get("content", ""))

            # Function calling相关的也要计算
            if msg.get("tool_calls"):
                content += str(msg["tool_calls"])
            if msg.get("name"):
                content += msg["name"]

            total_chars += len(content)

            # 统计中文字符
            chinese_chars += sum(1 for char in content if '\u4e00' <= char <= '\u9fff')

        # 估算公式：中文1.5字符≈1token，英文4字符≈1token
        # 简化为：total_tokens ≈ chinese_chars / 1.5 + (total_chars - chinese_chars) / 4
        estimated_tokens = int(chinese_chars / 1.5 + (total_chars - chinese_chars) / 4)

        logger.debug(f"使用简单估算: {estimated_tokens} tokens (chars={total_chars}, chinese={chinese_chars})")
        return estimated_tokens

    def should_compress(self, messages: List[Dict]) -> bool:
        """判断是否需要压缩

        Args:
            messages: 消息列表

        Returns:
            是否需要压缩
        """
        stats = self.calculate_usage(messages)
        return stats["should_compress"]

    def compress_conversation_history(
        self,
        conversation_history: List[Dict],
        llm_client,
        merge_recent_tools: bool = False  # 是否也合并最近对话的tool调用
    ) -> List[Dict]:
        """压缩对话历史

        Args:
            conversation_history: 完整对话历史
            llm_client: LLM客户端,用于生成摘要
            merge_recent_tools: 是否也合并最近对话中的连续tool调用（默认False，保留详细信息）

        Returns:
            压缩后的对话历史
        """
        if len(conversation_history) <= self.recent_turns_to_keep * 2:
            logger.info("对话历史太短,无需压缩")
            return conversation_history

        # 计算压缩前的token数
        before_stats = self.calculate_usage(conversation_history)
        logger.info(f"压缩前: {len(conversation_history)}条消息, {before_stats['total_tokens']} tokens")

        # 分离最近的对话和旧对话
        recent = conversation_history[-(self.recent_turns_to_keep * 2):]
        old = conversation_history[:-(self.recent_turns_to_keep * 2)]

        if not old:
            logger.info("没有旧对话可压缩")
            return conversation_history

        logger.info(f"开始压缩对话历史: {len(old)}条旧对话 + {len(recent)}条最近对话")

        try:
            # 第零步：合并连续的同类tool调用（特别是web_search）
            old_merged = self._merge_consecutive_tool_calls(old)
            logger.info(f"Tool调用合并(旧对话): {len(old)}条 → {len(old_merged)}条消息")

            # 可选：也合并最近对话的tool调用（激进模式）
            if merge_recent_tools:
                recent_merged = self._merge_consecutive_tool_calls(recent)
                logger.info(f"Tool调用合并(最近对话): {len(recent)}条 → {len(recent_merged)}条消息")
                recent = recent_merged

            # 第一步：清理旧对话中的tool结果（Anthropic推荐的低成本优化）
            old_cleaned = self._clear_tool_results(old_merged)
            logger.info(f"Tool结果清理: {len(old_merged)}条 → {len(old_cleaned)}条非空消息")

            # 第二步：生成压缩摘要
            summary = self._generate_summary(old_cleaned, llm_client)

            if not summary:
                logger.error("⚠️  摘要生成失败或为空,保留原始历史")
                return conversation_history

            logger.info(f"摘要生成成功: {len(summary)}字符")

            # 构建压缩后的历史
            compressed = [
                {
                    "role": "system",
                    "content": f"[历史对话摘要 - 自动压缩于第{len(conversation_history)//2}轮]\n\n{summary}\n\n---\n\n[以下是最近的对话内容]"
                }
            ] + recent

            # 计算压缩后的token数
            after_stats = self.calculate_usage(compressed)
            compression_ratio = (1 - after_stats['total_tokens'] / before_stats['total_tokens']) * 100

            logger.info(f"压缩完成: {len(conversation_history)}条 → {len(compressed)}条")
            logger.info(f"Token压缩: {before_stats['total_tokens']} → {after_stats['total_tokens']} ({compression_ratio:.1f}%减少)")

            # 如果压缩后token数反而增加，返回原始历史
            if after_stats['total_tokens'] >= before_stats['total_tokens']:
                logger.warning(f"⚠️  压缩后token数未减少({before_stats['total_tokens']} → {after_stats['total_tokens']})，保留原始历史")
                return conversation_history

            return compressed

        except Exception as e:
            logger.error(f"对话压缩失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return conversation_history

    def _merge_consecutive_tool_calls(self, messages: List[Dict]) -> List[Dict]:
        """合并连续的同类tool调用（特别是web_search）

        策略：
        - web_search：3次以上合并为摘要（只保留"搜了N次+成功率"）
        - code_executor：保留最后1次完整记录
        - 其他工具：不合并

        Args:
            messages: 原始消息列表

        Returns:
            合并后的消息列表
        """
        merged = []
        buffer = []  # 缓存连续的同类tool消息

        for msg in messages:
            if msg.get('role') == 'tool':
                tool_name = msg.get('name', '')

                # 如果buffer为空或同类工具，加入buffer
                if not buffer or buffer[0].get('name') == tool_name:
                    buffer.append(msg)
                else:
                    # 不同类工具，处理buffer
                    merged.extend(self._process_tool_buffer(buffer))
                    buffer = [msg]
            else:
                # 非tool消息，先处理buffer
                if buffer:
                    merged.extend(self._process_tool_buffer(buffer))
                    buffer = []
                merged.append(msg)

        # 处理最后的buffer
        if buffer:
            merged.extend(self._process_tool_buffer(buffer))

        return merged

    def _process_tool_buffer(self, buffer: List[Dict]) -> List[Dict]:
        """处理tool buffer：决定保留、合并还是删除

        Args:
            buffer: 连续的同类tool消息

        Returns:
            处理后的消息列表
        """
        if not buffer:
            return []

        if len(buffer) < 3:
            return buffer  # 少于3次，不合并

        tool_name = buffer[0].get('name', '')

        # Web Search：合并为摘要
        if tool_name == 'web_search':
            import json

            # 统计成功率
            success_count = 0
            total_count = len(buffer)

            for msg in buffer:
                try:
                    content = msg.get('content', '')
                    data = json.loads(content)
                    if data.get('status') == 'success':
                        success_count += 1
                except:
                    pass

            # 生成摘要消息
            summary_msg = {
                'role': 'tool',
                'tool_call_id': buffer[-1]['tool_call_id'],  # 用最后一次的ID
                'name': tool_name,
                'content': json.dumps({
                    'status': 'summary',
                    'data': {
                        'tool': 'web_search',
                        'total_calls': total_count,
                        'successful': success_count,
                        'failed': total_count - success_count,
                        'note': f'执行了{total_count}次搜索，成功{success_count}次。详细结果已压缩以节省context。'
                    }
                }, ensure_ascii=False)
            }

            logger.info(f"[Tool合并] web_search: {total_count}次调用 → 1条摘要消息")
            return [summary_msg]

        # Code Executor：保留最后1次
        elif tool_name == 'code_executor':
            logger.info(f"[Tool合并] code_executor: {len(buffer)}次调用 → 保留最后1次")
            return [buffer[-1]]

        # 其他工具：保持原样
        else:
            return buffer

    def _clear_tool_results(self, messages: List[Dict]) -> List[Dict]:
        """清理tool结果以节省context（Anthropic推荐的tool result clearing）

        策略：
        1. 保留tool调用本身（assistant的tool_calls）
        2. 压缩冗长的tool结果（只保留摘要）
        3. 完全移除纯状态反馈的tool消息

        Args:
            messages: 消息列表

        Returns:
            清理后的消息列表
        """
        cleaned = []
        for msg in messages:
            if msg.get('role') == 'tool':
                content = msg.get('content', '')

                # 如果是短消息（<200字符），直接保留
                if len(content) < 200:
                    cleaned.append(msg)
                    continue

                # 对于长消息，压缩为摘要
                try:
                    # 尝试解析JSON结构
                    import json
                    data = json.loads(content)

                    # 构建简洁摘要
                    summary_parts = []
                    if data.get('status'):
                        summary_parts.append(f"Status: {data['status']}")
                    if data.get('generated_files'):
                        files = data['generated_files']
                        summary_parts.append(f"Files: {', '.join(files[:3])}")
                    if data.get('error'):
                        summary_parts.append(f"Error: {data['error'][:100]}")

                    summary = " | ".join(summary_parts) if summary_parts else content[:150]

                    cleaned.append({
                        'role': 'tool',
                        'tool_call_id': msg.get('tool_call_id'),
                        'name': msg.get('name'),
                        'content': f"[Compressed: {len(content)} chars] {summary}"
                    })
                except:
                    # 如果不是JSON，直接截断
                    cleaned.append({
                        'role': 'tool',
                        'tool_call_id': msg.get('tool_call_id'),
                        'name': msg.get('name'),
                        'content': f"[Compressed: {len(content)} chars] {content[:200]}..."
                    })
            else:
                # 非tool消息，保持原样
                cleaned.append(msg)

        return cleaned

    def _generate_summary(self, old_conversation: List[Dict], llm_client) -> str:
        """生成对话摘要

        Args:
            old_conversation: 旧对话列表
            llm_client: LLM客户端

        Returns:
            摘要文本
        """
        # 构造对话文本
        conversation_text = self._format_conversation_for_summary(old_conversation)

        # 压缩提示词
        compression_prompt = self._build_compression_prompt(conversation_text)

        logger.info(f"调用LLM生成对话摘要... (原对话: {len(conversation_text)}字符)")

        try:
            # 调用LLM生成摘要
            response = llm_client.chat(
                messages=[
                    {"role": "user", "content": compression_prompt}
                ],
                tools=None,  # 不使用工具
                stream=False
            )

            # 检查响应格式
            if isinstance(response, dict):
                summary = response.get("content", "")
            elif isinstance(response, str):
                summary = response
            else:
                logger.error(f"LLM返回未知格式: {type(response)}")
                return ""

            if not summary or not summary.strip():
                logger.error("LLM返回空摘要")
                return ""

            summary = summary.strip()
            logger.info(f"摘要生成成功: {len(summary)}字符 (压缩比: {len(summary)/len(conversation_text)*100:.1f}%)")

            return summary

        except Exception as e:
            logger.error(f"LLM生成摘要失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return ""

    def _format_conversation_for_summary(self, conversation: List[Dict]) -> str:
        """格式化对话为可读文本

        Args:
            conversation: 对话列表

        Returns:
            格式化的对话文本
        """
        lines = []
        turn_number = 1

        for i in range(0, len(conversation), 2):
            if i + 1 < len(conversation):
                user_msg = conversation[i]
                assistant_msg = conversation[i + 1]

                lines.append(f"【第{turn_number}轮对话】")
                lines.append(f"用户: {user_msg.get('content', '')}")
                lines.append(f"助手: {assistant_msg.get('content', '')}")
                lines.append("")

                turn_number += 1

        return "\n".join(lines)

    def _build_compression_prompt(self, conversation_text: str) -> str:
        """构建压缩提示词（基于Anthropic的context engineering最佳实践）

        Args:
            conversation_text: 对话文本

        Returns:
            压缩提示词
        """
        return f"""你是一个专业的对话历史压缩助手。请将以下历史对话压缩为高信号密度的摘要。

# 🎯 压缩原则（参考Anthropic Context Engineering）

找到**最小的高信号token集合**来保留关键上下文，丢弃冗余信息。

## ✅ 必须保留 (Critical Elements)

### 1. 架构决策 (Architectural Decisions)
   - 用户选择的技术方案、工具、方法
   - 明确拒绝的方案和原因

### 2. 未解决的问题 (Unresolved Issues)
   - 遇到的bug和错误
   - 待解决的技术难题
   - 需要后续关注的问题

### 3. 实现细节 (Implementation Details)
   - 关键参数和配置（尺寸、格式、风格）
   - 文件名和文件关系
   - 代码实现的重要约束

### 4. 用户偏好和明确指令
   - 质量标准和约束条件
   - 风格偏好（颜色、字体等）
   - 明确的"要"和"不要"

## ❌ 可以丢弃 (Redundant Content)

1. 冗余的tool输出（已被清理为摘要）
2. 中间的思考过程和尝试
3. 重复的确认和礼貌用语
4. 已被后续操作替代的临时内容

## 📝 输出格式

使用简洁的结构化格式：

```
【核心任务】
[一句话总结用户的整体目标]

【已完成】
- 任务1: 结果（文件名、关键参数）
- 任务2: 结果

【进行中/待解决】
- 问题A: 状态描述
- 任务B: 计划说明

【关键决策】
- 技术选择: 原因
- 用户偏好: 具体要求

【重要文件】
- file1.ext: 用途 | 参数
- file2.ext: 用途 | 关联
```

---

# 📋 需要压缩的对话内容

{conversation_text}

---

**请生成压缩摘要（200-500 tokens为佳）**："""
