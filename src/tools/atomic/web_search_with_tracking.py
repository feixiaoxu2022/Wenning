"""Web搜索工具（带使用统计）

在原有web_search基础上增加本地使用量跟踪功能。
支持Tavily双账号自动切换。
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
    - 使用的API（Tavily主账号/Tavily副账号/Serper）
    - 查询内容
    - 结果数量

    统计数据保存在 data/search_usage.jsonl
    Tavily支持双账号配置，当主账号额度用尽时自动切换到副账号。
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

        # 统计文件路径
        self.stats_file = Path("data/search_usage.jsonl")
        self.stats_file.parent.mkdir(exist_ok=True)

        # 状态文件路径（记录当前使用的Tavily key）
        self.state_file = config.output_dir / ".tavily_key_state.json"
        self._current_tavily_key = None
        self._load_state()

    def _load_state(self):
        """从状态文件加载当前使用的Tavily key

        如果检测到月份变化（quota重置），自动切回主账号
        """
        try:
            current_month = datetime.now().strftime("%Y-%m")

            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    current_key_type = state.get("current_key", "primary")
                    saved_month = state.get("month", "")

                    # 检测月份变化，自动重置到主账号（quota重置）
                    if saved_month and saved_month != current_month:
                        logger.info(f"检测到月份变化（{saved_month} → {current_month}），Tavily quota已重置，切换回主账号")
                        self._current_tavily_key = self.tavily_key_primary
                        self._save_state("primary")  # 更新状态文件
                        return

                    if current_key_type == "secondary" and self.tavily_key_secondary:
                        self._current_tavily_key = self.tavily_key_secondary
                        logger.info("从状态文件加载：使用Tavily副账号（主账号已知额度用尽）")
                    elif self.tavily_key_primary:
                        self._current_tavily_key = self.tavily_key_primary
                        logger.info("从状态文件加载：使用Tavily主账号")
            else:
                self._current_tavily_key = self.tavily_key_primary
                logger.info("首次使用Tavily主账号")
        except Exception as e:
            logger.warning(f"加载Tavily状态文件失败: {e}, 使用主账号")
            self._current_tavily_key = self.tavily_key_primary

    def _save_state(self, key_type: str):
        """保存当前使用的Tavily key状态（附带月份信息）"""
        try:
            current_month = datetime.now().strftime("%Y-%m")
            with open(self.state_file, 'w') as f:
                json.dump({
                    "current_key": key_type,
                    "month": current_month
                }, f, indent=2)
            logger.info(f"已保存Tavily状态: {key_type} (月份: {current_month})")
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
            self._current_tavily_key = self.tavily_key_primary
            self._save_state("primary")
            logger.info("Tavily副账号失败，尝试切回主账号")
            return True
        return False

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
        # 优先使用Tavily（支持双账号自动切换）
        if self._current_tavily_key:
            current_key_type = "primary" if self._current_tavily_key == self.tavily_key_primary else "secondary"

            # 尝试使用当前Tavily key
            try:
                logger.info(f"使用Tavily {current_key_type}账号搜索: query='{query}'")
                result = self._tavily_search(query, max_results, search_depth, self._current_tavily_key)
                self._log_usage(f"tavily_{current_key_type}", query, result.get("total", 0), True)
                return result

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
                    status_code == 432 or  # Tavily: Insufficient Credits
                    "quota" in error_detail.lower() or
                    "limit" in error_detail.lower() or
                    "credit" in error_detail.lower() or
                    "exceeded" in error_detail.lower()
                )

                if is_quota_error:
                    logger.warning(f"Tavily {current_key_type}账号额度用尽或受限: {error_detail}")
                    self._log_usage(f"tavily_{current_key_type}", query, 0, False)

                    # 如果有备用key，尝试切换
                    if self._switch_tavily_key():
                        try:
                            new_key_type = "primary" if self._current_tavily_key == self.tavily_key_primary else "secondary"
                            logger.info(f"切换到Tavily {new_key_type}账号重试: query='{query}'")
                            result = self._tavily_search(query, max_results, search_depth, self._current_tavily_key)
                            self._log_usage(f"tavily_{new_key_type}", query, result.get("total", 0), True)
                            return result
                        except Exception as e2:
                            logger.warning(f"备用Tavily账号也失败: {str(e2)}, 切换到Serper")
                            self._log_usage(f"tavily_{new_key_type}", query, 0, False)
                    else:
                        logger.warning("没有可用的备用Tavily账号")
                else:
                    # 非额度问题的错误，直接抛出
                    logger.error(f"Tavily搜索失败（非额度问题）: {error_detail}")
                    self._log_usage(f"tavily_{current_key_type}", query, 0, False)
                    raise

            except Exception as e:
                # 其他非HTTP错误
                logger.error(f"Tavily搜索异常: {str(e)}")
                self._log_usage(f"tavily_{current_key_type}", query, 0, False)
                raise

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
        headers = {"Content-Type": "application/json"}
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
