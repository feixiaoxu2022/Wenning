from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict
import json
from passlib.context import CryptContext


# 默认使用 pbkdf2_sha256，避免对系统 bcrypt 后端的依赖与版本兼容问题。
# 如果将来需要兼容历史 bcrypt 哈希，可再增加 "bcrypt_sha256" / "bcrypt" 到 schemes。
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


@dataclass
class AuthConfig:
    users_path: Path
    allow_register: bool = True


class AuthStore:
    def __init__(self, path: Path, allow_register: bool = True):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.allow_register = allow_register
        if not self.path.exists():
            self._save({})

    def _load(self) -> Dict[str, Dict[str, str]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: Dict):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, username: str) -> Optional[Dict[str, str]]:
        return self._load().get(username)

    def register(self, username: str, password: str):
        if not self.allow_register:
            raise PermissionError("注册被禁用")
        users = self._load()
        if username in users:
            raise ValueError("用户名已存在")
        hashed = pwd_context.hash(password)
        users[username] = {"password": hashed}
        self._save(users)

    def verify(self, username: str, password: str) -> bool:
        user = self.get(username)
        if not user:
            return False
        try:
            return pwd_context.verify(password, user.get("password", ""))
        except Exception:
            # 对异常情况（例如极端长密码、非法编码等）统一返回False，避免抛至上层
            return False
