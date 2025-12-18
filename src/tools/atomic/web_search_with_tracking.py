"""Web搜索工具（带使用统计）

在原有web_search基础上增加本地使用量跟踪功能。
"""

import requests
import json
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime
from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchWithTrackingTool(BaseAtomicTool):
    """Web搜索工具（带使用统计）

    在每次搜索时记录：
    - 时间戳
    - 使用的API（Tavily/Serper）
    - 查询内容
    - 结果数量

    统计数据保存在 data/search_usage.jsonl
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

        # 统计文件路径
        self.stats_file = Path("data/search_usage.jsonl")
        self.stats_file.parent.mkdir(exist_ok=True)

    def _log_usage(self, api_name: str, query: str, result_count: int, success: bool):
        """记录使用情况

        Args:
            api_name: API名称（tavily/serper）
            query: 搜索查询
            result_count: 返回结果数
            success: 是否成功
        """
        try:
            usage_record = {
                "timestamp": datetime.now().isoformat(),
                "api": api_name,
                "query": query,
                "result_count": result_count,
                "success": success
            }

            with open(self.stats_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(usage_record, ensure_ascii=False) + "\n")

            logger.info(f"[使用统计] {api_name}: {query[:50]}... → {result_count}条结果")
        except Exception as e:
            logger.warning(f"记录使用统计失败: {e}")

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
                result = self._tavily_search(query, max_results, search_depth)
                self._log_usage("tavily", query, result.get("total", 0), True)
                return result
            except Exception as e:
                logger.warning(f"Tavily搜索失败: {str(e)}, 切换到Serper")
                self._log_usage("tavily", query, 0, False)

        # 回退到Serper
        if self.serper_key:
            try:
                logger.info(f"使用Serper搜索: query='{query}'")
                result = self._serper_search(query, max_results)
                self._log_usage("serper", query, result.get("total", 0), True)
                return result
            except Exception as e:
                logger.error(f"Serper搜索失败: {str(e)}")
                self._log_usage("serper", query, 0, False)
                raise

        raise RuntimeError("没有可用的搜索引擎API")

    def _tavily_search(self, query: str, max_results: int, search_depth: str) -> Dict[str, Any]:
        """使用Tavily API搜索"""
        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
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
            "answer": data.get("answer"),
            "results": results,
            "source": "tavily",
            "total": len(results)
        }

    def _serper_search(self, query: str, max_results: int) -> Dict[str, Any]:
        """使用Serper API搜索"""
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
            "answer": None,
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
        """带站点过滤的搜索"""
        if site:
            query = f"site:{site} {query}"
        return self.execute(query, max_results)

    def get_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """获取使用统计

        Args:
            days: 统计最近N天的数据

        Returns:
            统计信息字典
        """
        if not self.stats_file.exists():
            return {
                "total_searches": 0,
                "tavily_count": 0,
                "serper_count": 0,
                "success_rate": 0.0
            }

        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)

            total = 0
            tavily_count = 0
            serper_count = 0
            success_count = 0

            with open(self.stats_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        record_time = datetime.fromisoformat(record["timestamp"])

                        if record_time >= cutoff_date:
                            total += 1
                            if record["api"] == "tavily":
                                tavily_count += 1
                            elif record["api"] == "serper":
                                serper_count += 1

                            if record["success"]:
                                success_count += 1
                    except:
                        continue

            return {
                "period_days": days,
                "total_searches": total,
                "tavily_count": tavily_count,
                "serper_count": serper_count,
                "success_count": success_count,
                "success_rate": round(success_count / total * 100, 2) if total > 0 else 0.0
            }
        except Exception as e:
            logger.error(f"读取使用统计失败: {e}")
            return {
                "error": str(e)
            }
