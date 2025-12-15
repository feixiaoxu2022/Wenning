"""MiniMax Text-to-Speech 原子工具

使用 MiniMax API (v1/t2a_v2) 将文本转换为语音。

官方文档: https://platform.minimaxi.com/docs/api-reference/speech-t2a-async

依赖:
  - pip install requests

凭据(环境变量):
  - MINIMAX_API_KEY (必需)

参数:
  - text(str, 必填): 要合成的文本
  - conversation_id(str, 必填): 会话ID, 用于输出目录
  - model(str): 模型名称 (默认: speech-2.6-hd)
  - voice_id(str): 音色ID (例如: male-qn-qingse, female-tianmei-jingpin)
  - speed(float): 语速倍数(0.5~2.0), 默认1.0
  - vol(float): 音量(0.1~10.0), 默认1.0
  - pitch(int): 音调(-12~12), 默认0
  - emotion(str): 情感(happy/sad/angry/fearful/surprised), 默认无
  - format(str): 输出格式 'mp3' 或 'wav' 或 'pcm' (默认 mp3)
  - sample_rate(int): 采样率 (默认: 32000)
  - filename(str): 输出文件名(可选)
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


class TTSMiniMax(BaseAtomicTool):
    name = "tts_minimax"
    description = (
        "MiniMax 语音合成（中文优化）: 将文本转换为自然流畅的语音，支持多种情感表达（开心happy、悲伤sad、愤怒angry等）。"
        "支持使用预设音色或自定义复刻音色（如 feixiaoxu_voice_001）。"
        "适用场景：中文有声内容、需要情感色彩的语音场景、高质量配音。"
        "参数: text(必填文本), conversation_id(必填), voice_id(音色，支持自定义), emotion(情感), speed(语速), format(格式)"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要合成的文本"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "model": {
                "type": "string",
                "description": "模型名称",
                "default": "speech-2.6-hd"
            },
            "voice_id": {
                "type": "string",
                "description": "音色ID。预设音色如：male-qn-qingse, female-tianmei-jingpin；自定义音色如：feixiaoxu_voice_001（用户复刻的音色）",
                "default": "male-qn-qingse"
            },
            "speed": {"type": "number", "description": "语速(0.5~2.0)", "default": 1.0},
            "vol": {"type": "number", "description": "音量(0.1~10.0)", "default": 1.0},
            "pitch": {"type": "integer", "description": "音调(-12~12)", "default": 0},
            "emotion": {
                "type": "string",
                "enum": ["happy", "sad", "angry", "fearful", "surprised"],
                "description": "情感"
            },
            "format": {"type": "string", "enum": ["mp3", "wav", "pcm"], "default": "mp3"},
            "sample_rate": {"type": "integer", "description": "采样率", "default": 32000},
            "filename": {"type": "string", "description": "输出文件名(含后缀)"}
        },
        "required": ["text", "conversation_id"]
    }

    def __init__(self, config, conv_manager=None):
        super().__init__(config)
        self.api_key = config.minimax_api_key
        self.api_url = config.minimax_tts_api_url
        self.timeout = getattr(config, "code_executor_timeout", 180)
        self.output_dir = config.output_dir
        self.conv_manager = conv_manager

    def execute(self, **kwargs) -> Dict[str, Any]:
        # BaseAtomicTool 需要此方法；真实逻辑在 run()
        return {}

    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        try:
            text: str = (kwargs.get("text") or "").strip()
            conv_id: str = kwargs.get("conversation_id")
            model: str = kwargs.get("model") or "speech-2.6-hd"
            voice_id: str = kwargs.get("voice_id") or "male-qn-qingse"
            speed: float = float(kwargs.get("speed") or 1.0)
            vol: float = float(kwargs.get("vol") or 1.0)
            pitch: int = int(kwargs.get("pitch") or 0)
            emotion: Optional[str] = kwargs.get("emotion")
            fmt: str = (kwargs.get("format") or "mp3").lower()
            sample_rate: int = int(kwargs.get("sample_rate") or 32000)
            filename: Optional[str] = kwargs.get("filename")

            if not text:
                return {"status": "failed", "error": "text不能为空"}
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
            if not filename:
                filename = f"narration.{fmt}"
            out_path = work_dir / filename

            # 构建 voice_setting
            voice_setting = {
                "voice_id": voice_id,
                "speed": speed,
                "vol": vol,
                "pitch": pitch
            }
            if emotion:
                voice_setting["emotion"] = emotion

            # 构建请求体（严格按照官方文档格式）
            payload = {
                "model": model,
                "text": text,
                "stream": False,
                "voice_setting": voice_setting,
                "audio_setting": {
                    "sample_rate": sample_rate,
                    "bitrate": 128000,
                    "format": fmt,
                    "channel": 1
                },
                "subtitle_enable": False
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            logger.info(f"调用 MiniMax TTS API: model={model}, voice_id={voice_id}, speed={speed}, emotion={emotion}")

            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_msg = f"MiniMax TTS API 错误: HTTP {response.status_code}, {response.text}"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}

            result = response.json()

            # 检查 base_resp.status_code
            base_resp = result.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                error_msg = base_resp.get("status_msg", "未知错误")
                return {"status": "failed", "error": f"MiniMax TTS 失败: {error_msg}"}

            # 提取音频数据
            # MiniMax TTS API 返回格式: {"base_resp": {...}, "data": {"audio": "hex_or_base64_string", ...}}
            if "data" in result and "audio" in result["data"]:
                audio_encoded = result["data"]["audio"]

                # 调试信息：检查编码数据
                logger.info(f"收到音频编码数据，长度: {len(audio_encoded)} 字符")
                logger.info(f"数据前100字符: {audio_encoded[:100]}")

                # 检测编码类型（十六进制 vs base64）
                # 十六进制只包含 0-9, a-f, A-F
                # Base64包含 A-Z, a-z, 0-9, +, /, =
                is_hex = all(c in '0123456789abcdefABCDEF' for c in audio_encoded)

                try:
                    if is_hex:
                        # 十六进制解码
                        logger.info("检测到十六进制编码，使用hex解码")
                        audio_bytes = bytes.fromhex(audio_encoded)
                        logger.info(f"Hex解码成功，音频数据大小: {len(audio_bytes)} 字节")
                    else:
                        # Base64解码
                        logger.info("检测到base64编码，使用base64解码")
                        import base64
                        # 修复base64 padding问题
                        missing_padding = len(audio_encoded) % 4
                        if missing_padding:
                            audio_encoded += '=' * (4 - missing_padding)
                            logger.info(f"已修复base64 padding，补充了 {4 - missing_padding} 个'='")
                        audio_bytes = base64.b64decode(audio_encoded)
                        logger.info(f"Base64解码成功，音频数据大小: {len(audio_bytes)} 字节")
                except Exception as decode_error:
                    error_msg = f"音频解码失败: {decode_error}. 数据前100字符: {audio_encoded[:100]}"
                    logger.error(error_msg)
                    return {"status": "failed", "error": error_msg}

                # 验证音频文件格式
                if len(audio_bytes) < 10:
                    error_msg = f"音频数据太短（{len(audio_bytes)}字节），可能不是有效的音频文件"
                    logger.error(error_msg)
                    return {"status": "failed", "error": error_msg}

                # 检查文件头，判断实际格式
                header = audio_bytes[:10]
                logger.info(f"音频文件头 (hex): {header.hex()}")

                # MP3文件头: ID3 (0x494433) 或 MPEG sync (0xFFxx)
                # WAV文件头: RIFF (0x52494646)
                actual_format = None
                if header[:3] == b'ID3' or header[0:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2']:
                    actual_format = "mp3"
                    logger.info("✓ 检测到有效的MP3文件格式")
                elif header[:4] == b'RIFF':
                    actual_format = "wav"
                    logger.warning("⚠️ 检测到WAV格式，但请求的是MP3格式")
                else:
                    # 尝试检查是否是文本
                    try:
                        text_sample = audio_bytes[:100].decode('utf-8', errors='ignore')
                        if all(32 <= ord(c) < 127 or c in '\n\r\t' for c in text_sample):
                            logger.error(f"❌ 音频数据实际是文本内容: {text_sample[:200]}")
                            return {"status": "failed", "error": f"API返回的不是音频文件，而是文本: {text_sample[:100]}"}
                    except:
                        pass
                    logger.warning(f"⚠️ 无法识别的音频格式，文件头: {header.hex()}")

                out_path.write_bytes(audio_bytes)
                logger.info(f"音频保存成功: {filename}（实际格式: {actual_format or '未知'}）")

                return {
                    "status": "success",
                    "data": {
                        "model": model,
                        "voice_id": voice_id,
                        "speed": speed,
                        "vol": vol,
                        "pitch": pitch,
                        "emotion": emotion,
                        "format": fmt,
                        "file_path": str(out_path)
                    },
                    "generated_files": [out_path.name]
                }
            else:
                return {"status": "failed", "error": "响应中缺少音频数据"}

        except requests.exceptions.RequestException as e:
            logger.error(f"tts_minimax 网络请求失败: {e}")
            return {"status": "failed", "error": f"网络请求失败: {str(e)}"}
        except Exception as e:
            logger.error(f"tts_minimax 执行失败: {e}")
            return {"status": "failed", "error": str(e)}
