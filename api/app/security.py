import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import Cookie, Depends, HTTPException

from .config import ENCRYPTION_KEY
from .db import connect

ph = PasswordHasher(time_cost=2, memory_cost=32768, parallelism=2)


def now():
    return datetime.now(timezone.utc)


def iso(value=None):
    return (value or now()).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def make_token():
    return secrets.token_urlsafe(32)


def require_user(session: str | None = Cookie(default=None)):
    if not session:
        raise HTTPException(401, "请先登录")
    with connect() as db:
        user = db.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_hash=? AND s.expires_at>? AND u.deleted_at IS NULL",
            (digest(session), iso()),
        ).fetchone()
    if not user:
        raise HTTPException(401, "登录已过期")
    return dict(user)


def require_admin(user=Depends(require_user)):
    if not user["is_admin"]:
        raise HTTPException(403, "需要管理员权限")
    return user


def cipher():
    if not ENCRYPTION_KEY:
        raise HTTPException(503, "服务端尚未配置密钥加密")
    try:
        return Fernet(ENCRYPTION_KEY.encode())
    except ValueError as exc:
        raise HTTPException(503, "服务端密钥加密配置无效") from exc


def encrypt_key(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt_key(value):
    return cipher().decrypt(value.encode()).decode()
