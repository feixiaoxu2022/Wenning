"""Shell 执行工具（安全受限）

在会话工作目录(outputs/{conversation_id})内执行受限的 shell 命令。
用途：批量重命名、简单编解码、用系统工具做轻量处理等。

安全策略（基础版）：
- 必须提供 conversation_id；工作目录固定为 outputs/{conversation_id}
- 拒绝明显危险命令/模式：rm、sudo、chmod、chown、mv 到上级、重定向到绝对/上级路径等
- 超时可配，默认与代码执行超时一致
- 返回 stdout/stderr/returncode，并给出“本次新增的文件列表”（会话目录差集）
"""

from pathlib import Path
from typing import Dict, Any, Optional
import subprocess
import os
import re

from src.tools.base import BaseAtomicTool, ToolStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ShellExecutor(BaseAtomicTool):
    """受限 Shell 执行工具"""

    name = "shell_executor"
    description = (
        "Shell命令执行: 在会话目录中执行bash命令（安全受限）。"
        "适用场景：批量文件操作（重命名、移动、复制）、快速查找（find/grep）、管道处理（cat|sort|uniq）、系统工具调用（wc/awk/sed）。"
        "优势：Shell语法简洁（一行完成批量操作）、支持管道和重定向、适合快速命令。"
        "不适用：复杂编程逻辑、需要Python库的数据处理（使用code_executor）。"
        "安全限制：禁止rm、sudo、pip install、ssh等危险命令。"
        "参数: cmd(bash命令,必需), conversation_id(必需), timeout(超时秒数)"
    )
    required_params = ["cmd", "conversation_id"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "cmd": {"type": "string", "description": "要执行的 shell 命令(在bash -lc中执行)"},
            "conversation_id": {"type": "string", "description": "会话ID(用于定位工作目录)"},
            "timeout": {"type": "integer", "description": "超时时间(秒)", "minimum": 1}
        },
        "required": ["cmd", "conversation_id"]
    }

    def __init__(self, config):
        super().__init__(config)
        self.timeout = config.code_executor_timeout
        self.output_dir = config.output_dir

    def _is_dangerous(self, cmd: str) -> Optional[str]:
        """检查命令是否包含危险模式

        Returns:
            如果危险，返回匹配的模式；否则返回None
        """
        # 基础危险命令
        bad_patterns = [
            r"\bsudo\b",
            r"\brm\b",
            r"\bchmod\b",
            r"\bchown\b",
            r"\bmkfs\b",
            r"\bmount\b",
            r"\bumount\b",
            r"\bshutdown\b|\breboot\b",
            r"\bscp\b|\bssh\b",
        ]

        # 包管理和环境修改命令（新增）
        package_management_patterns = [
            r"\bpip\s+install\b",
            r"\bpip3\s+install\b",
            r"\bconda\s+install\b",
            r"\bplaywright\s+install\b",
            r"\bnpm\s+install\b",
            r"\byarn\s+(add|install)\b",
            r"\bapt-get\s+install\b",
            r"\byum\s+install\b",
            r"\bbrew\s+install\b",
        ]

        # 合并所有模式
        all_patterns = bad_patterns + package_management_patterns

        for p in all_patterns:
            if re.search(p, cmd, re.IGNORECASE):
                return p

        # 禁止向上级/绝对路径进行重定向或写入
        forbid_paths = ["../", "/"]
        if any(tok in cmd for tok in [">>", ">", "2>"]):
            if any(fp in cmd for fp in forbid_paths):
                return "redirect-outside-cwd"
        # 禁止显式 mv 到上级
        if re.search(r"\bmv\b[^\n]*\.\./", cmd):
            return "mv-parent"
        return None

    def execute(self, **kwargs) -> Dict[str, Any]:
        cmd: str = kwargs.get("cmd", "").strip()
        conversation_id: Optional[str] = kwargs.get("conversation_id")
        output_dir_name: str = kwargs.get("_output_dir_name")  # 由master_agent统一注入
        timeout: int = kwargs.get("timeout") or self.timeout

        if not cmd:
            raise ValueError("缺少cmd参数")
        if not conversation_id:
            raise ValueError("缺少conversation_id参数")
        if not output_dir_name:
            raise ValueError("缺少_output_dir_name参数（应由master_agent自动注入）")

        danger = self._is_dangerous(cmd)
        if danger:
            raise RuntimeError(f"命令包含受限模式: {danger}")

        work_dir = self.output_dir / output_dir_name
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            pre_files = {p.name for p in work_dir.iterdir() if p.is_file()}
        except Exception:
            pre_files = set()

        logger.info(f"Shell执行: cwd={work_dir}, cmd={cmd}")
        import time
        start_ns = time.time_ns()
        try:
            result = subprocess.run(
                ["bash", "-lc", cmd],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ}
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"shell执行超时（限制{timeout}s）")

        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode

        try:
            post_paths = [p for p in work_dir.iterdir() if p.is_file()]
            post_files = {p.name for p in post_paths}
        except Exception:
            post_paths = []
            post_files = set()
        new_files_set = post_files - pre_files
        try:
            changed = [p.name for p in post_paths if getattr(p.stat(), 'st_mtime_ns', int(p.stat().st_mtime*1e9)) >= (start_ns - 5_000_000)]
        except Exception:
            changed = []
        new_files = sorted(list({*new_files_set, *set(changed)}))

        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": returncode,
            "execution_time": f"<{timeout}s",
            "generated_files": new_files
        }
