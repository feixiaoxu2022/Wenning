"""Azure Cognitive Services Speech TTS 原子工具

使用 Azure 语音合成将文本转换为音频文件。

依赖:
  - pip install azure-cognitiveservices-speech

凭据(环境变量, 至少其一):
  - AZURE_SPEECH_KEY / SPEECH_KEY
  - AZURE_SPEECH_REGION / SPEECH_REGION

参数:
  - text(str, 必填): 要合成的文本
  - conversation_id(str, 必填): 会话ID, 用于输出目录
  - voice_name(str): 语音名称, 例如 zh-CN-XiaoxiaoNeural / en-US-JennyNeural
  - speaking_rate(float): 语速倍数(0.25~4.0), 通过SSML prosody rate实现
  - pitch(float): 音高(-20.0~20.0), 通过SSML prosody pitch实现(以st近似)
  - format(str): 'mp3' 或 'wav' (默认 mp3)
  - filename(str): 输出文件名(可选), 未提供时将按format生成 narration.mp3/wav
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import os

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TTSAzure(BaseAtomicTool):
    name = "tts_azure"
    description = (
        "Azure Speech TTS: text->audio, 支持 voice/speaking_rate/pitch, 输出 mp3/wav。"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要合成的文本"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "voice_name": {"type": "string", "description": "语音名称, 如 zh-CN-XiaoxiaoNeural"},
            "speaking_rate": {"type": "number", "description": "语速(0.25~4.0)", "default": 1.0},
            "pitch": {"type": "number", "description": "音高(-20~20)", "default": 0.0},
            "format": {"type": "string", "enum": ["mp3", "wav"], "default": "mp3"},
            "filename": {"type": "string", "description": "输出文件名(含后缀)"}
        },
        "required": ["text", "conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.timeout = getattr(config, "code_executor_timeout", 180)
        self.output_dir = config.output_dir

    def execute(self, **kwargs) -> Dict[str, Any]:
        # 真正逻辑在 run(); 该方法仅满足抽象基类
        return {}

    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        try:
            text: str = (kwargs.get("text") or "").strip()
            conv_id: str = kwargs.get("conversation_id")
            output_dir_name: str = kwargs.get("_output_dir_name")  # 由master_agent统一注入
            voice_name: Optional[str] = kwargs.get("voice_name") or "zh-CN-XiaoxiaoNeural"
            rate: float = float(kwargs.get("speaking_rate") or 1.0)
            pitch: float = float(kwargs.get("pitch") or 0.0)
            fmt: str = (kwargs.get("format") or "mp3").lower()
            filename: Optional[str] = kwargs.get("filename")

            if not text:
                return {"status": "failed", "error": "text不能为空"}
            if not conv_id:
                return {"status": "failed", "error": "conversation_id缺失"}
            if not output_dir_name:
                return {"status": "failed", "error": "缺少_output_dir_name参数（应由master_agent自动注入）"}

            # 规范化会话ID
            from pathlib import Path as _P
            conv_id = _P(str(conv_id)).name

            # 凭据
            key = os.getenv("AZURE_SPEECH_KEY") or os.getenv("SPEECH_KEY") or os.getenv("AZURE_TTS_KEY")
            region = os.getenv("AZURE_SPEECH_REGION") or os.getenv("SPEECH_REGION") or os.getenv("AZURE_TTS_REGION")
            if not key or not region:
                return {"status": "failed", "error": "缺少AZURE_SPEECH_KEY/SPEECH_KEY或AZURE_SPEECH_REGION/SPEECH_REGION环境变量"}

            try:
                import azure.cognitiveservices.speech as speechsdk  # type: ignore
            except Exception as e:
                return {"status": "failed", "error": f"缺少依赖 azure-cognitiveservices-speech，请安装: {e}"}

            # 输出文件与目录
            work_dir = self.output_dir / output_dir_name
            work_dir.mkdir(parents=True, exist_ok=True)
            if not filename:
                filename = f"narration.{fmt}"
            out_path = work_dir / filename

            # Speech Config
            speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
            speech_config.speech_synthesis_voice_name = voice_name

            # 输出格式
            if fmt == "mp3":
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3
                )
            else:  # wav
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
                )

            audio_config = speechsdk.audio.AudioOutputConfig(filename=str(out_path))
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

            # 构造SSML以支持rate/pitch
            # Azure pitch单位可用 st/Hz，此处用相对st近似；rate 用百分比
            rate_pct = int((rate - 1.0) * 100)
            rate_attr = f"{rate_pct:+d}%"
            pitch_attr = f"{int(pitch):+d}st"
            ssml = f"""
<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='{voice_name.split('-')[0].lower()}'>
  <voice name='{voice_name}'>
    <prosody rate='{rate_attr}' pitch='{pitch_attr}'>
      {self._escape(text)}
    </prosody>
  </voice>
</speak>
"""

            result = synthesizer.speak_ssml(ssml)
            from azure.cognitiveservices.speech import ResultReason  # type: ignore
            if result.reason != ResultReason.SynthesizingAudioCompleted:
                details = getattr(result, "cancellation_details", None)
                err = getattr(details, "error_details", None) if details else None
                return {"status": "failed", "error": f"Azure TTS失败: {err or result.reason}"}

            return {"status": "success", "data": {"voice_name": voice_name, "format": fmt}, "generated_files": [out_path.name]}

        except Exception as e:
            logger.error(f"tts_azure 执行失败: {e}")
            return {"status": "failed", "error": str(e)}

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&apos;")
        )

