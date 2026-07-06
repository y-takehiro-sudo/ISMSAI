"""ログイン・ログアウトルート"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.auth import (
    verify_password, create_session_token, decode_session_token,
    get_current_user, audit, get_client_ip, SESSION_COOKIE,
)
from app.web.deps import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/", error: str = "", db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(next if next != "/" else ("/admin/top" if user.role == "admin" else "/user/mypage"), status_code=302)
    return templates.TemplateResponse(request, "auth/login.html", context={
        "error": error, "next": next,
    })


@router.post("/login")
def login(
    request: Request,
    login_id: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.login_id == login_id, User.is_active == 1).first()
    ip = get_client_ip(request)

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        audit(db, action="login_failed", detail=f"login_id={login_id}", ip_address=ip)
        db.commit()
        return templates.TemplateResponse(request, "auth/login.html", context={
            "error": "IDまたはパスワードが違います", "next": next,
        }, status_code=401)

    user.last_login_at = datetime.now().isoformat()
    audit(db, action="login", user=user, ip_address=ip)
    db.commit()

    token = create_session_token(user.id)
    redirect_to = next if next.startswith("/") else "/"
    # roleに応じてデフォルトリダイレクト先を決定
    if redirect_to == "/":
        redirect_to = "/admin/top" if user.role == "admin" else "/user/mypage"

    response = RedirectResponse(redirect_to, status_code=303)
    response.set_cookie(SESSION_COOKIE, token, max_age=60*60*8, httponly=True, samesite="lax")
    return response


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    from app.auth import get_current_user as gcu
    user = gcu(request, db)
    if user:
        audit(db, action="logout", user=user, ip_address=get_client_ip(request))
        db.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response
