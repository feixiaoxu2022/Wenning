"""Prompt模板检索工具

根据预定义的模板类型直接获取最佳实践instruction prompt。
使用enum参数明确列出所有可用模板，无需复杂的模糊检索。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PromptTemplateRetriever(BaseAtomicTool):
    name = "retrieve_prompt_template"
    description = (
        "Prompt模板检索工具: 根据预定义的模板类型获取最佳实践instruction prompt。"
        "适用场景：需要专业prompt指导提升输出质量时、执行特定类型创作任务时。"
        "当前可用模板：tech_demo_video(技术演示视频制作指南 - 参考Anthropic'Claude plays Catan'风格，包含完整视觉规范、动画系统、质量标准)。"
        "参数: template_type(必需，从可用enum中选择)"
    )
    required_params = ["template_type"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "template_type": {
                "type": "string",
                "enum": ["tech_demo_video"],
                "description": "模板类型。tech_demo_video: 技术演示视频制作指南(知识教学、产品演示、技术讲解、带旁白的视频)"
            }
        },
        "required": ["template_type"]
    }

    def __init__(self, config):
        super().__init__(config)

        # 获取模板库路径
        current_file = Path(__file__).resolve()
        base_dir = current_file.parent.parent.parent.parent
        self.templates_dir = base_dir / "prompt_templates"
        self.index_file = self.templates_dir / "templates.json"

        # 加载模板索引
        self.templates_data = self._load_index()

        logger.info(f"PromptTemplateRetriever 初始化完成, 可用模板: {list(self.templates_data.get('templates', {}).keys())}")

    def _load_index(self) -> Dict:
        """加载模板索引文件"""
        if not self.index_file.exists():
            logger.error(f"模板索引文件不存在: {self.index_file}")
            return {"templates": {}}

        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载模板索引失败: {e}")
            return {"templates": {}}

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行prompt模板检索

        Args:
            template_type: 模板类型（从enum中选择）

        Returns:
            {
                "status": "success" | "not_found" | "error",
                "template": {
                    "type": "...",
                    "title": "...",
                    "description": "...",
                    "content": "完整模板内容"
                }
            }
        """
        template_type: str = kwargs.get("template_type", "")

        if not template_type:
            return {
                "status": "error",
                "error": "template_type参数不能为空"
            }

        logger.info(f"检索prompt模板: template_type='{template_type}'")

        # 直接从索引中获取模板信息
        templates = self.templates_data.get("templates", {})

        if template_type not in templates:
            logger.warning(f"模板类型不存在: {template_type}")
            available = list(templates.keys())
            return {
                "status": "not_found",
                "error": f"模板类型 '{template_type}' 不存在",
                "available_templates": available
            }

        template_info = templates[template_type]

        # 读取模板文件内容
        template_file = self.templates_dir / template_info["file_path"]

        if not template_file.exists():
            logger.error(f"模板文件不存在: {template_file}")
            return {
                "status": "error",
                "error": f"模板文件不存在: {template_info['file_path']}"
            }

        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"读取模板文件失败: {e}")
            return {
                "status": "error",
                "error": f"读取模板文件失败: {str(e)}"
            }

        logger.info(f"成功检索模板: {template_info['title']} ({len(content)} 字符)")

        return {
            "status": "success",
            "template": {
                "type": template_type,
                "title": template_info["title"],
                "description": template_info["description"],
                "category": template_info.get("category", ""),
                "content": content
            }
        }
