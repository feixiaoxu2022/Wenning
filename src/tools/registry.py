"""Tool Registry模块

统一管理所有可用工具(Atomic Tools和Workflow Tools)，
提供工具注册、查询和执行的统一接口。
"""

from typing import Dict, List, Any, Optional
from src.tools.base import BaseAtomicTool, BaseWorkflowTool
from src.tools.result import ToolResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册中心

    职责:
    1. 注册和管理所有可用工具
    2. 生成Function Calling的tools schema
    3. 执行指定的工具调用
    """

    def __init__(self):
        """初始化工具注册中心"""
        self.tools: Dict[str, Any] = {}  # name -> Tool instance
        logger.info("ToolRegistry初始化完成")

    def register_atomic_tool(self, tool: BaseAtomicTool):
        """注册原子工具

        Args:
            tool: 原子工具实例
        """
        if tool.name in self.tools:
            logger.warning(f"工具 {tool.name} 已存在,将被覆盖")

        self.tools[tool.name] = tool
        logger.info(f"注册原子工具: {tool.name}")

    def register_workflow_tool(self, tool: BaseWorkflowTool):
        """注册工作流工具

        Args:
            tool: 工作流工具实例
        """
        if tool.name in self.tools:
            logger.warning(f"工具 {tool.name} 已存在,将被覆盖")

        self.tools[tool.name] = tool
        logger.info(f"注册工作流工具: {tool.name}")

    def get_function_calling_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的Function Calling schema

        Returns:
            符合OpenAI Function Calling格式的tools列表
        """
        schemas = []

        for tool_name, tool in self.tools.items():
            # 检查工具是否有to_function_schema方法
            if hasattr(tool, 'to_function_schema'):
                schemas.append(tool.to_function_schema())
            else:
                logger.warning(f"工具 {tool_name} 没有实现to_function_schema方法,跳过")

        return schemas

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """执行指定工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            ToolResult对象

        Raises:
            ValueError: 如果工具不存在
        """
        if tool_name not in self.tools:
            error_msg = f"工具不存在: {tool_name}. 可用工具: {list(self.tools.keys())}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        tool = self.tools[tool_name]

        logger.info(f"执行工具: {tool_name}, 参数: {arguments}")

        # 区分Atomic Tool和Workflow Tool的执行方式
        if isinstance(tool, BaseWorkflowTool):
            # Workflow Tool: execute()返回ToolResult
            return tool.execute(arguments)

        elif isinstance(tool, BaseAtomicTool):
            # Atomic Tool: run()返回Dict,需要转换为ToolResult
            result_dict = tool.run(**arguments)

            # 转换为ToolResult
            from src.tools.result import create_success_result, create_failure_result

            if result_dict.get("status") == "success":
                # 提取generated_files字段(如果有)
                # 先从顶层找，如果没有再从data里面找（因为execute()返回的dict被包装在data中）
                generated_files = result_dict.get("generated_files", [])
                if not generated_files and isinstance(result_dict.get("data"), dict):
                    generated_files = result_dict["data"].get("generated_files", [])

                return create_success_result(
                    tool_name=tool_name,
                    tool_type="atomic",
                    data=result_dict.get("data"),
                    generated_files=generated_files
                )
            else:
                from src.tools.result import ErrorType
                return create_failure_result(
                    tool_name=tool_name,
                    tool_type="atomic",
                    error_type=ErrorType.TOOL_EXECUTION_ERROR,
                    error_message=result_dict.get("error", "未知错误")
                )

        else:
            raise TypeError(f"未知的工具类型: {type(tool)}")

    def get_tool(self, tool_name: str) -> Optional[Any]:
        """获取指定工具实例

        Args:
            tool_name: 工具名称

        Returns:
            工具实例,如果不存在返回None
        """
        return self.tools.get(tool_name)

    def list_tools(self) -> List[str]:
        """列出所有已注册工具的名称

        Returns:
            工具名称列表
        """
        return list(self.tools.keys())

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={len(self.tools)})"
