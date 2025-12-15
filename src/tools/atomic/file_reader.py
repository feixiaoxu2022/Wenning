"""会话隔离文件读取工具（只读）

支持读取会话目录(outputs/{conversation_id})下的文件，返回结构化预览：
- text/json/csv：文本/对象/表格预览（限长/限行）
- excel：返回HTML预览片段 + sheet信息
- binary/image：返回元信息，必要时返回图片尺寸

安全：
- 仅在会话目录内读取，不允许路径穿越
- 限制读取大小/行数，避免大文件阻塞
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import io
import json
import mimetypes
import csv

from src.tools.base import BaseAtomicTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FileReader(BaseAtomicTool):
    name = "file_reader"
    description = (
        "文件读取工具: 读取会话目录中的文件并返回结构化预览（只读，安全限长）。"
        "适用场景：快速查看文件内容、预览CSV/Excel表格（自动识别格式）、读取JSON/文本配置、提取PDF文本内容。"
        "优势：自动格式识别、返回结构化预览、限长保护（避免大文件阻塞）、支持多种编码。"
        "PDF支持：优先使用PyPDF2（纯Python，无系统依赖），自动fallback到pdfplumber（需要Poppler）。"
        "不适用：需要完整读取大文件、需要复杂文本处理（使用code_executor）。"
        "参数: filename(文件名), conversation_id(必需), mode(可选:text/json/csv/excel/pdf), max_bytes/max_lines/max_pages"
    )
    required_params = ["filename", "conversation_id"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "文件名（仅文件名，不含路径）"},
            "conversation_id": {"type": "string", "description": "会话ID"},
            "mode": {
                "type": "string",
                "enum": ["auto", "text", "json", "csv", "excel", "pdf", "binary"],
                "default": "auto",
                "description": "读取模式"
            },
            "encoding": {"type": "string", "description": "文本编码", "default": "utf-8"},
            "max_bytes": {"type": "integer", "description": "最大读取字节数", "default": 200_000},
            "max_lines": {"type": "integer", "description": "最大行数(文本/CSV)", "default": 200},
            "rows": {"type": "integer", "description": "Excel/CSV 预览行数", "default": 100},
            "sheet": {"type": "string", "description": "Excel sheet名或索引", "default": "0"},
            "max_pages": {"type": "integer", "description": "PDF最大读取页数", "default": 10}
        },
        "required": ["filename", "conversation_id"]
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

    def _infer_mode(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext in [".txt", ".md", ".log", ".jsonl"]:
            return "text"
        if ext == ".json":
            return "json"
        if ext in [".csv", ".tsv"]:
            return "csv"
        if ext in [".xls", ".xlsx"]:
            return "excel"
        if ext == ".pdf":
            return "pdf"
        if ext in [".png", ".jpg", ".jpeg"]:
            return "binary"  # image as binary meta
        return "binary"

    def _read_text(self, path: Path, encoding: str, max_bytes: int, max_lines: int) -> Dict[str, Any]:
        data = path.open("rb").read(max_bytes)
        text = data.decode(encoding, errors="replace")
        lines = text.splitlines()
        truncated = path.stat().st_size > len(data) or len(lines) > max_lines
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        return {"content": "\n".join(lines), "truncated": truncated}

    def _read_json(self, path: Path, encoding: str, max_bytes: int) -> Dict[str, Any]:
        size = path.stat().st_size
        truncated = False
        content = None
        if size <= max_bytes:
            try:
                with path.open("r", encoding=encoding, errors="replace") as f:
                    content = json.load(f)
            except Exception as e:
                return {"error": f"JSON解析失败: {e}", "truncated": False}
        else:
            truncated = True
            with path.open("r", encoding=encoding, errors="replace") as f:
                head = f.read(max_bytes)
            content = head
        return {"content": content, "truncated": truncated}

    def _read_csv(self, path: Path, encoding: str, rows: int) -> Dict[str, Any]:
        out_rows: List[List[str]] = []
        headers: Optional[List[str]] = None
        try:
            with path.open("r", encoding=encoding, errors="replace", newline="") as f:
                sample = f.read(2048)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except Exception:
                    dialect = csv.excel
                reader = csv.reader(f, dialect)
                for i, row in enumerate(reader):
                    if i == 0:
                        headers = row
                    else:
                        out_rows.append(row)
                    if i >= rows:
                        break
        except Exception as e:
            return {"error": f"CSV读取失败: {e}"}
        return {"headers": headers, "rows": out_rows, "truncated": True}

    def _read_excel(self, path: Path, sheet: str, rows: int) -> Dict[str, Any]:
        try:
            import pandas as pd
            # 解析sheet
            if sheet.isdigit():
                sh = int(sheet)
            else:
                sh = sheet
            # 获取sheet列表
            xls = pd.ExcelFile(path)
            sheet_names = list(xls.sheet_names)
            target_sheet = sh if (isinstance(sh, int) or sh in sheet_names) else 0
            df = pd.read_excel(path, sheet_name=target_sheet, nrows=rows)
            html = df.to_html(index=False, classes='excel-table', border=0)
            return {
                "sheet_names": sheet_names,
                "sheet": target_sheet,
                "preview_rows": len(df.index),
                "html": html,
                "truncated": True
            }
        except Exception as e:
            return {"error": f"Excel读取失败: {e}"}

    def _read_binary(self, path: Path) -> Dict[str, Any]:
        size = path.stat().st_size
        mime, _ = mimetypes.guess_type(path.name)
        meta = {"size": size, "mime": mime or "application/octet-stream"}
        try:
            from PIL import Image
            if path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                with Image.open(path) as im:
                    meta.update({"image": {"width": im.width, "height": im.height, "mode": im.mode}})
        except Exception:
            pass
        return {"meta": meta}

    def _read_pdf(self, path: Path, max_pages: int = 10) -> Dict[str, Any]:
        """读取PDF文件内容（多方案fallback）

        优先使用PyPDF2（纯Python，无系统依赖），如果失败则尝试pdfplumber（需要Poppler）

        Args:
            path: PDF文件路径
            max_pages: 最多读取页数（避免大文件阻塞）

        Returns:
            包含文本内容、页数等信息的字典
        """
        result = {"filename": path.name, "type": "pdf"}

        # 方案1: 优先使用 PyPDF2 (纯Python，无系统依赖)
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(path))
            total_pages = len(reader.pages)
            read_pages = min(max_pages, total_pages)

            text_parts = []
            for i in range(read_pages):
                try:
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {i+1} ---\n{page_text}")
                except Exception as e:
                    text_parts.append(f"--- Page {i+1} ---\n[提取失败: {e}]")

            result.update({
                "content": "\n\n".join(text_parts),
                "pages": total_pages,
                "read_pages": read_pages,
                "truncated": read_pages < total_pages,
                "method": "PyPDF2"
            })

            logger.info(f"使用PyPDF2成功读取PDF: {path.name}, {total_pages}页")
            return result

        except ImportError:
            logger.warning("PyPDF2未安装，尝试使用pdfplumber...")
        except Exception as e:
            logger.warning(f"PyPDF2读取失败: {e}，尝试使用pdfplumber...")

        # 方案2: 尝试使用 pdfplumber (功能更强，但需要Poppler)
        try:
            import pdfplumber

            with pdfplumber.open(str(path)) as pdf:
                total_pages = len(pdf.pages)
                read_pages = min(max_pages, total_pages)

                text_parts = []
                for i in range(read_pages):
                    try:
                        page = pdf.pages[i]
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"--- Page {i+1} ---\n{page_text}")
                    except Exception as e:
                        text_parts.append(f"--- Page {i+1} ---\n[提取失败: {e}]")

                result.update({
                    "content": "\n\n".join(text_parts),
                    "pages": total_pages,
                    "read_pages": read_pages,
                    "truncated": read_pages < total_pages,
                    "method": "pdfplumber"
                })

                logger.info(f"使用pdfplumber成功读取PDF: {path.name}, {total_pages}页")
                return result

        except ImportError:
            error_msg = (
                "PDF读取失败: 缺少必要的Python库。\n"
                "请安装: pip install PyPDF2 pdfplumber\n"
                "注意: pdfplumber需要系统安装Poppler (macOS: brew install poppler)"
            )
            logger.error(error_msg)
            return {"error": error_msg, "type": "pdf"}
        except Exception as e:
            error_msg = f"pdfplumber读取失败: {e}"
            logger.error(error_msg)

            # 提供详细的安装指导
            if "poppler" in str(e).lower():
                install_guide = (
                    "\n\n系统缺少Poppler工具，请安装:\n"
                    "macOS: brew install poppler\n"
                    "Ubuntu/Debian: sudo apt-get install poppler-utils\n"
                    "或者只使用PyPDF2 (pip install PyPDF2，无需系统依赖)"
                )
                error_msg += install_guide

            return {"error": error_msg, "type": "pdf"}

    def execute(self, **kwargs) -> Dict[str, Any]:
        filename: str = kwargs.get("filename")
        output_dir_name: str = kwargs.get("_output_dir_name")  # 由master_agent统一注入
        mode: str = (kwargs.get("mode") or "auto").lower()
        encoding: str = kwargs.get("encoding") or "utf-8"
        max_bytes: int = int(kwargs.get("max_bytes") or 200_000)
        max_lines: int = int(kwargs.get("max_lines") or 200)
        rows: int = int(kwargs.get("rows") or 100)
        sheet: str = str(kwargs.get("sheet") or "0")
        max_pages: int = int(kwargs.get("max_pages") or 10)  # PDF最大页数

        if not output_dir_name:
            raise ValueError("缺少_output_dir_name参数（应由master_agent自动注入）")

        path = self._safe_path(output_dir_name, filename)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {filename}")

        file_mode = mode if mode != "auto" else self._infer_mode(filename)
        logger.info(f"读取文件: mode={file_mode}, file={path}")

        data: Dict[str, Any] = {"filename": filename, "type": file_mode}
        if file_mode == "text":
            data.update(self._read_text(path, encoding, max_bytes, max_lines))
        elif file_mode == "json":
            data.update(self._read_json(path, encoding, max_bytes))
        elif file_mode == "csv":
            data.update(self._read_csv(path, encoding, rows))
        elif file_mode == "excel":
            data.update(self._read_excel(path, sheet, rows))
        elif file_mode == "pdf":
            data.update(self._read_pdf(path, max_pages))
        else:
            data.update(self._read_binary(path))

        # 基本元信息
        try:
            st = path.stat()
            data.setdefault("meta", {})
            data["meta"].update({"size": st.st_size})
        except Exception:
            pass

        return data

