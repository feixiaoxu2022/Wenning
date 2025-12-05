"""URL内容抓取工具

支持Jina Reader和Firecrawl两个服务，Jina为主（免费），Firecrawl为备用。
"""

import requests
from typing import Dict, Any
from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class URLFetchTool(BaseAtomicTool):
    """URL内容抓取工具

    将URL内容转换为Markdown格式，便于LLM处理。
    """

    name = "url_fetch"
    description = "抓取URL内容并转换为Markdown格式"
    required_params = ["url"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要抓取的网页URL"
            }
        },
        "required": ["url"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.firecrawl_key = config.firecrawl_api_key
        self.timeout = 60  # URL抓取超时时间

    def execute(self, url: str) -> Dict[str, Any]:
        """抓取URL内容

        Args:
            url: 目标URL

        Returns:
            抓取结果字典
        """
        # 优先使用Jina Reader（免费）
        try:
            logger.info(f"使用Jina Reader抓取: {url}")
            return self._jina_fetch(url)
        except Exception as e:
            logger.warning(f"Jina Reader失败: {str(e)}, 切换到Firecrawl")

        # 回退到Firecrawl
        if self.firecrawl_key:
            try:
                logger.info(f"使用Firecrawl抓取: {url}")
                return self._firecrawl_fetch(url)
            except Exception as e:
                logger.error(f"Firecrawl失败: {str(e)}")
                raise

        raise RuntimeError("Jina Reader失败且未配置Firecrawl API")

    def _jina_fetch(self, url: str) -> Dict[str, Any]:
        """使用Jina Reader抓取

        Args:
            url: 目标URL

        Returns:
            标准化的抓取结果
        """
        # Jina Reader的URL格式
        jina_url = f"https://r.jina.ai/{url}"

        headers = {
            "X-Return-Format": "markdown",
            "X-Timeout": str(self.timeout)
        }

        response = requests.get(jina_url, headers=headers, timeout=self.timeout)
        response.raise_for_status()

        content = response.text

        # 提取标题（从Markdown的第一个#标题）
        title = ""
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("# "):
                title = line.strip()[2:]
                break

        return {
            "url": url,
            "title": title,
            "content": content,
            "format": "markdown",
            "source": "jina",
            "length": len(content)
        }

    def _firecrawl_fetch(self, url: str) -> Dict[str, Any]:
        """使用Firecrawl抓取

        Args:
            url: 目标URL

        Returns:
            标准化的抓取结果
        """
        api_url = "https://api.firecrawl.dev/v0/scrape"

        headers = {
            "Authorization": f"Bearer {self.firecrawl_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "url": url,
            "formats": ["markdown"]
        }

        response = requests.post(api_url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        return {
            "url": url,
            "title": data.get("metadata", {}).get("title", ""),
            "content": data.get("markdown", ""),
            "format": "markdown",
            "source": "firecrawl",
            "metadata": data.get("metadata", {}),
            "length": len(data.get("markdown", ""))
        }

    def fetch_multiple(self, urls: list[str]) -> list[Dict[str, Any]]:
        """批量抓取多个URL

        Args:
            urls: URL列表

        Returns:
            抓取结果列表
        """
        results = []
        for url in urls:
            try:
                result = self.execute(url)
                results.append(result)
            except Exception as e:
                logger.error(f"抓取URL失败: {url}, error={str(e)}")
                results.append({
                    "url": url,
                    "error": str(e),
                    "status": "failed"
                })

        return results
