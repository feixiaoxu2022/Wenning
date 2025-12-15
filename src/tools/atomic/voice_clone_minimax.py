"""MiniMax Voice Clone 原子工具

使用 MiniMax API 克隆用户的音色，返回可用的voice_id。

官方文档: https://platform.minimaxi.com/document/voice-cloning

依赖:
  - pip install requests

凭据(环境变量):
  - MINIMAX_API_KEY (必需)

参数:
  - audio_file(str, 必填): 用户录音文件的路径（支持mp3/m4a/wav，10秒-5分钟，≤20MB）
  - voice_id(str, 必填): 自定义音色ID（如 user_voice_001）
  - conversation_id(str, 必填): 会话ID
  - prompt_audio(str, 可选): 示例音频路径（<8秒，增强克隆效果）
  - prompt_text(str, 可选): 示例音频对应的文本
  - test_text(str, 可选): 试听文本，默认为通用测试语句
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import os
import requests
import time
import base64

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceCloneMiniMax(BaseAtomicTool):
    name = "voice_clone_minimax"
    description = (
        "MiniMax 音色克隆: 上传用户的录音文件，复刻专属音色，返回可用的voice_id供TTS使用。"
        "适用场景：需要使用用户自己的声音进行配音、旁白、语音生成。"
        "参数: audio_file(必填，音频文件路径), voice_id(必填，自定义音色ID), conversation_id(必填)"
        "返回: voice_id和试听音频"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "audio_file": {
                "type": "string",
                "description": "用户录音文件的路径（如 docs/my_recording.m4a）。要求：mp3/m4a/wav格式，10秒-5分钟，≤20MB"
            },
            "voice_id": {
                "type": "string",
                "description": "自定义音色ID（如 user_voice_001）。建议格式：用户名_voice_序号"
            },
            "conversation_id": {
                "type": "string",
                "description": "会话ID(必须)"
            },
            "prompt_audio": {
                "type": "string",
                "description": "可选：示例音频路径（<8秒），用于增强克隆效果"
            },
            "prompt_text": {
                "type": "string",
                "description": "可选：示例音频对应的文本内容"
            },
            "test_text": {
                "type": "string",
                "description": "试听文本，用于生成音色样本",
                "default": "大家好，这是我复刻的声音。现在我可以用这个音色来生成各种语音内容了。"
            }
        },
        "required": ["audio_file", "voice_id", "conversation_id"]
    }

    def __init__(self, config, conv_manager=None):
        super().__init__(config)
        self.api_key = config.minimax_api_key
        self.upload_url = "https://api.minimaxi.com/v1/files/upload"
        self.clone_url = "https://api.minimaxi.com/v1/voice_clone"
        self.timeout = 180  # 克隆可能较慢
        self.output_dir = config.output_dir
        self.conv_manager = conv_manager

    def execute(self, **kwargs) -> Dict[str, Any]:
        # BaseAtomicTool 需要此方法；真实逻辑在 run()
        return {}

    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        try:
            audio_file: str = kwargs.get("audio_file", "").strip()
            voice_id: str = kwargs.get("voice_id", "").strip()
            conv_id: str = kwargs.get("conversation_id", "").strip()
            prompt_audio: Optional[str] = kwargs.get("prompt_audio")
            prompt_text: Optional[str] = kwargs.get("prompt_text")
            test_text: str = kwargs.get("test_text") or "大家好，这是我复刻的声音。现在我可以用这个音色来生成各种语音内容了。"

            # 参数验证
            if not audio_file:
                return {"status": "failed", "error": "audio_file不能为空"}
            if not voice_id:
                return {"status": "failed", "error": "voice_id不能为空"}
            if not conv_id:
                return {"status": "failed", "error": "conversation_id缺失"}
            if not self.api_key:
                return {"status": "failed", "error": "缺少 MINIMAX_API_KEY 环境变量"}

            # 检查音频文件是否存在
            audio_path = Path(audio_file)
            if not audio_path.exists():
                return {"status": "failed", "error": f"音频文件不存在: {audio_file}"}

            # 检查文件格式和大小
            file_ext = audio_path.suffix.lower()
            if file_ext not in ['.mp3', '.m4a', '.wav']:
                return {"status": "failed", "error": f"不支持的音频格式: {file_ext}，仅支持 mp3/m4a/wav"}

            file_size = audio_path.stat().st_size
            if file_size > 20 * 1024 * 1024:  # 20MB
                return {"status": "failed", "error": f"文件过大: {file_size / 1024 / 1024:.1f}MB，最大支持20MB"}

            logger.info(f"开始音色克隆: audio_file={audio_file}, voice_id={voice_id}")

            # 步骤1：上传克隆音频
            logger.info("步骤1: 上传克隆音频...")
            try:
                with open(audio_path, "rb") as f:
                    files = {"file": (audio_path.name, f)}
                    data = {"purpose": "voice_clone"}
                    headers = {"Authorization": f"Bearer {self.api_key}"}

                    response = requests.post(
                        self.upload_url,
                        headers=headers,
                        data=data,
                        files=files,
                        timeout=60
                    )
                    response.raise_for_status()

                result = response.json()
                file_id = result.get("file", {}).get("file_id")

                if not file_id:
                    return {"status": "failed", "error": f"上传失败: {result}"}

                logger.info(f"克隆音频上传成功: file_id={file_id}")

            except Exception as e:
                return {"status": "failed", "error": f"上传克隆音频失败: {str(e)}"}

            # 步骤2：上传示例音频（可选）
            prompt_file_id = None
            if prompt_audio:
                logger.info("步骤2: 上传示例音频...")
                prompt_path = Path(prompt_audio)
                if not prompt_path.exists():
                    logger.warning(f"示例音频文件不存在，跳过: {prompt_audio}")
                else:
                    try:
                        with open(prompt_path, "rb") as f:
                            files = {"file": (prompt_path.name, f)}
                            data = {"purpose": "prompt_audio"}
                            headers = {"Authorization": f"Bearer {self.api_key}"}

                            response = requests.post(
                                self.upload_url,
                                headers=headers,
                                data=data,
                                files=files,
                                timeout=60
                            )
                            response.raise_for_status()

                        result = response.json()
                        prompt_file_id = result.get("file", {}).get("file_id")
                        logger.info(f"示例音频上传成功: file_id={prompt_file_id}")

                    except Exception as e:
                        logger.warning(f"上传示例音频失败，继续克隆: {str(e)}")

            # 步骤3：执行音色克隆
            logger.info(f"步骤3: 执行音色克隆 (voice_id={voice_id})...")

            payload = {
                "file_id": file_id,
                "voice_id": voice_id,
                "text": test_text,
                "model": "speech-2.6-hd"
            }

            # 如果有示例音频，添加到payload
            if prompt_file_id and prompt_text:
                payload["clone_prompt"] = {
                    "prompt_audio": prompt_file_id,
                    "prompt_text": prompt_text
                }

            clone_headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            try:
                response = requests.post(
                    self.clone_url,
                    headers=clone_headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

                result = response.json()
                logger.info(f"克隆响应: {result}")

            except Exception as e:
                return {"status": "failed", "error": f"音色克隆失败: {str(e)}"}

            # 检查响应
            base_resp = result.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                error_msg = base_resp.get("status_msg", "未知错误")
                return {"status": "failed", "error": f"克隆失败: {error_msg}"}

            logger.info(f"音色克隆成功: voice_id={voice_id}")

            # 步骤4：保存试听音频（如果有）
            demo_audio_url = result.get("demo_audio")
            sample_filename = None

            if demo_audio_url:
                logger.info("步骤4: 下载试听音频...")
                try:
                    # 下载试听音频
                    audio_response = requests.get(demo_audio_url, timeout=30)
                    audio_response.raise_for_status()

                    # 保存到输出目录
                    if not self.conv_manager:
                        logger.warning("缺少conv_manager，试听音频未保存")
                    else:
                        output_dir_name = self.conv_manager.get_output_dir_name(conv_id)
                        work_dir = self.output_dir / output_dir_name
                        work_dir.mkdir(parents=True, exist_ok=True)

                        sample_filename = f"voice_sample_{voice_id}.mp3"
                        sample_path = work_dir / sample_filename

                        sample_path.write_bytes(audio_response.content)
                        logger.info(f"试听音频已保存: {sample_filename} ({len(audio_response.content)} bytes)")

                except Exception as e:
                    logger.warning(f"保存试听音频失败: {str(e)}")

            # 步骤5：保存配置信息
            config_info = {
                "voice_id": voice_id,
                "file_id": file_id,
                "source_audio": str(audio_file),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "test_text": test_text,
                "demo_audio_url": demo_audio_url
            }

            if prompt_file_id:
                config_info["prompt_file_id"] = prompt_file_id
                config_info["prompt_text"] = prompt_text

            # 返回结果
            self.status = ToolStatus.SUCCESS
            return {
                "status": "success",
                "voice_id": voice_id,
                "message": f"音色克隆成功！自定义音色ID: {voice_id}",
                "sample_audio": sample_filename,
                "demo_audio_url": demo_audio_url,
                "config": config_info,
                "generated_files": [sample_filename] if sample_filename else [],
                "usage_instruction": f"在TTS工具中使用 voice_id=\"{voice_id}\" 即可使用这个音色"
            }

        except Exception as e:
            self.status = ToolStatus.FAILED
            logger.error(f"音色克隆执行失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"status": "failed", "error": f"音色克隆失败: {str(e)}"}
