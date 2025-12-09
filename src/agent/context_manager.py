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

    def __init__(self, model_name: str = "gpt-4", max_tokens: int = 128000):
        """初始化Context Manager

        Args:
            model_name: 模型名称,用于token计数
            max_tokens: 最大context window大小
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.compression_threshold = 0.80  # 80%触发压缩
        self.recent_turns_to_keep = 1  # 保留最近1轮不压缩

        logger.info(f"ContextManager初始化: model={model_name}, max_tokens={max_tokens}, threshold={self.compression_threshold}")

    def calculate_usage(self, messages: List[Dict]) -> Dict[str, Any]:
        """计算context使用情况

        Args:
            messages: 消息列表

        Returns:
            使用情况统计
        """
        try:
            import tiktoken
            import socket

            # 设置更短的超时时间，避免长时间等待
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(5.0)  # 5秒超时

            try:
                encoder = tiktoken.encoding_for_model(self.model_name)
            except KeyError:
                # 如果模型不在tiktoken中,使用默认编码
                logger.warning(f"模型{self.model_name}不在tiktoken中,使用cl100k_base编码")
                encoder = tiktoken.get_encoding("cl100k_base")
            finally:
                # 恢复默认超时
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
        llm_client
    ) -> List[Dict]:
        """压缩对话历史

        Args:
            conversation_history: 完整对话历史
            llm_client: LLM客户端,用于生成摘要

        Returns:
            压缩后的对话历史
        """
        if len(conversation_history) <= self.recent_turns_to_keep * 2:
            logger.info("对话历史太短,无需压缩")
            return conversation_history

        # 分离最近的对话和旧对话
        recent = conversation_history[-(self.recent_turns_to_keep * 2):]
        old = conversation_history[:-(self.recent_turns_to_keep * 2)]

        if not old:
            logger.info("没有旧对话可压缩")
            return conversation_history

        logger.info(f"开始压缩对话历史: {len(old)}条旧对话 + {len(recent)}条最近对话")

        try:
            # 生成压缩摘要
            summary = self._generate_summary(old, llm_client)

            if not summary:
                logger.warning("摘要生成失败,保留原始历史")
                return conversation_history

            # 构建压缩后的历史
            compressed = [
                {
                    "role": "system",
                    "content": f"[历史对话摘要 - 自动压缩于第{len(conversation_history)//2}轮]\n\n{summary}\n\n---\n\n[以下是最近的对话内容]"
                }
            ] + recent

            logger.info(f"对话压缩完成: {len(conversation_history)}条 → {len(compressed)}条")

            return compressed

        except Exception as e:
            logger.error(f"对话压缩失败: {str(e)}")
            return conversation_history

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

        logger.info("调用LLM生成对话摘要...")

        try:
            # 调用LLM生成摘要
            response = llm_client.chat(
                messages=[
                    {"role": "user", "content": compression_prompt}
                ],
                tools=None,  # 不使用工具
                model_override=None
            )

            summary = response.get("content", "")

            if not summary:
                logger.error("LLM返回空摘要")
                return ""

            logger.info(f"摘要生成成功,长度: {len(summary)}字符")

            return summary

        except Exception as e:
            logger.error(f"LLM生成摘要失败: {str(e)}")
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
        """构建压缩提示词

        Args:
            conversation_text: 对话文本

        Returns:
            压缩提示词
        """
        return f"""你是一个专业的对话历史总结助手。请将以下历史对话压缩为简洁的摘要,用于保留关键上下文信息。

# 📋 总结要求

## ✅ 必须保留的信息 (按优先级排序)

### 1. **任务计划和执行进度** ⭐ 最高优先级
   - 用户的整体任务目标
   - 已完成的步骤和结果
   - 进行中的步骤和状态
   - 待执行的步骤
   - 计划变更记录

### 2. **生成的文件和内容**
   - 文件名称、类型、用途
   - 文件的关键参数(如:尺寸、格式、主题)
   - 文件之间的关联关系

### 3. **用户需求和偏好**
   - 明确表达的需求和目标
   - 风格和格式偏好(颜色、字体、布局等)
   - 质量标准和约束条件
   - 拒绝或不喜欢的方案

### 4. **重要决策和结论**
   - 用户的选择和确认
   - 明确的指令和修改要求
   - 重要的反馈意见

### 5. **数据和知识**
   - 搜索获取的重要信息
   - 分析得出的关键结论
   - 用户提供的原始数据

## ❌ 可以大幅压缩或省略的信息

1. 工具调用的详细参数和执行过程
2. 中间步骤的详细思考过程
3. 错误尝试和调试细节(除非影响最终方案)
4. 重复性的确认和礼貌用语
5. 已被后续操作替代的临时内容

## 📝 输出格式

使用简洁的结构化格式,突出任务进展:

```
【任务计划】
整体目标: [一句话描述]
✅ 已完成:
  - 步骤1: 结果概要
  - 步骤2: 结果概要
🔄 进行中:
  - 步骤3: 当前状态
⏳ 待执行:
  - 步骤4: 计划说明

【生成文件】
- 文件1.xlsx: 用途 | 关键参数 | 相关文件
- 文件2.png: 用途 | 关键参数 | 相关文件

【用户偏好】
- 风格: 具体描述
- 格式: 具体要求
- 约束: 限制条件

【关键数据】
- 数据来源1: 核心内容摘要
- 结论1: 重要发现

【待办事项】
- [ ] 任务1: 具体说明
- [ ] 任务2: 具体说明
```

# 📚 待总结的历史对话

{conversation_text}

# ⚠️ 注意事项

1. **任务计划是最重要的上下文**,必须详细保留每个步骤的完成情况
2. 总结长度控制在原对话的15-25%以内
3. 保持客观中立,不添加推测和解释
4. 使用第三人称叙述("用户要求...", "系统生成了...")
5. 保留具体的数值、名称、路径等关键细节
6. 如果某个文件被多次修改,只保留最终版本的信息
7. 按时间顺序组织,但同类信息可以合并
8. **直接输出摘要内容,不要添加任何前缀或解释**

请开始总结:"""
