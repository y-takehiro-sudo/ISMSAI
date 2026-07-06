from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import NotificationQueue, TaskInstance, Task, TaskAssignee, User, Report
from app.db.session import get_db
from app.web.deps import templates

router = APIRouter(prefix="/admin")


# ─── 送信前キュー ───────────────────────────────────────────

@router.get("/queue", response_class=HTMLResponse)
def queue_list(request: Request, db: Session = Depends(get_db)):
    items = (
        db.query(NotificationQueue)
        .filter(NotificationQueue.status == "draft")
        .order_by(NotificationQueue.scheduled_at)
        .all()
    )
    users = {u.id: u for u in db.query(User).all()}
    tasks_map = {t.id: t for t in db.query(Task).all()}
    instances_map = {i.id: i for i in db.query(TaskInstance).all()}

    enriched = []
    for item in items:
        instance = instances_map.get(item.instance_id) if item.instance_id else None
        task = tasks_map.get(instance.task_id) if instance else None
        target_user = users.get(item.target_user_id)
        enriched.append({
            "item": item,
            "task": task,
            "target_user": target_user,
        })

    return templates.TemplateResponse(request, "admin/queue.html", context={
        "enriched": enriched,
        "total": len(enriched),
    })


@router.post("/queue/{item_id}/approve")
def queue_approve(item_id: str, db: Session = Depends(get_db)):
    item = db.query(NotificationQueue).filter(NotificationQueue.id == item_id).first()
    if item and item.status == "draft":
        item.status = "approved"
        db.commit()

        # autoモード相当：approvedになったら即送信
        try:
            from app.notifier.sender import flush_approved_queue
            flush_approved_queue(db)
        except Exception:
            pass

    return RedirectResponse("/admin/queue", status_code=303)


@router.post("/queue/{item_id}/cancel")
def queue_cancel(item_id: str, db: Session = Depends(get_db)):
    item = db.query(NotificationQueue).filter(NotificationQueue.id == item_id).first()
    if item and item.status == "draft":
        item.status = "cancelled"
        db.commit()
    return RedirectResponse("/admin/queue", status_code=303)


@router.post("/queue/approve-all")
def queue_approve_all(db: Session = Depends(get_db)):
    items = db.query(NotificationQueue).filter(NotificationQueue.status == "draft").all()
    for item in items:
        item.status = "approved"
    db.commit()

    try:
        from app.notifier.sender import flush_approved_queue
        flush_approved_queue(db)
    except Exception:
        pass

    return RedirectResponse("/admin/queue", status_code=303)


@router.get("/queue/{item_id}/edit", response_class=HTMLResponse)
def queue_edit_form(item_id: str, request: Request, db: Session = Depends(get_db)):
    item = db.query(NotificationQueue).filter(NotificationQueue.id == item_id).first()
    if not item:
        return HTMLResponse("Not found", status_code=404)
    users = db.query(User).filter(User.is_active == 1).all()
    return templates.TemplateResponse(request, "admin/queue_edit.html", context={
        "item": item,
        "users": users,
    })


@router.post("/queue/{item_id}/edit")
def queue_edit(
    item_id: str,
    message_body: str = Form(...),
    target_user_id: str = Form(""),
    scheduled_at: str = Form(""),
    db: Session = Depends(get_db),
):
    item = db.query(NotificationQueue).filter(NotificationQueue.id == item_id).first()
    if item:
        item.message_body = message_body
        if target_user_id:
            item.target_user_id = target_user_id
        if scheduled_at:
            item.scheduled_at = scheduled_at
        db.commit()
    return RedirectResponse("/admin/queue", status_code=303)


# ─── 完了追跡ビュー ───────────────────────────────────────────

@router.get("/tracking", response_class=HTMLResponse)
def tracking(
    request: Request,
    filter: str = "",
    db: Session = Depends(get_db),
):
    today = datetime.now().date().isoformat()
    week_end = datetime.now().date().strftime("%Y-%m-") + str(datetime.now().day + 7).zfill(2)

    q = db.query(TaskInstance).filter(TaskInstance.status.in_(["pending", "in_progress", "escalated"]))
    if filter == "overdue":
        q = q.filter(TaskInstance.due_date < today)
    elif filter == "this_week":
        q = q.filter(TaskInstance.due_date >= today, TaskInstance.due_date <= week_end)
    elif filter == "escalated":
        q = q.filter(TaskInstance.status == "escalated")

    instances = q.order_by(TaskInstance.due_date).all()
    tasks_map = {t.id: t for t in db.query(Task).all()}
    users_map = {u.id: u for u in db.query(User).all()}

    rows = []
    for inst in instances:
        task = tasks_map.get(inst.task_id)
        assignees = db.query(TaskAssignee).filter(TaskAssignee.task_id == inst.task_id).all()
        reports = {r.user_id: r for r in db.query(Report).filter(Report.instance_id == inst.id).all()}

        assignee_statuses = []
        for a in assignees:
            r = reports.get(a.user_id)
            assignee_statuses.append({
                "user": users_map.get(a.user_id),
                "reported": r is not None and r.reported_at is not None,
                "reported_at": r.reported_at if r else None,
            })

        rows.append({
            "instance": inst,
            "task": task,
            "assignee_statuses": assignee_statuses,
            "is_overdue": inst.due_date and inst.due_date < today,
        })

    return templates.TemplateResponse(request, "admin/tracking.html", context={
        "rows": rows,
        "filter": filter,
        "today": today,
    })
