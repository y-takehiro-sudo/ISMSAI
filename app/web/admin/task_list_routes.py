"""タスク一覧画面（管理者タスク・ユーザータスク・トリガーマスタ）"""
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import AdminTask, UserTask, UserTaskAssignee, AlertTemplate, User
from app.db.session import get_db
from app.web.deps import templates

router = APIRouter(prefix="/admin")


@router.get("/admin-tasks", response_class=HTMLResponse)
def admin_tasks_page(request: Request, show_completed: str = "", db: Session = Depends(get_db)):
    admin_tasks = db.query(AdminTask).order_by(AdminTask.created_at.desc()).all()
    user_tasks = db.query(UserTask).order_by(UserTask.created_at.desc()).all()
    alert_templates = db.query(AlertTemplate).order_by(AlertTemplate.sort_order).all()
    users = db.query(User).filter(User.is_active == 1).all()

    users_map = {u.id: u.name for u in db.query(User).all()}
    assignee_ids_map: dict = {}
    assignees_map: dict = {}
    done_count_map: dict = {}
    for ta in db.query(UserTaskAssignee).all():
        assignee_ids_map.setdefault(ta.task_id, []).append(ta.user_id)
        assignees_map.setdefault(ta.task_id, []).append(users_map.get(ta.user_id, ta.user_id))
        if ta.completed_at:
            done_count_map[ta.task_id] = done_count_map.get(ta.task_id, 0) + 1

    if show_completed != "1":
        admin_tasks = [t for t in admin_tasks if t.status != "done"]
        user_tasks = [t for t in user_tasks if t.status != "done"]

    return templates.TemplateResponse(request, "admin/admin_tasks.html", context={
        "admin_tasks": admin_tasks,
        "user_tasks": user_tasks,
        "alert_templates": alert_templates,
        "users": users,
        "assignees_map": assignees_map,
        "assignee_ids_map": assignee_ids_map,
        "done_count_map": done_count_map,
        "show_completed": show_completed,
    })


# ── 管理者タスク CRUD ──────────────────────────────────────────

@router.post("/admin-tasks/admin/new")
def admin_task_new(
    title: str = Form(...),
    description: str = Form(""),
    due_date: str = Form(""),
    trigger_event: str = Form("manual"),
    related_user_name: str = Form(""),
    db: Session = Depends(get_db),
):
    db.add(AdminTask(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        due_date=due_date,
        trigger_event=trigger_event,
        related_user_name=related_user_name,
        status="open",
    ))
    db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


@router.post("/admin-tasks/admin/{task_id}/inline-update")
def admin_task_inline_update(
    task_id: str,
    title: str = Form(...),
    description: str = Form(""),
    due_date: str = Form(""),
    db: Session = Depends(get_db),
):
    task = db.query(AdminTask).filter(AdminTask.id == task_id).first()
    if task:
        task.title = title
        task.description = description
        task.due_date = due_date
        task.updated_at = datetime.now().isoformat()
        db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


@router.post("/admin-tasks/admin/{task_id}/toggle-done")
def admin_task_toggle_done(task_id: str, db: Session = Depends(get_db)):
    task = db.query(AdminTask).filter(AdminTask.id == task_id).first()
    if task:
        task.status = "done" if task.status != "done" else "open"
        task.updated_at = datetime.now().isoformat()
        db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


@router.post("/admin-tasks/admin/{task_id}/delete")
def admin_task_delete(task_id: str, db: Session = Depends(get_db)):
    db.query(AdminTask).filter(AdminTask.id == task_id).delete()
    db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


# ── ユーザー向けタスク詳細 ───────────────────────────────────────

@router.get("/admin-tasks/user/{task_id}", response_class=HTMLResponse)
def user_task_detail(task_id: str, request: Request, db: Session = Depends(get_db)):
    task = db.query(UserTask).filter(UserTask.id == task_id).first()
    if not task:
        return HTMLResponse("タスクが見つかりません", status_code=404)

    users_map = {u.id: u for u in db.query(User).all()}
    assignees = db.query(UserTaskAssignee).filter(UserTaskAssignee.task_id == task_id).all()
    assignee_details = [
        {
            "user": users_map.get(a.user_id),
            "comment": a.comment or "",
            "completed_at": a.completed_at[:10] if a.completed_at else None,
        }
        for a in assignees
    ]
    done_count = sum(1 for a in assignees if a.completed_at)

    return templates.TemplateResponse(request, "admin/user_task_detail.html", context={
        "task": task,
        "assignee_details": assignee_details,
        "done_count": done_count,
        "total_count": len(assignees),
    })


# ── ユーザー向けタスク CRUD ──────────────────────────────────────

@router.post("/admin-tasks/user/new")
def user_task_new(
    title: str = Form(...),
    description: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    url: str = Form(""),
    assignee_ids: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()
    task = UserTask(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        start_date=start_date,
        end_date=end_date,
        url=url,
        status="open",
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.flush()
    for uid in assignee_ids:
        if uid:
            db.add(UserTaskAssignee(id=str(uuid.uuid4()), task_id=task.id, user_id=uid, created_at=now))
    db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


@router.post("/admin-tasks/user/{task_id}/inline-update")
def user_task_inline_update(
    task_id: str,
    title: str = Form(...),
    description: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    url: str = Form(""),
    assignee_ids: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    task = db.query(UserTask).filter(UserTask.id == task_id).first()
    if task:
        task.title = title
        task.description = description
        task.start_date = start_date
        task.end_date = end_date
        task.url = url
        task.updated_at = datetime.now().isoformat()
        db.query(UserTaskAssignee).filter(UserTaskAssignee.task_id == task_id).delete()
        now = datetime.now().isoformat()
        for uid in assignee_ids:
            if uid:
                db.add(UserTaskAssignee(id=str(uuid.uuid4()), task_id=task_id, user_id=uid, created_at=now))
        db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


@router.post("/admin-tasks/user/{task_id}/toggle-done")
def user_task_toggle_done(task_id: str, db: Session = Depends(get_db)):
    task = db.query(UserTask).filter(UserTask.id == task_id).first()
    if task:
        task.status = "done" if task.status != "done" else "open"
        task.updated_at = datetime.now().isoformat()
        db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


@router.post("/admin-tasks/user/{task_id}/delete")
def user_task_delete(task_id: str, db: Session = Depends(get_db)):
    db.query(UserTaskAssignee).filter(UserTaskAssignee.task_id == task_id).delete()
    db.query(UserTask).filter(UserTask.id == task_id).delete()
    db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


# ── トリガーマスタ CRUD ──────────────────────────────────────────

@router.post("/admin-tasks/master/new")
def alert_template_new(
    title: str = Form(...),
    description: str = Form(""),
    trigger_event: str = Form("retired"),
    assignee_role: str = Form("admin"),
    db: Session = Depends(get_db),
):
    count = db.query(AlertTemplate).count()
    db.add(AlertTemplate(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        trigger_event=trigger_event,
        assignee_role=assignee_role,
        sort_order=count,
    ))
    db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


@router.post("/admin-tasks/master/{tpl_id}/inline-update")
def alert_template_inline_update(
    tpl_id: str,
    title: str = Form(...),
    description: str = Form(""),
    trigger_event: str = Form("retired"),
    assignee_role: str = Form("admin"),
    db: Session = Depends(get_db),
):
    tpl = db.query(AlertTemplate).filter(AlertTemplate.id == tpl_id).first()
    if tpl:
        tpl.title = title
        tpl.description = description
        tpl.trigger_event = trigger_event
        tpl.assignee_role = assignee_role
        db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)


@router.post("/admin-tasks/master/{tpl_id}/delete")
def alert_template_delete(tpl_id: str, db: Session = Depends(get_db)):
    db.query(AlertTemplate).filter(AlertTemplate.id == tpl_id).delete()
    db.commit()
    return RedirectResponse("/admin/admin-tasks", status_code=303)
