"""操作ログ閲覧・その他ページ"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import AuditLog, User
from app.db.session import get_db
from app.auth import require_admin
from app.web.deps import templates

router = APIRouter(prefix="/admin")

ACTION_LABELS = {
    "login":         ("🔑 ログイン",      "green"),
    "login_failed":  ("⚠️ ログイン失敗",  "red"),
    "logout":        ("🚪 ログアウト",    "gray"),
    "create":        ("➕ 作成",          "blue"),
    "update":        ("✏️ 更新",          "blue"),
    "delete":        ("🗑️ 削除",         "red"),
    "approve":       ("✅ 承認",          "green"),
    "cancel":        ("❌ 却下",          "red"),
    "submit":        ("📤 申告提出",      "purple"),
    "evaluate":      ("⭐ 評価",          "orange"),
}


@router.get("/others", response_class=HTMLResponse)
def others_page(
    request: Request,
    user_id: str = "",
    action: str = "",
    limit: int = 100,
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    users = db.query(User).order_by(User.name).all()

    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    logs = q.limit(limit).all()
    actions_list = db.query(AuditLog.action).distinct().all()

    enriched_logs = []
    for log in logs:
        label, color = ACTION_LABELS.get(log.action, (log.action, "gray"))
        enriched_logs.append({"log": log, "label": label, "color": color})

    return templates.TemplateResponse(request, "admin/others.html", context={
        "users": users,
        "logs": enriched_logs,
        "actions": [a[0] for a in actions_list],
        "filter_user": user_id,
        "filter_action": action,
        "action_labels": ACTION_LABELS,
    })


@router.get("/audit-logs", response_class=HTMLResponse)
def audit_logs(
    request: Request,
    user_id: str = "",
    action: str = "",
    limit: int = 100,
    db: Session = Depends(get_db),
):
    require_admin(request, db)

    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    logs = q.limit(limit).all()

    users = db.query(User).all()
    actions = db.query(AuditLog.action).distinct().all()

    enriched = []
    for log in logs:
        label, color = ACTION_LABELS.get(log.action, (log.action, "gray"))
        enriched.append({"log": log, "label": label, "color": color})

    return templates.TemplateResponse(request, "admin/audit_logs.html", context={
        "logs": enriched,
        "users": users,
        "actions": [a[0] for a in actions],
        "filter_user": user_id,
        "filter_action": action,
        "action_labels": ACTION_LABELS,
    })
