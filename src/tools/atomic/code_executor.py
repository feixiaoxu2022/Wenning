"""代码执行沙箱工具

在隔离环境中安全执行LLM生成的Python代码。
MVP阶段使用subprocess隔离，V1.5升级为Docker容器。
"""

import subprocess
import sys
import time
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional
from src.tools.base import BaseAtomicTool, ToolStatus
from src.tools.result import ErrorType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CodeExecutor(BaseAtomicTool):
    """代码执行沙箱工具

    支持Python代码的安全执行，限制资源和超时。
    """

    name = "code_executor"
    description = (
        "Python代码执行沙箱: 在安全环境中执行Python代码进行数据处理、科学计算和可视化。"
        "支持两种模式：\n"
        "1. 内联模式（code参数）：直接传入代码，适合一次性代码\n"
        "2. 文件模式（script_file参数）：执行已保存的脚本文件，适合需要迭代调整的代码\n"
        "适用场景：数据统计分析、科学计算、数据可视化（图表生成）、技术图形绘制、算法演示、"
        "数据动画（matplotlib.animation）、数学动画（manim库生成教学视频）、视频编辑（moviepy）、复杂文件处理。"
        "优势：完整的Python生态（pandas/numpy/matplotlib/PIL/moviepy/manim）、适合复杂编程逻辑、可以使用各种Python库、支持文件模式便于迭代。"
        "不适用场景：艺术创作类的图像/视频生成（优先使用MiniMax API）、简单的批量文件操作和命令（优先使用shell_executor更简洁）。"
        "参数: code(内联代码)或script_file(脚本文件名,二选一), conversation_id(会自动注入), language(默认python), timeout(超时秒数)"
    )
    required_params = []  # code和script_file二选一，不能硬性要求
    # 为Function Calling提供明确的参数schema，避免LLM不传必需参数
    parameters_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "【模式1-内联】要执行的Python代码（与script_file二选一）"
            },
            "script_file": {
                "type": "string",
                "description": "【模式2-文件】要执行的脚本文件名（仅文件名，不含路径，与code二选一）"
            },
            "language": {
                "type": "string",
                "enum": ["python"],
                "description": "编程语言，仅支持python",
                "default": "python"
            },
            "save_output": {
                "type": "boolean",
                "description": "是否保存输出文件",
                "default": True
            },
            "output_filename": {
                "type": "string",
                "description": "期望生成的文件名（如 .xlsx/.png）"
            },
            "timeout": {
                "type": "integer",
                "description": "执行超时(秒)",
                "minimum": 1
            }
        },
        "required": []  # code和script_file至少有一个，在execute中验证
    }

    def __init__(self, config, conv_manager=None):
        super().__init__(config)
        self.timeout = config.code_executor_timeout
        self.output_dir = config.output_dir
        self.conv_manager = conv_manager  # 保存conv_manager用于图片识别

    def execute(
        self,
        code: Optional[str] = None,
        script_file: Optional[str] = None,
        language: str = "python",
        save_output: bool = True,
        output_filename: Optional[str] = None,
        timeout: Optional[int] = None,
        conversation_id: Optional[str] = None,
        **kwargs  # 接收master_agent注入的_output_dir_name等参数
    ) -> Dict[str, Any]:
        """执行代码

        Args:
            code: 要执行的代码（与script_file二选一）
            script_file: 要执行的脚本文件名（与code二选一）
            language: 编程语言（目前仅支持python）
            save_output: 是否保存输出文件
            output_filename: 输出文件名（如生成图片）
            timeout: 超时秒数
            conversation_id: 会话ID

        Returns:
            执行结果数据字典（不含状态包装），由run()进行包装
        """
        # 模式验证：code和script_file必须提供且只能提供一个
        if not code and not script_file:
            raise ValueError(
                "必须提供code或script_file参数之一。\n"
                "- 模式1（内联）：传入code参数\n"
                "- 模式2（文件）：传入script_file参数"
            )

        if code and script_file:
            raise ValueError(
                "不能同时提供code和script_file参数，请选择一种模式：\n"
                "- 模式1（内联）：只传code\n"
                "- 模式2（文件）：只传script_file"
            )

        if language != "python":
            raise ValueError(f"暂不支持的语言: {language}")

        # 强制要求会话ID，避免落到根目录
        if not conversation_id or str(conversation_id).strip() == "":
            raise RuntimeError("缺少conversation_id，拒绝执行以避免写入根目录")

        # 模式2：从文件读取代码
        if script_file:
            # 安全路径检查
            p = Path(script_file)
            if p.is_absolute() or ".." in p.parts or "/" in script_file or "\\" in script_file:
                raise ValueError("script_file仅允许文件名，不允许路径")

            # 获取master_agent注入的输出目录名
            output_dir_name = kwargs.get("_output_dir_name")
            if not output_dir_name:
                raise ValueError("缺少_output_dir_name参数（应由master_agent自动注入）")

            # 构造文件路径
            script_path = self.output_dir / output_dir_name / script_file

            if not script_path.exists():
                raise FileNotFoundError(
                    f"脚本文件不存在: {script_file}\n"
                    "提示：请先使用file_writer工具创建脚本文件，再使用code_executor执行"
                )

            # 读取文件内容
            logger.info(f"从文件读取代码: {script_path}")
            code = script_path.read_text(encoding='utf-8')
            logger.info(f"读取完成: {len(code)} characters")

        used_timeout = int(timeout or self.timeout)
        logger.info(f"执行Python代码: {len(code)} characters (conversation_id={conversation_id}, timeout={used_timeout}s, mode={'file' if script_file else 'inline'})")

        # 预处理代码：
        # - 修正LLM常见导入拼写(moviepy.edit -> moviepy.editor)
        # - 修正可能导致嵌套目录的路径问题
        # - 自动注入中文字体支持（避免视频/图表中文乱码）
        code = self._harmonize_imports(code)
        code = self._sanitize_code_paths(code, conversation_id)
        code = self._inject_chinese_font_support(code)

        # 创建临时文件（直接写用户代码，cwd 由我们控制）
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            temp_file = f.name
            f.write(code)

        try:
            # 执行代码
            # 确定工作目录（对话级隔离）
            output_dir_name = kwargs.get("_output_dir_name")
            if not output_dir_name:
                raise ValueError("缺少_output_dir_name参数（应由master_agent自动注入）")

            work_dir = self.output_dir / output_dir_name
            work_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"CodeExecutor work_dir resolved to: {work_dir}")

            # 记录执行前文件快照
            try:
                pre_files = {p.name for p in work_dir.iterdir() if p.is_file()}
            except Exception:
                pre_files = set()
            # 仅观测会话目录

            start_ns = time.time_ns()
            # 使用与当前进程一致的解释器，避免在多环境下出现依赖缺失（如moviepy）
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=used_timeout,
                cwd=str(work_dir)  # 在工作目录执行，方便保存文件
            )

            stdout = result.stdout
            stderr = result.stderr
            returncode = result.returncode

            # 检查是否成功
            if returncode == 0:
                logger.info(f"代码执行成功 (work_dir={work_dir})")

                # 记录执行后文件快照并计算新文件集（覆盖写的情况另行加入）
                try:
                    post_paths = [p for p in work_dir.iterdir() if p.is_file()]
                    post_files = {p.name for p in post_paths}
                except Exception:
                    post_paths = []
                    post_files = set()
                new_files_set = set(post_files - pre_files)
                # 新增：并入“执行期间被修改/覆盖”的文件（按修改时间判断）
                try:
                    changed = [p.name for p in post_paths if getattr(p.stat(), 'st_mtime_ns', int(p.stat().st_mtime*1e9)) >= (start_ns - 5_000_000)]
                except Exception:
                    changed = []
                merged = sorted(list({*new_files_set, *set(changed)}))
                new_files = merged
                logger.info(f"新增文件（仅会话目录差集）: {new_files}")

                if not new_files and not (output_filename and (work_dir / output_filename).exists()):
                    # 允许不生成文件的代码执行（如检查、分析类代码）
                    # 只在明确指定output_filename但文件不存在时记录警告
                    if output_filename:
                        logger.warning(f"指定的输出文件不存在: {output_filename}")
                    else:
                        logger.info("代码执行成功，无新文件生成（可能是检查/分析类代码）")

                if output_filename:
                    expected_path = work_dir / output_filename
                    if expected_path.exists() and output_filename not in new_files:
                        new_files.append(output_filename)

                generated_files = new_files

                # 返回纯数据，run() 负责包装与提升 generated_files
                return {
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": returncode,
                    "execution_time": f"<{used_timeout}s",
                    "generated_files": generated_files
                }
            else:
                logger.error(f"代码执行失败: returncode={returncode}, stderr={stderr}")
                raise RuntimeError(
                    f"代码执行失败 (返回码: {returncode})\n{stderr.strip()}"
                )

        except subprocess.TimeoutExpired:
            logger.error(f"代码执行超时: timeout={used_timeout}s")
            raise RuntimeError(f"执行超时（限制{used_timeout}秒）")

        except Exception as e:
            logger.error(f"代码执行异常: {str(e)}")
            raise

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except Exception:
                pass
        
        
    def _find_generated_files(self, expected_filename: Optional[str] = None, work_dir: Optional[Path] = None) -> list[str]:
        """查找会话目录中的文件（仅会话目录）"""
        generated_files = []
        base_dir = work_dir if work_dir is not None else self.output_dir
        if expected_filename:
            expected_path = base_dir / expected_filename
            if expected_path.exists():
                generated_files.append(expected_path.name)
        else:
            try:
                for file_path in base_dir.iterdir():
                    if file_path.is_file():
                        generated_files.append(file_path.name)
            except Exception:
                pass
        return generated_files

    # 覆盖基类，提升 generated_files 到顶层，便于Registry传递
    def run(self, **kwargs) -> Dict[str, Any]:
        self.status = ToolStatus.RUNNING
        logger.info(f"{self.name}: 开始执行, params={kwargs}")

        try:
            if not self.validate_params(**kwargs):
                self.status = ToolStatus.FAILED
                return {
                    "status": "failed",
                    "error": "参数校验失败",
                    "tool": self.name
                }

            result = self.execute(**kwargs)
            self.status = ToolStatus.SUCCESS

            # 提升 generated_files 到顶层，供Registry使用
            top_level_generated = []
            try:
                if isinstance(result, dict) and "generated_files" in result:
                    top_level_generated = result.get("generated_files") or []
            except Exception:
                top_level_generated = []

            return {
                "status": "success",
                "data": result,
                "tool": self.name,
                "generated_files": top_level_generated
            }

        except Exception as e:
            self.status = ToolStatus.FAILED
            logger.error(f"{self.name}: 执行失败, error={str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "tool": self.name
            }

    def execute_with_context(
        self,
        code: str,
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行代码并传入上下文数据

        Args:
            code: 要执行的代码
            context_data: 上下文数据（会序列化为JSON传递）

        Returns:
            执行结果
        """
        if context_data:
            # 将上下文数据注入代码
            import json
            context_json = json.dumps(context_data, ensure_ascii=False)

            injected_code = f"""
import json

# 注入的上下文数据
_context_data = json.loads('''{context_json}''')

# 用户代码
{code}
"""
            return self.execute(injected_code)
        else:
            return self.execute(code)

    def _sanitize_code_paths(self, code: str, conversation_id: str) -> str:
        """清理代码中的路径问题，避免创建嵌套子目录

        常见问题模式:
        1. os.makedirs('outputs/xxx', ...) - 创建子目录
        2. plt.savefig('outputs/xxx/file.png') - 带路径前缀的保存
        3. df.to_excel('./output/file.xlsx') - 相对路径
        4. open('/tmp/file.txt', 'w') - 绝对路径

        修正策略: 将所有路径简化为纯文件名
        """
        import re

        original_code = code

        # 模式1: 移除 os.makedirs 调用（工作目录已由系统设置）
        code = re.sub(
            r'os\.makedirs\s*\([^)]+\)\s*\n?',
            '# [auto-removed] makedirs not needed, cwd is already set\n',
            code
        )

        # 模式2: 简化文件保存路径 - 提取纯文件名
        # 匹配: savefig('outputs/xxx/file.png') 或 savefig("./output/file.png")
        def simplify_save_path(match):
            full_match = match.group(0)
            path_str = match.group(1)

            # 提取文件名
            if '/' in path_str:
                filename = path_str.split('/')[-1]
            elif '\\' in path_str:
                filename = path_str.split('\\')[-1]
            else:
                filename = path_str

            # 保持原始引号类型
            quote = "'" if "'" in full_match else '"'
            return f"savefig({quote}{filename}{quote}"

        code = re.sub(
            r'savefig\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            simplify_save_path,
            code
        )

        # 模式3: 简化 to_excel/to_csv 等路径
        def simplify_to_method_path(match):
            method = match.group(1)
            path_str = match.group(2)

            if '/' in path_str:
                filename = path_str.split('/')[-1]
            elif '\\' in path_str:
                filename = path_str.split('\\')[-1]
            else:
                filename = path_str

            quote = "'" if "'" in match.group(0) else '"'
            return f".{method}({quote}{filename}{quote}"

        code = re.sub(
            r'\.(to_excel|to_csv|to_json|to_html)\s*\(\s*[\'"]([^\'"]+)[\'"]\s*',
            simplify_to_method_path,
            code
        )

        # 模式4: 简化 Image.save() 等路径
        def simplify_image_save(match):
            path_str = match.group(1)

            if '/' in path_str:
                filename = path_str.split('/')[-1]
            elif '\\' in path_str:
                filename = path_str.split('\\')[-1]
            else:
                filename = path_str

            quote = "'" if "'" in match.group(0) else '"'
            return f".save({quote}{filename}{quote}"

        code = re.sub(
            r'\.save\s*\(\s*[\'"]([^\'"]+)[\'"]\s*',
            simplify_image_save,
            code
        )

        # 模式5: 简化 open() 写文件路径（仅处理写模式）
        def simplify_open_path(match):
            path_str = match.group(1)
            mode = match.group(2)

            # 只处理写模式
            if 'w' not in mode and 'a' not in mode:
                return match.group(0)

            if '/' in path_str:
                filename = path_str.split('/')[-1]
            elif '\\' in path_str:
                filename = path_str.split('\\')[-1]
            else:
                filename = path_str

            quote = "'" if "'" in match.group(0) else '"'
            return f"open({quote}{filename}{quote}, {quote}{mode}{quote}"

        code = re.sub(
            r'open\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*',
            simplify_open_path,
            code
        )

        # 模式6: 移除 Path().mkdir() 调用
        code = re.sub(
            r'Path\s*\([^)]*\)\.mkdir\s*\([^)]*\)\s*\n?',
            '# [auto-removed] mkdir not needed\n',
            code
        )

        if code != original_code:
            logger.info(f"代码路径已自动修正 (conversation_id={conversation_id})")

        return code

    def _harmonize_imports(self, code: str) -> str:
        """修正常见第三方导入拼写错误，提升容错性。

        注意：moviepy.edit -> moviepy.editor 的修正（常见拼写错误）
        不再进行版本相关的自动转换，让LLM根据版本信息生成正确代码
        """
        import re
        original = code

        # 只修正明显的拼写错误：moviepy.edit -> moviepy.editor
        patterns = [
            # from moviepy.edit -> from moviepy.editor（拼写错误修正）
            (r"\bfrom\s+moviepy\.edit\b", "from moviepy.editor"),
            # import moviepy.edit as mpy -> import moviepy.editor as mpy
            (r"\bimport\s+moviepy\.edit\s+as\s+(\w+)", r"import moviepy.editor as \1"),
            # import moviepy.edit -> import moviepy.editor
            (r"\bimport\s+moviepy\.edit\b", "import moviepy.editor"),
        ]
        for pat, rep in patterns:
            code = re.sub(pat, rep, code)
        if code != original:
            logger.info("已将 'moviepy.edit' 拼写错误修正为 'moviepy.editor'")
        return code

    def _get_chinese_font_path(self) -> str:
        """获取系统中文字体路径

        Returns:
            字体文件路径，如果找不到则返回空字符串
        """
        import platform

        system = platform.system()

        # macOS字体路径
        if system == "Darwin":
            fonts = [
                "/System/Library/Fonts/PingFang.ttc",  # 苹方（推荐）
                "/System/Library/Fonts/STHeiti Medium.ttc",  # 黑体
                "/System/Library/Fonts/Supplemental/Songti.ttc",  # 宋体
            ]
        # Linux字体路径
        elif system == "Linux":
            fonts = [
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # 文泉驿微米黑
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Droid
                "/usr/share/fonts/truetype/arphic/uming.ttc",  # AR PL UMing
            ]
        # Windows字体路径
        elif system == "Windows":
            fonts = [
                "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑（推荐）
                "C:/Windows/Fonts/simhei.ttf",  # 黑体
                "C:/Windows/Fonts/simsun.ttc",  # 宋体
            ]
        else:
            logger.warning(f"不支持的操作系统: {system}")
            return ""

        # 查找第一个存在的字体
        for font in fonts:
            if Path(font).exists():
                logger.info(f"检测到中文字体: {font}")
                return font

        logger.warning(f"未找到中文字体 (系统: {system})")
        return ""

    def _inject_chinese_font_support(self, code: str) -> str:
        """自动注入中文字体支持代码

        在用户代码开头注入字体检测和配置逻辑，确保matplotlib和moviepy中文正常显示。

        Args:
            code: 原始用户代码

        Returns:
            注入字体配置后的代码
        """
        import re

        # 获取字体配置
        font_path = self._get_chinese_font_path()

        if not font_path:
            logger.warning("未找到系统中文字体，视频/图表中的中文可能显示为方块")
            return code

        # 构建注入代码（包含matplotlib和moviepy配置）
        injection = f'''
# ==== 自动注入：中文字体配置（避免乱码） ====
_CHINESE_FONT_PATH = r"{font_path}"

# matplotlib中文字体配置
try:
    import matplotlib
    import matplotlib.pyplot as plt
    # 根据字体路径判断字体名称
    if "PingFang" in _CHINESE_FONT_PATH or "pingfang" in _CHINESE_FONT_PATH:
        matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Arial Unicode MS', 'DejaVu Sans']
    elif "Heiti" in _CHINESE_FONT_PATH or "heiti" in _CHINESE_FONT_PATH:
        matplotlib.rcParams['font.sans-serif'] = ['Heiti SC', 'Arial Unicode MS', 'DejaVu Sans']
    elif "yahei" in _CHINESE_FONT_PATH.lower() or "msyh" in _CHINESE_FONT_PATH.lower():
        matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    elif "wqy" in _CHINESE_FONT_PATH.lower():
        matplotlib.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'DejaVu Sans']
    else:
        matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
except ImportError:
    pass  # matplotlib未安装，跳过

# 为moviepy的TextClip提供默认字体配置（在需要时可直接使用）
_MOVIEPY_FONT_CONFIG = {{'font': _CHINESE_FONT_PATH, 'fontsize': 40, 'color': 'white'}}
# 使用示例: TextClip("中文文本", **_MOVIEPY_FONT_CONFIG)
# ==== 注入结束 ====

'''

        # 将注入代码插入到import语句之后、第一行实际代码之前
        lines = code.split('\n')
        insert_pos = 0

        # 找到最后一个import/from语句的位置
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):  # 跳过空行和注释
                if stripped.startswith('import ') or stripped.startswith('from '):
                    insert_pos = i + 1
                elif insert_pos > 0:  # 已经遇到过import，现在遇到非import语句，停止
                    break

        # 如果没有import语句，插入到开头
        if insert_pos == 0:
            # 寻找第一个非空非注释行
            for i, line in enumerate(lines):
                if line.strip() and not line.strip().startswith('#'):
                    insert_pos = i
                    break

        lines.insert(insert_pos, injection)
        modified_code = '\n'.join(lines)

        logger.info("已自动注入中文字体配置代码")
        return modified_code

    def validate_code_safety(self, code: str) -> tuple[bool, Optional[str]]:
        """代码安全性检查（基础版）

        Args:
            code: 待检查的代码

        Returns:
            (是否安全, 不安全原因)
        """
        # 危险操作列表
        dangerous_patterns = [
            "import os",
            "import subprocess",
            "import sys",
            "__import__",
            "eval(",
            "exec(",
            "compile(",
            "open(",  # 文件操作需谨慎
            "rmdir",
            "remove",
            "unlink"
        ]

        for pattern in dangerous_patterns:
            if pattern in code:
                return False, f"代码包含潜在危险操作: {pattern}"

        return True, None
