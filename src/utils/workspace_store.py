from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


class WorkspaceStore:
    """简单的基于JSON的Workspace存储，按用户名划分，再按会话划分文件列表。

    数据结构:
    {
      "username": {
          "conv_id": ["file1.png", "file2.xlsx"]
      }
    }
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
        data = self._load()
        return list((data.get(username) or {}).get(conv_id) or [])

    def add_file(self, username: str, conv_id: str, filename: str):
        data = self._load()
        user = data.setdefault(username, {})
        files = user.setdefault(conv_id, [])
        if filename not in files:
            files.append(filename)
        self._save(data)

    def remove_file(self, username: str, conv_id: str, filename: str):
        data = self._load()
        user = data.get(username) or {}
        files = user.get(conv_id) or []
        if filename in files:
            files.remove(filename)
            # 清理空结构
            if not files:
                user.pop(conv_id, None)
            if not user:
                data.pop(username, None)
            self._save(data)
