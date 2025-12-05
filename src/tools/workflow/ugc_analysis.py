"""UGC分析工作流

完整的用户生成内容（UGC）分析流程，包含数据采集、情感分析、内容筛选、回复生成和报告生成。
"""

import json
from typing import Dict, Any, List
from datetime import datetime
from src.tools.base import BaseWorkflowTool, WorkflowStage
from src.tools.atomic.web_search import WebSearchTool
from src.tools.atomic.code_executor import CodeExecutor
from src.llm.prompts import (
    UGC_SENTIMENT_ANALYSIS_PROMPT,
    UGC_FILTER_PROMPT,
    UGC_REPLY_GENERATION_PROMPT,
    format_prompt
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UGCAnalysisWorkflow(BaseWorkflowTool):
    """UGC分析工作流

    5步流程：数据采集 → 情感分析 → 内容筛选 → 回复生成 → Excel报告
    """

    name = "ugc_analysis"
    description = "分析社交媒体用户评论，生成分析报告和回复建议"

    def __init__(self, config, llm_client):
        super().__init__(config, llm_client)

        # 初始化Atomic Tools
        self.web_search = WebSearchTool(config)
        self.code_executor = CodeExecutor(config)

    def define_stages(self) -> List[WorkflowStage]:
        """定义5个工作流阶段"""
        return [
            WorkflowStage(
                stage_id=1,
                name="数据采集",
                description="通过Web搜索采集UGC数据",
                critical=True,
                retry_limit=3
            ),
            WorkflowStage(
                stage_id=2,
                name="情感分析",
                description="LLM分析评论情感倾向",
                critical=True,
                retry_limit=2
            ),
            WorkflowStage(
                stage_id=3,
                name="内容筛选",
                description="筛选高价值评论",
                critical=False,  # 非关键，失败可跳过
                retry_limit=2
            ),
            WorkflowStage(
                stage_id=4,
                name="回复生成",
                description="生成回复建议",
                critical=True,
                retry_limit=2
            ),
            WorkflowStage(
                stage_id=5,
                name="报告生成",
                description="生成Excel分析报告",
                critical=True,
                retry_limit=3
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
            return self._stage1_data_collection(params)

        elif stage.stage_id == 2:
            comments_data = prev_results[0]
            return self._stage2_sentiment_analysis(comments_data)

        elif stage.stage_id == 3:
            sentiment_data = prev_results[1]
            return self._stage3_content_filtering(params, sentiment_data)

        elif stage.stage_id == 4:
            # 如果阶段3失败，使用阶段2的结果
            filtered_data = prev_results[2] if prev_results[2] else prev_results[1]
            return self._stage4_reply_generation(filtered_data)

        elif stage.stage_id == 5:
            return self._stage5_report_generation(params, prev_results)

        else:
            raise ValueError(f"未知阶段: {stage.stage_id}")

    def _stage1_data_collection(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """阶段1: 数据采集

        Args:
            params: 包含platform, keyword等

        Returns:
            采集的评论数据
        """
        platform = params.get("platform", "")
        keyword = params.get("keyword", "")
        max_results = params.get("max_results", 10)

        # 如果关键参数缺失,尝试从user_input中提取
        if not keyword and "user_input" in params:
            import re
            user_input = params["user_input"]

            # 提取引号内容作为keyword
            keyword_match = re.search(r'["""](.*?)["""]', user_input)
            if keyword_match:
                keyword = keyword_match.group(1)

            # 提取平台
            if not platform:
                for p in ["小红书", "抖音", "微博", "知乎", "B站"]:
                    if p in user_input:
                        platform = p
                        break

        # 验证必需参数
        if not keyword:
            raise ValueError("缺少必需参数: keyword (关键词)")

        logger.info(f"数据采集: platform={platform}, keyword={keyword}")

        # 构建搜索query
        if platform:
            query = f"site:{platform} {keyword}"
        else:
            query = keyword

        # 调用Web Search Tool
        search_result = self.web_search.run(
            query=query,
            max_results=max_results
        )

        if search_result["status"] != "success":
            raise RuntimeError(f"Web搜索失败: {search_result.get('error')}")

        # 提取评论内容（这里简化为搜索结果的snippet）
        comments = []
        for item in search_result["data"]["results"]:
            comments.append({
                "text": item["snippet"],
                "url": item["url"],
                "title": item["title"]
            })

        logger.info(f"采集到{len(comments)}条评论")

        return {
            "platform": platform,
            "keyword": keyword,
            "comments": comments,
            "total": len(comments),
            "raw_search_result": search_result["data"]
        }

    def _stage2_sentiment_analysis(self, comments_data: Dict[str, Any]) -> Dict[str, Any]:
        """阶段2: 情感分析（LLM直接处理）

        Args:
            comments_data: 阶段1的评论数据

        Returns:
            情感分析结果
        """
        comments = comments_data["comments"]
        logger.info(f"情感分析: {len(comments)}条评论")

        # 构建prompt
        comments_text = "\n\n".join([
            f"[{i+1}] {c['text']}" for i, c in enumerate(comments)
        ])

        prompt = format_prompt(
            UGC_SENTIMENT_ANALYSIS_PROMPT,
            comments=comments_text
        )

        # LLM分析
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.3)

        # 解析LLM返回的JSON（多重容错策略）
        import re
        content = response["content"]

        # 调试日志：打印原始返回内容
        logger.debug(f"LLM原始返回内容前200字符: {repr(content[:200])}")

        analysis_result = None

        # 策略1: 直接解析JSON
        try:
            analysis_result = json.loads(content)
            logger.info("直接解析JSON成功")
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"直接解析JSON失败: {str(e)}")

            # 策略2: 清理前后空白后解析
            try:
                analysis_result = json.loads(content.strip())
                logger.info("清理空白后解析成功")
            except:
                # 策略3: 提取```json代码块
                json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    try:
                        analysis_result = json.loads(json_match.group(1).strip())
                        logger.info("从```json代码块提取成功")
                    except:
                        pass

                # 策略4: 提取任意```代码块
                if not analysis_result:
                    json_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
                    if json_match:
                        try:
                            analysis_result = json.loads(json_match.group(1).strip())
                            logger.info("从```代码块提取成功")
                        except:
                            pass

                # 策略5: 提取{}或[]包裹的内容
                if not analysis_result:
                    json_match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
                    if json_match:
                        try:
                            analysis_result = json.loads(json_match.group(1).strip())
                            logger.info("从{}包裹内容提取成功")
                        except:
                            pass

        # 如果所有策略都失败,抛出异常让workflow的重试机制处理
        if not analysis_result:
            error_msg = f"无法解析LLM返回的JSON。原始内容前100字符: {content[:200]}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 确保解析结果是字典
        if not isinstance(analysis_result, dict):
            error_msg = f"LLM返回的JSON解析后不是字典类型，而是 {type(analysis_result).__name__}。内容: {str(analysis_result)[:200]}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"情感分析完成: {analysis_result.get('overall_sentiment', 'unknown')}")

        return {
            "comments_with_sentiment": analysis_result.get("comments", comments),
            "overall_sentiment": analysis_result.get("overall_sentiment"),
            "statistics": analysis_result.get("statistics"),
            "raw_llm_response": response
        }

    def _stage3_content_filtering(
        self,
        params: Dict[str, Any],
        sentiment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """阶段3: 内容筛选（LLM直接处理）

        Args:
            params: 用户参数（可能包含筛选条件）
            sentiment_data: 阶段2的情感分析结果

        Returns:
            筛选后的高价值评论
        """
        filter_criteria = params.get("filter_criteria", "筛选出情感强烈（正面或负面）且内容详细的评论")

        logger.info(f"内容筛选: criteria={filter_criteria}")

        # 构建prompt
        comments_json = json.dumps(
            sentiment_data["comments_with_sentiment"],
            ensure_ascii=False,
            indent=2
        )

        prompt = format_prompt(
            UGC_FILTER_PROMPT,
            filter_criteria=filter_criteria,
            comments_data=comments_json
        )

        # LLM筛选
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.2)

        try:
            filter_result = json.loads(response["content"])
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"筛选结果非标准JSON: {str(e)}，尝试提取代码块")

            # 尝试提取```json ... ```格式
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', response["content"], re.DOTALL)
            if json_match:
                try:
                    filter_result = json.loads(json_match.group(1))
                    logger.info("成功从代码块提取JSON")
                except:
                    filter_result = {"filtered_comments": sentiment_data["comments_with_sentiment"]}
            else:
                filter_result = {"filtered_comments": sentiment_data["comments_with_sentiment"]}

        filtered_count = len(filter_result.get("filtered_comments", []))
        logger.info(f"筛选完成: {filtered_count}条高价值评论")

        return filter_result

    def _stage4_reply_generation(self, filtered_data: Dict[str, Any]) -> Dict[str, Any]:
        """阶段4: 回复生成（LLM直接处理）

        Args:
            filtered_data: 阶段3的筛选结果

        Returns:
            回复建议
        """
        comments = filtered_data.get("filtered_comments", [])
        logger.info(f"回复生成: {len(comments)}条评论")

        # 限制评论数量（避免prompt过长）
        if len(comments) > 10:
            logger.info(f"评论数量过多，仅对前10条生成回复")
            comments = comments[:10]

        comments_json = json.dumps(comments, ensure_ascii=False, indent=2)

        prompt = format_prompt(
            UGC_REPLY_GENERATION_PROMPT,
            comments=comments_json
        )

        # LLM生成回复
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ], temperature=0.7)

        try:
            reply_result = json.loads(response["content"])
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"回复生成结果非标准JSON: {str(e)}，尝试提取代码块")

            # 尝试提取```json ... ```格式
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', response["content"], re.DOTALL)
            if json_match:
                try:
                    reply_result = json.loads(json_match.group(1))
                    logger.info("成功从代码块提取JSON")
                except:
                    reply_result = {"raw_response": response["content"]}
            else:
                reply_result = {"raw_response": response["content"]}

        logger.info(f"回复生成完成: {len(reply_result.get('replies', []))}条回复")

        return reply_result

    def _stage5_report_generation(
        self,
        params: Dict[str, Any],
        prev_results: List[Any]
    ) -> Dict[str, Any]:
        """阶段5: Excel报告生成（LLM代码生成 + 代码执行）

        Args:
            params: 用户参数
            prev_results: 前4个阶段的所有结果

        Returns:
            报告文件路径
        """
        logger.info("生成Excel报告")

        # 整合所有数据
        all_data = {
            "platform": params.get("platform"),
            "keyword": params.get("keyword"),
            "collection_time": datetime.now().isoformat(),
            "comments": prev_results[0]["comments"],
            "sentiment_analysis": prev_results[1],
            "filtered_comments": prev_results[2].get("filtered_comments", []) if prev_results[2] else [],
            "replies": prev_results[3].get("replies", [])
        }

        # 生成文件名（工作目录由CodeExecutor按对话隔离设定）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ugc_analysis_{timestamp}.xlsx"

        # LLM生成openpyxl代码（要求保存为当前工作目录下的 filename）
        code_prompt = f"""
生成Python代码，使用openpyxl创建UGC分析Excel报告。

数据（JSON格式）：
{json.dumps(all_data, ensure_ascii=False, indent=2)}

要求：
1. 使用openpyxl库
2. 创建多个sheet：原始评论、情感分析、回复建议
3. 设置表头样式（加粗）
4. 保存为: {filename} （直接保存到当前工作目录）
5. 只输出Python代码，不要解释

代码用```python包裹。
"""

        # LLM生成代码
        code = self.llm.generate_code(
            task_description=code_prompt,
            language="python"
        )

        logger.info(f"生成的代码长度: {len(code)} characters")

        # 执行代码
        exec_result = self.code_executor.run(
            code=code,
            output_filename=filename,
            conversation_id=params.get("conversation_id")
        )

        if exec_result["status"] != "success":
            raise RuntimeError(f"Excel生成失败: {exec_result.get('error')}")

        logger.info(f"Excel报告生成成功: {filename}")

        return {
            "report_path": filename,
            "filename": filename,
            "generated_files": exec_result["data"].get("generated_files", []),
            "code_execution": exec_result
        }
