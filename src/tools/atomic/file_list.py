"""会话目录文件列表工具（只读）"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger
import time

logger = get_logger(__name__)


class FileList(BaseAtomicTool):
    name = "file_list"
    description = (
        "文件列表工具: 列出会话目录中的文件，支持过滤、排序和限制。"
        "适用场景：查找生成的文件、检查文件是否存在、按类型/时间筛选文件、统计文件数量。"
        "优势：支持扩展名过滤(.png/.xlsx)、glob模式匹配(*.png)、多种排序方式(name/mtime/size)。"
        "不适用：递归查找子目录、复杂文件操作（使用shell_executor的find命令或code_executor）。"
        "参数: conversation_id(必需), ext(扩展名过滤), pattern(glob模式), limit(条数限制), sort(排序方式)"
    )
    required_params = ["conversation_id"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "conversation_id": {"type": "string", "description": "会话ID"},
            "ext": {"type": "string", "description": "扩展名过滤(如 .png, .xlsx)"},
            "pattern": {"type": "string", "description": "glob 模式过滤(如 *.png)"},
            "limit": {"type": "integer", "description": "返回条数上限", "default": 200},
            "sort": {"type": "string", "enum": ["name", "mtime", "size"], "default": "mtime"},
            "order": {"type": "string", "enum": ["asc", "desc"], "default": "desc"}
        },
        "required": ["conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.output_dir = config.output_dir

    def execute(self, **kwargs) -> Dict[str, Any]:
        conv: str = kwargs.get("conversation_id")
        ext: Optional[str] = kwargs.get("ext")
        pattern: Optional[str] = kwargs.get("pattern")
        limit: int = int(kwargs.get("limit") or 200)
        sort: str = (kwargs.get("sort") or "mtime").lower()
        order: str = (kwargs.get("order") or "desc").lower()

        base = self.output_dir / conv
        if not base.exists():
            return {"files": []}

        files: List[Path] = []
        if pattern:
            files = list(base.glob(pattern))
        else:
            files = [p for p in base.iterdir() if p.is_file()]

        if ext:
            e = ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            files = [p for p in files if p.suffix.lower() == e]

        def key(p: Path):
            if sort == 'name':
                return p.name.lower()
            if sort == 'size':
                try:
                    return p.stat().st_size
                except Exception:
                    return 0
            # mtime 默认
            try:
                return p.stat().st_mtime
            except Exception:
                return 0

        files.sort(key=key, reverse=(order == 'desc'))
        files = files[:limit]

        items = []
        for p in files:
            try:
                st = p.stat()
                items.append({
                    "name": p.name,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "ext": p.suffix.lower(),
                })
            except Exception:
                continue

        return {"files": items}

