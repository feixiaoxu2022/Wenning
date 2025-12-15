"""配置管理模块

负责加载和管理所有配置项，包括API密钥、模型配置等。
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Config:
    """全局配置类

    从.env文件加载配置，提供类型安全的配置访问。
    """

    def __init__(self, env_file: Optional[str] = None):
        """初始化配置

        Args:
            env_file: .env文件路径，默认为项目根目录的.env
        """
        if env_file is None:
            # 自动查找项目根目录的 .env（src/utils/config.py -> repo_root）
            current_dir = Path(__file__).resolve().parent
            repo_root = current_dir.parent.parent.parent
            candidate = repo_root / ".env"
            # 兜底：如果未找到，则尝试当前工作目录
            env_file = candidate if candidate.exists() else Path.cwd() / ".env"

        # 加载环境变量（即使文件不存在也不会报错）
        load_dotenv(env_file)

        # Web Search APIs
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self.serper_api_key = os.getenv("SERPER_API_KEY", "")

        # URL Fetch APIs
        self.firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY", "")
        # Jina Reader无需API Key

        # LLM API - 统一接入点
        self.agent_model_api_key = os.getenv("AGENT_MODEL_API_KEY", "")
        self.agent_model_base_url = os.getenv("AGENT_MODEL_BASE_URL", "http://yy.dbh.baidu-int.com/v1/chat/completions")
        self.agent_model_timeout = int(os.getenv("AGENT_MODEL_TIMEOUT", "600"))
        self.agent_enable_request_logging = os.getenv("AGENT_ENABLE_REQUEST_LOGGING", "false").lower() == "true"

        # LLM API - EB5专用
        self.eb5_api_base_url = os.getenv("EB5_API_BASE_URL", "https://qianfan.baidubce.com/v2/chat/completions")
        self.eb5_api_key = os.getenv("EB5_API_KEY", "")
        self.eb5_model_name = os.getenv("EB5_MODEL_NAME", "ernie-5.0-thinking-preview")

        # MiniMax API - 多模态能力
        self.minimax_api_key = os.getenv("MINIMAX_API_KEY", "")
        self.minimax_tts_api_url = os.getenv("MINIMAX_TTS_API_URL", "https://api.minimaxi.com/v1/t2a_v2")
        self.minimax_image_api_url = os.getenv("MINIMAX_IMAGE_API_URL", "https://api.minimaxi.com/v1/image_generation")
        self.minimax_video_api_url = os.getenv("MINIMAX_VIDEO_API_URL", "https://api.minimaxi.com/v1/video_generation")
        self.minimax_music_api_url = os.getenv("MINIMAX_MUSIC_API_URL", "https://api.minimaxi.com/v1/music_generation")

        # Claude(Anthropic/Bedrock) 专用（可选）
        # 若未配置则默认沿用统一网关；当启用原生适配时会将统一网关的 /v1/chat/completions 替换为 /v1/messages 进行尝试
        self.claude_api_base_url = os.getenv("CLAUDE_API_BASE_URL", "")
        self.claude_force_native = os.getenv("CLAUDE_FORCE_NATIVE", "true").lower() == "true"

        # 可用模型列表
        self.available_models = [
            "ernie-5.0-thinking-preview",  # EB5（默认）
            "glm-4.5",
            "gpt-5",
            "gpt-5.2",
            "doubao-seed-1-6-thinking-250615",
            "gemini-2.5-pro",
            "gemini-3-pro-preview",
            "claude-sonnet-4-5-20250929",
        ]

        # 兼容开关已移除：统一按OpenAI ChatCompletions协议发送messages

        # 代码执行沙箱配置
        # 提高默认超时（更适合真实任务）：180s，可通过环境变量覆盖
        self.code_executor_timeout = int(os.getenv("CODE_EXECUTOR_TIMEOUT", "180"))
        self.code_executor_memory_limit = os.getenv("CODE_EXECUTOR_MEMORY_LIMIT", "512m")

        # 输出目录
        project_root = Path(__file__).resolve().parent.parent.parent
        self.output_dir = project_root / "outputs"
        self.output_dir.mkdir(exist_ok=True)

        # Auth 配置
        self.auth_required = os.getenv("AUTH_REQUIRED", "false").lower() == "true"
        self.auth_allow_register = os.getenv("AUTH_ALLOW_REGISTER", "true").lower() == "true"
        self.auth_secret = os.getenv("AUTH_SECRET", "wenning-dev-secret-key")

        # 验证必需配置
        self._validate()

    def _validate(self):
        """验证必需的配置项是否存在"""
        errors = []

        # 检查Web Search API（至少有一个）
        if not self.tavily_api_key and not self.serper_api_key:
            errors.append("至少需要配置 TAVILY_API_KEY 或 SERPER_API_KEY")

        # 检查LLM API
        if not self.agent_model_api_key:
            errors.append("必须配置 AGENT_MODEL_API_KEY")

        if not self.eb5_api_key:
            errors.append("必须配置 EB5_API_KEY")

        if errors:
            error_msg = "配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

    def get_model_config(self, model_name: str) -> dict:
        """获取指定模型的配置

        Args:
            model_name: 模型名称

        Returns:
            模型配置字典，包含api_key, base_url等

        Raises:
            ValueError: 如果模型名称不在可用列表中
        """
        if model_name not in self.available_models:
            raise ValueError(f"不支持的模型: {model_name}. 可用模型: {self.available_models}")

        # EB5使用专用端点
        if model_name == "ernie-5.0-thinking-preview":
            return {
                "model": self.eb5_model_name,
                "api_key": self.eb5_api_key,
                "base_url": self.eb5_api_base_url,
                "timeout": self.agent_model_timeout
            }

        # Claude 可选原生端点（若配置）
        if model_name.startswith("claude") and self.claude_api_base_url:
            return {
                "model": model_name,
                "api_key": self.agent_model_api_key,
                "base_url": self.claude_api_base_url,
                "timeout": self.agent_model_timeout
            }

        # 其他模型使用统一端点
        return {
            "model": model_name,
            "api_key": self.agent_model_api_key,
            "base_url": self.agent_model_base_url,
            "timeout": self.agent_model_timeout
        }

    def __repr__(self) -> str:
        """安全的字符串表示（隐藏敏感信息）"""
        return (
            f"Config(\n"
            f"  tavily_api_key={'***' if self.tavily_api_key else 'Not Set'},\n"
            f"  serper_api_key={'***' if self.serper_api_key else 'Not Set'},\n"
            f"  agent_model_base_url={self.agent_model_base_url},\n"
            f"  available_models={self.available_models},\n"
            f"  output_dir={self.output_dir}\n"
            f")"
        )


# 全局配置实例（单例模式）
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例

    Returns:
        Config实例
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
