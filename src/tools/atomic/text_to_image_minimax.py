"""MiniMax Text-to-Image 原子工具

使用 MiniMax API 根据文本描述生成图像。

依赖:
  - pip install requests

凭据(环境变量):
  - MINIMAX_API_KEY (必需)
  - MINIMAX_GROUP_ID (必需)
  - MINIMAX_T2I_API_URL (可选, 默认: https://api.minimaxi.com/v1/text_to_image)

参数:
  - prompt(str, 必填): 图像描述文本
  - conversation_id(str, 必填): 会话ID, 用于输出目录
  - model(str): 模型名称 (默认: MiniMax-Text-01)
  - width(int): 图像宽度 (默认: 1024)
  - height(int): 图像高度 (默认: 1024)
  - quality(str): 图像质量 'standard' 或 'high' (默认: standard)
  - n(int): 生成图像数量 (默认: 1)
  - filename_prefix(str): 输出文件名前缀(可选)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, List
import os
import requests
import time
import base64

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TextToImageMiniMax(BaseAtomicTool):
    name = "text_to_image_minimax"
    description = (
        "MiniMax 文生图（精确控制模式）: 根据文本描述生成图像，使用精确的width×height像素尺寸控制，支持质量级别选择。"
        "适用场景：网站banner、产品展示图、打印素材、需要固定尺寸规格的场景。"
        "参数: prompt(必填描述), conversation_id(必填), width(宽度像素), height(高度像素), quality(质量standard/high), n(生成数量)"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "图像描述文本"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "model": {
                "type": "string",
                "description": "模型名称",
                "default": "MiniMax-Text-01"
            },
            "width": {"type": "integer", "description": "图像宽度", "default": 1024},
            "height": {"type": "integer", "description": "图像高度", "default": 1024},
            "quality": {
                "type": "string",
                "enum": ["standard", "high"],
                "description": "图像质量",
                "default": "standard"
            },
            "n": {"type": "integer", "description": "生成图像数量(1-4)", "default": 1},
            "filename_prefix": {"type": "string", "description": "输出文件名前缀"}
        },
        "required": ["prompt", "conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.api_key = os.getenv("MINIMAX_API_KEY") or ""
        self.group_id = os.getenv("MINIMAX_GROUP_ID") or ""
        self.api_url = os.getenv("MINIMAX_T2I_API_URL") or "https://api.minimaxi.com/v1/text_to_image"
        self.timeout = getattr(config, "code_executor_timeout", 180)
        self.output_dir = config.output_dir

    def execute(self, **kwargs) -> Dict[str, Any]:
        # BaseAtomicTool 需要此方法；真实逻辑在 run()
        return {}

    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        try:
            prompt: str = (kwargs.get("prompt") or "").strip()
            conv_id: str = kwargs.get("conversation_id")
            model: str = kwargs.get("model") or "MiniMax-Text-01"
            width: int = int(kwargs.get("width") or 1024)
            height: int = int(kwargs.get("height") or 1024)
            quality: str = kwargs.get("quality") or "standard"
            n: int = int(kwargs.get("n") or 1)
            filename_prefix: Optional[str] = kwargs.get("filename_prefix") or "generated_image"

            if not prompt:
                return {"status": "failed", "error": "prompt不能为空"}
            if not conv_id:
                return {"status": "failed", "error": "conversation_id缺失"}

            # 检查凭据
            if not self.api_key or not self.group_id:
                return {
                    "status": "failed",
                    "error": "缺少 MINIMAX_API_KEY 或 MINIMAX_GROUP_ID 环境变量"
                }

            # 输出路径
            work_dir = self.output_dir / conv_id
            work_dir.mkdir(parents=True, exist_ok=True)

            # 调用 MiniMax Text-to-Image API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "group_id": self.group_id,
                "model": model,
                "prompt": prompt,
                "width": width,
                "height": height,
                "quality": quality,
                "n": n
            }

            logger.info(f"调用 MiniMax Text-to-Image API: model={model}, size={width}x{height}, n={n}")

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_msg = f"MiniMax Text-to-Image API 错误: HTTP {response.status_code}, {response.text}"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}

            result = response.json()

            # MiniMax API 通常返回 base_resp.status_code=0 表示成功
            if result.get("base_resp", {}).get("status_code") != 0:
                error_msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                return {"status": "failed", "error": f"MiniMax Text-to-Image 失败: {error_msg}"}

            # 提取并保存图像
            generated_files = []
            images_data = []

            if "data" in result and "images" in result["data"]:
                images = result["data"]["images"]

                for idx, image_item in enumerate(images):
                    # 处理不同的返回格式
                    image_data = None

                    # 方式1: base64编码
                    if "b64_json" in image_item:
                        image_data = base64.b64decode(image_item["b64_json"])

                    # 方式2: URL
                    elif "url" in image_item:
                        image_url = image_item["url"]
                        img_response = requests.get(image_url, timeout=30)
                        if img_response.status_code == 200:
                            image_data = img_response.content
                        else:
                            logger.warning(f"下载图像 {idx+1} 失败: HTTP {img_response.status_code}")
                            continue

                    if image_data:
                        filename = f"{filename_prefix}_{idx+1}.png"
                        file_path = work_dir / filename
                        file_path.write_bytes(image_data)
                        generated_files.append(filename)
                        images_data.append({
                            "filename": filename,
                            "index": idx + 1,
                            "revised_prompt": image_item.get("revised_prompt", prompt)
                        })
                        logger.info(f"图像 {idx+1} 保存成功: {filename}")

            if not generated_files:
                return {"status": "failed", "error": "未能从响应中提取图像数据"}

            return {
                "status": "success",
                "data": {
                    "model": model,
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "quality": quality,
                    "count": len(generated_files),
                    "images": images_data
                },
                "generated_files": generated_files
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"text_to_image_minimax 网络请求失败: {e}")
            return {"status": "failed", "error": f"网络请求失败: {str(e)}"}
        except Exception as e:
            logger.error(f"text_to_image_minimax 执行失败: {e}")
            return {"status": "failed", "error": str(e)}
