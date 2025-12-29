"""@mention功能处理器

解析消息中的@文件名，并复制工作区文件到当前对话目录
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import List, Tuple, Set
from dataclasses import dataclass

from src.utils.workspace_store import WorkspaceStore
from src.utils.conversation_manager_v2 import ConversationManagerV2
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MentionedFile:
    """被@mention的文件信息"""
    filename: str
    source_conv_id: str
    found: bool
    copied: bool
    error: str = ""


class MentionHandler:
    """处理消息中的@mention文件"""

    def __init__(
        self,
        workspace_store: WorkspaceStore,
        conv_manager: ConversationManagerV2,
        output_dir: Path = Path("outputs")
    ):
        self.workspace_store = workspace_store
        self.conv_manager = conv_manager
        self.output_dir = output_dir

    def parse_mentions(self, message: str) -> List[str]:
        """从消息中解析@mention的文件名

        支持的格式：
        - @filename.txt
        - @"filename with spaces.txt"
        - @'filename with spaces.txt'

        Args:
            message: 用户消息文本

        Returns:
            文件名列表（去重）
        """
        # 匹配模式：@后跟文件名（支持引号包裹）
        # 1. @"filename with spaces.txt"
        # 2. @'filename with spaces.txt'
        # 3. @filename.txt（不含空格）
        pattern = r'@(?:"([^"]+)"|\'([^\']+)\'|(\S+))'
        matches = re.findall(pattern, message)

        filenames = set()
        for match in matches:
            # match是一个三元组：(双引号内容, 单引号内容, 无引号内容)
            filename = match[0] or match[1] or match[2]
            if filename:
                filenames.add(filename)

        return list(filenames)

    def process_mentions(
        self,
        message: str,
        username: str,
        current_conv_id: str
    ) -> Tuple[str, List[MentionedFile]]:
        """处理消息中的@mention文件

        解析@mention，从工作区查找文件，复制到当前对话目录

        Args:
            message: 用户消息文本
            username: 当前用户名
            current_conv_id: 当前对话ID

        Returns:
            (处理后的消息, 被mention的文件列表)
            处理后的消息会附加文件可用性说明
        """
        # 解析@mention
        mentioned_filenames = self.parse_mentions(message)
        if not mentioned_filenames:
            return message, []

        logger.info(f"检测到@mention文件: {mentioned_filenames}")

        # 查询用户的工作区文件
        workspace_files = self.workspace_store.list_all_files(username)
        workspace_map = {f["filename"]: f["source_conv_id"] for f in workspace_files}

        # 处理每个被mention的文件
        results = []
        successfully_copied = []

        for filename in mentioned_filenames:
            result = MentionedFile(
                filename=filename,
                source_conv_id="",
                found=False,
                copied=False
            )

            # 查找文件源对话ID
            if filename not in workspace_map:
                result.error = f"文件 {filename} 不在工作区中"
                logger.warning(result.error)
                results.append(result)
                continue

            result.found = True
            result.source_conv_id = workspace_map[filename]

            # 如果文件已经在当前对话目录，跳过复制
            current_output_dir = self.output_dir / self.conv_manager.get_output_dir_name(current_conv_id)
            target_path = current_output_dir / filename

            if target_path.exists():
                logger.info(f"文件 {filename} 已存在于当前对话目录，跳过复制")
                result.copied = True
                successfully_copied.append(filename)
                results.append(result)
                continue

            # 复制文件从源对话到当前对话
            try:
                source_output_dir = self.output_dir / self.conv_manager.get_output_dir_name(result.source_conv_id)
                source_path = source_output_dir / filename

                if not source_path.exists():
                    result.error = f"源文件不存在: {source_path}"
                    logger.warning(result.error)
                    results.append(result)
                    continue

                # 确保目标目录存在
                current_output_dir.mkdir(parents=True, exist_ok=True)

                # 复制文件
                shutil.copy2(source_path, target_path)
                logger.info(f"已复制文件: {source_path} -> {target_path}")

                result.copied = True
                successfully_copied.append(filename)

            except Exception as e:
                result.error = f"复制文件失败: {str(e)}"
                logger.error(result.error)

            results.append(result)

        # 构建附加消息
        if successfully_copied:
            note = f"\n\n[系统提示：已将以下工作区文件复制到当前对话: {', '.join(successfully_copied)}]"
            modified_message = message + note
        else:
            modified_message = message

        return modified_message, results
