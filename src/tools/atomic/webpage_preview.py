"""网页预览工具

在右侧预览面板展示在线网页（使用iframe）。
"""

from typing import Dict, Any
from urllib.parse import urlparse
from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WebPagePreviewTool(BaseAtomicTool):
    """网页预览工具

    将在线网页URL加载到右侧预览面板，使用iframe展示网页内容。
    """

    name = "webpage_preview"
    description = "在右侧面板预览在线网页。当用户要求预览、查看、打开某个网页URL时使用此工具。"
    required_params = ["url"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要预览的网页URL，必须以http://或https://开头"
            },
            "title": {
                "type": "string",
                "description": "网页标题（可选），如果不提供则使用URL作为标题"
            }
        },
        "required": ["url"]
    }

    def __init__(self, config):
        super().__init__(config)

    def execute(self, url: str, title: str = None) -> Dict[str, Any]:
        """预览网页

        Args:
            url: 网页URL
            title: 网页标题（可选）

        Returns:
            包含URL和generated_files的结果字典
        """
        # 验证URL格式
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"URL必须以http://或https://开头: {url}")

        # 解析URL，提取域名作为默认标题
        parsed = urlparse(url)
        default_title = parsed.netloc or url
        display_title = title or default_title

        logger.info(f"网页预览: {url} (标题: {display_title})")

        # 返回结果，generated_files中包含URL，前端会识别并加载
        return {
            "url": url,
            "title": display_title,
            "generated_files": [url],  # 前端通过这个字段识别要预览的URL
            "type": "webpage",
            "message": f"已加载网页: {display_title}"
        }
