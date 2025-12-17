"""图片查看列表管理工具

LLM可以主动调用此工具管理图片查看列表（增删查清）。
"""

from typing import Dict, Any, List, Literal
from src.tools.base import BaseAtomicTool
from pathlib import Path


class ManageImagesViewTool(BaseAtomicTool):
    """图片查看列表管理工具

    LLM可以通过此工具管理待查看的图片列表：
    - 添加图片到列表（LLM下轮对话会看到）
    - 移除不需要的图片
    - 查看当前列表内容
    - 清空整个列表
    """

    name = "manage_images_view"
    description = """管理LLM图片查看列表。控制你（LLM）在下一轮对话中能看到哪些图片。

使用场景：
- add: 添加图片到查看列表（如需要分析工具生成的图表、视频帧）
- remove: 移除不需要的图片（如已分析完成）
- list: 查看当前列表中有哪些图片
- clear: 清空所有图片（如开始新任务）

重要机制 - 查看次数限制：
- 默认情况下，每张图片只查看1次后自动移除（避免token浪费）
- 如需多轮查看同一图片，使用view_count参数指定次数（如对比分析时设为2-3）
- 每次注入到LLM后，remaining_views会自动递减，归零后自动移除

detail级别选择：
- low: 节省token，适合快速判断/预览
- high: 详细分析，适合OCR/细节识别（消耗更多token）
- auto: 自动平衡（推荐）"""

    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "remove", "list", "clear"],
                "description": "操作类型：add添加/remove移除/list查看/clear清空"
            },
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "图片文件名列表（add/remove操作时必填）"
            },
            "view_count": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 10,
                "description": "查看次数限制（仅add操作生效）。默认1次后自动移除，如需多轮对比可设为2-3"
            },
            "detail": {
                "type": "string",
                "enum": ["low", "high", "auto"],
                "default": "auto",
                "description": "图片细节级别（仅add操作生效）：low快速/high详细/auto平衡"
            },
            "conversation_id": {
                "type": "string",
                "description": "对话ID（系统自动注入）"
            }
        },
        "required": ["action"]
    }

    def __init__(self, config, conv_manager):
        """初始化工具

        Args:
            config: 全局配置
            conv_manager: 对话管理器
        """
        super().__init__(config)
        self.conv_manager = conv_manager

    def execute(
        self,
        action: Literal["add", "remove", "list", "clear"],
        image_paths: List[str] = None,
        view_count: int = 1,
        detail: str = "auto",
        conversation_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """执行图片列表管理操作

        Args:
            action: 操作类型
            image_paths: 图片文件名列表
            view_count: 查看次数限制（默认1）
            detail: 细节级别
            conversation_id: 对话ID

        Returns:
            执行结果
        """
        if not conversation_id:
            return {
                "success": False,
                "error": "缺少conversation_id参数"
            }

        # === list 操作：查看当前列表 ===
        if action == "list":
            images = self.conv_manager.get_images_to_view(conversation_id)
            return {
                "success": True,
                "action": "list",
                "count": len(images),
                "images": images,
                "message": f"当前查看列表中有 {len(images)} 张图片" if images else "查看列表为空"
            }

        # === clear 操作：清空列表 ===
        if action == "clear":
            success = self.conv_manager.clear_images_to_view(conversation_id)
            if not success:
                return {"success": False, "error": "清空列表失败"}
            return {
                "success": True,
                "action": "clear",
                "message": "已清空图片查看列表"
            }

        # === add/remove 操作：需要image_paths参数 ===
        if not image_paths:
            return {
                "success": False,
                "error": f"{action} 操作需要提供 image_paths 参数"
            }

        # 获取输出目录
        output_dir_name = self.conv_manager.get_output_dir_name(conversation_id)
        conv_dir = Path("outputs") / output_dir_name

        # === add 操作：添加图片 ===
        if action == "add":
            # 验证view_count参数
            if not isinstance(view_count, int) or view_count < 1:
                view_count = 1
            view_count = min(view_count, 10)  # 最多10次

            # 验证detail参数
            if detail not in ["low", "high", "auto"]:
                detail = "auto"

            # 验证图片文件是否存在
            valid_paths = []
            invalid_paths = []

            for path in image_paths:
                # 只接受纯文件名
                if "/" in path or "\\" in path:
                    invalid_paths.append(path)
                    continue

                file_path = conv_dir / path
                if file_path.exists():
                    valid_paths.append(path)
                else:
                    invalid_paths.append(path)

            if not valid_paths:
                return {
                    "success": False,
                    "error": f"所有图片文件都不存在: {invalid_paths}"
                }

            # 添加到列表
            success = self.conv_manager.add_images_to_view(
                conversation_id,
                valid_paths,
                detail,
                view_count  # 传递查看次数
            )

            if not success:
                return {"success": False, "error": "添加图片失败"}

            result = {
                "success": True,
                "action": "add",
                "added_count": len(valid_paths),
                "added_images": valid_paths,
                "detail_level": detail,
                "view_count": view_count,
                "message": f"已添加 {len(valid_paths)} 张图片到查看列表（detail={detail}, 查看{view_count}次后自动移除）"
            }

            if invalid_paths:
                result["warning"] = f"部分文件不存在或路径无效: {invalid_paths}"

            return result

        # === remove 操作：移除图片 ===
        if action == "remove":
            # 获取当前列表
            current_images = self.conv_manager.get_images_to_view(conversation_id)
            current_paths = {img["path"] for img in current_images}

            # 过滤出要移除的路径
            to_remove = [p for p in image_paths if p in current_paths]
            not_found = [p for p in image_paths if p not in current_paths]

            if not to_remove:
                return {
                    "success": False,
                    "error": f"指定的图片不在列表中: {image_paths}"
                }

            # 移除：保留不在to_remove中的图片
            remaining = [img for img in current_images if img["path"] not in to_remove]

            # 更新列表（先清空再添加）
            self.conv_manager.clear_images_to_view(conversation_id)
            if remaining:
                # 按(detail, view_count)分组批量添加
                from collections import defaultdict
                groups = defaultdict(list)
                for img in remaining:
                    key = (img.get("detail", "auto"), img.get("remaining_views", 1))
                    groups[key].append(img["path"])

                for (detail_level, view_count), paths in groups.items():
                    self.conv_manager.add_images_to_view(
                        conversation_id,
                        paths,
                        detail_level,
                        view_count
                    )

            result = {
                "success": True,
                "action": "remove",
                "removed_count": len(to_remove),
                "removed_images": to_remove,
                "remaining_count": len(remaining),
                "message": f"已移除 {len(to_remove)} 张图片，列表中还剩 {len(remaining)} 张"
            }

            if not_found:
                result["warning"] = f"部分图片不在列表中: {not_found}"

            return result

        return {
            "success": False,
            "error": f"未知操作类型: {action}"
        }
