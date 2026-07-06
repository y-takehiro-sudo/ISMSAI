"""アカウント管理：サービスマトリクス・在職状況・履歴"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import (
    User, Service, UserService, UserServiceHistory, NotificationQueue,
    AlertTemplate, AdminTask,
)
from app.db.session import get_db
from app.web.deps import templates

router = APIRouter(prefix="/admin")


@router.get("/accounts", response_class=HTMLResponse)
def accounts_page(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.name).all()
    services = db.query(Service).order_by(Service.sort_order, Service.name).all()

    # user_services を (user_id, service_id) → UserService にマップ
    all_us = db.query(UserService).all()
    us_map: dict[tuple, UserService] = {(us.user_id, us.service_id): us for us in all_us}

    alert_templates = db.query(AlertTemplate).order_by(AlertTemplate.sort_order, AlertTemplate.created_at).all()

    return templates.TemplateResponse(request, "admin/accounts.html", context={
        "users": users,
        "services": services,
        "us_map": us_map,
        "alert_templates": alert_templates,
    })


@router.post("/accounts/services/add")
def add_service(
    name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()
    svc = Service(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        sort_order=0,
        created_at=now,
    )
    db.add(svc)
    db.commit()
    return RedirectResponse("/admin/accounts", status_code=303)


@router.post("/accounts/services/{service_id}/delete")
def delete_service(service_id: str, db: Session = Depends(get_db)):
    svc = db.query(Service).filter(Service.id == service_id).first()
    if svc:
        db.delete(svc)
        db.commit()
    return RedirectResponse("/admin/accounts", status_code=303)


@router.post("/accounts/user-service/update")
def update_user_service(
    request: Request,
    user_id: str = Form(...),
    service_id: str = Form(...),
    status: str = Form("none"),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()

    us = db.query(UserService).filter(
        UserService.user_id == user_id,
        UserService.service_id == service_id,
    ).first()

    action_map = {"active": "activated", "suspended": "suspended", "none": "deactivated"}
    action = action_map.get(status, "deactivated")

    # 操作者（セッションユーザー）を取得
    changed_by = getattr(getattr(request.state, "current_user", None), "name", "管理者")

    if us:
        us.status = status
        us.note = note
        us.updated_at = now
    else:
        us = UserService(
            id=str(uuid.uuid4()),
            user_id=user_id,
            service_id=service_id,
            status=status,
            note=note,
            updated_at=now,
        )
        db.add(us)

    db.add(UserServiceHistory(
        id=str(uuid.uuid4()),
        user_id=user_id,
        service_id=service_id,
        action=action,
        changed_by=changed_by,
        note=note,
        created_at=now,
    ))
    db.commit()
    return RedirectResponse("/admin/accounts", status_code=303)


@router.post("/accounts/emp-status")
def update_emp_status(
    request: Request,
    user_id: str = Form(...),
    emp_status: str = Form("active"),
    emp_status_start: str = Form(""),
    emp_status_end: str = Form(""),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse("/admin/accounts", status_code=303)

    now = datetime.now().isoformat()
    user.emp_status = emp_status
    user.emp_status_start = emp_status_start or None
    user.emp_status_end = emp_status_end or None

    # 退職・休職の場合は通知キューに追加
    if emp_status in ("retired", "leave"):
        admin = db.query(User).filter(User.role == "admin", User.is_active == 1).first()
        admin_id = admin.id if admin else None
        status_label = "退職" if emp_status == "retired" else "休職"
        msg = f"【{status_label}】{user.name}さんのステータスが「{status_label}」に変更されました。アカウント処理を確認してください。"
        db.add(NotificationQueue(
            id=str(uuid.uuid4()),
            instance_id=None,
            target_user_id=admin_id,
            space_type="dm",
            message_body=msg,
            status="pending",
            scheduled_at=now,
            sent_at=None,
            created_at=now,
        ))

        # AlertTemplateからAdminTaskを自動生成
        templates_to_trigger = db.query(AlertTemplate).filter(
            (AlertTemplate.trigger_event == emp_status) | (AlertTemplate.trigger_event == "both")
        ).all()
        for tpl in templates_to_trigger:
            db.add(AdminTask(
                id=str(uuid.uuid4()),
                title=tpl.title,
                description=tpl.description,
                status="open",
                trigger_event=emp_status,
                related_user_id=user.id,
                related_user_name=user.name,
                created_at=now,
                updated_at=now,
            ))

    db.commit()
    return RedirectResponse("/admin/accounts", status_code=303)


@router.post("/accounts/alert-templates/add")
def add_alert_template(
    title: str = Form(...),
    description: str = Form(""),
    trigger_event: str = Form("retired"),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()
    db.add(AlertTemplate(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        trigger_event=trigger_event,
        created_at=now,
    ))
    db.commit()
    return RedirectResponse("/admin/accounts", status_code=303)


@router.post("/accounts/alert-templates/{tpl_id}/delete")
def delete_alert_template(tpl_id: str, db: Session = Depends(get_db)):
    tpl = db.query(AlertTemplate).filter(AlertTemplate.id == tpl_id).first()
    if tpl:
        db.delete(tpl)
        db.commit()
    return RedirectResponse("/admin/accounts", status_code=303)


@router.get("/accounts/history", response_class=HTMLResponse)
def account_history(request: Request, db: Session = Depends(get_db)):
    histories = db.query(UserServiceHistory).order_by(UserServiceHistory.created_at.desc()).limit(200).all()
    users_map = {u.id: u for u in db.query(User).all()}
    services_map = {s.id: s for s in db.query(Service).all()}

    rows = []
    for h in histories:
        rows.append({
            "h": h,
            "user": users_map.get(h.user_id),
            "service": services_map.get(h.service_id),
        })

    return templates.TemplateResponse(request, "admin/account_history.html", context={"rows": rows})
