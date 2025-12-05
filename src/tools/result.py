"""Tool执行结果的标准化定义

所有Tool（Atomic和Workflow）必须返回ToolResult对象，确保Agent能够理解和处理。
"""

from typing import Any, Dict, List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum


class ErrorType(Enum):
    """错误类型枚举"""
    # LLM相关错误
    LLM_TIMEOUT = "llm_timeout"
    LLM_RESPONSE_PARSE_ERROR = "llm_response_parse_error"
    LLM_API_ERROR = "llm_api_error"

    # 工具执行错误
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    PARAMETER_VALIDATION_ERROR = "parameter_validation_error"

    # 外部API错误
    EXTERNAL_API_ERROR = "external_api_error"
    NETWORK_ERROR = "network_error"
    RATE_LIMIT_ERROR = "rate_limit_error"

    # 数据处理错误
    DATA_NOT_FOUND = "data_not_found"
    DATA_FORMAT_ERROR = "data_format_error"

    # 系统错误
    RESOURCE_EXHAUSTED = "resource_exhausted"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ToolResult:
    """Tool执行结果的标准格式

    设计原则：
    1. Tool永远不抛异常，只返回ToolResult
    2. 包含丰富的语义信息，让Agent能够理解和反思
    3. 提供恢复建议，帮助Agent决策下一步行动
    """

    # === 基础信息 ===
    success: bool
    tool_name: str
    tool_type: Literal["atomic", "workflow"]

    # === 成功时的数据 ===
    data: Optional[Any] = None

    # === 失败时的错误信息 ===
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = field(default_factory=dict)

    # === Workflow特有信息 ===
    stage_info: Optional[Dict[str, Any]] = None  # 当前阶段信息
    partial_results: Dict[str, Any] = field(default_factory=dict)  # 部分成功的结果

    # === 恢复相关信息 ===
    recoverable: bool = False
    recovery_suggestions: List[str] = field(default_factory=list)
    estimated_retry_success_rate: float = 0.0

    # === 元信息 ===
    execution_time_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_files: List[str] = field(default_factory=list)  # 生成的文件名列表

    def to_agent_message(self) -> str:
        """转换为对Agent友好的自然语言描述

        Returns:
            自然语言格式的执行结果描述
        """
        if self.success:
            return self._success_message()
        else:
            return self._failure_message()

    def _success_message(self) -> str:
        """成功消息"""
        # 使用更简洁的现代勾号符号
        msg = f"✓ {self.tool_name} 执行成功"

        if self.tool_type == "workflow" and self.stage_info:
            msg += f"，完成 {self.stage_info.get('completed_stages', 0)}/{self.stage_info.get('total_stages', 0)} 个阶段"

        return msg

    def _failure_message(self) -> str:
        """失败消息，包含丰富的上下文"""
        # 失败提示更现代：使用 ✗
        msg = f"✗ {self.tool_name} 执行失败\n\n"

        # 错误类型和消息
        msg += f"**错误类型**: {self.error_type.value if self.error_type else 'unknown'}\n"
        msg += f"**错误描述**: {self.error_message}\n\n"

        # Workflow特有：阶段信息
        if self.stage_info:
            msg += f"**失败阶段**: {self.stage_info.get('stage_name')} (阶段 {self.stage_info.get('current_stage')}/{self.stage_info.get('total_stages')})\n\n"

        # 部分成功的结果
        if self.partial_results:
            msg += f"**已完成的工作**: \n"
            for key, value in self.partial_results.items():
                msg += f"  - {key}: {self._summarize_result(value)}\n"
            msg += "\n"

        # 错误详情
        if self.error_details:
            msg += f"**详细信息**:\n"
            for key, value in self.error_details.items():
                if key == "llm_raw_response":
                    # LLM响应截断显示
                    msg += f"  - LLM原始响应: {str(value)[:200]}...\n"
                else:
                    msg += f"  - {key}: {value}\n"
            msg += "\n"

        # 恢复建议
        if self.recoverable and self.recovery_suggestions:
            msg += f"**可能的修复方案** (成功率 ~{self.estimated_retry_success_rate*100:.0f}%):\n"
            for i, suggestion in enumerate(self.recovery_suggestions, 1):
                msg += f"  {i}. {suggestion}\n"

        return msg

    def _summarize_result(self, result: Any) -> str:
        """总结结果（避免过长）"""
        if isinstance(result, dict):
            return f"字典({len(result)}个键)"
        elif isinstance(result, list):
            return f"列表({len(result)}项)"
        elif isinstance(result, str):
            return f"{result[:50]}..." if len(result) > 50 else result
        else:
            return str(result)[:50]


def create_success_result(
    tool_name: str,
    tool_type: Literal["atomic", "workflow"],
    data: Any,
    **kwargs
) -> ToolResult:
    """创建成功结果的便捷函数"""
    return ToolResult(
        success=True,
        tool_name=tool_name,
        tool_type=tool_type,
        data=data,
        **kwargs
    )


def create_failure_result(
    tool_name: str,
    tool_type: Literal["atomic", "workflow"],
    error_type: ErrorType,
    error_message: str,
    **kwargs
) -> ToolResult:
    """创建失败结果的便捷函数"""
    return ToolResult(
        success=False,
        tool_name=tool_name,
        tool_type=tool_type,
        error_type=error_type,
        error_message=error_message,
        **kwargs
    )
