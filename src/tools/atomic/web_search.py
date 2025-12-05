"""Web搜索工具

支持Tavily和Serper两个搜索引擎，Tavily为主，Serper为备用。
"""

import requests
from typing import Dict, Any, List
from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchTool(BaseAtomicTool):
    """Web搜索工具

    使用Tavily API（主）或Serper API（备）进行网络搜索。
    """

    name = "web_search"
    description = "搜索互联网获取实时信息和最新内容。适用于需要网络资料、新闻、博客文章、用户评论等场景。"
    required_params = ["query"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或查询语句"
            },
            "max_results": {
                "type": "integer",
                "description": "返回的最大结果数量,默认5",
                "default": 5
            }
        },
        "required": ["query"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.tavily_key = config.tavily_api_key
        self.serper_key = config.serper_api_key
        self.timeout = 15

    def execute(self, query: str, max_results: int = 5, search_depth: str = "basic") -> Dict[str, Any]:
        """执行Web搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数
            search_depth: 搜索深度（basic/advanced）

        Returns:
            搜索结果字典
        """
        # 优先使用Tavily
        if self.tavily_key:
            try:
                logger.info(f"使用Tavily搜索: query='{query}'")
                return self._tavily_search(query, max_results, search_depth)
            except Exception as e:
                logger.warning(f"Tavily搜索失败: {str(e)}, 切换到Serper")

        # 回退到Serper
        if self.serper_key:
            try:
                logger.info(f"使用Serper搜索: query='{query}'")
                return self._serper_search(query, max_results)
            except Exception as e:
                logger.error(f"Serper搜索失败: {str(e)}")
                raise

        raise RuntimeError("没有可用的搜索引擎API")

    def _tavily_search(self, query: str, max_results: int, search_depth: str) -> Dict[str, Any]:
        """使用Tavily API搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数
            search_depth: 搜索深度

        Returns:
            标准化的搜索结果
        """
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "api_key": self.tavily_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": False
        }

        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        # 标准化返回格式
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "score": item.get("score", 0.0)
            })

        return {
            "query": query,
            "answer": data.get("answer"),  # Tavily特有的AI生成答案
            "results": results,
            "source": "tavily",
            "total": len(results)
        }

    def _serper_search(self, query: str, max_results: int) -> Dict[str, Any]:
        """使用Serper API搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            标准化的搜索结果
        """
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.serper_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": max_results
        }

        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        # 标准化返回格式
        results = []
        for item in data.get("organic", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "position": item.get("position", 0)
            })

        return {
            "query": query,
            "answer": None,  # Serper没有AI生成答案
            "results": results,
            "source": "serper",
            "total": len(results)
        }

    def search_with_filter(
        self,
        query: str,
        site: str = None,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """带站点过滤的搜索

        Args:
            query: 搜索查询
            site: 限定站点（如"xiaohongshu.com"）
            max_results: 最大结果数

        Returns:
            搜索结果
        """
        if site:
            query = f"site:{site} {query}"

        return self.execute(query, max_results)
