import smtplib
import secrets
from datetime import timedelta
from email.message import EmailMessage

from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from . import config
from .common import uid
from .db import connect, transaction
from .security import digest, iso, make_token, now, ph, require_admin, require_user

router = APIRouter(prefix="/api")


class RegisterInput(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=24, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=12, max_length=128)
    invite_code: str


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class EmailInput(BaseModel):
    email: EmailStr


class VerificationInput(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class InviteInput(BaseModel):
    uses: int = Field(default=1, ge=1, le=100)
    days: int = Field(default=14, ge=1, le=90)


def send_verification(email, token):
    # Keep the token in the URL fragment so browsers do not send it to the web
    # server, reverse proxy, or referrer headers when loading the verify page.
    url = f"{config.APP_ORIGIN}/verify#token={token}"
    if not config.MAIL_HOST:
        if config.APP_ORIGIN.startswith("http://localhost"):
            return url
        raise HTTPException(503, "邮件服务未配置")
    if config.MAIL_USER and not config.MAIL_TLS:
        raise HTTPException(503, "SMTP 登录必须启用 TLS")
    msg = EmailMessage()
    msg["Subject"] = "验证成长平台邮箱"
    msg["From"] = config.MAIL_FROM
    msg["To"] = email
    msg.set_content(f"请在 24 小时内打开此链接验证邮箱：\n{url}\n")
    smtp_class = smtplib.SMTP_SSL if config.MAIL_TLS and config.MAIL_PORT == 465 else smtplib.SMTP
    with smtp_class(config.MAIL_HOST, config.MAIL_PORT, timeout=10) as smtp:
        if config.MAIL_TLS and config.MAIL_PORT != 465:
            smtp.starttls()
        if config.MAIL_USER:
            smtp.login(config.MAIL_USER, config.MAIL_PASSWORD)
        smtp.send_message(msg)
    return None


@router.post("/auth/register", status_code=201)
def register(data: RegisterInput):
    email = str(data.email).lower()
    username = data.username.lower()
    token = make_token()
    user_id = uid()
    with transaction() as db:
        invite = db.execute("SELECT * FROM invites WHERE code_hash=? AND expires_at>? AND uses_left>0", (digest(data.invite_code), iso())).fetchone()
        if not invite:
            raise HTTPException(400, "邀请码无效或已过期")
        if db.execute("SELECT 1 FROM users WHERE email=? OR username=?", (email, username)).fetchone():
            raise HTTPException(409, "邮箱或用户名已被使用")
        db.execute(
            "INSERT INTO users(id,email,username,password_hash,is_admin,created_at) VALUES(?,?,?,?,?,?)",
            (user_id, email, username, ph.hash(data.password), int(email == config.ADMIN_EMAIL), iso()),
        )
        db.execute("UPDATE invites SET uses_left=uses_left-1 WHERE code_hash=?", (digest(data.invite_code),))
        db.execute("INSERT INTO verification_tokens VALUES(?,?,?)", (digest(token), user_id, iso(now() + timedelta(hours=24))))
    try:
        dev_url = send_verification(email, token)
    except Exception:
        with transaction() as db:
            db.execute("DELETE FROM users WHERE id=?", (user_id,))
            db.execute("UPDATE invites SET uses_left=uses_left+1 WHERE code_hash=?", (digest(data.invite_code),))
        raise
    return {"message": "请查收验证邮件", **({"dev_verification_url": dev_url} if dev_url else {})}


@router.post("/auth/verify")
def verify(data: VerificationInput):
    with transaction() as db:
        row = db.execute("SELECT user_id FROM verification_tokens WHERE token_hash=? AND expires_at>?", (digest(data.token), iso())).fetchone()
        if not row:
            raise HTTPException(400, "验证链接无效或已过期")
        db.execute("UPDATE users SET verified_at=COALESCE(verified_at,?) WHERE id=?", (iso(), row["user_id"]))
    return {"message": "邮箱验证成功"}


@router.post("/auth/resend-verification")
def resend_verification(data: EmailInput):
    email = str(data.email).lower()
    generic = {"message": "如果该邮箱尚未验证，新的验证邮件会发送到邮箱"}
    token = make_token()
    with transaction() as db:
        user = db.execute("SELECT id,verified_at FROM users WHERE email=? AND deleted_at IS NULL", (email,)).fetchone()
        if not user or user["verified_at"]:
            return generic
        latest = db.execute("SELECT MAX(expires_at) FROM verification_tokens WHERE user_id=?", (user["id"],)).fetchone()[0]
        if latest and latest > iso(now() + timedelta(hours=23, minutes=55)):
            return generic
        db.execute("INSERT INTO verification_tokens VALUES(?,?,?)", (digest(token), user["id"], iso(now() + timedelta(hours=24))))
    try:
        dev_url = send_verification(email, token)
    except Exception:
        with transaction() as db:
            db.execute("DELETE FROM verification_tokens WHERE token_hash=?", (digest(token),))
        raise
    return {**generic, **({"dev_verification_url": dev_url} if dev_url else {})}


@router.post("/auth/login")
def login(data: LoginInput, request: Request, response: Response):
    email = str(data.email).lower()
    ip = request.client.host if request.client else "unknown"
    rate_key = digest(f"{ip}:{email}")
    with connect() as db:
        attempt = db.execute("SELECT * FROM login_attempts WHERE key=?", (rate_key,)).fetchone()
        if attempt and attempt["window_start"] > iso(now() - timedelta(minutes=15)) and attempt["count"] >= 5:
            raise HTTPException(429, "尝试次数过多，请 15 分钟后重试")
        user = db.execute("SELECT * FROM users WHERE email=? AND deleted_at IS NULL", (email,)).fetchone()
        valid = False
        if user:
            try:
                valid = ph.verify(user["password_hash"], data.password)
            except VerifyMismatchError:
                pass
    if not valid:
        with transaction() as db:
            if not attempt or attempt["window_start"] <= iso(now() - timedelta(minutes=15)):
                db.execute("INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)", (rate_key, 1, iso()))
            else:
                db.execute("UPDATE login_attempts SET count=count+1 WHERE key=?", (rate_key,))
        raise HTTPException(401, "邮箱或密码不正确")
    if not user["verified_at"]:
        raise HTTPException(403, "请先验证邮箱")
    with transaction() as db:
        db.execute("DELETE FROM login_attempts WHERE key=?", (rate_key,))
        token = make_token()
        db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest(token), user["id"], iso(now() + timedelta(days=14)), iso()))
    response.set_cookie("session", token, httponly=True, secure=config.COOKIE_SECURE, samesite="lax", max_age=14 * 86400, path="/")
    return {"id": user["id"], "username": user["username"], "is_admin": bool(user["is_admin"])}


@router.post("/auth/logout")
def logout(request: Request, response: Response, user=Depends(require_user)):
    token = request.cookies.get("session")
    if token:
        with transaction() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=? AND user_id=?", (digest(token), user["id"]))
    response.delete_cookie("session", path="/")
    return {"message": "已退出"}


@router.get("/me")
def me(user=Depends(require_user)):
    return {key: user[key] for key in ("id", "email", "username", "start_date", "timezone", "is_admin")}


class ProfileInput(BaseModel):
    start_date: str | None = None
    timezone: str = "Asia/Shanghai"


@router.patch("/me")
def update_profile(data: ProfileInput, user=Depends(require_user)):
    from datetime import date
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    if data.start_date:
        try:
            date.fromisoformat(data.start_date)
        except ValueError:
            raise HTTPException(422, "开始日期无效")
    try:
        ZoneInfo(data.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "时区无效")
    with transaction() as db:
        db.execute("UPDATE users SET start_date=?,timezone=? WHERE id=?", (data.start_date, data.timezone, user["id"]))
    return {"start_date": data.start_date, "timezone": data.timezone}


@router.delete("/me", status_code=204)
def delete_account(response: Response, user=Depends(require_user)):
    with transaction() as db:
        db.execute("DELETE FROM users WHERE id=?", (user["id"],))
    response.delete_cookie("session", path="/")


@router.post("/admin/invites")
def create_invite(data: InviteInput, user=Depends(require_admin)):
    code = secrets.token_urlsafe(12)
    with transaction() as db:
        db.execute("INSERT INTO invites VALUES(?,?,?,?,?)", (digest(code), user["id"], data.uses, iso(now() + timedelta(days=data.days)), iso()))
    return {"code": code, "uses": data.uses, "expires_at": iso(now() + timedelta(days=data.days))}


def bootstrap_invite():
    import os
    code = os.getenv("BOOTSTRAP_INVITE", "")
    if not code:
        return
    with transaction() as db:
        db.execute("INSERT OR IGNORE INTO invites VALUES(?,?,?,?,?)", (digest(code), None, 1, iso(now() + timedelta(days=30)), iso()))
