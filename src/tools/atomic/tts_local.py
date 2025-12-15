"""本地TTS原子工具（离线优先）

macOS: 调用系统 `say` 生成AIFF，再用ffmpeg转为WAV/M4A。
Linux/Windows: 尝试使用pyttsx3（若可用）；否则返回失败并提示使用ShellExecutor/ffmpeg。

输出均写入会话目录 outputs/{conversation_id}/ 下，仅返回生成的文件名。
"""

from __future__ import annotations

import os
import platform
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TTSLocal(BaseAtomicTool):
    name = "tts_local"
    description = (
        "离线文本转语音。macOS使用系统'say'合成AIFF并可转换为WAV/M4A；"
        "其他平台尝试pyttsx3（若可用）。参数: text(必填), voice, rate, format(wav/m4a/aiff), filename"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要合成的文本(UTF-8)"},
            "voice": {"type": "string", "description": "语音名称, 例如 macOS: Ting-Ting/Samantha/Daniel"},
            "rate": {"type": "integer", "description": "语速(例如 160-200)", "minimum": 80, "maximum": 400},
            "format": {"type": "string", "enum": ["wav", "m4a", "aiff"], "default": "wav"},
            "filename": {"type": "string", "description": "输出文件名(含扩展名), 默认基于format生成"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "timeout": {"type": "integer", "description": "超时(秒)", "minimum": 5}
        },
        "required": ["text", "conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.timeout = max(30, int(getattr(config, "code_executor_timeout", 180)))
        self.output_dir = config.output_dir

    def execute(self, **kwargs) -> Dict[str, Any]:
        """满足抽象基类要求；实际逻辑在 run()，此处返回空数据。"""
        return {}

    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        try:
            text: str = kwargs.get("text", "").strip()
            voice: Optional[str] = kwargs.get("voice")
            rate: Optional[int] = kwargs.get("rate")
            fmt: str = (kwargs.get("format") or "wav").lower()
            filename: Optional[str] = kwargs.get("filename")
            conv_id: str = kwargs.get("conversation_id")
            output_dir_name: str = kwargs.get("_output_dir_name")  # 由master_agent统一注入
            timeout: int = int(kwargs.get("timeout") or self.timeout)

            if not text:
                return {"status": "failed", "error": "text不能为空"}
            if not conv_id:
                return {"status": "failed", "error": "conversation_id缺失"}
            if not output_dir_name:
                return {"status": "failed", "error": "缺少_output_dir_name参数（应由master_agent自动注入）"}

            # 规范化会话ID（防止传入 'outputs/<id>' 或包含路径）
            from pathlib import Path as _P
            conv_id = _P(str(conv_id)).name

            work_dir = self.output_dir / output_dir_name
            work_dir.mkdir(parents=True, exist_ok=True)

            sysname = platform.system().lower()
            gen_files: List[str] = []

            # 默认目标文件名
            if not filename:
                filename = f"narration.{fmt}"

            if sysname == "darwin":
                # macOS: say -> AIFF，再可转 wav/m4a
                aiff_name = Path(filename).with_suffix(".aiff").name
                aiff_path = work_dir / aiff_name
                # 构造 say 命令
                cmd = ["say"]
                if voice:
                    cmd += ["-v", voice]
                if rate:
                    cmd += ["-r", str(rate)]
                cmd += ["-o", aiff_name, text]

                logger.info(f"TTSLocal: say command: {' '.join(shlex.quote(c) for c in cmd)} (cwd={work_dir})")
                r = subprocess.run(cmd, cwd=str(work_dir), capture_output=True, text=True, timeout=timeout)
                if r.returncode != 0:
                    msg = (r.stderr or r.stdout or "").strip()
                    # 常见：指定 voice 不存在，自动降级为系统默认
                    if "Voice" in msg and "not found" in msg:
                        logger.warning(f"TTSLocal: 指定voice不可用({voice})，自动降级为系统默认")
                        cmd_fallback = ["say"]
                        if rate:
                            cmd_fallback += ["-r", str(rate)]
                        cmd_fallback += ["-o", aiff_name, text]
                        r2 = subprocess.run(cmd_fallback, cwd=str(work_dir), capture_output=True, text=True, timeout=timeout)
                        if r2.returncode != 0:
                            return {"status": "failed", "error": f"say失败: {r2.stderr.strip() or r2.stdout.strip()}"}
                    else:
                        return {"status": "failed", "error": f"say失败: {msg}"}

                gen_files.append(aiff_name)

                # 需要转换格式
                if fmt in ("wav", "m4a"):
                    out_path = work_dir / filename
                    if fmt == "wav":
                        ffmpeg_cmd = [
                            "ffmpeg", "-y", "-i", aiff_name,
                            "-ar", "44100", "-ac", "2",
                            out_path.name,
                        ]
                    else:  # m4a (aac in mp4)
                        ffmpeg_cmd = [
                            "ffmpeg", "-y", "-i", aiff_name,
                            "-c:a", "aac", "-b:a", "128k",
                            out_path.name,
                        ]
                    logger.info(f"TTSLocal: ffmpeg command: {' '.join(shlex.quote(c) for c in ffmpeg_cmd)}")
                    rr = subprocess.run(ffmpeg_cmd, cwd=str(work_dir), capture_output=True, text=True, timeout=timeout)
                    if rr.returncode != 0:
                        return {"status": "failed", "error": f"ffmpeg转码失败: {rr.stderr.strip() or rr.stdout.strip()}"}
                    gen_files.append(out_path.name)

                return {"status": "success", "data": {"voice": voice, "rate": rate, "format": fmt}, "generated_files": gen_files}

            # 其他平台: 尝试pyttsx3
            try:
                import pyttsx3  # type: ignore
            except Exception:
                return {"status": "failed", "error": "非macOS且未安装pyttsx3，无法离线TTS。可改用ShellExecutor+系统TTS，或启用云TTS。"}

            engine = pyttsx3.init()
            if voice:
                # 尝试匹配包含voice关键字的id/name
                try:
                    for v in engine.getProperty("voices"):
                        if voice.lower() in (v.id or "").lower() or voice.lower() in (v.name or "").lower():
                            engine.setProperty("voice", v.id)
                            break
                except Exception:
                    pass
            if rate:
                try:
                    engine.setProperty("rate", int(rate))
                except Exception:
                    pass

            # pyttsx3 保存到 wav
            out = work_dir / (Path(filename).with_suffix(".wav").name)
            try:
                engine.save_to_file(text, str(out))
                engine.runAndWait()
            except Exception as e:
                return {"status": "failed", "error": f"pyttsx3合成失败: {e}"}

            gen_files.append(out.name)
            return {"status": "success", "data": {"voice": voice, "rate": rate, "format": "wav"}, "generated_files": gen_files}

        except Exception as e:
            logger.error(f"tts_local执行失败: {e}")
            return {"status": "failed", "error": str(e)}
