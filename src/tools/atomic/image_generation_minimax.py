"""MiniMax Image Generation 原子工具

使用 MiniMax API (v1/image_generation) 根据文本生成图像。

官方文档: https://platform.minimaxi.com/docs/api-reference/image-generation

依赖:
  - pip install requests

凭据(环境变量):
  - MINIMAX_API_KEY (必需)

参数:
  - prompt(str, 必填): 图像描述文本
  - conversation_id(str, 必填): 会话ID, 用于输出目录
  - model(str): 模型名称 (默认: image-01)
  - aspect_ratio(str): 宽高比 (1:1, 16:9, 9:16, 4:3, 3:4) 默认: 16:9
  - response_format(str): 响应格式 'url' 或 'b64_json' (默认: url)
  - n(int): 生成图像数量(1-4), 默认: 1
  - prompt_optimizer(bool): 是否优化prompt, 默认: False
  - subject_reference(list): 主体参考图像列表
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


class ImageGenerationMiniMax(BaseAtomicTool):
    name = "image_generation_minimax"
    description = (
        "MiniMax 文生图（艺术创作模式）: 根据文本描述生成艺术风格图像，使用宽高比参数（16:9、1:1、9:16等），支持AI自动优化prompt。"
        "适用场景：社交媒体封面、海报设计、创意插图、艺术创作等需要创意表达的场景。"
        "参数: prompt(必填描述), conversation_id(必填), aspect_ratio(宽高比), prompt_optimizer(是否优化prompt), n(生成数量)"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "图像描述文本"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "model": {
                "type": "string",
                "description": "模型名称",
                "default": "image-01"
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                "description": "宽高比",
                "default": "16:9"
            },
            "response_format": {
                "type": "string",
                "enum": ["url", "b64_json"],
                "description": "响应格式",
                "default": "url"
            },
            "n": {"type": "integer", "description": "生成图像数量(1-4)", "default": 1},
            "prompt_optimizer": {"type": "boolean", "description": "是否优化prompt", "default": False},
            "filename_prefix": {"type": "string", "description": "输出文件名前缀"}
        },
        "required": ["prompt", "conversation_id"]
    }

    def __init__(self, config, conv_manager=None):
        super().__init__(config)
        self.api_key = config.minimax_api_key
        self.api_url = config.minimax_image_api_url
        self.timeout = getattr(config, "code_executor_timeout", 180)
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
            model: str = kwargs.get("model") or "image-01"
            aspect_ratio: str = kwargs.get("aspect_ratio") or "16:9"
            response_format: str = kwargs.get("response_format") or "url"
            n: int = int(kwargs.get("n") or 1)
            prompt_optimizer: bool = kwargs.get("prompt_optimizer", False)
            filename_prefix: Optional[str] = kwargs.get("filename_prefix") or "generated_image"

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
                "aspect_ratio": aspect_ratio,
                "response_format": response_format,
                "n": n,
                "prompt_optimizer": prompt_optimizer
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            logger.info(f"调用 MiniMax Image Generation API: model={model}, aspect_ratio={aspect_ratio}, n={n}")

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_msg = f"MiniMax Image Generation API 错误: HTTP {response.status_code}, {response.text}"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}

            result = response.json()

            # 检查 base_resp.status_code
            base_resp = result.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                error_msg = base_resp.get("status_msg", "未知错误")
                return {"status": "failed", "error": f"MiniMax Image Generation 失败: {error_msg}"}

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
                            continue
                    except Exception as e:
                        logger.warning(f"下载图像 {idx+1} 异常: {e}")
                        continue

            if not generated_files:
                return {"status": "failed", "error": "未能从响应中提取图像数据"}

            return {
                "status": "success",
                "data": {
                    "model": model,
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "count": len(generated_files),
                    "images": images_data
                },
                "generated_files": generated_files
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"image_generation_minimax 网络请求失败: {e}")
            return {"status": "failed", "error": f"网络请求失败: {str(e)}"}
        except Exception as e:
            logger.error(f"image_generation_minimax 执行失败: {e}")
            return {"status": "failed", "error": str(e)}
