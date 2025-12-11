"""FastAPI Web UI for Wenning

完全透明、可控的前端实现，零黑盒。
"""

from fastapi import FastAPI, Query, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import time
import pandas as pd
from typing import Optional, List
from dataclasses import asdict, is_dataclass
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from src.utils.config import get_config
from src.agent.master_agent import MasterAgent
from src.tools.registry import ToolRegistry
from src.tools.atomic.web_search import WebSearchTool
from src.tools.atomic.url_fetch import URLFetchTool
from src.tools.atomic.code_executor import CodeExecutor
from src.tools.atomic.shell_executor import ShellExecutor
from src.tools.atomic.plan import PlanTool
from src.tools.atomic.file_reader import FileReader
from src.tools.atomic.file_list import FileList
from src.tools.atomic.file_editor import FileEditor
from src.tools.atomic.media_ffmpeg import MediaFFmpeg
# 通用图像生成工具
from src.tools.atomic.image_generation import ImageGeneration
# MiniMax多模态工具
from src.tools.atomic.tts_minimax import TTSMiniMax
from src.tools.atomic.video_generation_minimax import VideoGenerationMiniMax
from src.tools.atomic.music_generation_minimax import MusicGenerationMiniMax
# 云端TTS暂不启用
# from src.tools.atomic.tts_google import TTSGoogle
# from src.tools.atomic.tts_azure import TTSAzure
from src.utils.logger import get_logger
from src.utils.conversation_manager_v2 import ConversationManagerV2
from src.tools.result import ToolResult
from src.utils.auth import AuthStore
from src.utils.workspace_store import WorkspaceStore
from src.utils.workspace_manager import WorkspaceManager

logger = get_logger(__name__)


def make_json_serializable(obj):
    """递归地将对象转换为JSON可序列化的格式"""
    if isinstance(obj, ToolResult):
        # 将ToolResult转换为dict
        result = asdict(obj)
        # 处理ErrorType枚举
        if result.get('error_type'):
            result['error_type'] = result['error_type'].value if hasattr(result['error_type'], 'value') else str(result['error_type'])
        return result
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif is_dataclass(obj):
        return asdict(obj)
    elif hasattr(obj, '__dict__'):
        return make_json_serializable(obj.__dict__)
    else:
        return obj


app = FastAPI(title="Wenning")

# 全局存储
agents = {}  # {model_name: MasterAgent}
current_conversation = {}  # {model_name: conv_id}

# 配置和对话管理器
config = get_config()
conv_manager = ConversationManagerV2()
auth_store = AuthStore(Path("data/users.json"), allow_register=config.auth_allow_register)
app.add_middleware(SessionMiddleware, secret_key=config.auth_secret)
workspace_store = WorkspaceStore(Path("data/workspace.json"))
workspace_manager = WorkspaceManager(Path(config.output_dir), conv_manager)


def require_user():
    def _dep(request: Request):
        if not config.auth_required:
            return request.session.get('user') or 'anonymous'
        user = request.session.get('user')
        if not user:
            raise HTTPException(status_code=401, detail="未登录")
        return user
    return _dep


class AuthBody(BaseModel):
    username: str
    password: str


def get_or_create_agent(model_name: str = "gpt-5") -> MasterAgent:
    """获取或创建Agent实例"""
    if model_name not in agents:
        # 初始化Tool Registry
        tool_registry = ToolRegistry()

        # 1. 核心工具（优先级最高）
        tool_registry.register_atomic_tool(WebSearchTool(config))
        tool_registry.register_atomic_tool(URLFetchTool(config))
        tool_registry.register_atomic_tool(CodeExecutor(config, conv_manager))

        # 2. 专用多模态生成工具（优先级高）
        tool_registry.register_atomic_tool(ImageGeneration(config, conv_manager))  # 通用图像生成
        tool_registry.register_atomic_tool(VideoGenerationMiniMax(config, conv_manager))
        tool_registry.register_atomic_tool(MusicGenerationMiniMax(config, conv_manager))
        tool_registry.register_atomic_tool(TTSMiniMax(config, conv_manager))

        # 3. 通用辅助工具
        tool_registry.register_atomic_tool(PlanTool(config))
        tool_registry.register_atomic_tool(MediaFFmpeg(config))
        tool_registry.register_atomic_tool(ShellExecutor(config))
        tool_registry.register_atomic_tool(FileReader(config))
        tool_registry.register_atomic_tool(FileList(config))
        tool_registry.register_atomic_tool(FileEditor(config))
        # 云端TTS暂不注册，按需开启
        # tool_registry.register_atomic_tool(TTSGoogle(config))
        # tool_registry.register_atomic_tool(TTSAzure(config))

        # 创建Agent
        agent = MasterAgent(config, tool_registry, model_name=model_name)
        agents[model_name] = agent
        logger.info(f"创建新Agent: model={model_name}, tools={len(tool_registry.list_tools())}")

    return agents[model_name]


@app.get("/chat")
async def chat(
    message: str = Query(..., description="用户消息"),
    model: str = Query("gpt-5", description="模型名称"),
    conversation_id: str = Query(..., description="对话ID"),
    client_msg_id: Optional[str] = Query(None, description="前端幂等ID"),
    user: str = Depends(require_user())
):
    """聊天接口 - Server-Sent Events流式响应"""

    def generate():
        try:
            # 获取对话历史并设置到Agent
            conv = conv_manager.get_conversation(conversation_id, username=user)
            if not conv:
                raise ValueError(f"对话不存在: {conversation_id}")

            # 模型选择策略：若前端传入与会话保存的模型不同，则更新会话绑定模型
            saved_model = conv.get("model", "gpt-5")
            effective_model = (model or saved_model) if model else saved_model
            if effective_model and effective_model != saved_model:
                try:
                    conv_manager.set_conversation_model(conversation_id, effective_model, username=user)
                    logger.info(f"会话{conversation_id}切换模型: {saved_model} -> {effective_model}")
                except Exception as _:
                    # 失败则退回原模型
                    effective_model = saved_model
            agent = get_or_create_agent(effective_model)
            logger.info(f"收到聊天请求: model={effective_model}, conv_id={conversation_id}, message={message[:50]}...")

            conversation_history = conv.get("messages", [])

            # 将对话历史设置到Agent内部状态（使用副本，避免Agent修改影响原数据）
            agent.conversation_history = list(conversation_history)
            agent.current_conversation_id = conversation_id
            logger.info(f"设置对话历史: {len(conversation_history)}条消息")

            # 添加用户消息（带幂等ID）
            conv_manager.add_message(conversation_id, "user", message, username=user, client_msg_id=client_msg_id, status="completed")

            # 定义消息保存回调函数
            def save_message_callback(msg: dict):
                """每当Agent产生新消息时调用此回调保存到数据库"""
                role = msg.get("role")
                content = msg.get("content", "")

                if role == "assistant":
                    tool_calls = msg.get("tool_calls")
                    conv_manager.add_message(
                        conversation_id,
                        role="assistant",
                        content=content,
                        tool_calls=tool_calls,
                        username=user,
                        status="completed"
                    )
                elif role == "tool":
                    tool_call_id = msg.get("tool_call_id")
                    name = msg.get("name")
                    conv_manager.add_message(
                        conversation_id,
                        role="tool",
                        content=content,
                        tool_call_id=tool_call_id,
                        name=name,
                        username=user,
                        status="completed"
                    )

            # 设置回调函数到Agent
            agent.message_callback = save_message_callback

            # 流式处理
            assistant_response = None
            all_generated_files = []  # 收集所有生成的文件
            # 执行前快照与开始时间，用于兜底补齐覆盖写或遗漏文件
            start_ts = time.time()
            # 使用带时间戳的输出目录名
            output_dir_name = conv_manager.get_output_dir_name(conversation_id)
            conv_dir = Path("outputs") / output_dir_name
            try:
                pre_files = {p.name for p in conv_dir.iterdir() if p.is_file()}
            except Exception:
                pre_files = set()

            for update in agent.process_with_progress(message):
                # 收集生成的文件
                if update.get("type") == "files_generated":
                    new_files = update.get("files", []) or []
                    all_generated_files.extend(new_files)

                # 转发给前端(处理ToolResult等不可序列化对象)
                serializable_update = make_json_serializable(update)
                yield f"data: {json.dumps(serializable_update, ensure_ascii=False)}\n\n"

            # 兜底：更新最后一条assistant消息的generated_files
            # 扫描执行期间新增/覆盖的文件
            try:
                unique_files = list(dict.fromkeys(all_generated_files)) if all_generated_files else []
            except Exception:
                unique_files = all_generated_files or []

            try:
                post_paths = [p for p in conv_dir.iterdir() if p.is_file()]
                post_files = {p.name for p in post_paths}
            except Exception:
                post_paths = []
                post_files = set()
            new_set = post_files - pre_files
            try:
                changed = [p.name for p in post_paths if p.stat().st_mtime >= (start_ts - 0.2)]
            except Exception:
                changed = []
            merged = list(dict.fromkeys((unique_files or []) + sorted(list(new_set)) + changed))

            # 更新最后一条assistant消息的generated_files
            if merged:
                try:
                    conv = conv_manager.get_conversation(conversation_id, username=user)
                    if conv and conv.get("messages"):
                        # 找到最后一条assistant消息
                        for i in range(len(conv["messages"]) - 1, -1, -1):
                            if conv["messages"][i].get("role") == "assistant":
                                last_assistant_id = conv["messages"][i].get("id")
                                if last_assistant_id:
                                    conv_manager.update_message(
                                        conversation_id,
                                        message_id=last_assistant_id,
                                        generated_files_delta=merged,
                                        username=user
                                    )
                                    logger.info(f"已更新最后assistant消息的generated_files: {merged}")
                                break
                except Exception as e:
                    logger.warning(f"更新generated_files失败: {e}")


            # 发送结束标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"聊天处理异常: {str(e)}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")

            # 发送错误信息
            error_update = {
                "type": "final",
                "result": {
                    "status": "failed",
                    "error": str(e)
                }
            }
            yield f"data: {json.dumps(error_update, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/outputs/list/{conversation_id}")
async def list_outputs_alt(conversation_id: str, user: str = Depends(require_user())):
    """列出会话目录下的文件（备用路由）"""
    return await list_outputs(conversation_id, user)


@app.get("/outputs/{conversation_id}/{filename}")
async def get_file_scoped(conversation_id: str, filename: str, user: str = Depends(require_user())):
    """对话隔离的文件下载接口（严格模式：仅会话目录，不回退根目录）"""
    # 权限校验：仅允许访问自己的会话
    conv = conv_manager.get_conversation(conversation_id, username=user)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "会话不存在或无权限"})
    # 使用带时间戳的输出目录名
    output_dir_name = conv_manager.get_output_dir_name(conversation_id)
    file_path = Path("outputs") / output_dir_name / filename

    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": f"文件不存在: {filename}"})

    suffix = file_path.suffix.lower()
    if suffix == ".png":
        media_type = "image/png"
    elif suffix in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif suffix == ".svg":
        media_type = "image/svg+xml"
    elif suffix == ".gif":
        media_type = "image/gif"
    elif suffix == ".webp":
        media_type = "image/webp"
    elif suffix == ".avif":
        media_type = "image/avif"
    elif suffix in (".mp3", ".mpeg"):
        media_type = "audio/mpeg"
    elif suffix == ".wav":
        media_type = "audio/wav"
    elif suffix == ".m4a":
        media_type = "audio/mp4"
    elif suffix == ".aac":
        media_type = "audio/aac"
    elif suffix == ".ogg":
        media_type = "audio/ogg"
    elif suffix == ".flac":
        media_type = "audio/flac"
    elif suffix == ".mp4":
        media_type = "video/mp4"
    elif suffix == ".webm":
        media_type = "video/webm"
    elif suffix == ".mov":
        media_type = "video/quicktime"
    elif suffix == ".xlsx":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif suffix == ".pdf":
        media_type = "application/pdf"
    elif suffix == ".csv":
        media_type = "text/csv; charset=utf-8"
    elif suffix == ".jsonl":
        media_type = "application/jsonl; charset=utf-8"
    elif suffix == ".json":
        media_type = "application/json; charset=utf-8"
    elif suffix == ".txt":
        media_type = "text/plain; charset=utf-8"
    elif suffix in (".yaml", ".yml"):
        media_type = "text/yaml; charset=utf-8"
    elif suffix == ".xml":
        media_type = "application/xml; charset=utf-8"
    elif suffix == ".md":
        media_type = "text/markdown; charset=utf-8"
    elif suffix == ".html":
        media_type = "text/html; charset=utf-8"
    elif suffix == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix == ".pptx":
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        media_type = "application/octet-stream"

    headers = {"X-File-Scope": "conversation"}
    # 为可内联预览的类型去掉 filename, 避免 Content-Disposition: attachment 导致浏览器不内联渲染（SVG 尤其如此）
    inline_types = {
        ".html", ".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".xml",
        ".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".avif",
        ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",
        ".mp4", ".webm", ".mov",
        ".pdf"
    }
    if suffix in inline_types:
        return FileResponse(path=str(file_path), media_type=media_type, headers=headers)
    return FileResponse(path=str(file_path), filename=filename, media_type=media_type, headers=headers)


@app.head("/outputs/{conversation_id}/{filename}")
async def head_file_scoped(conversation_id: str, filename: str, user: str = Depends(require_user())):
    conv = conv_manager.get_conversation(conversation_id, username=user)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "会话不存在或无权限"})
    # 使用带时间戳的输出目录名
    output_dir_name = conv_manager.get_output_dir_name(conversation_id)
    path = Path("outputs") / output_dir_name / filename

    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    suffix = path.suffix.lower()
    if suffix == ".png":
        media_type = "image/png"
    elif suffix in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif suffix in (".mp3", ".mpeg"):
        media_type = "audio/mpeg"
    elif suffix == ".wav":
        media_type = "audio/wav"
    elif suffix == ".m4a":
        media_type = "audio/mp4"
    elif suffix == ".aac":
        media_type = "audio/aac"
    elif suffix == ".ogg":
        media_type = "audio/ogg"
    elif suffix == ".flac":
        media_type = "audio/flac"
    elif suffix == ".mp4":
        media_type = "video/mp4"
    elif suffix == ".webm":
        media_type = "video/webm"
    elif suffix == ".mov":
        media_type = "video/quicktime"
    elif suffix == ".xlsx":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif suffix == ".pdf":
        media_type = "application/pdf"
    elif suffix == ".csv":
        media_type = "text/csv; charset=utf-8"
    elif suffix == ".jsonl":
        media_type = "application/jsonl; charset=utf-8"
    elif suffix == ".json":
        media_type = "application/json; charset=utf-8"
    elif suffix == ".txt":
        media_type = "text/plain; charset=utf-8"
    elif suffix == ".md":
        media_type = "text/markdown; charset=utf-8"
    elif suffix == ".html":
        media_type = "text/html; charset=utf-8"
    elif suffix == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix == ".pptx":
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        media_type = "application/octet-stream"

    return JSONResponse(status_code=200, content=None, headers={"Content-Type": media_type, "X-File-Scope": "conversation"})


@app.post("/upload/{conversation_id}")
async def upload_files(
    conversation_id: str,
    files: List[UploadFile] = File(...),
    add_to_workspace: bool = Form(False),
    user: str = Depends(require_user()),
):
    """上传文件到会话隔离目录(outputs/{conversation_id}/)。

    - 仅保存文件名，不允许路径穿越
    - 同名文件自动追加 _1/_2 后缀避免覆盖
    - 可选写入Workspace列表
    """
    # 权限校验
    conv = conv_manager.get_conversation(conversation_id, username=user)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "会话不存在或无权限"})

    # 使用带时间戳的输出目录名
    output_dir_name = conv_manager.get_output_dir_name(conversation_id)
    conv_dir = Path("outputs") / output_dir_name
    conv_dir.mkdir(parents=True, exist_ok=True)

    saved: List[str] = []
    for uf in (files or []):
        try:
            raw_name = (uf.filename or "upload.bin").strip()
            # 仅保留文件名，防止路径穿越
            safe_name = Path(raw_name).name
            if not safe_name or safe_name in (".", ".."):
                import time as _t
                safe_name = f"upload_{int(_t.time()*1000)}.bin"

            target = conv_dir / safe_name
            if target.exists():
                # 同名去重: name -> name_1.ext -> name_2.ext
                stem, suf = target.stem, target.suffix
                i = 1
                while target.exists():
                    target = conv_dir / f"{stem}_{i}{suf}"
                    i += 1

            # 流式写入，避免一次性读大文件
            with target.open("wb") as w:
                while True:
                    chunk = await uf.read(1024 * 1024)
                    if not chunk:
                        break
                    w.write(chunk)
            await uf.close()

            saved.append(target.name)

            # 可选加入Workspace列表
            try:
                if add_to_workspace:
                    workspace_store.add_file(user, conversation_id, target.name)
            except Exception as e:
                logger.warning(f"workspace add failed: {e}")

        except Exception as e:
            logger.error(f"文件保存失败: {getattr(uf, 'filename', 'unknown')} error={e}")
            # 不中断其余文件
            continue

    return JSONResponse(content={"success": True, "files": saved})


@app.delete("/upload/{conversation_id}/{filename}")
async def delete_file(
    conversation_id: str,
    filename: str,
    user: str = Depends(require_user()),
):
    """删除会话目录中的文件，并从Workspace移除该引用。

    安全措施：
    - 仅允许删除 outputs/{conversation_id} 下的文件
    - 拒绝路径穿越（只接受纯文件名）
    """
    conv = conv_manager.get_conversation(conversation_id, username=user)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "会话不存在或无权限"})

    # 仅文件名
    p = Path(filename)
    if p.is_absolute() or p.name != filename or filename in ("", ".", ".."):
        return JSONResponse(status_code=400, content={"error": "非法文件名"})

    # 使用带时间戳的输出目录名
    output_dir_name = conv_manager.get_output_dir_name(conversation_id)
    path = Path("outputs") / output_dir_name / filename
    if not path.exists() or not path.is_file():
        return JSONResponse(status_code=404, content={"error": "文件不存在"})

    try:
        path.unlink()
    except Exception as e:
        logger.error(f"删除文件失败: {path} error={e}")
        return JSONResponse(status_code=500, content={"error": "删除失败"})

    # 同步移除Workspace引用（忽略错误）
    try:
        workspace_store.remove_file(user, conversation_id, filename)
    except Exception as e:
        logger.warning(f"workspace remove failed: {e}")

    return JSONResponse(content={"success": True})


# ===== Range streaming (audio/video friendly) =====
def _guess_media_type_by_suffix(suffix: str) -> str:
    s = suffix.lower()
    if s == ".png":
        return "image/png"
    if s in (".jpg", ".jpeg"):
        return "image/jpeg"
    if s == ".svg":
        return "image/svg+xml"
    if s == ".gif":
        return "image/gif"
    if s == ".webp":
        return "image/webp"
    if s == ".avif":
        return "image/avif"
    if s in (".mp3", ".mpeg"):
        return "audio/mpeg"
    if s == ".wav":
        return "audio/wav"
    if s == ".m4a":
        return "audio/mp4"
    if s == ".aac":
        return "audio/aac"
    if s == ".ogg":
        return "audio/ogg"
    if s == ".flac":
        return "audio/flac"
    if s == ".mp4":
        return "video/mp4"
    if s == ".webm":
        return "video/webm"
    if s == ".mov":
        return "video/quicktime"
    if s == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if s == ".html":
        return "text/html; charset=utf-8"
    return "application/octet-stream"


def _iter_file_range(path: Path, start: int, end: int, chunk_size: int = 1024 * 1024):
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            read_len = min(chunk_size, remaining)
            data = f.read(read_len)
            if not data:
                break
            yield data
            remaining -= len(data)


@app.get("/stream/{conversation_id}/{filename}")
async def stream_scoped(conversation_id: str, filename: str, request: Request, user: str = Depends(require_user())):
    # 权限校验
    conv = conv_manager.get_conversation(conversation_id, username=user)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "会话不存在或无权限"})

    # 使用带时间戳的输出目录名
    output_dir_name = conv_manager.get_output_dir_name(conversation_id)
    file_path = Path("outputs") / output_dir_name / filename
    if not file_path.exists() or not file_path.is_file():
        return JSONResponse(status_code=404, content={"error": "文件不存在"})

    file_size = file_path.stat().st_size
    range_header = request.headers.get('range')
    media_type = _guess_media_type_by_suffix(file_path.suffix)
    headers = {"Accept-Ranges": "bytes"}

    if range_header:
        # e.g. "bytes=start-end"
        try:
            units, _, rng = range_header.partition('=')
            if units.strip().lower() != 'bytes':
                raise ValueError
            start_str, _, end_str = rng.partition('-')
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            start = max(0, start)
            end = min(file_size - 1, end)
            if start > end:
                start, end = 0, file_size - 1
        except Exception:
            start, end = 0, file_size - 1

        content_length = end - start + 1
        headers.update({
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length)
        })
        return StreamingResponse(_iter_file_range(file_path, start, end), status_code=206, media_type=media_type, headers=headers)

    # No range → full content
    headers["Content-Length"] = str(file_size)
    return StreamingResponse(_iter_file_range(file_path, 0, file_size - 1), media_type=media_type, headers=headers)


@app.get("/stream/{filename}")
async def stream_root(filename: str, request: Request):
    file_path = Path("outputs") / filename
    if not file_path.exists() or not file_path.is_file():
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    file_size = file_path.stat().st_size
    range_header = request.headers.get('range')
    media_type = _guess_media_type_by_suffix(file_path.suffix)
    headers = {"Accept-Ranges": "bytes"}
    if range_header:
        try:
            units, _, rng = range_header.partition('=')
            if units.strip().lower() != 'bytes':
                raise ValueError
            start_str, _, end_str = rng.partition('-')
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            start = max(0, start)
            end = min(file_size - 1, end)
            if start > end:
                start, end = 0, file_size - 1
        except Exception:
            start, end = 0, file_size - 1

        content_length = end - start + 1
        headers.update({
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length)
        })
        return StreamingResponse(_iter_file_range(file_path, start, end), status_code=206, media_type=media_type, headers=headers)

    headers["Content-Length"] = str(file_size)
    return StreamingResponse(_iter_file_range(file_path, 0, file_size - 1), media_type=media_type, headers=headers)


@app.get("/outputs/{conversation_id}/list")
async def list_outputs(conversation_id: str, user: str = Depends(require_user())):
    """列出会话目录下的文件名（按修改时间倒序），仅返回文件名。"""
    conv = conv_manager.get_conversation(conversation_id, username=user)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "会话不存在或无权限"})
    # 使用带时间戳的输出目录名
    output_dir_name = conv_manager.get_output_dir_name(conversation_id)
    conv_dir = Path("outputs") / output_dir_name
    if not conv_dir.exists():
        return JSONResponse(content={"files": []})
    try:
        items = []
        for p in conv_dir.iterdir():
            if p.is_file():
                try:
                    m = p.stat().st_mtime
                except Exception:
                    m = 0
                items.append((m, p.name))
        items.sort(reverse=True)
        return JSONResponse(content={"files": [n for _, n in items]})
    except Exception as e:
        logger.error(f"列出会话文件失败: {e}")
        return JSONResponse(status_code=500, content={"error": "list failed"})


@app.get("/preview/excel/{filename}")
async def preview_excel(
    filename: str,
    max_rows: int = Query(20, description="预览最大行数")
):
    """Excel文件预览接口（根outputs目录 - 兼容旧链接）"""
    file_path = Path("outputs") / filename

    if not file_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"文件不存在: {filename}"}
        )

    try:
        df = pd.read_excel(file_path, nrows=max_rows)
        html = df.to_html(index=False, classes='excel-table', border=0, escape=False)
        total_rows = len(pd.read_excel(file_path))
        return JSONResponse(content={
            "html": html,
            "preview_rows": len(df),
            "total_rows": total_rows,
            "truncated": total_rows > max_rows
        })
    except Exception as e:
        logger.error(f"Excel预览失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"预览失败: {str(e)}"})


@app.get("/preview/excel/{conversation_id}/{filename}")
async def preview_excel_scoped(
    conversation_id: str,
    filename: str,
    max_rows: int = Query(20, description="预览最大行数"),
    user: str = Depends(require_user())
):
    """Excel文件预览接口（会话隔离目录）"""
    conv = conv_manager.get_conversation(conversation_id, username=user)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "会话不存在或无权限"})
    # 使用带时间戳的输出目录名
    output_dir_name = conv_manager.get_output_dir_name(conversation_id)
    file_path = Path("outputs") / output_dir_name / filename

    if not file_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"文件不存在: {filename}"}
        )

    try:
        df = pd.read_excel(file_path, nrows=max_rows)
        html = df.to_html(index=False, classes='excel-table', border=0, escape=False)
        total_rows = len(pd.read_excel(file_path))
        return JSONResponse(content={
            "html": html,
            "preview_rows": len(df),
            "total_rows": total_rows,
            "truncated": total_rows > max_rows
        })
    except Exception as e:
        logger.error(f"[scoped] Excel预览失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"预览失败: {str(e)}"})


@app.get("/models")
async def list_models():
    """获取可用模型列表"""
    models = [
        {"name": "gpt-5", "display_name": "OpenAI GPT-5", "default": True},
        {"name": "ernie-5.0-thinking-preview", "display_name": "百度 EB5 思考模型", "default": False},
        {"name": "glm-4.5", "display_name": "智谱GLM-4.5", "default": False},
        {"name": "doubao-seed-1-6-thinking-250615", "display_name": "豆包Thinking模型", "default": False},
        {"name": "gemini-2.5-pro", "display_name": "Google Gemini 2.5 Pro", "default": False},
        {"name": "gemini-3-pro-preview", "display_name": "Google Gemini 3 Pro (Preview)", "default": False},
        {"name": "claude-sonnet-4-5-20250929", "display_name": "Anthropic Claude Sonnet 4.5 (2025-09-29)", "default": False},
    ]
    return JSONResponse(content={"models": models})


@app.get("/conversations")
async def list_conversations(model: str = Query(None, description="模型名称筛选"), user: str = Depends(require_user())):
    """列出所有对话"""
    try:
        convs = conv_manager.list_conversations(model, username=user)
        return JSONResponse(content={"conversations": convs})
    except Exception as e:
        logger.error(f"列出对话失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


class CreateConversationBody(BaseModel):
    model: str = "gpt-5"

@app.post("/conversations")
async def create_conversation(body: CreateConversationBody = None, user: str = Depends(require_user())):
    """创建新对话"""
    try:
        # 兼容两种方式：如果有body则使用body.model，否则使用默认值
        model = body.model if body else "gpt-5"
        conv_id = conv_manager.create_conversation(model, username=user)
        logger.info(f"创建新对话: conv_id={conv_id}, model={model}, user={user}")
        return JSONResponse(content={"conversation_id": conv_id})
    except Exception as e:
        logger.error(f"创建对话失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: str = Depends(require_user())):
    """获取对话详情"""
    try:
        conv = conv_manager.get_conversation(conversation_id, username=user)
        if not conv:
            return JSONResponse(status_code=404, content={"error": "对话不存在"})

        # 添加output_dir字段到返回数据（前端需要用它构造文件路径）
        conv["output_dir"] = conv_manager.get_output_dir_name(conversation_id)

        # 计算当前对话的context使用情况
        if conv.get("messages") and len(conv["messages"]) > 0:
            try:
                model_name = conv.get("model", "gpt-5")
                agent = get_or_create_agent(model_name)
                context_stats = agent.context_manager.calculate_usage(conv["messages"])
                conv["context_stats"] = context_stats
            except Exception as e:
                logger.warning(f"计算context统计失败: {str(e)}")
                # 即使计算失败也继续返回对话

        return JSONResponse(content=conv)
    except Exception as e:
        logger.error(f"获取对话失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: str = Depends(require_user())):
    """删除对话"""
    try:
        conv_manager.delete_conversation(conversation_id, username=user)
        logger.info(f"删除对话: conv_id={conversation_id}")
        return JSONResponse(content={"success": True})
    except Exception as e:
        logger.error(f"删除对话失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    """首页"""
    index_file = Path("static/index.html")
    if not index_file.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "前端文件未找到，请先创建 static/index.html"}
        )
    return FileResponse("static/index.html")


# ========== Auth APIs ==========

@app.post("/auth/register")
async def auth_register(body: AuthBody):
    if not config.auth_allow_register:
        return JSONResponse(status_code=403, content={"error": "注册被禁用"})
    try:
        auth_store.register(body.username, body.password)
        return JSONResponse(content={"success": True})
    except ValueError as e:
        # 业务校验错误（如用户已存在）
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.error(f"注册失败: {e}")
        return JSONResponse(status_code=400, content={"error": "注册失败"})


@app.post("/auth/login")
async def auth_login(body: AuthBody, request: Request):
    if not auth_store.verify(body.username, body.password):
        return JSONResponse(status_code=401, content={"error": "用户名或密码错误"})
    request.session['user'] = body.username
    return JSONResponse(content={"success": True, "user": body.username})


@app.post("/auth/logout")
async def auth_logout(request: Request):
    request.session.pop('user', None)
    return JSONResponse(content={"success": True})


@app.get("/auth/me")
async def auth_me(request: Request):
    user = request.session.get('user')
    if config.auth_required and not user:
        return JSONResponse(status_code=401, content={"error": "未登录"})
    return JSONResponse(content={
        "user": user or None,
        "logged_in": bool(user),
        "auth_required": config.auth_required,
        "allow_register": config.auth_allow_register,
    })


@app.get("/auth/config")
async def auth_config():
    """公开的认证配置，便于前端在未登录时做UI调整"""
    return JSONResponse(content={
        "auth_required": config.auth_required,
        "allow_register": config.auth_allow_register,
    })


# ========== Workspace APIs (per-user) ==========

class WorkspaceBody(BaseModel):
    filename: str


@app.get("/workspace/{conversation_id}/files")
async def workspace_list(conversation_id: str, user: str = Depends(require_user())):
    try:
        files = workspace_store.list_files(user, conversation_id)
        return JSONResponse(content={"files": files})
    except Exception as e:
        logger.error(f"workspace_list失败: {e}")
        return JSONResponse(status_code=500, content={"error": "workspace list failed"})


@app.post("/workspace/{conversation_id}/files")
async def workspace_add(conversation_id: str, body: WorkspaceBody, user: str = Depends(require_user())):
    try:
        # 简单校验：文件需存在于该会话目录
        # 使用带时间戳的输出目录名
        output_dir_name = conv_manager.get_output_dir_name(conversation_id)
        f = Path("outputs") / output_dir_name / body.filename
        if not f.exists():
            return JSONResponse(status_code=404, content={"error": "文件不存在于该会话目录"})
        workspace_store.add_file(user, conversation_id, body.filename)
        return JSONResponse(content={"success": True})
    except Exception as e:
        logger.error(f"workspace_add失败: {e}")
        return JSONResponse(status_code=500, content={"error": "workspace add failed"})


@app.delete("/workspace/{conversation_id}/files")
async def workspace_remove(conversation_id: str, body: WorkspaceBody, user: str = Depends(require_user())):
    try:
        workspace_store.remove_file(user, conversation_id, body.filename)
        return JSONResponse(content={"success": True})
    except Exception as e:
        logger.error(f"workspace_remove失败: {e}")
        return JSONResponse(status_code=500, content={"error": "workspace remove failed"})


@app.get("/workspace/{conversation_id}/categorized")
async def workspace_categorized(conversation_id: str, user: str = Depends(require_user())):
    """获取会话目录下的分类文件列表及统计信息

    Returns:
        {
            "categories": {
                "图片": [{name, path, size_str, mtime_str, ...}, ...],
                "视频": [...],
                ...
            },
            "statistics": {
                "total_files": 10,
                "total_size": "25.6 MB",
                "by_category": {"图片": 5, "视频": 2, ...}
            }
        }
    """
    try:
        # 权限校验
        conv = conv_manager.get_conversation(conversation_id, username=user)
        if not conv:
            return JSONResponse(status_code=404, content={"error": "会话不存在或无权限"})

        # 获取分类文件列表
        categorized = workspace_manager.get_conversation_files(conversation_id)

        # 获取统计信息
        statistics = workspace_manager.get_statistics(conversation_id)

        return JSONResponse(content={
            "categories": categorized,
            "statistics": statistics
        })
    except Exception as e:
        logger.error(f"workspace_categorized失败: {e}")
        return JSONResponse(status_code=500, content={"error": "获取分类文件失败"})


@app.get("/workspace/user/all")
async def workspace_user_all(user: str = Depends(require_user())):
    """获取用户所有会话的分类文件列表及统计信息（仅包含用户明确保存的文件）

    Returns:
        {
            "categories": {
                "图片": [{name, conversation_id, size_str, mtime_str, ...}, ...],
                "视频": [...],
                ...
            },
            "statistics": {
                "total_files": 50,
                "total_size": "125.6 MB",
                "by_category": {"图片": 25, "视频": 10, ...},
                "conversations": 5
            }
        }
    """
    try:
        # 获取用户所有会话
        convs = conv_manager.list_conversations(model=None, username=user)
        conversation_ids = [c["id"] for c in convs]

        if not conversation_ids:
            return JSONResponse(content={
                "categories": {cat: [] for cat in workspace_manager.FILE_CATEGORIES.keys()},
                "statistics": {
                    "total_files": 0,
                    "total_size": "0 B",
                    "by_category": {},
                    "conversations": 0
                }
            })

        # 获取用户所有已保存的文件（需要传递workspace_store）
        categorized = workspace_manager.get_user_files(user, conversation_ids, workspace_store)

        # 获取统计信息
        statistics = workspace_manager.get_user_statistics(user, conversation_ids, workspace_store)

        return JSONResponse(content={
            "categories": categorized,
            "statistics": statistics
        })
    except Exception as e:
        logger.error(f"workspace_user_all失败: {e}")
        return JSONResponse(status_code=500, content={"error": "获取用户文件失败"})


if __name__ == "__main__":
    import uvicorn
    # 配置uvicorn以支持长时间运行的请求（如MiniMax生成任务）
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=80,
        timeout_keep_alive=650,  # keepalive超时: 10分50秒（略大于最长任务时间）
        limit_concurrency=100     # 并发限制
    )
