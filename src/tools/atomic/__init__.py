"""Atomic Tools包

提供所有原子工具的统一导入接口。
"""

from src.tools.atomic.web_search import WebSearchTool
from src.tools.atomic.url_fetch import URLFetchTool
from src.tools.atomic.code_executor import CodeExecutor
from src.tools.atomic.tts_minimax import TTSMiniMax
from src.tools.atomic.voice_clone_minimax import VoiceCloneMiniMax
from src.tools.atomic.image_generation import ImageGeneration  # 通用图像生成
from src.tools.atomic.video_generation_minimax import VideoGenerationMiniMax
from src.tools.atomic.music_generation_minimax import MusicGenerationMiniMax
from src.tools.atomic.prompt_template_tool import PromptTemplateRetriever

__all__ = [
    "WebSearchTool",
    "URLFetchTool",
    "CodeExecutor",
    "TTSMiniMax",
    "VoiceCloneMiniMax",
    "ImageGeneration",  # 通用图像生成
    "VideoGenerationMiniMax",
    "MusicGenerationMiniMax",
    "PromptTemplateRetriever",
]
