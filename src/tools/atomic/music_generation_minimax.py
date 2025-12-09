"""MiniMax Music Generation 原子工具

使用 MiniMax API (v1/music_generation) 根据提示词和歌词生成音乐。

官方文档: https://platform.minimaxi.com/docs/api-reference/music-generation

依赖:
  - pip install requests

凭据(环境变量):
  - MINIMAX_API_KEY (必需)

参数:
  - prompt(str, 必填): 音乐风格描述
  - conversation_id(str, 必填): 会话ID, 用于输出目录
  - lyrics(str, 可选): 歌词内容
  - model(str): 模型名称 (默认: music-2.0)
  - sample_rate(int): 采样率 (默认: 44100)
  - bitrate(int): 比特率 (默认: 256000)
  - format(str): 输出格式 (默认: mp3)
  - filename(str): 输出文件名
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import os
import requests
import base64

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MusicGenerationMiniMax(BaseAtomicTool):
    name = "music_generation_minimax"
    description = (
        "MiniMax 音乐生成: 根据提示词和歌词生成完整音乐作品，支持风格控制和歌词演唱。"
        "适用场景：背景音乐创作、歌曲制作、音效生成、需要原创音乐的各类场景。"
        "参数: prompt(必填风格描述), conversation_id(必填), lyrics(歌词内容可选), format(输出格式)"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "音乐风格描述"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "lyrics": {"type": "string", "description": "歌词内容"},
            "model": {
                "type": "string",
                "description": "模型名称",
                "default": "music-2.0"
            },
            "sample_rate": {"type": "integer", "description": "采样率", "default": 44100},
            "bitrate": {"type": "integer", "description": "比特率", "default": 256000},
            "format": {"type": "string", "enum": ["mp3", "wav"], "default": "mp3"},
            "filename": {"type": "string", "description": "输出文件名"}
        },
        "required": ["prompt", "conversation_id"]
    }

    def __init__(self, config, conv_manager=None):
        super().__init__(config)
        self.api_key = config.minimax_api_key
        self.api_url = config.minimax_music_api_url
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
            lyrics: Optional[str] = kwargs.get("lyrics")
            model: str = kwargs.get("model") or "music-2.0"
            sample_rate: int = int(kwargs.get("sample_rate") or 44100)
            bitrate: int = int(kwargs.get("bitrate") or 256000)
            fmt: str = (kwargs.get("format") or "mp3").lower()
            filename: Optional[str] = kwargs.get("filename") or f"generated_music.{fmt}"

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
                "audio_setting": {
                    "sample_rate": sample_rate,
                    "bitrate": bitrate,
                    "format": fmt
                }
            }

            # 添加歌词（如果提供）
            if lyrics:
                payload["lyrics"] = lyrics

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            logger.info(f"调用 MiniMax Music Generation API: model={model}, format={fmt}, has_lyrics={bool(lyrics)}")

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_msg = f"MiniMax Music Generation API 错误: HTTP {response.status_code}, {response.text}"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}

            result = response.json()

            # 检查 base_resp.status_code
            base_resp = result.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                error_msg = base_resp.get("status_msg", "未知错误")
                return {"status": "failed", "error": f"MiniMax Music Generation 失败: {error_msg}"}

            # 提取音频数据
            # MiniMax Music API 返回格式: {"base_resp": {...}, "data": {"audio": "base64_string", ...}}
            if "data" in result and "audio" in result["data"]:
                audio_base64 = result["data"]["audio"]

                # 调试信息：检查base64字符串
                logger.info(f"收到音频base64数据，长度: {len(audio_base64)} 字符")

                # 修复base64 padding问题
                # 某些API返回的base64可能缺少padding，需要补全
                missing_padding = len(audio_base64) % 4
                if missing_padding:
                    audio_base64 += '=' * (4 - missing_padding)
                    logger.info(f"已修复base64 padding，补充了 {4 - missing_padding} 个'='")

                try:
                    audio_bytes = base64.b64decode(audio_base64)
                    logger.info(f"base64解码成功，音频数据大小: {len(audio_bytes)} 字节")
                except Exception as decode_error:
                    error_msg = f"base64解码失败: {decode_error}. base64前100字符: {audio_base64[:100]}"
                    logger.error(error_msg)
                    return {"status": "failed", "error": error_msg}

                file_path = work_dir / filename
                file_path.write_bytes(audio_bytes)
                logger.info(f"音乐文件保存成功: {filename}")

                return {
                    "status": "success",
                    "data": {
                        "model": model,
                        "prompt": prompt,
                        "has_lyrics": bool(lyrics),
                        "format": fmt,
                        "sample_rate": sample_rate,
                        "bitrate": bitrate,
                        "file_path": str(file_path)
                    },
                    "generated_files": [filename]
                }
            else:
                # 增加调试信息
                logger.error(f"响应格式异常，result keys: {result.keys()}")
                if "data" in result:
                    logger.error(f"data keys: {result['data'].keys()}")
                return {"status": "failed", "error": "响应中缺少音频数据"}

        except requests.exceptions.RequestException as e:
            logger.error(f"music_generation_minimax 网络请求失败: {e}")
            return {"status": "failed", "error": f"网络请求失败: {str(e)}"}
        except Exception as e:
            logger.error(f"music_generation_minimax 执行失败: {e}")
            return {"status": "failed", "error": str(e)}
