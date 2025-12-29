from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, TypedDict


class WorkspaceFile(TypedDict):
    """工作区文件条目（用于API返回）"""
    filename: str
    source_conv_id: str


class WorkspaceStore:
    """简单的基于JSON的Workspace存储，按用户名划分，再按会话划分文件列表。

    数据结构:
    {
      "username": {
          "conv_id": ["file1.png", "file2.xlsx"]  # 字符串数组
      }
    }

    conversation_id已经作为key存在，不需要在文件里再存一遍。
    只有在跨对话查询（list_all_files）时才需要返回source_conv_id。
    """

    def __init__(self, path: Path = Path("data/workspace.json")):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({})

    def _load(self) -> Dict[str, Dict[str, List[str]]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: Dict[str, Dict[str, List[str]]]):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list_files(self, username: str, conv_id: str) -> List[str]:
        """返回用户在指定对话中保存的所有文件"""
        data = self._load()
        return (data.get(username) or {}).get(conv_id) or []

    def add_file(self, username: str, conv_id: str, filename: str):
        """添加文件到工作区"""
        data = self._load()
        if username not in data:
            data[username] = {}
        if conv_id not in data[username]:
            data[username][conv_id] = []
        if filename not in data[username][conv_id]:
            data[username][conv_id].append(filename)
        self._save(data)

    def remove_file(self, username: str, conv_id: str, filename: str):
        """从工作区移除文件"""
        data = self._load()
        if username in data and conv_id in data[username]:
            try:
                data[username][conv_id].remove(filename)
                if not data[username][conv_id]:
                    del data[username][conv_id]
                if not data[username]:
                    del data[username]
                self._save(data)
            except ValueError:
                pass

    def list_all_files(self, username: str) -> List[WorkspaceFile]:
        """返回用户在所有对话中保存的所有文件（带源对话ID，用于@mention）"""
        data = self._load()
        user_data = data.get(username) or {}
        result = []
        for conv_id, files in user_data.items():
            for filename in files:
                result.append({
                    "filename": filename,
                    "source_conv_id": conv_id
                })
        return result
