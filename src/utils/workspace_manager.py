"""工作区管理器 - 处理文件浏览、分类、操作"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import shutil
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WorkspaceManager:
    """工作区管理器"""

    # 文件分类配置
    FILE_CATEGORIES = {
        "图片": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"],
        "视频": [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"],
        "表格": [".xlsx", ".xls", ".csv"],
        "文档": [".md", ".txt", ".pdf", ".doc", ".docx"],
        "音频": [".mp3", ".wav", ".m4a", ".flac", ".aac"],
        "代码": [".py", ".js", ".html", ".css", ".json"],
        "其他": []  # 默认分类
    }

    def __init__(self, output_dir: Path, conv_manager=None):
        """初始化工作区管理器

        Args:
            output_dir: 输出文件根目录
            conv_manager: ConversationManager实例，用于解析带时间戳的目录名
        """
        self.output_dir = Path(output_dir)
        self.conv_manager = conv_manager
        logger.info(f"WorkspaceManager初始化: output_dir={self.output_dir}")

    def get_conversation_files(self, conversation_id: str) -> Dict[str, List[Dict]]:
        """获取会话目录下的所有文件，按类型分类

        Args:
            conversation_id: 会话ID

        Returns:
            按类型分类的文件列表
            {
                "图片": [{name, path, size, mtime, ...}, ...],
                "视频": [...],
                ...
            }
        """
        # 使用conv_manager解析带时间戳的目录名
        if self.conv_manager:
            output_dir_name = self.conv_manager.get_output_dir_name(conversation_id)
            conv_dir = self.output_dir / output_dir_name
        else:
            conv_dir = self.output_dir / conversation_id
        if not conv_dir.exists():
            logger.warning(f"会话目录不存在: {conv_dir}")
            return {cat: [] for cat in self.FILE_CATEGORIES.keys()}

        # 获取所有文件
        all_files = []
        try:
            for file_path in conv_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    file_info = {
                        "name": file_path.name,
                        "path": str(file_path),
                        "relative_path": file_path.name,  # 相对路径（仅文件名）
                        "size": stat.st_size,
                        "size_str": self._format_size(stat.st_size),
                        "mtime": stat.st_mtime,
                        "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "ext": file_path.suffix.lower(),
                        "category": self._get_file_category(file_path.suffix.lower())
                    }
                    all_files.append(file_info)
        except Exception as e:
            logger.error(f"读取会话目录失败: {e}")
            return {cat: [] for cat in self.FILE_CATEGORIES.keys()}

        # 按类型分类
        categorized = {cat: [] for cat in self.FILE_CATEGORIES.keys()}
        for file_info in all_files:
            category = file_info["category"]
            categorized[category].append(file_info)

        # 每个类别按修改时间降序排序
        for category in categorized:
            categorized[category].sort(key=lambda x: x["mtime"], reverse=True)

        logger.info(f"获取会话文件: {conversation_id}, 共{len(all_files)}个文件")
        return categorized

    def _get_file_category(self, ext: str) -> str:
        """根据扩展名获取文件分类

        Args:
            ext: 文件扩展名（如 .png）

        Returns:
            分类名称
        """
        for category, extensions in self.FILE_CATEGORIES.items():
            if ext in extensions:
                return category
        return "其他"

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小

        Args:
            size_bytes: 字节数

        Returns:
            格式化后的大小（如 1.5 MB）
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def delete_file(self, conversation_id: str, filename: str) -> Tuple[bool, str]:
        """删除文件

        Args:
            conversation_id: 会话ID
            filename: 文件名

        Returns:
            (是否成功, 消息)
        """
        try:
            # 使用conv_manager解析带时间戳的目录名
            if self.conv_manager:
                output_dir_name = self.conv_manager.get_output_dir_name(conversation_id)
                file_path = self.output_dir / output_dir_name / filename
            else:
                file_path = self.output_dir / conversation_id / filename
            if not file_path.exists():
                return False, f"文件不存在: {filename}"

            file_path.unlink()
            logger.info(f"删除文件成功: {file_path}")
            return True, f"✅ 已删除: {filename}"
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False, f"❌ 删除失败: {str(e)}"

    def get_file_path(self, conversation_id: str, filename: str) -> Optional[Path]:
        """获取文件完整路径

        Args:
            conversation_id: 会话ID
            filename: 文件名

        Returns:
            文件路径，如果不存在返回None
        """
        # 使用conv_manager解析带时间戳的目录名
        if self.conv_manager:
            output_dir_name = self.conv_manager.get_output_dir_name(conversation_id)
            file_path = self.output_dir / output_dir_name / filename
        else:
            file_path = self.output_dir / conversation_id / filename
        return file_path if file_path.exists() else None

    def get_statistics(self, conversation_id: str) -> Dict:
        """获取工作区统计信息

        Args:
            conversation_id: 会话ID

        Returns:
            统计信息字典
        """
        categorized = self.get_conversation_files(conversation_id)

        total_files = sum(len(files) for files in categorized.values())
        total_size = 0

        # 使用conv_manager解析带时间戳的目录名
        if self.conv_manager:
            output_dir_name = self.conv_manager.get_output_dir_name(conversation_id)
            conv_dir = self.output_dir / output_dir_name
        else:
            conv_dir = self.output_dir / conversation_id
        if conv_dir.exists():
            for file_path in conv_dir.iterdir():
                if file_path.is_file():
                    total_size += file_path.stat().st_size

        return {
            "total_files": total_files,
            "total_size": self._format_size(total_size),
            "by_category": {cat: len(files) for cat, files in categorized.items() if len(files) > 0}
        }

    def get_user_files(self, username: str, conversation_ids: List[str], workspace_store) -> Dict[str, List[Dict]]:
        """获取用户所有会话的文件，按类型分类（仅包含用户明确保存的文件）

        Args:
            username: 用户名
            conversation_ids: 用户的所有会话ID列表
            workspace_store: WorkspaceStore实例，用于获取已保存的文件列表

        Returns:
            按类型分类的文件列表，每个文件包含conversation_id字段
            {
                "图片": [{name, conversation_id, size_str, mtime_str, ...}, ...],
                "视频": [...],
                ...
            }
        """
        categorized = {cat: [] for cat in self.FILE_CATEGORIES.keys()}

        for conv_id in conversation_ids:
            # 获取该会话中用户明确保存的文件
            saved_files = workspace_store.list_files(username, conv_id)
            if not saved_files:
                continue

            # 使用conv_manager解析带时间戳的目录名
            if self.conv_manager:
                output_dir_name = self.conv_manager.get_output_dir_name(conv_id)
                conv_dir = self.output_dir / output_dir_name
            else:
                conv_dir = self.output_dir / conv_id
            if not conv_dir.exists():
                continue

            try:
                for filename in saved_files:
                    file_path = conv_dir / filename
                    if not file_path.exists() or not file_path.is_file():
                        continue

                    stat = file_path.stat()
                    file_info = {
                        "name": file_path.name,
                        "conversation_id": conv_id,
                        "path": str(file_path),
                        "size": stat.st_size,
                        "size_str": self._format_size(stat.st_size),
                        "mtime": stat.st_mtime,
                        "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "ext": file_path.suffix.lower(),
                        "category": self._get_file_category(file_path.suffix.lower())
                    }
                    category = file_info["category"]
                    categorized[category].append(file_info)
            except Exception as e:
                logger.error(f"读取会话目录失败: {conv_id}, error={e}")
                continue

        # 每个类别按修改时间降序排序
        for category in categorized:
            categorized[category].sort(key=lambda x: x["mtime"], reverse=True)

        total_files = sum(len(files) for files in categorized.values())
        logger.info(f"获取用户Workspace文件: {len(conversation_ids)}个会话, 共{total_files}个已保存文件")
        return categorized

    def get_user_statistics(self, username: str, conversation_ids: List[str], workspace_store) -> Dict:
        """获取用户所有文件的统计信息（仅统计已保存的文件）

        Args:
            username: 用户名
            conversation_ids: 用户的所有会话ID列表
            workspace_store: WorkspaceStore实例

        Returns:
            统计信息字典
        """
        categorized = self.get_user_files(username, conversation_ids, workspace_store)

        total_files = sum(len(files) for files in categorized.values())
        total_size = 0

        # 仅统计已保存文件的大小
        for conv_id in conversation_ids:
            saved_files = workspace_store.list_files(username, conv_id)
            if not saved_files:
                continue

            # 使用conv_manager解析带时间戳的目录名
            if self.conv_manager:
                output_dir_name = self.conv_manager.get_output_dir_name(conv_id)
                conv_dir = self.output_dir / output_dir_name
            else:
                conv_dir = self.output_dir / conv_id
            if not conv_dir.exists():
                continue

            try:
                for filename in saved_files:
                    file_path = conv_dir / filename
                    if file_path.exists() and file_path.is_file():
                        total_size += file_path.stat().st_size
            except Exception:
                continue

        return {
            "total_files": total_files,
            "total_size": self._format_size(total_size),
            "by_category": {cat: len(files) for cat, files in categorized.items() if len(files) > 0},
            "conversations": len(conversation_ids)
        }
