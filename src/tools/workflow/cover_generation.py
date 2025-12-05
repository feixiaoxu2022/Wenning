"""封面生成工作流

生成图文封面的完整流程，包含风格理解、代码生成和图片生成。
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from src.tools.base import BaseWorkflowTool, WorkflowStage
from src.tools.atomic.code_executor import CodeExecutor
from src.llm.prompts import (
    COVER_STYLE_UNDERSTANDING_PROMPT,
    COVER_CODE_GENERATION_PROMPT,
    format_prompt
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CoverGenerationWorkflow(BaseWorkflowTool):
    """封面生成工作流

    3步流程：风格理解 → 代码生成 → 图片生成
    """

    name = "cover_generation"
    description = "生成图文封面图片"

    def __init__(self, config, llm_client):
        super().__init__(config, llm_client)

        # 初始化Code Executor
        self.code_executor = CodeExecutor(config)

    def define_stages(self) -> List[WorkflowStage]:
        """定义3个工作流阶段"""
        return [
            WorkflowStage(
                stage_id=1,
                name="风格理解",
                description="LLM解析用户需求，提取设计要素",
                critical=True,
                retry_limit=2
            ),
            WorkflowStage(
                stage_id=2,
                name="代码生成",
                description="LLM生成PIL图像处理代码",
                critical=True,
                retry_limit=3
            ),
            WorkflowStage(
                stage_id=3,
                name="图片生成",
                description="执行代码生成最终图片",
                critical=True,
                retry_limit=2
            )
        ]

    def execute_stage(
        self,
        stage: WorkflowStage,
        params: Dict[str, Any],
        prev_results: List[Any]
    ) -> Any:
        """执行单个阶段"""

        if stage.stage_id == 1:
            return self._stage1_style_understanding(params)

        elif stage.stage_id == 2:
            design_spec = prev_results[0]
            return self._stage2_code_generation(params, design_spec)

        elif stage.stage_id == 3:
            code_data = prev_results[1]
            return self._stage3_image_generation(code_data, params)

        else:
            raise ValueError(f"未知阶段: {stage.stage_id}")

    def _stage1_style_understanding(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """阶段1: 风格理解（LLM直接处理）

        Args:
            params: 包含title, style等用户需求

        Returns:
            设计规格
        """
        user_requirement = params.get("requirement", "")
        title = params.get("title", "")
        style = params.get("style", "")

        # 整合用户需求
        if not user_requirement:
            user_requirement = f"标题：{title}\n风格：{style}"

        logger.info(f"风格理解: {user_requirement}")

        # 构建prompt
        prompt = format_prompt(
            COVER_STYLE_UNDERSTANDING_PROMPT,
            user_requirement=user_requirement
        )

        # LLM解析
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.5)

        # 解析JSON
        try:
            design_spec = json.loads(response["content"])
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"风格理解返回非标准JSON: {str(e)}，尝试提取代码块")

            # 尝试提取```json ... ```格式
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', response["content"], re.DOTALL)
            if json_match:
                try:
                    design_spec = json.loads(json_match.group(1))
                    logger.info("成功从代码块提取JSON")
                except:
                    design_spec = {
                        "title_text": title,
                        "subtitle_text": "",
                        "color_scheme": {"primary": "#3498db", "background": "#ffffff", "text": "#2c3e50"},
                        "style_keywords": [style] if style else ["简洁", "现代"],
                        "layout": "居中布局"
                    }
            else:
                design_spec = {
                    "title_text": title,
                    "subtitle_text": "",
                    "color_scheme": {"primary": "#3498db", "background": "#ffffff", "text": "#2c3e50"},
                    "style_keywords": [style] if style else ["简洁", "现代"],
                    "layout": "居中布局"
                }

        logger.info(f"设计规格: {design_spec.get('title_text')}, 配色: {design_spec.get('color_scheme', {}).get('primary')}")

        return design_spec

    def _stage2_code_generation(
        self,
        params: Dict[str, Any],
        design_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """阶段2: 代码生成（LLM生成代码）

        Args:
            params: 用户参数
            design_spec: 阶段1的设计规格

        Returns:
            生成的代码
        """
        logger.info("生成PIL代码")

        # 生成文件名（工作目录由CodeExecutor按对话隔离设定）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cover_{timestamp}.png"

        # 构建设计规格描述
        design_desc = json.dumps(design_spec, ensure_ascii=False, indent=2)

        # LLM生成代码：要求直接保存为当前工作目录下的 filename
        prompt = format_prompt(
            COVER_CODE_GENERATION_PROMPT,
            design_spec=design_desc,
            output_path=filename
        )

        code = self.llm.generate_code(
            task_description=prompt,
            language="python"
        )

        logger.info(f"代码生成完成: {len(code)} characters")

        return {
            "code": code,
            "output_path": filename,
            "filename": filename,
            "design_spec": design_spec
        }

    def _stage3_image_generation(self, code_data: Dict[str, Any], params: Dict[str, Any] = None) -> Dict[str, Any]:
        """阶段3: 图片生成（执行代码）

        Args:
            code_data: 阶段2的代码数据

        Returns:
            生成的图片路径
        """
        code = code_data["code"]
        filename = code_data["filename"]

        logger.info(f"执行代码生成图片: {filename}")

        # 执行代码
        conversation_id = None
        if isinstance(params, dict):
            conversation_id = params.get("conversation_id")
        exec_result = self.code_executor.run(
            code=code,
            output_filename=filename,
            conversation_id=conversation_id
        )

        if exec_result["status"] != "success":
            raise RuntimeError(f"图片生成失败: {exec_result.get('error')}")

        generated_files = exec_result["data"].get("generated_files", [])

        if not generated_files:
            raise RuntimeError("代码执行成功但未找到生成的图片文件")

        image_path = generated_files[0]
        logger.info(f"封面生成成功: {image_path}")

        return {
            "image_path": image_path,
            "filename": filename,
            "code_execution": exec_result,
            "design_spec": code_data["design_spec"]
        }
