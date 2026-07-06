"""エントリーポイント：管理画面・報告フォーム・スケジューラーを一括起動する。"""
import os
import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

os.makedirs("logs", exist_ok=True)
handler = RotatingFileHandler("logs/isms.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[handler, logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# DB初期化
from app.db.init_db import init_db
from app.db.session import get_session_factory

DB_PATH = os.getenv("DB_PATH", "isms.db")
init_db(DB_PATH)
get_session_factory(DB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリ起動・終了時の処理。uvicorn経由でもスケジューラーが確実に起動する。"""
    try:
        from app.scheduler.runner import start_scheduler
        start_scheduler()
        logger.info("スケジューラー起動完了")
    except Exception as e:
        logger.error(f"スケジューラー起動失敗: {e}")
    yield
    # shutdown処理（必要なら追加）


# FastAPIアプリ組み立て
app = FastAPI(title="ISMS PDCAシステム", lifespan=lifespan)

# ── 認証ミドルウェア ────────────────────────────────────
from app.auth import decode_session_token, SESSION_COOKIE
from app.db.models import User

ADMIN_PREFIX = "/admin"
USER_PREFIX  = "/user"
PUBLIC_PATHS = {"/login", "/logout", "/report", "/user/check"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    logger.info(f"[MW] {request.method} {path} cookie={bool(request.cookies.get(SESSION_COOKIE))}")

    # 公開パス・静的ファイルはスルー
    if (path in ("/", "/login", "/logout")
            or path.startswith("/static")
            or path.startswith("/uploads")
            or path.startswith("/report/")
            or path.startswith("/user/check/")):
        return await call_next(request)

    # セッション確認
    token = request.cookies.get(SESSION_COOKIE)
    user_id = decode_session_token(token) if token else None

    if not user_id:
        return RedirectResponse(f"/login?next={path}", status_code=302)

    # ユーザー取得
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
        if not user:
            resp = RedirectResponse("/login", status_code=302)
            resp.delete_cookie(SESSION_COOKIE)
            return resp

        # /admin/* は admin のみ
        if path.startswith(ADMIN_PREFIX) and user.role != "admin":
            return RedirectResponse("/user/mypage", status_code=302)

        # /user/* は認証済みならOK（check/* はトークンなので公開済み）

        request.state.current_user = user
    finally:
        db.close()

    return await call_next(request)


# ── ルーター登録 ────────────────────────────────────────
from app.web.auth_routes import router as auth_router
from app.web.admin.routes import router as admin_router
from app.web.admin.hr_routes import router as hr_router
from app.web.admin.queue_routes import router as queue_router
from app.web.admin.check_routes import router as check_router
from app.web.admin.dashboard_routes import router as dashboard_router
from app.web.admin.audit_routes import router as audit_router
from app.web.admin.account_routes import router as account_router
from app.web.admin.task_list_routes import router as admin_task_router
from app.web.admin.asset_routes import router as asset_router
from app.web.user.routes import router as user_router
from app.web.report.routes import router as report_router

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(hr_router)
app.include_router(queue_router)
app.include_router(check_router)
app.include_router(dashboard_router)
app.include_router(audit_router)
app.include_router(account_router)
app.include_router(admin_task_router)
app.include_router(asset_router)
app.include_router(user_router)
app.include_router(report_router)

# 静的ファイル
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
def root(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    user_id = decode_session_token(token) if token else None
    if not user_id:
        return RedirectResponse("/login")
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active == 1).first()
        if user and user.role == "admin":
            return RedirectResponse("/admin/top")
        if user:
            return RedirectResponse("/user/mypage")
    finally:
        db.close()
    return RedirectResponse("/login")


if __name__ == "__main__":
    host = os.getenv("SERVER_HOST", "localhost")
    port = int(os.getenv("SERVER_PORT", "8000"))
    logger.info(f"サーバー起動: http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=False)
