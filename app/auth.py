"""認証・セッション・操作ログのユーティリティ"""
import uuid, os
from datetime import datetime
from typing import Optional

import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import User, AuditLog

SECRET_KEY = os.getenv("SECRET_KEY", "isms-secret-key-change-in-production")
_serializer = URLSafeTimedSerializer(SECRET_KEY)
SESSION_COOKIE = "isms_session"
SESSION_MAX_AGE = 60 * 60 * 8  # 8時間


# ── パスワード ────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── セッション ────────────────────────────────────────────

def create_session_token(user_id: str) -> str:
    return _serializer.dumps({"user_id": user_id})


def decode_session_token(token: str) -> Optional[str]:
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("user_id")
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user_id = decode_session_token(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == 1).first()


def require_login(request: Request, db: Session) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


def require_admin(request: Request, db: Session) -> User:
    user = require_login(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return user


# ── 操作ログ ──────────────────────────────────────────────

def audit(
    db: Session,
    action: str,
    user: Optional[User] = None,
    target: str = "",
    target_id: str = "",
    detail: str = "",
    ip_address: str = "",
):
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        user_id=user.id if user else None,
        user_name=user.name if user else "anonymous",
        action=action,
        target=target,
        target_id=target_id,
        detail=detail,
        ip_address=ip_address,
        created_at=datetime.now().isoformat(),
    ))
    # commitは呼び出し元に任せる


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
