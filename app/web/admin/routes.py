import uuid
import os
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import Task, TaskAssignee, TaskInstance, Report, User, TaskOwner
from app.db.session import get_db
from app.auth import get_current_user
from app.web.deps import templates

router = APIRouter(prefix="/admin")


@router.get("/tasks", response_class=HTMLResponse)
def task_list(
    request: Request,
    phase: Optional[str] = None,
    show_completed: str = "",
    db: Session = Depends(get_db),
):
    q = db.query(Task)
    if phase:
        q = q.filter(Task.phase == phase)
    tasks = q.order_by(Task.start_date, Task.created_at).all()

    users = db.query(User).filter(User.is_active == 1).all()
    users_map = {u.id: u.name for u in users}

    # assignees per task
    assignees_map: dict[str, list[str]] = {}
    assignee_ids_map: dict[str, list[str]] = {}
    for ta in db.query(TaskAssignee).all():
        assignees_map.setdefault(ta.task_id, []).append(users_map.get(ta.user_id, ta.user_id))
        assignee_ids_map.setdefault(ta.task_id, []).append(ta.user_id)

    # owners per task
    owners_map: dict[str, list[str]] = {}
    owner_ids_map: dict[str, list[str]] = {}
    for to in db.query(TaskOwner).all():
        owners_map.setdefault(to.task_id, []).append(users_map.get(to.user_id, to.user_id))
        owner_ids_map.setdefault(to.task_id, []).append(to.user_id)

    # completion status per task
    instances_map: dict[str, TaskInstance] = {}
    for inst in db.query(TaskInstance).all():
        if inst.task_id not in instances_map or (inst.created_at or "") > (instances_map[inst.task_id].created_at or ""):
            instances_map[inst.task_id] = inst

    # reported counts per task (how many assignees submitted a Report)
    reported_by_instance: dict[str, set] = {}
    for r in db.query(Report).filter(Report.reported_at.isnot(None)).all():
        reported_by_instance.setdefault(r.instance_id, set()).add(r.user_id)
    reported_count_map: dict[str, int] = {
        task_id: len(reported_by_instance.get(inst.id, set()))
        for task_id, inst in instances_map.items()
    }

    # filter completed tasks unless show_completed
    if show_completed != "1":
        tasks = [t for t in tasks if instances_map.get(t.id) is None or instances_map.get(t.id).status != "completed"]

    return templates.TemplateResponse(request, "admin/task_list.html", context={
        "tasks": tasks,
        "users": users,
        "users_map": users_map,
        "assignees_map": assignees_map,
        "assignee_ids_map": assignee_ids_map,
        "owners_map": owners_map,
        "owner_ids_map": owner_ids_map,
        "instances_map": instances_map,
        "reported_count_map": reported_count_map,
        "filter_phase": phase or "",
        "show_completed": show_completed,
    })


@router.get("/tasks/new", response_class=HTMLResponse)
def task_new_form(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == 1).all()
    return templates.TemplateResponse(request, "admin/task_form.html", context={
        "task": None,
        "users": users,
        "assignee_ids": [],
        "owner_ids": [],
        "title": "新規タスク作成",
    })


@router.post("/tasks/new")
def task_new(
    request: Request,
    phase: str = Form(""),
    name: str = Form(...),
    description: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    url: str = Form(""),
    owner_ids: List[str] = Form(default=[]),
    assignee_ids: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()
    task = Task(
        id=str(uuid.uuid4()),
        phase=phase,
        name=name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        url=url,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.flush()
    for uid in assignee_ids:
        if uid:
            db.add(TaskAssignee(id=str(uuid.uuid4()), task_id=task.id, user_id=uid, created_at=now))
    for uid in owner_ids:
        if uid:
            db.add(TaskOwner(id=str(uuid.uuid4()), task_id=task.id, user_id=uid))
    # 新規タスクには必ずインスタンスを作成（ポータル表示に必要）
    db.add(TaskInstance(
        id=str(uuid.uuid4()),
        task_id=task.id,
        status="pending",
        due_date=end_date,
        created_at=now,
    ))
    db.commit()
    return RedirectResponse("/admin/tasks", status_code=303)


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def task_detail(task_id: str, request: Request, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return HTMLResponse("タスクが見つかりません", status_code=404)

    assignees = db.query(TaskAssignee).filter(TaskAssignee.task_id == task_id).all()
    users_map = {u.id: u for u in db.query(User).all()}

    instance = db.query(TaskInstance).filter(TaskInstance.task_id == task_id).order_by(TaskInstance.created_at.desc()).first()
    reports = []
    if instance:
        reports = db.query(Report).filter(Report.instance_id == instance.id).all()

    assignee_details = []
    for ta in assignees:
        u = users_map.get(ta.user_id)
        rep = next((r for r in reports if r.user_id == ta.user_id), None)
        assignee_details.append({"user": u, "report": rep})

    owner_records = db.query(TaskOwner).filter(TaskOwner.task_id == task_id).all()
    owner_names = [users_map[o.user_id].name for o in owner_records if o.user_id in users_map]

    return templates.TemplateResponse(request, "admin/task_detail.html", context={
        "task": task,
        "instance": instance,
        "assignee_details": assignee_details,
        "owner_names": owner_names,
        "completed_by_name": users_map.get(instance.completed_by, None).name if instance and instance.completed_by and users_map.get(instance.completed_by) else None,
    })


@router.post("/tasks/{task_id}/inline-update")
def task_inline_update(
    task_id: str,
    phase: str = Form(""),
    name: str = Form(...),
    description: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    url: str = Form(""),
    owner_ids: List[str] = Form(default=[]),
    assignee_ids: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse("/admin/tasks", status_code=303)

    task.phase = phase
    task.name = name
    task.description = description
    task.start_date = start_date
    task.end_date = end_date
    task.url = url
    task.updated_at = datetime.now().isoformat()

    db.query(TaskAssignee).filter(TaskAssignee.task_id == task_id).delete()
    db.query(TaskOwner).filter(TaskOwner.task_id == task_id).delete()
    now = datetime.now().isoformat()
    for uid in assignee_ids:
        if uid:
            db.add(TaskAssignee(id=str(uuid.uuid4()), task_id=task_id, user_id=uid, created_at=now))
    for uid in owner_ids:
        if uid:
            db.add(TaskOwner(id=str(uuid.uuid4()), task_id=task_id, user_id=uid))
    # インスタンスがなければ作成（ポータル表示に必要）
    existing_inst = db.query(TaskInstance).filter(TaskInstance.task_id == task_id).first()
    if not existing_inst:
        db.add(TaskInstance(
            id=str(uuid.uuid4()),
            task_id=task_id,
            status="pending",
            due_date=end_date,
            created_at=now,
        ))
    else:
        existing_inst.due_date = end_date
    db.commit()
    return RedirectResponse("/admin/tasks", status_code=303)


@router.post("/tasks/{task_id}/toggle-complete")
def task_toggle_complete(task_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse("/admin/tasks", status_code=303)

    instance = db.query(TaskInstance).filter(TaskInstance.task_id == task_id).order_by(TaskInstance.created_at.desc()).first()
    now = datetime.now().isoformat()

    if not instance:
        instance = TaskInstance(
            id=str(uuid.uuid4()),
            task_id=task_id,
            status="completed",
            completed_at=now,
            completed_by=user.id if user else "",
            created_at=now,
        )
        db.add(instance)
    elif instance.status == "completed":
        instance.status = "pending"
        instance.completed_at = ""
        instance.completed_by = ""
    else:
        instance.status = "completed"
        instance.completed_at = now
        instance.completed_by = user.id if user else ""

    db.commit()
    return RedirectResponse("/admin/tasks", status_code=303)


@router.post("/tasks/{task_id}/duplicate")
def task_duplicate(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse("/admin/tasks", status_code=303)
    now = datetime.now().isoformat()
    new_task = Task(
        id=str(uuid.uuid4()),
        phase=task.phase,
        name=task.name + " (コピー)",
        description=task.description,
        start_date=getattr(task, "start_date", ""),
        end_date=getattr(task, "end_date", ""),
        url=getattr(task, "url", ""),
        created_at=now,
        updated_at=now,
    )
    db.add(new_task)
    db.flush()
    for to in db.query(TaskOwner).filter(TaskOwner.task_id == task_id).all():
        db.add(TaskOwner(id=str(uuid.uuid4()), task_id=new_task.id, user_id=to.user_id))
    db.add(TaskInstance(
        id=str(uuid.uuid4()),
        task_id=new_task.id,
        status="pending",
        due_date=getattr(task, "end_date", ""),
        created_at=now,
    ))
    db.commit()
    return RedirectResponse("/admin/tasks", status_code=303)


@router.post("/tasks/{task_id}/delete")
def task_delete(task_id: str, db: Session = Depends(get_db)):
    db.query(TaskAssignee).filter(TaskAssignee.task_id == task_id).delete()
    db.query(TaskOwner).filter(TaskOwner.task_id == task_id).delete()
    db.query(TaskInstance).filter(TaskInstance.task_id == task_id).delete()
    db.query(Task).filter(Task.id == task_id).delete()
    db.commit()
    return RedirectResponse("/admin/tasks", status_code=303)


@router.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
def task_edit_form(task_id: str, request: Request, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return HTMLResponse("タスクが見つかりません", status_code=404)
    users = db.query(User).filter(User.is_active == 1).all()
    assignee_ids = [ta.user_id for ta in db.query(TaskAssignee).filter(TaskAssignee.task_id == task_id).all()]
    owner_ids = [to.user_id for to in db.query(TaskOwner).filter(TaskOwner.task_id == task_id).all()]
    return templates.TemplateResponse(request, "admin/task_form.html", context={
        "task": task,
        "users": users,
        "assignee_ids": assignee_ids,
        "owner_ids": owner_ids,
        "title": "タスク編集",
    })


@router.post("/tasks/{task_id}/update")
def task_update(
    task_id: str,
    phase: str = Form(""),
    name: str = Form(...),
    description: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    url: str = Form(""),
    owner_ids: List[str] = Form(default=[]),
    assignee_ids: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse("/admin/tasks", status_code=303)
    task.phase = phase
    task.name = name
    task.description = description
    task.start_date = start_date
    task.end_date = end_date
    task.url = url
    task.updated_at = datetime.now().isoformat()

    db.query(TaskAssignee).filter(TaskAssignee.task_id == task_id).delete()
    db.query(TaskOwner).filter(TaskOwner.task_id == task_id).delete()
    now = datetime.now().isoformat()
    for uid in assignee_ids:
        if uid:
            db.add(TaskAssignee(id=str(uuid.uuid4()), task_id=task_id, user_id=uid, created_at=now))
    for uid in owner_ids:
        if uid:
            db.add(TaskOwner(id=str(uuid.uuid4()), task_id=task_id, user_id=uid))
    existing_inst = db.query(TaskInstance).filter(TaskInstance.task_id == task_id).first()
    if not existing_inst:
        db.add(TaskInstance(
            id=str(uuid.uuid4()),
            task_id=task_id,
            status="pending",
            due_date=end_date,
            created_at=now,
        ))
    else:
        existing_inst.due_date = end_date
    db.commit()
    return RedirectResponse("/admin/tasks", status_code=303)
