"""对话管理模块 V2 - 分片存储版本

按用户和日期分片存储对话,解决单文件过大问题

目录结构:
data/
  conversations/
    {username}/
      2024-12/
        {conv_id}.json
    anonymous/
      2024-12/
        {conv_id}.json
  index.json  # 轻量级索引(仅元数据,不含messages)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import re
import uuid


class ConversationManagerV2:
    """对话管理器 V2 - 分片存储版本"""

    def __init__(self, storage_dir: str = "data/conversations"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 索引文件路径
        self.index_path = self.storage_dir.parent / "index.json"

        # 加载索引(仅元数据,不含messages)
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        """加载对话索引(仅元数据)"""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_index(self):
        """保存对话索引"""
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def _get_conv_path(self, conv_id: str, username: Optional[str] = None, created_at: Optional[str] = None) -> Path:
        """获取对话文件路径

        Args:
            conv_id: 对话ID
            username: 用户名(可选,从index获取)
            created_at: 创建时间(可选,从index获取)

        Returns:
            对话文件路径
        """
        # 从index获取元数据
        if conv_id in self.index:
            username = self.index[conv_id].get("user") or "anonymous"
            created_at = self.index[conv_id].get("created_at")
        else:
            username = username or "anonymous"
            created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 提取年月: 2024-12-02 -> 2024-12
        year_month = created_at[:7] if created_at else datetime.now().strftime("%Y-%m")

        # 提取时间戳前缀: 2024-12-02 15:30:45 -> 20241202_153045
        timestamp_prefix = created_at.replace("-", "").replace(":", "").replace(" ", "_")[:15] if created_at else datetime.now().strftime("%Y%m%d_%H%M%S")

        # 构建路径: data/conversations/{username}/{year_month}/{timestamp}_{conv_id}.json
        conv_dir = self.storage_dir / username / year_month
        conv_dir.mkdir(parents=True, exist_ok=True)

        return conv_dir / f"{timestamp_prefix}_{conv_id}.json"

    def _load_conversation_file(self, conv_path: Path) -> Optional[Dict]:
        """从文件加载对话内容"""
        if not conv_path.exists():
            return None
        try:
            with open(conv_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _save_conversation_file(self, conv_path: Path, conv: Dict):
        """保存对话到文件"""
        conv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(conv_path, 'w', encoding='utf-8') as f:
            json.dump(conv, f, ensure_ascii=False, indent=2)

    def create_conversation(self, model: str = "gpt-5", username: str | None = None) -> str:
        """创建新对话

        Args:
            model: 模型名称
            username: 用户名

        Returns:
            对话ID
        """
        conv_id = str(uuid.uuid4())[:8]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = username or "anonymous"

        # 创建对话数据
        conv = {
            "id": conv_id,
            "title": "新对话",
            "model": model,
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "user": username,
            "pending_images": []  # 待附加的图片列表
        }

        # 保存对话文件
        conv_path = self._get_conv_path(conv_id, username, now)
        self._save_conversation_file(conv_path, conv)

        # 生成输出目录名: {timestamp}_{conv_id}
        timestamp_prefix = now.replace("-", "").replace(":", "").replace(" ", "_")[:15]
        output_dir_name = f"{timestamp_prefix}_{conv_id}"

        # 更新索引(仅元数据)
        self.index[conv_id] = {
            "id": conv_id,
            "title": conv["title"],
            "model": model,
            "created_at": now,
            "updated_at": now,
            "user": username,
            "output_dir": output_dir_name  # 存储输出目录名
        }
        self._save_index()

        # 创建会话级输出目录: outputs/{timestamp}_{conv_id}
        try:
            out_root = Path("outputs")
            out_root.mkdir(exist_ok=True)
            (out_root / output_dir_name).mkdir(exist_ok=True)
        except Exception:
            pass

        return conv_id

    def get_output_dir_name(self, conv_id: str) -> str:
        """获取对话的输出目录名称

        Args:
            conv_id: 对话ID

        Returns:
            输出目录名称: {timestamp}_{conv_id}
        """
        if conv_id in self.index:
            return self.index[conv_id].get("output_dir", conv_id)
        return conv_id

    def get_conversation(self, conv_id: str, username: str | None = None) -> Optional[Dict]:
        """获取对话详情(懒加载)

        Args:
            conv_id: 对话ID
            username: 用户名(可选,用于权限校验)

        Returns:
            对话数据(包含messages)
        """
        # 检查索引
        if conv_id not in self.index:
            return None

        # 权限校验
        conv_user = self.index[conv_id].get("user")
        if username is not None and conv_user not in (None, username):
            return None

        # 懒加载对话文件
        conv_path = self._get_conv_path(conv_id)
        conv = self._load_conversation_file(conv_path)

        return conv

    def list_conversations(self, model: Optional[str] = None, username: str | None = None) -> List[Dict]:
        """列出所有对话(基于索引,快速)

        Args:
            model: 可选,按模型筛选
            username: 可选,按用户筛选

        Returns:
            对话列表(仅元数据,不含messages,按更新时间倒序)
        """
        convs = list(self.index.values())

        # 用户过滤
        if username is not None:
            convs = [
                c for c in convs
                if c.get("user") in (None, username) and (
                    c.get("user") == username or
                    username == 'anonymous' and c.get("user") is None
                )
            ]

        # 模型过滤
        if model:
            convs = [c for c in convs if c.get("model") == model]

        # 按更新时间倒序
        convs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        return convs

    def update_conversation(
        self,
        conv_id: str,
        messages: List[Dict],
        title: Optional[str] = None,
        username: str | None = None
    ):
        """更新对话内容

        Args:
            conv_id: 对话ID
            messages: 消息列表
            title: 可选,对话标题
            username: 可选,用户名(权限校验)
        """
        # 检查权限
        if conv_id not in self.index:
            return
        if username is not None and self.index[conv_id].get("user") not in (None, username):
            return

        # 加载对话
        conv_path = self._get_conv_path(conv_id)
        conv = self._load_conversation_file(conv_path)
        if not conv:
            return

        # 更新内容
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conv["messages"] = messages
        conv["updated_at"] = now

        # 自动生成标题(基于第一条用户消息)
        if not title and messages:
            first_user_msg = next((m for m in messages if m.get("role") == "user"), None)
            if first_user_msg:
                title = first_user_msg.get("content", "")[:20]
                if len(first_user_msg.get("content", "")) > 20:
                    title += "..."

        if title:
            conv["title"] = title

        # 保存对话文件
        self._save_conversation_file(conv_path, conv)

        # 更新索引
        self.index[conv_id]["updated_at"] = now
        if title:
            self.index[conv_id]["title"] = title
        self._save_index()

    def delete_conversation(self, conv_id: str, username: str | None = None):
        """删除对话

        Args:
            conv_id: 对话ID
            username: 可选,用户名(权限校验)
        """
        if conv_id not in self.index:
            return

        # 权限校验
        if username is not None and self.index[conv_id].get("user") not in (None, username):
            return

        # 删除对话文件
        conv_path = self._get_conv_path(conv_id)
        if conv_path.exists():
            conv_path.unlink()

        # 从索引移除
        del self.index[conv_id]
        self._save_index()

    def update_model(self, conv_id: str, model: str, username: Optional[str] = None):
        """更新对话使用的模型

        Args:
            conv_id: 对话ID
            model: 新模型名称
            username: 可选,用户名(权限校验)
        """
        # 检查权限
        if conv_id not in self.index:
            return False
        if username is not None and self.index[conv_id].get("user") not in (None, username):
            return False

        # 加载对话
        conv_path = self._get_conv_path(conv_id)
        conv = self._load_conversation_file(conv_path)
        if not conv:
            return False

        # 更新模型
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conv["model"] = model
        conv["updated_at"] = now

        # 保存对话文件
        self._save_conversation_file(conv_path, conv)

        # 更新索引
        self.index[conv_id]["model"] = model
        self.index[conv_id]["updated_at"] = now
        self._save_index()

        return True

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        generated_files: Optional[List[str]] = None,
        username: str | None = None,
        client_msg_id: Optional[str] = None,
        status: str = "completed",
        tool_calls: Optional[List[Dict]] = None,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> str:
        """向对话添加消息(幂等 + 近邻合并),返回消息ID

        Args:
            conv_id: 对话ID
            role: 消息角色
            content: 消息内容
            generated_files: 生成的文件列表
            username: 用户名(权限校验)
            client_msg_id: 客户端消息ID(幂等)
            status: 消息状态
            tool_calls: assistant消息的tool_calls列表
            tool_call_id: tool消息对应的tool_call_id
            name: tool消息的工具名称

        Returns:
            消息ID
        """
        # 检查权限
        if conv_id not in self.index:
            return ""
        if username is not None and self.index[conv_id].get("user") not in (None, username):
            return ""

        # 加载对话
        conv_path = self._get_conv_path(conv_id)
        conv = self._load_conversation_file(conv_path)
        if not conv:
            return ""

        # 构建新消息
        new_msg = {
            "role": role,
            "content": content,
        }
        if role == "assistant" and generated_files:
            new_msg["generated_files"] = generated_files
        if role == "assistant" and tool_calls:
            new_msg["tool_calls"] = tool_calls
        if role == "tool" and tool_call_id:
            new_msg["tool_call_id"] = tool_call_id
        if role == "tool" and name:
            new_msg["name"] = name
        if client_msg_id:
            new_msg["client_msg_id"] = client_msg_id
        if status:
            new_msg["status"] = status

        msgs = conv["messages"]

        def _norm(txt: str) -> str:
            if txt is None:
                return ""
            s = str(txt).replace("\r\n", "\n").replace("\u00a0", " ")
            s = re.sub(r"[ \t]+", " ", s).strip()
            return s

        # 幂等: client_msg_id 匹配则直接合并并返回
        if client_msg_id:
            for i in range(len(msgs) - 1, -1, -1):
                m = msgs[i]
                if m.get("role") == role and m.get("client_msg_id") == client_msg_id:
                    if generated_files:
                        cur = m.get("generated_files") or []
                        m["generated_files"] = list({*cur, *generated_files})
                    m["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self._save_conversation_file(conv_path, conv)
                    return m.get("id", "")

        # 近邻合并: 相邻规范化文本相同
        if msgs:
            last = msgs[-1]
            if last.get("role") == role and _norm(last.get("content")) == _norm(content):
                last_files = last.get("generated_files") or []
                new_files = (generated_files or [])
                try:
                    same = sorted(last_files) == sorted(new_files)
                except Exception:
                    same = last_files == new_files
                if not same:
                    merged = list({*last_files, *new_files}) if (last_files or new_files) else []
                    if merged:
                        last["generated_files"] = merged
                last["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_conversation_file(conv_path, conv)
                return last.get("id", "")

        # 写入新消息
        msg_id = uuid.uuid4().hex[:12]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_msg.update({"id": msg_id, "created_at": now, "updated_at": now})
        msgs.append(new_msg)
        conv["updated_at"] = now

        # 自动生成标题(基于第一条用户消息)
        if len(msgs) == 1 and role == "user":
            title = content[:20] + ("..." if len(content) > 20 else "")
            conv["title"] = title
            self.index[conv_id]["title"] = title

        # 保存对话文件
        self._save_conversation_file(conv_path, conv)

        # 更新索引的updated_at
        self.index[conv_id]["updated_at"] = now
        self._save_index()

        return msg_id

    def update_message(
        self,
        conv_id: str,
        message_id: Optional[str] = None,
        role: str = "assistant",
        client_msg_id: Optional[str] = None,
        content: Optional[str] = None,
        append_content: Optional[str] = None,
        generated_files_delta: Optional[List[str]] = None,
        status: Optional[str] = None,
        username: Optional[str] = None,
    ) -> Optional[str]:
        """更新消息内容

        Args:
            conv_id: 对话ID
            message_id: 消息ID
            role: 消息角色
            client_msg_id: 客户端消息ID
            content: 新内容(覆盖)
            append_content: 追加内容
            generated_files_delta: 新增的文件列表
            status: 状态
            username: 用户名(权限校验)

        Returns:
            消息ID
        """
        # 加载对话
        conv = self.get_conversation(conv_id, username=username)
        if not conv:
            return None

        msgs = conv.get("messages", [])
        target = None

        # 查找目标消息
        if message_id:
            target = next((m for m in msgs if m.get("id") == message_id), None)
        if not target and client_msg_id:
            for i in range(len(msgs) - 1, -1, -1):
                m = msgs[i]
                if m.get("role") == role and m.get("client_msg_id") == client_msg_id:
                    target = m
                    break
        if not target:
            for i in range(len(msgs) - 1, -1, -1):
                m = msgs[i]
                if m.get("role") == role and m.get("status") in ("in_progress", None):
                    target = m
                    break

        if not target:
            return None

        # 更新内容
        if content is not None:
            target["content"] = content
        if append_content:
            target["content"] = (target.get("content") or "") + append_content
        if generated_files_delta:
            cur = target.get("generated_files") or []
            target["generated_files"] = list({*cur, *generated_files_delta})
        if status:
            target["status"] = status

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target["updated_at"] = now
        conv["updated_at"] = now

        # 保存对话文件
        conv_path = self._get_conv_path(conv_id)
        self._save_conversation_file(conv_path, conv)

        # 更新索引
        self.index[conv_id]["updated_at"] = now
        self._save_index()

        return target.get("id")

    def set_conversation_model(self, conv_id: str, model: str, username: str | None = None):
        """更新会话绑定的模型，并刷新更新时间。"""
        # 权限校验
        if conv_id not in self.index:
            return False
        if username is not None and self.index[conv_id].get("user") not in (None, username):
            return False

        # 加载并更新
        conv_path = self._get_conv_path(conv_id)
        conv = self._load_conversation_file(conv_path)
        if not conv:
            return False
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conv["model"] = model
        conv["updated_at"] = now
        self._save_conversation_file(conv_path, conv)
        # 同步索引
        self.index[conv_id]["model"] = model
        self.index[conv_id]["updated_at"] = now
        self._save_index()
        return True

    def update_message_feedback(
        self,
        conv_id: str,
        message_id: str,
        feedback: str,
        username: str | None = None
    ) -> bool:
        """更新消息的用户反馈

        Args:
            conv_id: 对话ID
            message_id: 消息ID
            feedback: 反馈内容 ("positive" / "neutral" / "negative")
            username: 用户名（权限校验）

        Returns:
            是否成功
        """
        # 权限校验
        if conv_id not in self.index:
            return False
        if username is not None and self.index[conv_id].get("user") not in (None, username):
            return False

        # 加载对话
        conv_path = self._get_conv_path(conv_id)
        conv = self._load_conversation_file(conv_path)
        if not conv:
            return False

        # 查找目标消息
        msgs = conv.get("messages", [])
        target = None
        for msg in msgs:
            if msg.get("id") == message_id:
                target = msg
                break

        if not target:
            return False

        # 更新反馈
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target["feedback"] = feedback
        target["feedback_time"] = now
        target["updated_at"] = now
        conv["updated_at"] = now

        # 保存对话文件
        self._save_conversation_file(conv_path, conv)

        # 更新索引
        self.index[conv_id]["updated_at"] = now
        self._save_index()

        return True

    # ===== 视觉控制：图片查看列表管理 =====
    # 存储格式: [{"path": "xxx.png", "detail": "auto", "remaining_views": 1}, ...]

    def add_images_to_view(
        self,
        conv_id: str,
        image_paths: List[str],
        detail: str = "auto",
        view_count: int = 1,
        username: str | None = None
    ) -> bool:
        """添加图片到LLM查看列表

        Args:
            conv_id: 对话ID
            image_paths: 图片文件路径列表（相对于outputs目录）
            detail: 图片细节级别 ("low"/"high"/"auto")
            view_count: 查看次数限制（默认1次，查看后自动移除）
            username: 用户名（权限校验）

        Returns:
            是否成功
        """
        conv = self.get_conversation(conv_id, username=username)
        if not conv:
            return False

        # 确保pending_images字段存在
        if "pending_images" not in conv:
            conv["pending_images"] = []

        # 转换为新格式（兼容旧数据）
        if conv["pending_images"] and isinstance(conv["pending_images"][0], str):
            conv["pending_images"] = [
                {"path": p, "detail": "auto", "remaining_views": 1} for p in conv["pending_images"]
            ]
        elif conv["pending_images"] and "remaining_views" not in conv["pending_images"][0]:
            # 旧格式但有dict结构，补充remaining_views
            for img in conv["pending_images"]:
                if "remaining_views" not in img:
                    img["remaining_views"] = 1

        # 添加图片（去重）
        existing_paths = {img["path"] for img in conv["pending_images"]}
        for path in image_paths:
            if path not in existing_paths:
                conv["pending_images"].append({
                    "path": path,
                    "detail": detail,
                    "remaining_views": max(1, view_count)  # 至少1次
                })

        # 保存对话文件
        conv_path = self._get_conv_path(conv_id)
        self._save_conversation_file(conv_path, conv)

        return True

    def get_images_to_view(self, conv_id: str, username: str | None = None) -> List[Dict]:
        """获取LLM查看列表中的图片

        Args:
            conv_id: 对话ID
            username: 用户名（权限校验）

        Returns:
            图片列表 [{"path": "xxx.png", "detail": "auto", "remaining_views": 1}, ...]
        """
        conv = self.get_conversation(conv_id, username=username)
        if not conv:
            return []

        pending = conv.get("pending_images", [])

        # 兼容旧格式（纯字符串列表）
        if pending and isinstance(pending[0], str):
            return [{"path": p, "detail": "auto", "remaining_views": 1} for p in pending]

        # 兼容旧dict格式（缺少remaining_views）
        if pending and "remaining_views" not in pending[0]:
            return [{"path": img["path"], "detail": img.get("detail", "auto"), "remaining_views": 1} for img in pending]

        return pending

    def decrement_views_and_cleanup(self, conv_id: str, username: str | None = None) -> int:
        """递减查看次数并移除已消耗的图片

        Args:
            conv_id: 对话ID
            username: 用户名（权限校验）

        Returns:
            移除的图片数量
        """
        conv = self.get_conversation(conv_id, username=username)
        if not conv:
            return 0

        pending = conv.get("pending_images", [])
        if not pending:
            return 0

        # 兼容性处理
        if isinstance(pending[0], str):
            conv["pending_images"] = []
            self._save_conversation_file(self._get_conv_path(conv_id), conv)
            return len(pending)

        # 递减并过滤
        remaining = []
        removed_count = 0

        for img in pending:
            if "remaining_views" not in img:
                img["remaining_views"] = 1

            img["remaining_views"] -= 1

            if img["remaining_views"] > 0:
                remaining.append(img)
            else:
                removed_count += 1

        # 更新列表
        conv["pending_images"] = remaining

        # 保存对话文件
        conv_path = self._get_conv_path(conv_id)
        self._save_conversation_file(conv_path, conv)

        return removed_count

    def clear_images_to_view(self, conv_id: str, username: str | None = None) -> bool:
        """清空LLM查看列表

        Args:
            conv_id: 对话ID
            username: 用户名（权限校验）

        Returns:
            是否成功
        """
        conv = self.get_conversation(conv_id, username=username)
        if not conv:
            return False

        conv["pending_images"] = []

        # 保存对话文件
        conv_path = self._get_conv_path(conv_id)
        self._save_conversation_file(conv_path, conv)

        return True

