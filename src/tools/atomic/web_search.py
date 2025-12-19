"""Web搜索工具

支持Tavily和Serper两个搜索引擎，Tavily为主，Serper为备用。
Tavily支持双账号配置，当主账号额度用尽时自动切换到副账号。
"""

import requests
import json
from pathlib import Path
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
        self.tavily_key_primary = config.tavily_api_key_primary
        self.tavily_key_secondary = config.tavily_api_key_secondary
        self.serper_key = config.serper_api_key
        self.timeout = 15

        # 状态文件路径（记录当前使用的Tavily key）
        # 用于多实例共享"已知主账号额度用尽"的状态
        self.state_file = config.output_dir / ".tavily_key_state.json"
        self._current_tavily_key = None
        self._load_state()

    def _load_state(self):
        """从状态文件加载当前使用的Tavily key

        状态文件记录"已知主账号额度用尽"的状态，用于多实例共享信息。
        """
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    current_key_type = state.get("current_key", "primary")

                    # 根据状态文件选择key
                    if current_key_type == "secondary" and self.tavily_key_secondary:
                        self._current_tavily_key = self.tavily_key_secondary
                        logger.info("从状态文件加载：使用Tavily副账号（主账号已知额度用尽）")
                    elif self.tavily_key_primary:
                        self._current_tavily_key = self.tavily_key_primary
                        logger.info("从状态文件加载：使用Tavily主账号")
            else:
                # 默认使用主账号
                self._current_tavily_key = self.tavily_key_primary
                logger.info("首次使用Tavily主账号")
        except Exception as e:
            logger.warning(f"加载Tavily状态文件失败: {e}, 使用主账号")
            self._current_tavily_key = self.tavily_key_primary

    def _save_state(self, key_type: str):
        """保存当前使用的Tavily key状态

        Args:
            key_type: "primary" 或 "secondary"
        """
        try:
            with open(self.state_file, 'w') as f:
                json.dump({"current_key": key_type}, f, indent=2)
            logger.info(f"已保存Tavily状态: {key_type}")
        except Exception as e:
            logger.warning(f"保存Tavily状态失败: {e}")

    def _switch_tavily_key(self):
        """切换到备用Tavily key"""
        if self._current_tavily_key == self.tavily_key_primary and self.tavily_key_secondary:
            self._current_tavily_key = self.tavily_key_secondary
            self._save_state("secondary")
            logger.info("Tavily主账号额度用尽，切换到副账号")
            return True
        elif self._current_tavily_key == self.tavily_key_secondary and self.tavily_key_primary:
            # 如果副账号也失败了，尝试重新使用主账号（可能是临时错误）
            self._current_tavily_key = self.tavily_key_primary
            self._save_state("primary")
            logger.info("Tavily副账号失败，尝试切回主账号")
            return True
        return False

    def execute(self, query: str, max_results: int = 5, search_depth: str = "basic") -> Dict[str, Any]:
        """执行Web搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数
            search_depth: 搜索深度（basic/advanced）

        Returns:
            搜索结果字典
        """
        # 优先使用Tavily（支持双账号自动切换）
        if self._current_tavily_key:
            current_key_type = "primary" if self._current_tavily_key == self.tavily_key_primary else "secondary"

            # 尝试使用当前Tavily key
            try:
                logger.info(f"使用Tavily {current_key_type}账号搜索: query='{query}'")
                return self._tavily_search(query, max_results, search_depth, self._current_tavily_key)

            except requests.exceptions.HTTPError as e:
                # 检查是否是额度用尽错误
                status_code = e.response.status_code if hasattr(e.response, 'status_code') else 0
                error_msg = str(e)

                # 尝试解析错误响应
                try:
                    error_data = e.response.json() if hasattr(e.response, 'json') else {}
                    error_detail = error_data.get('error', '') + ' ' + error_data.get('detail', '')
                except:
                    error_detail = error_msg

                # 判断是否是额度/限制错误
                is_quota_error = (
                    status_code == 429 or  # Too Many Requests
                    status_code == 402 or  # Payment Required
                    "quota" in error_detail.lower() or
                    "limit" in error_detail.lower() or
                    "credit" in error_detail.lower() or
                    "exceeded" in error_detail.lower()
                )

                if is_quota_error:
                    logger.warning(f"Tavily {current_key_type}账号额度用尽或受限: {error_detail}")

                    # 如果有备用key，尝试切换
                    if self._switch_tavily_key():
                        try:
                            new_key_type = "primary" if self._current_tavily_key == self.tavily_key_primary else "secondary"
                            logger.info(f"切换到Tavily {new_key_type}账号重试: query='{query}'")
                            return self._tavily_search(query, max_results, search_depth, self._current_tavily_key)
                        except Exception as e2:
                            logger.warning(f"备用Tavily账号也失败: {str(e2)}, 切换到Serper")
                    else:
                        logger.warning("没有可用的备用Tavily账号")
                else:
                    # 非额度问题的错误，直接抛出
                    logger.error(f"Tavily搜索失败（非额度问题）: {error_detail}")
                    raise

            except Exception as e:
                # 其他非HTTP错误
                logger.error(f"Tavily搜索异常: {str(e)}")
                raise

        # 回退到Serper
        if self.serper_key:
            try:
                logger.info(f"使用Serper搜索: query='{query}'")
                return self._serper_search(query, max_results)
            except Exception as e:
                logger.error(f"Serper搜索失败: {str(e)}")
                raise

        raise RuntimeError("没有可用的搜索引擎API")

    def _tavily_search(self, query: str, max_results: int, search_depth: str, api_key: str) -> Dict[str, Any]:
        """使用Tavily API搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数
            search_depth: 搜索深度
            api_key: Tavily API密钥

        Returns:
            标准化的搜索结果
        """
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "api_key": api_key,
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
