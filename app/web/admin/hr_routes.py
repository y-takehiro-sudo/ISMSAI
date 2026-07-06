import uuid
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import User, HrEvent, NotificationQueue
from app.db.session import get_db
from app.web.deps import templates

router = APIRouter(prefix="/admin")


# ─── ユーザー管理 ───────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
def user_list(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.name).all()
    return templates.TemplateResponse(request, "admin/user_list.html", context={"users": users})


@router.get("/users/new", response_class=HTMLResponse)
def user_new_form(request: Request):
    return templates.TemplateResponse(request, "admin/user_form.html", context={"user": None, "title": "ユーザー追加"})


@router.post("/users/new")
def user_new(
    name: str = Form(...),
    google_chat_user_id: str = Form(""),
    role: str = Form("member"),
    is_active: int = Form(1),
    login_id: str = Form(""),
    emp_type: str = Form("正社員"),
    org_name: str = Form(""),
    is_manager: int = Form(0),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        google_chat_user_id=google_chat_user_id,
        role=role,
        is_active=is_active,
        login_id=login_id or None,
        emp_type=emp_type,
        org_name=org_name or None,
        is_manager=is_manager,
    )
    db.add(user)
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.get("/users/{user_id}", response_class=HTMLResponse)
def user_detail(user_id: str, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return HTMLResponse("ユーザーが見つかりません", status_code=404)
    return templates.TemplateResponse(request, "admin/user_form.html", context={
        "user": user,
        "title": f"ユーザー編集: {user.name}",
    })


@router.post("/users/{user_id}")
def user_update(
    user_id: str,
    name: str = Form(...),
    google_chat_user_id: str = Form(""),
    role: str = Form("member"),
    is_active: int = Form(1),
    login_id: str = Form(""),
    emp_type: str = Form("正社員"),
    org_name: str = Form(""),
    is_manager: int = Form(0),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.name = name
        user.google_chat_user_id = google_chat_user_id
        user.role = role
        user.is_active = is_active
        user.login_id = login_id or None
        user.emp_type = emp_type
        user.org_name = org_name or None
        user.is_manager = is_manager
        db.commit()
    return RedirectResponse("/admin/users", status_code=303)


# ─── 入退社管理 ───────────────────────────────────────────

def _get_admin_user_id(db: Session) -> Optional[str]:
    admin = db.query(User).filter(User.role == "admin", User.is_active == 1).first()
    return admin.id if admin else None


def _queue_notifications(
    db: Session,
    user: User,
    event_type: str,
    event_date_str: str,
):
    """入退社イベントに対応する通知キューレコードを生成する。"""
    now = datetime.now().isoformat()
    event_dt = datetime.strptime(event_date_str, "%Y-%m-%d").date()
    admin_id = _get_admin_user_id(db)

    if event_type == "hire":
        schedule = [
            (event_dt - timedelta(days=3),  "dm", f"【入社準備】{user.name}さんが3日後に入社します。アカウント作成・貸与物の準備チェックをお願いします。"),
            (event_dt,                       "dm", f"【入社当日】{user.name}さんの入社日です。研修の実施・誓約書の取得を確認してください。"),
            (event_dt + timedelta(days=7),   "dm", f"【入社1週間後】{user.name}さん入社から1週間が経過しました。設定漏れの最終確認をお願いします。"),
        ]
    else:  # retirement
        schedule = [
            (event_dt - timedelta(days=14), "dm", f"【退社準備】{user.name}さんが2週間後に退社します。アカウント無効化・貸与物回収の準備をお願いします。"),
            (event_dt - timedelta(days=1),  "dm", f"【退社前日】{user.name}さんが明日退社します。当日対応の最終確認リストをご確認ください。"),
            (event_dt + timedelta(days=1),  "dm", f"【退社翌日・最重要】{user.name}さんの台帳更新が完了したか確認してください。"),
        ]

    for sched_date, space_type, message in schedule:
        db.add(NotificationQueue(
            id=str(uuid.uuid4()),
            instance_id=None,
            target_user_id=admin_id,
            space_type=space_type,
            message_body=message,
            status="draft",
            scheduled_at=datetime.combine(sched_date, datetime.min.time().replace(hour=8)).isoformat(),
            sent_at=None,
            created_at=now,
        ))


@router.get("/hr", response_class=HTMLResponse)
def hr_list(request: Request, db: Session = Depends(get_db)):
    events = (
        db.query(HrEvent, User)
        .join(User, HrEvent.user_id == User.id)
        .order_by(HrEvent.event_date.desc())
        .all()
    )
    users = db.query(User).filter(User.is_active == 1).order_by(User.name).all()
    return templates.TemplateResponse(request, "admin/hr.html", context={
        "events": events,
        "users": users,
    })


@router.post("/hr/hire")
def hr_hire(
    user_id: str = Form(...),
    event_date: str = Form(...),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()
    db.add(HrEvent(
        id=str(uuid.uuid4()),
        user_id=user_id,
        event_type="hire",
        event_date=event_date,
        created_at=now,
    ))
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        _queue_notifications(db, user, "hire", event_date)
    db.commit()
    return RedirectResponse("/admin/hr", status_code=303)


@router.post("/hr/retirement")
def hr_retirement(
    user_id: str = Form(...),
    event_date: str = Form(...),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()
    db.add(HrEvent(
        id=str(uuid.uuid4()),
        user_id=user_id,
        event_type="retirement",
        event_date=event_date,
        created_at=now,
    ))
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        _queue_notifications(db, user, "retirement", event_date)
    db.commit()
    return RedirectResponse("/admin/hr", status_code=303)
