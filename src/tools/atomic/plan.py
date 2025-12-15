"""任务规划工具

用于复杂多步骤任务的规划、跟踪和管理。
"""

from typing import Dict, Any, List
from src.tools.base import BaseAtomicTool
from src.tools.result import ToolResult
from src.utils.logger import get_logger
import json

logger = get_logger(__name__)


class PlanTool(BaseAtomicTool):
    """任务规划工具

    帮助LLM规划和跟踪复杂任务的执行步骤。
    """

    name = "create_plan"
    description = (
        "任务规划工具: 为复杂多步骤任务创建执行计划和进度跟踪（自动保存到plan.json）。"
        "适用场景：任务包含3个以上步骤、需要分阶段执行、需要向用户展示进度。"
        "典型场景：数据分析项目（获取→清洗→分析→可视化）、内容创作流程（调研→撰写→配图→校对）。"
        "优势：结构化验证、自动统计进度、格式化摘要展示、自动持久化到文件。"
        "不适用：简单的单步或两步任务。"
        "参数: task_description(任务总体描述), steps(步骤列表,每步包含step/action/status/result), conversation_id(必需)"
    )
    required_params = ["task_description", "steps", "conversation_id"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "任务的总体描述,说明要完成什么目标"
            },
            "steps": {
                "type": "array",
                "description": "任务的具体步骤列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {
                            "type": "integer",
                            "description": "步骤编号(从1开始)"
                        },
                        "action": {
                            "type": "string",
                            "description": "该步骤要执行的动作描述"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "failed"],
                            "description": "步骤状态: pending(待执行), in_progress(进行中), completed(已完成), failed(失败)"
                        },
                        "result": {
                            "type": "string",
                            "description": "步骤的执行结果或备注(可选)"
                        }
                    },
                    "required": ["step", "action", "status"]
                }
            },
            "conversation_id": {
                "type": "string",
                "description": "会话ID(必需,用于保存plan文件到对应会话目录)"
            }
        },
        "required": ["task_description", "steps", "conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.current_plan = None
        self.output_dir = config.output_dir

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行任务规划

        Args:
            task_description: 任务总体描述
            steps: 步骤列表,每个步骤包含:
                - step: 步骤编号
                - action: 动作描述
                - status: 状态 (pending/in_progress/completed/failed)
                - result: 结果(可选)
            conversation_id: 会话ID(必需,用于保存plan文件)

        Returns:
            ToolResult
        """
        try:
            task_description = kwargs.get("task_description", "")
            steps = kwargs.get("steps", [])
            conversation_id = kwargs.get("conversation_id")
            output_dir_name = kwargs.get("_output_dir_name")  # 由master_agent统一注入

            if not task_description:
                raise ValueError("缺少task_description参数")

            if not conversation_id:
                raise ValueError("缺少conversation_id参数")

            if not output_dir_name:
                raise ValueError("缺少_output_dir_name参数（应由master_agent自动注入）")

            if not isinstance(steps, list):
                raise ValueError("steps必须是列表类型")

            # 验证步骤格式
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    raise ValueError(f"步骤{i+1}必须是字典类型")

                required_fields = ["step", "action", "status"]
                for field in required_fields:
                    if field not in step:
                        raise ValueError(f"步骤{i+1}缺少必需字段: {field}")

                # 验证状态值
                valid_statuses = ["pending", "in_progress", "completed", "failed"]
                if step["status"] not in valid_statuses:
                    raise ValueError(f"步骤{i+1}的状态必须是: {', '.join(valid_statuses)}")

            # 保存计划（内存）
            self.current_plan = {
                "task_description": task_description,
                "steps": steps,
                "total_steps": len(steps),
                "completed_steps": len([s for s in steps if s["status"] == "completed"]),
                "in_progress_steps": len([s for s in steps if s["status"] == "in_progress"]),
                "pending_steps": len([s for s in steps if s["status"] == "pending"]),
                "failed_steps": len([s for s in steps if s["status"] == "failed"])
            }

            # 持久化到文件
            plan_dir = self.output_dir / output_dir_name
            plan_dir.mkdir(parents=True, exist_ok=True)
            plan_file = plan_dir / "plan.json"

            with open(plan_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_plan, f, ensure_ascii=False, indent=2)

            logger.info(f"Plan已保存到: {plan_file}")

            # 生成可读的计划摘要
            summary = self._format_plan_summary(self.current_plan)

            logger.info(f"任务计划已创建/更新: {task_description}")
            logger.info(f"总步骤: {len(steps)}, 已完成: {self.current_plan['completed_steps']}")

            # 🔧 关键修复：返回generated_files，让前端能实时预览生成的plan.json
            return {
                "status": "success",
                "data": {
                    "summary": summary,
                    "plan": self.current_plan,
                    "saved_to": "plan.json",
                    "plan_file_path": str(plan_file)
                },
                "generated_files": ["plan.json"]
            }

        except Exception as e:
            logger.error(f"创建计划失败: {str(e)}")
            raise RuntimeError(f"创建计划失败: {str(e)}")

    def _format_plan_summary(self, plan: Dict) -> str:
        """格式化计划摘要

        Args:
            plan: 计划字典

        Returns:
            格式化的摘要文本
        """
        summary_lines = [
            f"📋 任务计划: {plan['task_description']}",
            f"",
            f"进度: {plan['completed_steps']}/{plan['total_steps']} 已完成",
            f""
        ]

        # 按状态分组显示步骤
        completed = [s for s in plan['steps'] if s['status'] == 'completed']
        in_progress = [s for s in plan['steps'] if s['status'] == 'in_progress']
        pending = [s for s in plan['steps'] if s['status'] == 'pending']
        failed = [s for s in plan['steps'] if s['status'] == 'failed']

        if completed:
            summary_lines.append("✅ 已完成:")
            for step in completed:
                result_info = f" - {step.get('result', '')}" if step.get('result') else ""
                summary_lines.append(f"  {step['step']}. {step['action']}{result_info}")
            summary_lines.append("")

        if in_progress:
            summary_lines.append("🔄 进行中:")
            for step in in_progress:
                summary_lines.append(f"  {step['step']}. {step['action']}")
            summary_lines.append("")

        if pending:
            summary_lines.append("⏳ 待执行:")
            for step in pending:
                summary_lines.append(f"  {step['step']}. {step['action']}")
            summary_lines.append("")

        if failed:
            summary_lines.append("❌ 失败:")
            for step in failed:
                error_info = f" - {step.get('result', '')}" if step.get('result') else ""
                summary_lines.append(f"  {step['step']}. {step['action']}{error_info}")

        return "\n".join(summary_lines)

    def get_current_plan(self) -> Dict:
        """获取当前计划

        Returns:
            当前计划字典,如果没有则返回None
        """
        return self.current_plan
