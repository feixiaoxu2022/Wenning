"""图片处理工具，用于多模态LLM调用

支持：
1. 图片读取、压缩和编码
2. 转换为不同模型的multimodal格式
3. Token消耗估算
"""

import base64
import io
from pathlib import Path
from typing import List, Tuple, Literal
from PIL import Image

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ImageProcessor:
    """图片处理器，为LLM multimodal调用准备图片"""

    # 根据detail级别设置不同的压缩参数
    DETAIL_SETTINGS = {
        "low": {
            "max_size": (512, 512),
            "quality": 75,
            "description": "低分辨率，快速处理，适合预览"
        },
        "high": {
            "max_size": (2048, 2048),
            "quality": 95,
            "description": "高分辨率，细节丰富，适合详细分析"
        },
        "auto": {
            "max_size": (1024, 1024),
            "quality": 85,
            "description": "自动平衡，适合大多数场景"
        }
    }

    @staticmethod
    def to_base64_url(image_path: str, detail: Literal["low", "high", "auto"] = "auto") -> str:
        """转换图片为base64 data URL

        Args:
            image_path: 图片文件路径
            detail: 图片细节级别

        Returns:
            data:image/jpeg;base64,... 格式的URL
        """
        try:
            settings = ImageProcessor.DETAIL_SETTINGS.get(
                detail,
                ImageProcessor.DETAIL_SETTINGS["auto"]
            )

            # 读取图片
            img = Image.open(image_path)

            # 保持宽高比缩放
            img.thumbnail(settings["max_size"], Image.Resampling.LANCZOS)

            # 转换为RGB（移除alpha通道）
            if img.mode != 'RGB':
                # 如果有透明通道，用白色背景填充
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
                    img = background
                else:
                    img = img.convert('RGB')

            # 编码为JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=settings["quality"])

            # 转base64
            base64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')

            logger.debug(f"图片编码完成: {image_path} -> {len(base64_str)} chars (detail={detail})")

            return f"data:image/jpeg;base64,{base64_str}"

        except Exception as e:
            logger.error(f"图片编码失败: {image_path}, error={e}")
            raise

    @staticmethod
    def to_base64(image_path: str, detail: Literal["low", "high", "auto"] = "auto") -> str:
        """返回纯base64字符串（不含data URL前缀）

        Args:
            image_path: 图片文件路径
            detail: 图片细节级别

        Returns:
            纯base64字符串
        """
        url = ImageProcessor.to_base64_url(image_path, detail)
        return url.split(",")[1]

    @staticmethod
    def build_openai_content(
        image_paths: List[str],
        detail: Literal["low", "high", "auto"] = "auto"
    ) -> List[dict]:
        """构造OpenAI格式的图片内容

        Args:
            image_paths: 图片路径列表
            detail: 图片细节级别

        Returns:
            OpenAI格式的content数组
        """
        return [
            {
                "type": "image_url",
                "image_url": {
                    "url": ImageProcessor.to_base64_url(path, detail),
                    "detail": detail if detail in ["low", "high"] else "auto"
                }
            }
            for path in image_paths
        ]

    @staticmethod
    def build_anthropic_content(
        image_paths: List[str],
        detail: Literal["low", "high", "auto"] = "auto"
    ) -> List[dict]:
        """构造Anthropic (Claude) 格式的图片内容

        Args:
            image_paths: 图片路径列表
            detail: 图片细节级别

        Returns:
            Anthropic格式的content数组
        """
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": ImageProcessor.to_base64(path, detail)
                }
            }
            for path in image_paths
        ]

    @staticmethod
    def build_gemini_content(
        image_paths: List[str],
        detail: Literal["low", "high", "auto"] = "auto"
    ) -> List[dict]:
        """构造Gemini格式的图片内容

        Args:
            image_paths: 图片路径列表
            detail: 图片细节级别

        Returns:
            Gemini格式的content数组
        """
        # Gemini使用类似OpenAI的格式
        return [
            {
                "type": "image_url",
                "image_url": ImageProcessor.to_base64_url(path, detail)
            }
            for path in image_paths
        ]

    @staticmethod
    def estimate_tokens(image_path: str, detail: Literal["low", "high", "auto"] = "auto") -> int:
        """估算图片会消耗的token数（基于OpenAI的计费规则）

        Args:
            image_path: 图片文件路径
            detail: 图片细节级别

        Returns:
            估算的token数
        """
        try:
            if detail == "low":
                # low detail固定消耗
                return 85

            # high detail需要基于图片尺寸计算
            img = Image.open(image_path)
            width, height = img.size

            # OpenAI的token计算规则：
            # 1. 图片会被缩放到fit在 2048x2048 的正方形内
            # 2. 图片短边缩放到768px
            # 3. 计算需要多少个512px的tile来覆盖图片
            # 4. 每个tile消耗170 tokens，base消耗85 tokens

            # 简化计算：按照缩放后的尺寸估算tile数量
            settings = ImageProcessor.DETAIL_SETTINGS.get(detail, ImageProcessor.DETAIL_SETTINGS["auto"])
            max_size = settings["max_size"][0]

            # 缩放后的尺寸
            scale = min(max_size / width, max_size / height)
            scaled_width = int(width * scale)
            scaled_height = int(height * scale)

            # 计算tile数量（每个tile 512x512）
            tiles_x = (scaled_width + 511) // 512
            tiles_y = (scaled_height + 511) // 512
            total_tiles = tiles_x * tiles_y

            # 总token = base + tiles * tile_cost
            return 85 + 170 * total_tiles

        except Exception as e:
            logger.error(f"Token估算失败: {image_path}, error={e}")
            # 返回一个保守的估算值
            return 255  # 85 + 170 * 1

    @staticmethod
    def estimate_cost(
        num_images: int,
        detail: Literal["low", "high", "auto"] = "auto",
        model_name: str = "gpt-4o"
    ) -> float:
        """估算图片处理的成本（美元）

        Args:
            num_images: 图片数量
            detail: 图片细节级别
            model_name: 模型名称

        Returns:
            估算成本（美元）
        """
        # 价格表（2024年参考价格，实际使用时应从配置读取）
        VISION_COSTS = {
            "gpt-4-vision": {"low": 0.00085, "high": 0.00255},
            "gpt-4o": {"low": 0.00042, "high": 0.00127},
            "gpt-4o-mini": {"low": 0.00016, "high": 0.00048},
            "claude-3-opus": {"flat": 0.0015},
            "claude-3-sonnet": {"flat": 0.0008},
            "claude-3-haiku": {"flat": 0.0004},
            "gemini-pro-vision": {"flat": 0.00025}
        }

        # 查找模型价格
        if model_name not in VISION_COSTS:
            logger.warning(f"未知模型 {model_name}，使用默认价格")
            return num_images * 0.001  # 默认价格

        prices = VISION_COSTS[model_name]

        # 根据模型类型选择价格
        if "flat" in prices:
            # Anthropic/Gemini使用固定价格
            price_per_image = prices["flat"]
        else:
            # OpenAI使用detail分级价格
            price_per_image = prices.get(detail, prices.get("high", 0.001))

        return num_images * price_per_image

    @staticmethod
    def get_image_info(image_path: str) -> dict:
        """获取图片基本信息

        Args:
            image_path: 图片文件路径

        Returns:
            包含图片信息的字典
        """
        try:
            img = Image.open(image_path)
            file_size = Path(image_path).stat().st_size

            return {
                "path": image_path,
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.size[0],
                "height": img.size[1],
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / 1024 / 1024, 2)
            }
        except Exception as e:
            logger.error(f"获取图片信息失败: {image_path}, error={e}")
            return {"path": image_path, "error": str(e)}
