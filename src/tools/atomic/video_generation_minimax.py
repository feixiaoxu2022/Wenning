"""MiniMax Video Generation 原子工具

使用 MiniMax API (v1/video_generation) 根据文本生成视频。

官方文档: https://platform.minimaxi.com/docs/api-reference/video-generation

依赖:
  - pip install requests

凭据(环境变量):
  - MINIMAX_API_KEY (必需)

参数:
  - prompt(str, 必填): 视频描述文本
  - conversation_id(str, 必填): 会话ID, 用于输出目录
  - model(str): 模型名称 (默认: MiniMax-Hailuo-2.3)
  - duration(int): 视频时长(秒), 默认: 6
  - resolution(str): 分辨率 (720P, 1080P), 默认: 1080P
  - filename(str): 输出文件名
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import os
import requests
import time

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VideoGenerationMiniMax(BaseAtomicTool):
    name = "video_generation_minimax"
    description = (
        "MiniMax 文生视频（AI生成模式）: 根据文本描述生成6秒自然场景短视频，支持720P/1080P分辨率。"
        "适用场景：产品宣传片段、自然风景视频、人物动作、创意视觉效果等AI生成内容。"
        "不适用：数据动画、算法演示（使用code_executor+matplotlib）、视频编辑剪辑（使用code_executor+moviepy）。"
        "参数: prompt(必填描述), conversation_id(必填), duration(时长秒), resolution(分辨率720P/1080P)"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "视频描述文本"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "model": {
                "type": "string",
                "description": "模型名称",
                "default": "MiniMax-Hailuo-2.3"
            },
            "duration": {"type": "integer", "description": "视频时长(秒)", "default": 6},
            "resolution": {
                "type": "string",
                "enum": ["720P", "1080P"],
                "description": "分辨率",
                "default": "1080P"
            },
            "filename": {"type": "string", "description": "输出文件名"}
        },
        "required": ["prompt", "conversation_id"]
    }

    def __init__(self, config, conv_manager=None):
        super().__init__(config)
        self.api_key = config.minimax_api_key
        self.api_url = config.minimax_video_api_url
        # 视频生成通常需要更长时间
        self.timeout = int(os.getenv("MINIMAX_VIDEO_TIMEOUT", "300"))
        self.poll_interval = int(os.getenv("MINIMAX_VIDEO_POLL_INTERVAL", "5"))
        self.max_poll_attempts = int(os.getenv("MINIMAX_VIDEO_MAX_POLL_ATTEMPTS", "120"))
        self.output_dir = config.output_dir
        self.conv_manager = conv_manager

    def execute(self, **kwargs) -> Dict[str, Any]:
        # BaseAtomicTool 需要此方法；真实逻辑在 run()
        return {}

    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        try:
            prompt: str = (kwargs.get("prompt") or "").strip()
            conv_id: str = kwargs.get("conversation_id")
            model: str = kwargs.get("model") or "MiniMax-Hailuo-2.3"
            duration: int = int(kwargs.get("duration") or 6)
            resolution: str = kwargs.get("resolution") or "1080P"
            filename: Optional[str] = kwargs.get("filename") or "generated_video.mp4"

            if not prompt:
                return {"status": "failed", "error": "prompt不能为空"}
            if not conv_id:
                return {"status": "failed", "error": "conversation_id缺失"}

            # 检查凭据
            if not self.api_key:
                return {"status": "failed", "error": "缺少 MINIMAX_API_KEY 环境变量"}

            # 输出路径（使用带时间戳的输出目录名）
            if not self.conv_manager:
                return {"status": "failed", "error": "系统配置错误: 缺少conv_manager"}

            output_dir_name = self.conv_manager.get_output_dir_name(conv_id)
            work_dir = self.output_dir / output_dir_name
            work_dir.mkdir(parents=True, exist_ok=True)

            # 构建请求体（严格按照官方文档格式）
            payload = {
                "model": model,
                "prompt": prompt,
                "duration": duration,
                "resolution": resolution
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            logger.info(f"调用 MiniMax Video Generation API: model={model}, duration={duration}s, resolution={resolution}")

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_msg = f"MiniMax Video Generation API 错误: HTTP {response.status_code}, {response.text}"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}

            result = response.json()

            # 检查 base_resp.status_code
            base_resp = result.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                error_msg = base_resp.get("status_msg", "未知错误")
                return {"status": "failed", "error": f"MiniMax Video Generation 失败: {error_msg}"}

            # 视频生成通常是异步的
            task_id = result.get("data", {}).get("task_id")
            video_url = result.get("data", {}).get("video_url")

            # 情况1: 直接返回视频URL（同步，较少见）
            if video_url:
                video_data = self._download_video(video_url)
                if video_data:
                    file_path = work_dir / filename
                    file_path.write_bytes(video_data)
                    logger.info(f"视频下载成功: {filename}")

                    return {
                        "status": "success",
                        "data": {
                            "model": model,
                            "prompt": prompt,
                            "duration": duration,
                            "resolution": resolution,
                            "video_url": video_url,
                            "file_path": str(file_path)
                        },
                        "generated_files": [filename]
                    }

            # 情况2: 返回task_id，需要轮询（异步，通常情况）
            elif task_id:
                logger.info(f"视频生成任务已提交，task_id={task_id}，开始轮询...")
                video_url = self._poll_task_result(task_id, headers)

                if video_url:
                    video_data = self._download_video(video_url)
                    if video_data:
                        file_path = work_dir / filename
                        file_path.write_bytes(video_data)
                        logger.info(f"视频生成并下载成功: {filename}")

                        return {
                            "status": "success",
                            "data": {
                                "model": model,
                                "prompt": prompt,
                                "duration": duration,
                                "resolution": resolution,
                                "task_id": task_id,
                                "video_url": video_url,
                                "file_path": str(file_path)
                            },
                            "generated_files": [filename]
                        }
                else:
                    return {"status": "failed", "error": "视频生成超时或失败"}

            else:
                return {"status": "failed", "error": "未能从响应中提取task_id或video_url"}

        except requests.exceptions.RequestException as e:
            logger.error(f"video_generation_minimax 网络请求失败: {e}")
            return {"status": "failed", "error": f"网络请求失败: {str(e)}"}
        except Exception as e:
            logger.error(f"video_generation_minimax 执行失败: {e}")
            return {"status": "failed", "error": str(e)}

    def _poll_task_result(self, task_id: str, headers: dict) -> Optional[str]:
        """轮询任务结果，返回视频URL"""
        # 查询端点通常是 /query 或 /task/{task_id}
        query_url = f"{self.api_url.replace('/video_generation', '')}/query"

        for attempt in range(self.max_poll_attempts):
            try:
                time.sleep(self.poll_interval)

                response = requests.get(
                    query_url,
                    headers=headers,
                    params={"task_id": task_id},
                    timeout=30
                )

                if response.status_code != 200:
                    logger.warning(f"轮询失败 (尝试 {attempt + 1}/{self.max_poll_attempts}): HTTP {response.status_code}")
                    continue

                result = response.json()

                # 检查 base_resp
                base_resp = result.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    logger.warning(f"轮询API错误: {base_resp.get('status_msg')}")
                    continue

                status = result.get("data", {}).get("status")
                video_url = result.get("data", {}).get("video_url")

                if status == "completed" or status == "Success":
                    if video_url:
                        logger.info(f"视频生成完成，获取到URL")
                        return video_url
                elif status == "failed" or status == "Failed":
                    error_msg = result.get("data", {}).get("error_message", "未知错误")
                    logger.error(f"视频生成失败: {error_msg}")
                    return None
                elif status in ["pending", "processing", "Processing", "Pending"]:
                    logger.info(f"视频生成中... (尝试 {attempt + 1}/{self.max_poll_attempts}, status={status})")
                    continue

            except Exception as e:
                logger.warning(f"轮询异常 (尝试 {attempt + 1}/{self.max_poll_attempts}): {e}")
                continue

        logger.error(f"轮询超时: 超过 {self.max_poll_attempts * self.poll_interval} 秒未完成")
        return None

    def _download_video(self, video_url: str) -> Optional[bytes]:
        """下载视频文件"""
        try:
            logger.info(f"下载视频: {video_url}")
            response = requests.get(video_url, timeout=120, stream=True)

            if response.status_code == 200:
                # 流式下载，避免内存问题
                content = b""
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        content += chunk
                return content
            else:
                logger.error(f"下载视频失败: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"下载视频异常: {e}")
            return None
