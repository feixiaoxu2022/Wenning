"""工具基类模块

定义Atomic Tool和Workflow Tool的抽象基类。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from enum import Enum
from src.utils.logger import get_logger
from src.tools.result import ToolResult, ErrorType, create_success_result, create_failure_result

logger = get_logger(__name__)


class ToolStatus(Enum):
    """工具执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


class BaseAtomicTool(ABC):
    """原子工具抽象基类

    原子工具是最小粒度的能力单元，直接调用外部API或执行特定操作。
    """

    # 子类必须定义
    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}  # Function Calling参数schema

    # === 多模态支持配置 ===
    # 如果工具输出可以包含图片，并且支持LLM直接查看，设置为True
    supports_image_injection: bool = False

    def __init__(self, config):
        """初始化工具

        Args:
            config: 全局配置对象
        """
        self.config = config
        self.status = ToolStatus.PENDING

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具核心逻辑

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果字典，可以包含以下特殊字段：
            - inject_images: List[str] - 需要注入给LLM查看的图片路径列表
            - image_detail: str - 图片细节级别 ("low"/"high"/"auto")
            - generated_files: List[str] - 生成的文件列表
        """
        pass

    def to_function_schema(self) -> Dict[str, Any]:
        """生成Function Calling schema

        Returns:
            符合OpenAI Function Calling格式的schema
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema if self.parameters_schema else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }

    def validate_params(self, **kwargs) -> bool:
        """参数校验

        Args:
            **kwargs: 待校验参数

        Returns:
            是否通过校验
        """
        # 默认实现：检查必需参数是否存在
        required_params = getattr(self, 'required_params', [])
        for param in required_params:
            if param not in kwargs:
                logger.error(f"{self.name}: 缺少必需参数 {param}")
                return False
        return True

    def run(self, **kwargs) -> ToolResult:
        """带状态管理和错误处理的执行入口

        Args:
            **kwargs: 工具参数

        Returns:
            ToolResult对象，永远不抛异常
        """
        self.status = ToolStatus.RUNNING
        logger.info(f"{self.name}: 开始执行, params={kwargs}")

        try:
            # 参数校验
            if not self.validate_params(**kwargs):
                self.status = ToolStatus.FAILED
                return create_failure_result(
                    tool_name=self.name,
                    tool_type="atomic",
                    error_type=ErrorType.PARAMETER_VALIDATION_ERROR,
                    error_message="参数校验失败"
                )

            # 执行核心逻辑
            result = self.execute(**kwargs)

            # 成功
            self.status = ToolStatus.SUCCESS
            logger.info(f"{self.name}: 执行成功")

            # 提取特殊字段
            inject_images = result.pop("inject_images", None) if isinstance(result, dict) else None
            image_detail = result.pop("image_detail", "auto") if isinstance(result, dict) else "auto"
            generated_files = result.pop("generated_files", None) if isinstance(result, dict) else None

            # 构造ToolResult
            return create_success_result(
                tool_name=self.name,
                tool_type="atomic",
                data=result,
                inject_images=inject_images,
                image_detail=image_detail,
                generated_files=generated_files or []
            )

        except Exception as e:
            self.status = ToolStatus.FAILED
            logger.error(f"{self.name}: 执行失败, error={str(e)}")

            return create_failure_result(
                tool_name=self.name,
                tool_type="atomic",
                error_type=ErrorType.TOOL_EXECUTION_ERROR,
                error_message=str(e)
            )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, status={self.status.value})"


class WorkflowStage:
    """工作流阶段定义"""

    def __init__(
        self,
        stage_id: int,
        name: str,
        description: str,
        critical: bool = True,
        retry_limit: int = 3
    ):
        """
        Args:
            stage_id: 阶段编号
            name: 阶段名称
            description: 阶段描述
            critical: 是否关键阶段（失败则终止整个流程）
            retry_limit: 重试次数限制
        """
        self.stage_id = stage_id
        self.name = name
        self.description = description
        self.critical = critical
        self.retry_limit = retry_limit
        self.status = ToolStatus.PENDING
        self.error: Optional[str] = None
        self.result: Optional[Any] = None


class BaseWorkflowTool(ABC):
    """工作流工具抽象基类

    工作流工具封装多步骤的复杂任务，内部自动调度Atomic Tools和LLM。
    """

    # 子类必须定义
    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}  # Function Calling参数schema

    def __init__(self, config, llm_client):
        """初始化工作流工具

        Args:
            config: 全局配置对象
            llm_client: LLM客户端
        """
        self.config = config
        self.llm = llm_client
        self.status = ToolStatus.PENDING
        self.stages: List[WorkflowStage] = []

    def to_function_schema(self) -> Dict[str, Any]:
        """生成Function Calling schema

        Returns:
            符合OpenAI Function Calling格式的schema
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema if self.parameters_schema else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }

    @abstractmethod
    def define_stages(self) -> List[WorkflowStage]:
        """定义工作流的各个阶段

        Returns:
            阶段列表
        """
        pass

    @abstractmethod
    def execute_stage(
        self,
        stage: WorkflowStage,
        params: Dict[str, Any],
        prev_results: List[Any]
    ) -> Any:
        """执行单个阶段

        Args:
            stage: 阶段对象
            params: 用户输入参数
            prev_results: 前序阶段的结果列表

        Returns:
            当前阶段的执行结果
        """
        pass

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行完整工作流

        Args:
            params: 工作流参数

        Returns:
            ToolResult对象，永远不抛异常
        """
        self.status = ToolStatus.RUNNING
        self.stages = self.define_stages()
        stage_results = []

        logger.info(f"{self.name}: 开始执行工作流, 共{len(self.stages)}个阶段")

        for i, stage in enumerate(self.stages, 1):
            logger.info(f"{self.name}: 阶段{i}/{len(self.stages)} - {stage.name}")

            # 执行阶段（带重试）
            success, result = self._execute_stage_with_retry(stage, params, stage_results)

            if success:
                stage.status = ToolStatus.SUCCESS
                stage.result = result
                stage_results.append(result)
                logger.info(f"{self.name}: 阶段{i}完成")

            else:
                stage.status = ToolStatus.FAILED

                if stage.critical:
                    # 关键阶段失败，返回详细的失败信息
                    self.status = ToolStatus.FAILED
                    logger.error(f"{self.name}: 关键阶段{i}失败，终止流程")

                    # 构建部分结果字典
                    partial_results = {}
                    for j, prev_stage in enumerate(self.stages[:i-1], 1):
                        if prev_stage.result:
                            partial_results[f"阶段{j}_{prev_stage.name}"] = prev_stage.result

                    # 返回ToolResult
                    return create_failure_result(
                        tool_name=self.name,
                        tool_type="workflow",
                        error_type=self._infer_error_type(stage.error),
                        error_message=f"关键阶段失败: {stage.name}",
                        stage_info={
                            "current_stage": i,
                            "stage_name": stage.name,
                            "total_stages": len(self.stages),
                            "completed_stages": i - 1
                        },
                        error_details={
                            "stage_error": stage.error,
                            "stage_description": stage.description
                        },
                        partial_results=partial_results,
                        recoverable=True,
                        recovery_suggestions=self._generate_recovery_suggestions(stage, stage.error),
                        estimated_retry_success_rate=0.6
                    )
                else:
                    # 非关键阶段失败，继续执行
                    logger.warning(f"{self.name}: 非关键阶段{i}失败，继续执行")
                    stage_results.append(None)

        # 所有阶段完成
        self.status = ToolStatus.SUCCESS
        logger.info(f"{self.name}: 工作流执行成功")

        return create_success_result(
            tool_name=self.name,
            tool_type="workflow",
            data={
                "results": stage_results,
                "completed_stages": len(self.stages),
                "total_stages": len(self.stages)
            },
            stage_info={
                "completed_stages": len(self.stages),
                "total_stages": len(self.stages)
            }
        )

    def _infer_error_type(self, error_message: str) -> ErrorType:
        """根据错误消息推断错误类型"""
        error_lower = str(error_message).lower()

        if "json" in error_lower or "parse" in error_lower:
            return ErrorType.LLM_RESPONSE_PARSE_ERROR
        elif "timeout" in error_lower:
            return ErrorType.LLM_TIMEOUT
        elif "api" in error_lower or "request" in error_lower:
            return ErrorType.EXTERNAL_API_ERROR
        elif "network" in error_lower:
            return ErrorType.NETWORK_ERROR
        else:
            return ErrorType.TOOL_EXECUTION_ERROR

    def _generate_recovery_suggestions(self, stage: 'WorkflowStage', error: str) -> List[str]:
        """生成恢复建议"""
        suggestions = []

        error_lower = str(error).lower()

        if "json" in error_lower or "parse" in error_lower:
            suggestions.extend([
                f"重新执行'{stage.name}'阶段，在Prompt中明确要求返回标准JSON格式",
                "使用更宽松的解析策略，尝试提取关键信息",
                f"如果'{stage.name}'不是必需的，考虑跳过此阶段"
            ])
        elif "timeout" in error_lower:
            suggestions.extend([
                f"增加'{stage.name}'阶段的超时时间后重试",
                "简化任务复杂度，减少LLM处理时间",
                "切换到更快的LLM模型"
            ])
        elif "api" in error_lower or "network" in error_lower:
            suggestions.extend([
                f"等待片刻后重试'{stage.name}'阶段",
                "检查网络连接和API密钥配置",
                "切换到备用API服务"
            ])
        else:
            suggestions.append(f"检查'{stage.name}'阶段的输入参数，调整后重试")

        return suggestions

    def _execute_stage_with_retry(
        self,
        stage: WorkflowStage,
        params: Dict[str, Any],
        prev_results: List[Any]
    ) -> tuple[bool, Any]:
        """带重试机制的阶段执行

        Args:
            stage: 阶段对象
            params: 用户参数
            prev_results: 前序结果

        Returns:
            (是否成功, 结果)
        """
        for attempt in range(stage.retry_limit):
            try:
                stage.status = ToolStatus.RUNNING
                result = self.execute_stage(stage, params, prev_results)
                return True, result

            except Exception as e:
                stage.error = str(e)
                logger.warning(
                    f"{self.name}: 阶段{stage.stage_id}执行失败 "
                    f"(尝试{attempt + 1}/{stage.retry_limit}), error={str(e)}"
                )

                if attempt == stage.retry_limit - 1:
                    # 重试次数用尽
                    return False, None

        return False, None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, status={self.status.value}, stages={len(self.stages)})"
