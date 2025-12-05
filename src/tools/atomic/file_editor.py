"""会话隔离文件编辑工具

支持两种编辑模式：
1. 精确字符串替换 - 适合单次修改
2. 行范围编辑 - 适合多轮微调

安全：
- 仅在会话目录内编辑，不允许路径穿越
- 支持上下文验证，确保在正确位置修改
"""

from pathlib import Path
from typing import Dict, Any, Optional
import difflib

from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FileEditor(BaseAtomicTool):
    name = "file_editor"
    description = """编辑会话目录中的文件。支持两种模式：

【模式1：精确字符串替换】适合单次修改
- 参数：old_string（必需）, new_string（必需）, replace_all（可选）
- 用法：当你知道要替换的确切文本时使用
- 示例：file_editor(conversation_id="xxx", filename="app.py", old_string="foo", new_string="bar")

【模式2：行范围编辑】适合多轮微调同一位置
- 参数：start_line（必需）, end_line（必需）, line_content（必需）, verify_context（可选）
- 用法：当你需要在固定位置多次调整时使用
- 示例：file_editor(conversation_id="xxx", filename="app.py", start_line=100, end_line=102,
          line_content="new code\\n", verify_context="def my_func")

注意：
1. 两种模式互斥，不能同时使用
2. 模式2的行号从1开始计数
3. verify_context参数可选，用于安全验证是否在正确的上下文中修改
"""

    required_params = ["filename", "conversation_id"]

    parameters_schema = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "文件名（仅文件名，不含路径）"
            },
            "conversation_id": {
                "type": "string",
                "description": "会话ID"
            },

            # 模式1参数
            "old_string": {
                "type": "string",
                "description": "【模式1】要替换的原始字符串"
            },
            "new_string": {
                "type": "string",
                "description": "【模式1】替换后的新字符串"
            },
            "replace_all": {
                "type": "boolean",
                "description": "【模式1】是否替换所有匹配项（默认false，只替换第一个）",
                "default": False
            },

            # 模式2参数
            "start_line": {
                "type": "integer",
                "description": "【模式2】起始行号（从1开始）"
            },
            "end_line": {
                "type": "integer",
                "description": "【模式2】结束行号（包含该行）"
            },
            "line_content": {
                "type": "string",
                "description": "【模式2】替换的内容（注意保留缩进和换行符）"
            },

            # 通用参数
            "verify_context": {
                "type": "string",
                "description": "【可选】验证上下文：确保修改区域包含此文本，用于安全验证"
            },
            "encoding": {
                "type": "string",
                "description": "文件编码",
                "default": "utf-8"
            }
        },
        "required": ["filename", "conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.output_dir = config.output_dir

    def _safe_path(self, conv: str, filename: str) -> Path:
        """安全路径检查：防止路径穿越"""
        p = Path(filename)
        if p.is_absolute() or ".." in p.parts or "/" in filename or "\\" in filename:
            raise ValueError("仅允许文件名，不允许路径")
        return (self.output_dir / conv / filename)

    def _detect_mode(self, kwargs: Dict[str, Any]) -> str:
        """检测编辑模式"""
        has_old_string = "old_string" in kwargs and kwargs.get("old_string") is not None
        has_line_range = any(k in kwargs and kwargs.get(k) is not None
                            for k in ["start_line", "end_line"])

        if has_old_string and has_line_range:
            raise ValueError(
                "不能同时使用字符串替换模式和行范围编辑模式。\n"
                "请选择一种模式：\n"
                "- 模式1：提供 old_string + new_string\n"
                "- 模式2：提供 start_line + end_line + line_content"
            )

        if has_old_string:
            return "string_replace"
        elif has_line_range:
            return "line_range"
        else:
            raise ValueError(
                "必须指定编辑模式：\n"
                "- 模式1（字符串替换）：提供 old_string + new_string\n"
                "- 模式2（行范围编辑）：提供 start_line + end_line + line_content"
            )

    def _edit_by_string_replace(
        self,
        path: Path,
        old_string: str,
        new_string: str,
        replace_all: bool,
        encoding: str
    ) -> Dict[str, Any]:
        """模式1：精确字符串替换"""
        # 读取文件
        content = path.read_text(encoding=encoding)

        # 检查old_string是否存在
        if old_string not in content:
            raise ValueError(f"未找到要替换的字符串: {old_string[:100]}...")

        # 检查唯一性（如果不是replace_all）
        if not replace_all and content.count(old_string) > 1:
            raise ValueError(
                f"找到多个匹配项（{content.count(old_string)}个）。"
                "请提供更具体的old_string，或设置replace_all=true替换所有匹配项。"
            )

        # 执行替换
        if replace_all:
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
            count = 1

        # 写回文件
        path.write_text(new_content, encoding=encoding)

        return {
            "mode": "string_replace",
            "replacements": count,
            "old_length": len(old_string),
            "new_length": len(new_string),
            "success": True
        }

    def _edit_by_line_range(
        self,
        path: Path,
        start_line: int,
        end_line: int,
        line_content: str,
        verify_context: Optional[str],
        encoding: str
    ) -> Dict[str, Any]:
        """模式2：行范围编辑"""
        # 读取文件
        lines = path.read_text(encoding=encoding).splitlines(keepends=True)
        total_lines = len(lines)

        # 验证行号范围
        if start_line < 1 or end_line < 1:
            raise ValueError(f"行号必须从1开始：start_line={start_line}, end_line={end_line}")

        if start_line > total_lines or end_line > total_lines:
            raise ValueError(
                f"行号超出范围：start_line={start_line}, end_line={end_line}, "
                f"文件总共{total_lines}行"
            )

        if start_line > end_line:
            raise ValueError(f"start_line({start_line})不能大于end_line({end_line})")

        # 可选：验证上下文
        if verify_context:
            context_lines = ''.join(lines[start_line-1:end_line])
            if verify_context not in context_lines:
                raise ValueError(
                    f"上下文验证失败：在第{start_line}-{end_line}行未找到'{verify_context[:50]}...'\n"
                    f"实际内容：{context_lines[:200]}..."
                )

        # 保存原始内容用于diff
        old_content = ''.join(lines[start_line-1:end_line])

        # 执行替换
        new_lines = []
        new_lines.extend(lines[:start_line-1])  # 保留之前的行

        # 确保新内容以换行符结尾（如果原文件有换行符）
        if line_content and not line_content.endswith('\n') and lines and lines[-1].endswith('\n'):
            line_content = line_content + '\n'

        new_lines.append(line_content)  # 插入新内容
        new_lines.extend(lines[end_line:])  # 保留之后的行

        # 写回文件
        path.write_text(''.join(new_lines), encoding=encoding)

        # 生成diff用于展示
        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            line_content.splitlines(keepends=True),
            fromfile=f"{path.name} (lines {start_line}-{end_line})",
            tofile=f"{path.name} (new)",
            lineterm=''
        ))

        return {
            "mode": "line_range",
            "start_line": start_line,
            "end_line": end_line,
            "lines_replaced": end_line - start_line + 1,
            "old_length": len(old_content),
            "new_length": len(line_content),
            "diff": '\n'.join(diff[:20]) if diff else "(no changes)",
            "success": True
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行文件编辑"""
        filename: str = kwargs.get("filename")
        conversation_id: str = kwargs.get("conversation_id")
        encoding: str = kwargs.get("encoding") or "utf-8"

        # 获取文件路径
        path = self._safe_path(conversation_id, filename)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {filename}")

        # 检测编辑模式
        mode = self._detect_mode(kwargs)

        logger.info(f"编辑文件: mode={mode}, file={path}")

        # 根据模式执行编辑
        if mode == "string_replace":
            old_string = kwargs.get("old_string")
            new_string = kwargs.get("new_string")
            replace_all = kwargs.get("replace_all", False)

            if new_string is None:
                raise ValueError("模式1需要提供new_string参数")

            result = self._edit_by_string_replace(
                path, old_string, new_string, replace_all, encoding
            )
        else:  # line_range
            start_line = kwargs.get("start_line")
            end_line = kwargs.get("end_line")
            line_content = kwargs.get("line_content")
            verify_context = kwargs.get("verify_context")

            if start_line is None or end_line is None:
                raise ValueError("模式2需要提供start_line和end_line参数")
            if line_content is None:
                raise ValueError("模式2需要提供line_content参数")

            result = self._edit_by_line_range(
                path, int(start_line), int(end_line),
                line_content, verify_context, encoding
            )

        # 添加通用信息
        result.update({
            "filename": filename,
            "conversation_id": conversation_id,
            "file_size": path.stat().st_size
        })

        return result
