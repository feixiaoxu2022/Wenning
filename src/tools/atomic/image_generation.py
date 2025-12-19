"""通用图像生成原子工具

支持多种图像生成后端（Gemini、MiniMax等），通过配置文件选择后端。

依赖:
  - pip install requests

环境变量配置:
  - IMAGE_GENERATION_BACKEND: 后端类型 (gemini/minimax, 默认: gemini)
  - IMAGE_GENERATION_API_KEY: API密钥 (必需)
  - IMAGE_GENERATION_API_URL: API端点 (必需)
  - IMAGE_GENERATION_MODEL: 模型名称 (可选，各后端有默认值)

参数:
  - prompt(str, 必填): 图像描述文本
  - conversation_id(str, 必填): 会话ID, 用于输出目录
  - aspect_ratio(str): 宽高比，如 "16:9", "1:1", "9:16" 等
  - n(int): 生成图像数量，默认: 1
  - quality(str): 图像质量，"standard" 或 "high"，默认: standard
  - filename_prefix(str): 输出文件名前缀
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, List
import os
import requests
import base64

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ImageGeneration(BaseAtomicTool):
    name = "image_generation"
    description = (
        "文生图工具: 根据文本描述生成图像。支持多种宽高比（16:9、1:1、9:16等）和质量选项。"
        "适用场景：社交媒体封面、海报设计、创意插图、产品展示图等各类图像生成需求。"
        "参数: prompt(必填描述), conversation_id(必填), aspect_ratio(宽高比), quality(质量), n(生成数量)"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图像描述文本，详细描述想要生成的图像内容、风格、氛围等"
            },
            "conversation_id": {
                "type": "string",
                "description": "会话ID(必须提供)"
            },
            "aspect_ratio": {
                "type": "string",
                "description": "图像宽高比，如'16:9'(横向)、'9:16'(竖向)、'1:1'(正方形)、'4:3'、'3:4'等",
                "default": "16:9"
            },
            "n": {
                "type": "integer",
                "description": "生成图像数量(1-4)",
                "default": 1
            },
            "quality": {
                "type": "string",
                "enum": ["standard", "high"],
                "description": "图像质量级别",
                "default": "standard"
            },
            "filename_prefix": {
                "type": "string",
                "description": "输出文件名前缀",
                "default": "generated_image"
            }
        },
        "required": ["prompt", "conversation_id"]
    }

    def __init__(self, config, conv_manager=None):
        super().__init__(config)

        # 后端配置（从环境变量读取）
        self.backend = os.getenv("IMAGE_GENERATION_BACKEND", "gemini").lower()
        self.api_key = os.getenv("IMAGE_GENERATION_API_KEY", "")
        self.api_url = os.getenv("IMAGE_GENERATION_API_URL", "")
        self.model = os.getenv("IMAGE_GENERATION_MODEL", "")

        # 如果未配置，尝试使用统一的 agent_model_api_key
        if not self.api_key:
            self.api_key = config.agent_model_api_key

        # 根据后端设置默认值
        if self.backend == "gemini":
            if not self.api_url:
                # 使用统一网关，拼接 Gemini 端点
                base = config.agent_model_base_url.rsplit("/v1/", 1)[0]
                self.api_url = f"{base}/v1/models/gemini-2.5-flash-image"
            if not self.model:
                self.model = "gemini-2.5-flash-image"
        elif self.backend == "minimax":
            if not self.api_url:
                self.api_url = config.minimax_image_api_url
            if not self.model:
                self.model = "image-01"
            if not self.api_key:
                self.api_key = config.minimax_api_key

        self.timeout = getattr(config, "code_executor_timeout", 180)
        self.output_dir = config.output_dir
        self.conv_manager = conv_manager

        logger.info(f"ImageGeneration 初始化: backend={self.backend}, model={self.model}")

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行图像生成的核心逻辑"""
        # 提取通用参数
        prompt: str = (kwargs.get("prompt") or "").strip()
        conv_id: str = kwargs.get("conversation_id")
        aspect_ratio: str = kwargs.get("aspect_ratio") or "16:9"
        n: int = int(kwargs.get("n") or 1)
        quality: str = kwargs.get("quality") or "standard"
        filename_prefix: str = kwargs.get("filename_prefix") or "generated_image"

        # 参数验证
        if not prompt:
            raise RuntimeError("prompt不能为空")
        if not conv_id:
            raise RuntimeError("conversation_id缺失")
        if not self.api_key:
            raise RuntimeError("缺少图像生成API密钥配置")

        # 输出路径（使用带时间戳的输出目录名）
        if not self.conv_manager:
            raise RuntimeError("系统配置错误: 缺少conv_manager")

        output_dir_name = self.conv_manager.get_output_dir_name(conv_id)
        work_dir = self.output_dir / output_dir_name
        work_dir.mkdir(parents=True, exist_ok=True)

        # 根据后端调用不同的生成方法
        if self.backend == "gemini":
            return self._generate_with_gemini(
                prompt, work_dir, aspect_ratio, n, quality, filename_prefix
            )
        elif self.backend == "minimax":
            return self._generate_with_minimax(
                prompt, work_dir, aspect_ratio, n, quality, filename_prefix
            )
        else:
            raise RuntimeError(f"不支持的后端: {self.backend}")

    def _generate_with_gemini(
        self,
        prompt: str,
        work_dir: Path,
        aspect_ratio: str,
        n: int,
        quality: str,
        filename_prefix: str
    ) -> Dict[str, Any]:
        """使用 Gemini API 生成图像"""

        # 构建 Gemini native format 请求
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"Generate an image: {prompt}"}
                    ]
                }
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        logger.info(f"调用 Gemini Image Generation API: model={self.model}, prompt={prompt[:50]}...")

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )

        if response.status_code != 200:
            error_msg = f"Gemini API 错误: HTTP {response.status_code}, {response.text}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        result = response.json()

        # 提取并保存图像（Gemini 返回格式）
        generated_files = []
        images_data = []

        if "candidates" in result:
            for i, candidate in enumerate(result["candidates"]):
                if "content" in candidate and "parts" in candidate["content"]:
                    for j, part in enumerate(candidate["content"]["parts"]):
                        if "inlineData" in part:
                            # Base64 编码的图像
                            mime_type = part["inlineData"].get("mimeType", "image/png")
                            data = part["inlineData"].get("data", "")

                            if data:
                                ext = mime_type.split("/")[-1]
                                filename = f"{filename_prefix}_{len(generated_files)+1}.{ext}"
                                file_path = work_dir / filename

                                # 解码并保存
                                file_path.write_bytes(base64.b64decode(data))
                                generated_files.append(filename)

                                images_data.append({
                                    "filename": filename,
                                    "index": len(generated_files),
                                    "mime_type": mime_type
                                })
                                logger.info(f"图像 {len(generated_files)} 保存成功: {filename}")

        if not generated_files:
            raise RuntimeError("未能从Gemini响应中提取图像数据")

        return {
            "backend": "gemini",
            "model": self.model,
            "prompt": prompt,
            "count": len(generated_files),
            "images": images_data,
            "generated_files": generated_files
        }

    def _generate_with_minimax(
        self,
        prompt: str,
        work_dir: Path,
        aspect_ratio: str,
        n: int,
        quality: str,
        filename_prefix: str
    ) -> Dict[str, Any]:
        """使用 MiniMax API 生成图像"""

        # 构建 MiniMax API 请求
        payload = {
            "model": self.model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "response_format": "url",
            "n": n,
            "prompt_optimizer": False
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        logger.info(f"调用 MiniMax Image Generation API: model={self.model}, aspect_ratio={aspect_ratio}, n={n}")

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )

        if response.status_code != 200:
            error_msg = f"MiniMax API 错误: HTTP {response.status_code}, {response.text}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        result = response.json()

        # 检查 base_resp
        base_resp = result.get("base_resp", {})
        if base_resp.get("status_code") != 0:
            error_msg = base_resp.get("status_msg", "未知错误")
            raise RuntimeError(f"MiniMax API 失败: {error_msg}")

        # 提取并保存图像
        generated_files = []
        images_data = []

        if "data" in result and "image_urls" in result["data"]:
            image_urls = result["data"]["image_urls"]

            for idx, image_url in enumerate(image_urls):
                try:
                    # 下载图像
                    img_response = requests.get(image_url, timeout=30)
                    if img_response.status_code == 200:
                        image_data = img_response.content

                        filename = f"{filename_prefix}_{idx+1}.png"
                        file_path = work_dir / filename
                        file_path.write_bytes(image_data)
                        generated_files.append(filename)

                        images_data.append({
                            "filename": filename,
                            "index": idx + 1,
                            "url": image_url
                        })
                        logger.info(f"图像 {idx+1} 保存成功: {filename}")
                    else:
                        logger.warning(f"下载图像 {idx+1} 失败: HTTP {img_response.status_code}")
                except Exception as e:
                    logger.warning(f"下载图像 {idx+1} 异常: {e}")
                    continue

        if not generated_files:
            raise RuntimeError("未能从MiniMax响应中提取图像数据")

        return {
            "backend": "minimax",
            "model": self.model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "count": len(generated_files),
            "images": images_data,
            "generated_files": generated_files
        }
