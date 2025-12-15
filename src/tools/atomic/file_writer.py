"""会话隔离文件写入工具

支持创建新文件或覆盖已存在的文件。
适用场景：保存代码脚本、配置文件、数据文件等。

安全：
- 仅在会话目录内写入，不允许路径穿越
- 支持覆盖保护（可选）
"""

from pathlib import Path
from typing import Dict, Any, Optional

from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FileWriter(BaseAtomicTool):
    name = "file_writer"
    description = (
        "文件写入工具: 在会话目录中创建新文件或覆盖已有文件。"
        "适用场景：保存Python脚本供后续执行、创建配置文件、保存数据文件、生成文本文件。"
        "优势：简单直接的文件写入、支持覆盖保护、自动创建目录、支持多种编码。"
        "不适用：编辑已有文件（使用file_editor）、批量文件操作（使用shell_executor）。"
        "参数: filename(文件名,必需), content(文件内容,必需), conversation_id(会话ID,必需), "
        "overwrite(是否覆盖已有文件,默认true), encoding(编码,默认utf-8)"
    )

    required_params = ["filename", "content", "conversation_id"]

    parameters_schema = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "文件名（仅文件名，不含路径）"
            },
            "content": {
                "type": "string",
                "description": "文件内容（完整内容）"
            },
            "conversation_id": {
                "type": "string",
                "description": "会话ID"
            },
            "overwrite": {
                "type": "boolean",
                "description": "是否覆盖已存在的文件（默认true，允许覆盖）",
                "default": True
            },
            "encoding": {
                "type": "string",
                "description": "文件编码（默认utf-8）",
                "default": "utf-8"
            }
        },
        "required": ["filename", "content", "conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.output_dir = config.output_dir

    def _safe_path(self, output_dir_name: str, filename: str) -> Path:
        """安全路径检查：防止路径穿越

        Args:
            output_dir_name: 完整输出目录名（由master_agent统一注入）
            filename: 文件名
        """
        p = Path(filename)
        if p.is_absolute() or ".." in p.parts or "/" in filename or "\\" in filename:
            raise ValueError("仅允许文件名，不允许路径")

        return self.output_dir / output_dir_name / filename

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行文件写入

        Args:
            filename: 文件名（仅文件名，不含路径）
            content: 文件内容
            conversation_id: 会话ID
            overwrite: 是否覆盖已存在的文件（默认True）
            encoding: 文件编码（默认utf-8）

        Returns:
            执行结果数据字典
        """
        filename: str = kwargs.get("filename")
        content: str = kwargs.get("content")
        conversation_id: str = kwargs.get("conversation_id")
        output_dir_name: str = kwargs.get("_output_dir_name")  # 由master_agent统一注入
        overwrite: bool = kwargs.get("overwrite", True)
        encoding: str = kwargs.get("encoding") or "utf-8"

        # 验证必需参数
        if not filename:
            raise ValueError("缺少filename参数")
        if content is None:  # 允许空字符串
            raise ValueError("缺少content参数")
        if not conversation_id:
            raise ValueError("缺少conversation_id参数")
        if not output_dir_name:
            raise ValueError("缺少_output_dir_name参数（应由master_agent自动注入）")

        # 获取安全路径
        path = self._safe_path(output_dir_name, filename)

        # 检查是否已存在
        if path.exists() and not overwrite:
            raise FileExistsError(
                f"文件已存在: {filename}\n"
                "如需覆盖，请设置 overwrite=true；如需编辑，请使用file_editor工具"
            )

        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        logger.info(f"写入文件: {path} ({len(content)} chars, encoding={encoding})")
        path.write_text(content, encoding=encoding)

        # 返回结果
        file_size = path.stat().st_size
        result = {
            "filename": filename,
            "conversation_id": conversation_id,
            "file_size": file_size,
            "lines": content.count('\n') + 1 if content else 0,
            "encoding": encoding,
            "action": "overwritten" if path.exists() else "created",
            "success": True
        }

        logger.info(f"文件写入成功: {filename} ({file_size} bytes)")

        # 🔧 关键修复：返回generated_files，让前端能实时预览
        return {
            "status": "success",
            "data": result,
            "generated_files": [filename]
        }
