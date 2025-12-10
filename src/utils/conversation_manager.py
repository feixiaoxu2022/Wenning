"""对话管理模块

负责多对话的存储、检索、管理
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import re
import uuid


class ConversationManager:
    """对话管理器"""

    def __init__(self, storage_path: str = "data/conversations.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.conversations = self._load()

    def _load(self) -> Dict:
        """加载对话数据"""
        if self.storage_path.exists():
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save(self):
        """保存对话数据"""
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.conversations, f, ensure_ascii=False, indent=2)

    def create_conversation(self, model: str = "gpt-5", username: str | None = None) -> str:
        """创建新对话

        Args:
            model: 模型名称

        Returns:
            对话ID
        """
        conv_id = str(uuid.uuid4())[:8]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.conversations[conv_id] = {
            "id": conv_id,
            "title": "新对话",
            "model": model,
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "user": username or None
        }

        self._save()

        # 创建会话级输出目录: outputs/{conv_id}
        try:
            out_root = Path("outputs")
            out_root.mkdir(exist_ok=True)
            (out_root / conv_id).mkdir(exist_ok=True)
        except Exception:
            # 目录创建失败不影响对话创建
            pass
        return conv_id

    def get_conversation(self, conv_id: str, username: str | None = None) -> Optional[Dict]:
        """获取对话详情（可选用户校验）"""
        conv = self.conversations.get(conv_id)
        if not conv:
            return None
        if username is not None and conv.get("user") not in (None, username):
            # 不属于该用户
            return None
        return conv

    def list_conversations(self, model: Optional[str] = None, username: str | None = None) -> List[Dict]:
        """列出所有对话

        Args:
            model: 可选,按模型筛选

        Returns:
            对话列表(按更新时间倒序)
        """
        convs = list(self.conversations.values())
        # 用户过滤
        if username is not None:
            convs = [c for c in convs if c.get("user") in (None, username) and (c.get("user") == username or username == 'anonymous' and c.get("user") is None)]

        if model:
            convs = [c for c in convs if c.get("model") == model]

        # 按更新时间倒序
        convs.sort(key=lambda x: x["updated_at"], reverse=True)

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
        """
        if conv_id not in self.conversations:
            return
        if username is not None and self.conversations[conv_id].get("user") not in (None, username):
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conversations[conv_id]["messages"] = messages
        self.conversations[conv_id]["updated_at"] = now

        # 自动生成标题(基于第一条用户消息)
        if not title and messages:
            first_user_msg = next((m for m in messages if m["role"] == "user"), None)
            if first_user_msg:
                # 截取前20个字符作为标题
                title = first_user_msg["content"][:20]
                if len(first_user_msg["content"]) > 20:
                    title += "..."

        if title:
            self.conversations[conv_id]["title"] = title

        self._save()

    def delete_conversation(self, conv_id: str, username: str | None = None):
        """删除对话"""
        if conv_id in self.conversations:
            if username is not None and self.conversations[conv_id].get("user") not in (None, username):
                return
            del self.conversations[conv_id]
            self._save()

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
        """向对话添加消息（幂等 + 近邻合并），返回消息ID。

        Args:
            tool_calls: assistant消息的tool_calls列表
            tool_call_id: tool消息对应的tool_call_id
            name: tool消息的工具名称
        """
        if conv_id not in self.conversations:
            return ""
        if username is not None and self.conversations[conv_id].get("user") not in (None, username):
            return ""

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

        msgs = self.conversations[conv_id]["messages"]

        def _norm(txt: str) -> str:
            if txt is None:
                return ""
            s = str(txt).replace("\r\n", "\n").replace("\u00a0", " ")
            s = re.sub(r"[ \t]+", " ", s).strip()
            return s

        # 幂等：client_msg_id 匹配则直接合并并返回
        if client_msg_id:
            for i in range(len(msgs) - 1, -1, -1):
                m = msgs[i]
                if m.get("role") == role and m.get("client_msg_id") == client_msg_id:
                    if generated_files:
                        cur = m.get("generated_files") or []
                        m["generated_files"] = list({*cur, *generated_files})
                    m["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self._save()
                    return m.get("id", "")

        # 近邻合并：相邻规范化文本相同
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
                self._save()
                return last.get("id", "")

        # 写入新消息
        msg_id = uuid.uuid4().hex[:12]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_msg.update({"id": msg_id, "created_at": now, "updated_at": now})
        msgs.append(new_msg)
        self.conversations[conv_id]["updated_at"] = now

        if len(msgs) == 1 and role == "user":
            title = content[:20] + ("..." if len(content) > 20 else "")
            self.conversations[conv_id]["title"] = title

        self._save()
        return msg_id

    def set_conversation_model(self, conv_id: str, model: str, username: str | None = None):
        """更新会话绑定的模型，并刷新更新时间。"""
        conv = self.get_conversation(conv_id, username=username)
        if not conv:
            return False
        conv["model"] = model
        conv["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        return True

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
        conv = self.get_conversation(conv_id, username=username)
        if not conv:
            return None
        msgs = conv.get("messages", [])
        target = None
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

        if content is not None:
            target["content"] = content
        if append_content:
            target["content"] = (target.get("content") or "") + append_content
        if generated_files_delta:
            cur = target.get("generated_files") or []
            target["generated_files"] = list({*cur, *generated_files_delta})
        if status:
            target["status"] = status
        target["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        return target.get("id")
