"""FFmpeg 媒体处理原子工具

封装常见音视频处理：
- mux: 将音频合入视频(可选择转码到yuv420p+aac+faststart)
- transcode: 转码视频到yuv420p并faststart

所有路径仅接受文件名，工作目录固定在 outputs/{conversation_id}/。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, List
import subprocess
import shlex

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MediaFFmpeg(BaseAtomicTool):
    name = "media_ffmpeg"
    description = (
        "FFmpeg专业媒体处理: 底层音视频操作，支持转码、格式优化、专业混音。"
        "适用场景：音频混音（旁白+BGM+ducking效果）、视频转码（yuv420p+faststart优化兼容性）、音视频流合成（mux）。"
        "优势：专业级音频处理（sidechaincompress压缩、淡入淡出）、格式兼容性优化、底层FFmpeg精细控制。"
        "不适用：视频内容编辑（剪辑、添加字幕、特效）→ 使用code_executor+moviepy。"
        "\n支持模式："
        "\n- mux: 音视频合成(video+audio→out.mp4)"
        "\n- transcode: 视频转码优化(video→yuv420p+faststart)"
        "\n- mix: 专业混音(vocal+bgm→out, 支持ducking/淡入淡出/循环)"
        "\n参数: mode(必需), conversation_id(必需), out(输出文件), 根据模式选择video/audio/vocal/bgm等"
    )

    parameters_schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["mux", "transcode", "mix"], "description": "处理模式"},
            "conversation_id": {"type": "string", "description": "会话ID(必须)"},
            "video": {"type": "string", "description": "输入视频文件名(仅文件名)"},
            "audio": {"type": "string", "description": "输入音频文件名(仅文件名, mux模式需要)"},
            "out": {"type": "string", "description": "输出文件名(仅文件名, 必须以.mp4结尾)"},
            "ensure_yuv420p": {"type": "boolean", "default": True, "description": "转码为yuv420p(提升兼容性)"},
            "faststart": {"type": "boolean", "default": True, "description": "写入faststart优化"},
            "shortest": {"type": "boolean", "default": True, "description": "以较短轨道为准结束"},
            "reencode_video": {"type": "boolean", "default": False, "description": "即使不需要yuv420p也强制重编码视频"},
            "audio_codec": {"type": "string", "default": "aac", "description": "音频编码器(aac/copy)"},
            # mix 模式参数
            "vocal": {"type": "string", "description": "旁白音频文件(仅文件名)"},
            "bgm": {"type": "string", "description": "背景音乐文件(仅文件名)"},
            "bgm_gain_db": {"type": "number", "default": -14, "description": "背景音乐整体增益(dB)"},
            "ducking": {"type": "boolean", "default": True, "description": "启用ducking(旁白期间压低BGM)"},
            "threshold": {"type": "number", "default": -18, "description": "sidechaincompress阈值(dB)"},
            "ratio": {"type": "number", "default": 6, "description": "压缩比"},
            "attack_ms": {"type": "integer", "default": 20, "description": "起动(ms)"},
            "release_ms": {"type": "integer", "default": 250, "description": "释放(ms)"},
            "fade_in_ms": {"type": "integer", "default": 0, "description": "BGM淡入(ms)"},
            "fade_out_ms": {"type": "integer", "default": 0, "description": "BGM淡出(ms)"},
            "loop_bgm": {"type": "boolean", "default": False, "description": "是否循环BGM以覆盖全长"},
        },
        "required": ["mode", "conversation_id", "out"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.timeout = getattr(config, "code_executor_timeout", 180)
        self.output_dir = config.output_dir

    def execute(self, **kwargs) -> Dict[str, Any]:
        """满足抽象基类要求；实际逻辑在 run()，此处返回空数据。"""
        return {}

    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        try:
            mode = kwargs.get("mode")
            conv_id = kwargs.get("conversation_id")
            output_dir_name = kwargs.get("_output_dir_name")  # 由master_agent统一注入
            out_name = kwargs.get("out")
            ensure_420 = bool(kwargs.get("ensure_yuv420p", True))
            faststart = bool(kwargs.get("faststart", True))
            shortest = bool(kwargs.get("shortest", True))
            reencode_video = bool(kwargs.get("reencode_video", False))
            audio_codec = (kwargs.get("audio_codec") or "aac").lower()

            if not conv_id:
                return {"status": "failed", "error": "conversation_id缺失"}
            if not output_dir_name:
                return {"status": "failed", "error": "缺少_output_dir_name参数（应由master_agent自动注入）"}
            if not out_name or not out_name.lower().endswith(".mp4"):
                return {"status": "failed", "error": "out必须以.mp4结尾"}

            # 规范化会话ID（避免传入 'outputs/<id>' 或路径）
            from pathlib import Path as _P
            conv_id = _P(str(conv_id)).name

            work_dir = self.output_dir / output_dir_name
            work_dir.mkdir(parents=True, exist_ok=True)

            cmd: List[str] = ["ffmpeg", "-y"]

            if mode == "mux":
                video = kwargs.get("video")
                audio = kwargs.get("audio")
                if not video or not audio:
                    return {"status": "failed", "error": "mux模式需要video与audio"}

                cmd += ["-i", video, "-i", audio]

                # 视频编码策略
                if ensure_420 or reencode_video:
                    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
                    cmd += ["-vf", vf, "-c:v", "libx264", "-profile:v", "high", "-level", "4.1"]
                    if faststart:
                        cmd += ["-movflags", "+faststart"]
                else:
                    cmd += ["-c:v", "copy"]

                # 音频编码策略
                if audio_codec == "aac":
                    cmd += ["-c:a", "aac", "-b:a", "128k"]
                else:
                    cmd += ["-c:a", "copy"]

                if shortest:
                    cmd += ["-shortest"]

                cmd += [out_name]

            elif mode == "transcode":
                video = kwargs.get("video")
                if not video:
                    return {"status": "failed", "error": "transcode模式需要video"}

                cmd += ["-i", video]

                vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p" if ensure_420 else "scale=trunc(iw/2)*2:trunc(ih/2)*2"
                cmd += ["-vf", vf, "-c:v", "libx264", "-profile:v", "high", "-level", "4.1"]
                if faststart:
                    cmd += ["-movflags", "+faststart"]
                # 保持无音频或复制（不强制）
                cmd += ["-c:a", "copy"]
                cmd += [out_name]

            elif mode == "mix":
                # 旁白+BGM混音，可输出音频；若同时传入 video 且 out 以 .mp4 结尾，则生成视频（两段式）
                vocal = kwargs.get("vocal")
                bgm = kwargs.get("bgm")
                if not vocal or not bgm:
                    return {"status": "failed", "error": "mix模式需要vocal与bgm"}

                out_name = out_name  # already set
                is_video_out = out_name.lower().endswith(".mp4") and bool(kwargs.get("video"))

                # 目标音频文件名（中间产物或最终音频）
                audio_out_name = (
                    (Path(out_name).with_suffix(".m4a").name) if is_video_out else out_name
                )

                # BGM前置增益与淡入淡出
                bgm_gain_db = float(kwargs.get("bgm_gain_db", -14))
                ducking = bool(kwargs.get("ducking", True))
                thr = float(kwargs.get("threshold", -18))
                ratio = float(kwargs.get("ratio", 6))
                att = int(kwargs.get("attack_ms", 20))
                rel = int(kwargs.get("release_ms", 250))
                fin = int(kwargs.get("fade_in_ms", 0))
                fout = int(kwargs.get("fade_out_ms", 0))
                loop_bgm = bool(kwargs.get("loop_bgm", False))

                # 组装 filter_complex
                fc_parts: List[str] = []
                # 输入映射: 0:vocal, 1:bgm
                # 背景音乐音量与淡入/淡出
                bgm_chain = "[1:a]volume={:.2f}dB".format(bgm_gain_db)
                if fin > 0:
                    bgm_chain += ",afade=t=in:st=0:d={}".format(fin / 1000.0)
                if fout > 0:
                    bgm_chain += ",afade=t=out:st=99999:d={}".format(fout / 1000.0)  # 过长，后续以shortest截断
                bgm_chain += "[bgm0]"
                fc_parts.append(bgm_chain)

                if ducking:
                    # 侧链压缩: 以vocal作为sidechain，压低bgm
                    sc = (
                        "[bgm0][0:a]sidechaincompress=threshold={thr}dB:ratio={ratio}:"
                        "attack={att}:release={rel}:makeup=0:mix=1[ducked]"
                    ).format(thr=thr, ratio=ratio, att=att, rel=rel)
                    fc_parts.append(sc)
                    mix_input = "[ducked][0:a]amix=inputs=2:normalize=0:duration=longest[aout]"
                    fc_parts.append(mix_input)
                else:
                    # 直接混音
                    fc_parts.append("[bgm0][0:a]amix=inputs=2:normalize=0:duration=longest[aout]")

                filter_complex = ";".join(fc_parts)

                cmd += ["-i", vocal, "-i", bgm, "-filter_complex", filter_complex, "-map", "[aout]"]

                # 输出音频编码
                if audio_out_name.lower().endswith(".m4a"):
                    cmd += ["-c:a", "aac", "-b:a", "128k"]
                else:
                    # wav
                    cmd += ["-ar", "44100", "-ac", "2"]
                if shortest:
                    cmd += ["-shortest"]

                cmd += [audio_out_name]

                logger.info(f"media_ffmpeg 混音命令: {' '.join(shlex.quote(c) for c in cmd)} (cwd={work_dir})")
                r = subprocess.run(cmd, cwd=str(work_dir), capture_output=True, text=True, timeout=self.timeout)
                if r.returncode != 0:
                    return {"status": "failed", "error": r.stderr.strip() or r.stdout.strip()}

                generated: List[str] = [audio_out_name]

                # 如需要直接输出视频，再进行一次mux/transcode
                if is_video_out:
                    video = kwargs.get("video")
                    # 第二次调用 ffmpeg: 将 audio_out 与 video 合并，并确保兼容性
                    cmd2: List[str] = ["ffmpeg", "-y", "-i", video, "-i", audio_out_name]
                    if ensure_420 or reencode_video:
                        vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
                        cmd2 += ["-vf", vf, "-c:v", "libx264", "-profile:v", "high", "-level", "4.1"]
                        if faststart:
                            cmd2 += ["-movflags", "+faststart"]
                    else:
                        cmd2 += ["-c:v", "copy"]

                    # aac 音频
                    cmd2 += ["-c:a", "aac", "-b:a", "128k"]
                    if shortest:
                        cmd2 += ["-shortest"]
                    cmd2 += [out_name]

                    logger.info(f"media_ffmpeg 合成视频命令: {' '.join(shlex.quote(c) for c in cmd2)} (cwd={work_dir})")
                    r2 = subprocess.run(cmd2, cwd=str(work_dir), capture_output=True, text=True, timeout=self.timeout)
                    if r2.returncode != 0:
                        return {"status": "failed", "error": r2.stderr.strip() or r2.stdout.strip(), "generated_files": generated}
                    generated.append(out_name)

                return {"status": "success", "data": {"mode": mode, "out": out_name}, "generated_files": generated}

            else:
                return {"status": "failed", "error": f"不支持的mode: {mode}"}

            logger.info(f"media_ffmpeg 命令: {' '.join(shlex.quote(c) for c in cmd)} (cwd={work_dir})")
            r = subprocess.run(cmd, cwd=str(work_dir), capture_output=True, text=True, timeout=self.timeout)
            if r.returncode != 0:
                return {"status": "failed", "error": r.stderr.strip() or r.stdout.strip()}

            return {"status": "success", "data": {"mode": mode, "out": out_name}, "generated_files": [out_name]}

        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": f"ffmpeg超时({self.timeout}s)"}
        except Exception as e:
            logger.error(f"media_ffmpeg失败: {e}")
            return {"status": "failed", "error": str(e)}
