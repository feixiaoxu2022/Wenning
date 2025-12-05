"""Google Cloud Text-to-Speech 原子工具

使用服务账号凭据调用 Google Cloud TTS 生成旁白音频。

凭据获取方式（二选一）：
- 设置环境变量 GOOGLE_APPLICATION_CREDENTIALS=绝对路径/service-account.json
- 或设置 GCP_TTS_CREDENTIALS_JSON=服务账号JSON内容（整段JSON字符串）

参数（Function Calling）：
- text: 文本（必填）
- conversation_id: 会话ID（必填）
- language_code: 语言代码（默认 'cmn-CN'）
- voice_name: 具体音色（示例：'cmn-CN-Wavenet-A' / 'en-US-Wavenet-F'）
- speaking_rate: 语速（0.25~4.0，默认1.0）
- pitch: 音高（-20.0~20.0，默认0）
- format: 输出格式（'mp3'|'ogg_opus'|'wav'|'linear16'，默认'mp3'）
- filename: 输出文件名（不传则自动按格式生成，例如 narration.mp3）
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import os
import json

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TTSGoogle(BaseAtomicTool):
    name = "tts_google"
    description = (
        "Google Cloud TTS 文本转语音。参数: text(必填), language_code, voice_name, speaking_rate, pitch, format(mp3/ogg_opus/wav/linear16), filename"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要合成的文本"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "language_code": {"type": "string", "description": "语言代码(如 cmn-CN / en-US)", "default": "cmn-CN"},
            "voice_name": {"type": "string", "description": "具体音色(如 cmn-CN-Wavenet-A / en-US-Wavenet-F)"},
            "speaking_rate": {"type": "number", "description": "语速(0.25~4.0)", "default": 1.0},
            "pitch": {"type": "number", "description": "音高(-20.0~20.0)", "default": 0.0},
            "format": {"type": "string", "enum": ["mp3", "ogg_opus", "wav", "linear16"], "default": "mp3"},
            "filename": {"type": "string", "description": "输出文件名(含后缀)"}
        },
        "required": ["text", "conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.timeout = getattr(config, "code_executor_timeout", 180)
        self.output_dir = config.output_dir

    def execute(self, **kwargs) -> Dict[str, Any]:
        # BaseAtomicTool 需要此方法；真实逻辑在 run()
        return {}

    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        try:
            text: str = (kwargs.get("text") or "").strip()
            conv_id: str = kwargs.get("conversation_id")
            language_code: str = kwargs.get("language_code") or "cmn-CN"
            voice_name: Optional[str] = kwargs.get("voice_name")
            speaking_rate: float = float(kwargs.get("speaking_rate") or 1.0)
            pitch: float = float(kwargs.get("pitch") or 0.0)
            fmt: str = (kwargs.get("format") or "mp3").lower()
            filename: Optional[str] = kwargs.get("filename")

            if not text:
                return {"status": "failed", "error": "text不能为空"}
            if not conv_id:
                return {"status": "failed", "error": "conversation_id缺失"}

            # 输出路径
            work_dir = self.output_dir / conv_id
            work_dir.mkdir(parents=True, exist_ok=True)
            if not filename:
                ext = ".mp3" if fmt == "mp3" else (".ogg" if fmt == "ogg_opus" else ".wav")
                filename = f"narration{ext}"
            out_path = work_dir / filename

            # 载入凭据
            client = self._create_client()
            if client is None:
                return {"status": "failed", "error": "未找到Google TTS凭据，请设置 GOOGLE_APPLICATION_CREDENTIALS 或 GCP_TTS_CREDENTIALS_JSON"}

            # 组装请求
            try:
                from google.cloud import texttospeech as tts  # type: ignore
            except Exception as e:
                return {"status": "failed", "error": f"缺少依赖 google-cloud-texttospeech，请安装: {e}"}

            synthesis_input = tts.SynthesisInput(text=text)

            # 声音
            if voice_name:
                voice = tts.VoiceSelectionParams(language_code=language_code, name=voice_name)
            else:
                voice = tts.VoiceSelectionParams(language_code=language_code)

            # 输出编码
            encoding_map = {
                "mp3": tts.AudioEncoding.MP3,
                "ogg_opus": tts.AudioEncoding.OGG_OPUS,
                "wav": tts.AudioEncoding.LINEAR16,
                "linear16": tts.AudioEncoding.LINEAR16,
            }
            audio_encoding = encoding_map.get(fmt, tts.AudioEncoding.MP3)

            audio_config = tts.AudioConfig(
                audio_encoding=audio_encoding,
                speaking_rate=speaking_rate,
                pitch=pitch,
            )

            response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            content = response.audio_content
            if not content:
                return {"status": "failed", "error": "TTS返回空音频"}

            out_path.write_bytes(content)
            return {"status": "success", "data": {"language_code": language_code, "voice_name": voice_name, "format": fmt}, "generated_files": [out_path.name]}

        except Exception as e:
            logger.error(f"tts_google 执行失败: {e}")
            return {"status": "failed", "error": str(e)}

    def _create_client(self):
        """根据环境变量创建Google TTS客户端。

        优先使用 GCP_TTS_CREDENTIALS_JSON；否则走 GOOGLE_APPLICATION_CREDENTIALS。
        """
        try:
            from google.cloud import texttospeech as tts  # noqa: F401
            from google.oauth2 import service_account  # type: ignore
        except Exception:
            return None

        json_str = os.getenv("GCP_TTS_CREDENTIALS_JSON")
        if json_str:
            try:
                info = json.loads(json_str)
                creds = service_account.Credentials.from_service_account_info(info)
                from google.cloud import texttospeech as tts
                return tts.TextToSpeechClient(credentials=creds)
            except Exception as e:
                logger.error(f"解析 GCP_TTS_CREDENTIALS_JSON 失败: {e}")
                return None

        # 回退到默认ADC(使用 GOOGLE_APPLICATION_CREDENTIALS)
        try:
            from google.cloud import texttospeech as tts
            return tts.TextToSpeechClient()
        except Exception as e:
            logger.error(f"创建默认GCP TTS客户端失败: {e}")
            return None

