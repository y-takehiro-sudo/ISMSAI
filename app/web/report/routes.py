import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.models import Report, TaskInstance, Task, TaskAssignee, User
from app.db.session import get_db
from app.web.deps import templates

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_report_context(token: str, db: Session):
    """トークンからレポート表示に必要な情報を取得する。"""
    report = db.query(Report).filter(Report.report_token == token).first()
    if not report:
        return None, None, None, None, None

    instance = db.query(TaskInstance).filter(TaskInstance.id == report.instance_id).first()
    task = db.query(Task).filter(Task.id == instance.task_id).first() if instance else None
    user = db.query(User).filter(User.id == report.user_id).first()
    already_reported = report.reported_at is not None

    return report, instance, task, user, already_reported


@router.get("/report/{token}", response_class=HTMLResponse)
def report_form(token: str, request: Request, db: Session = Depends(get_db)):
    report, instance, task, user, already_reported = _get_report_context(token, db)

    if not report:
        return HTMLResponse("<h1>無効なURLです</h1>", status_code=404)

    return templates.TemplateResponse(request, "report/form.html", context={
        "token": token,
        "task": task,
        "instance": instance,
        "user": user,
        "already_reported": already_reported,
        "reported_at": report.reported_at,
    })


@router.post("/report/{token}")
def report_submit(
    token: str,
    request: Request,
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    report, instance, task, user, already_reported = _get_report_context(token, db)

    if not report:
        return HTMLResponse("<h1>無効なURLです</h1>", status_code=404)

    if already_reported:
        return templates.TemplateResponse(request, "report/form.html", context={
            "token": token,
            "task": task,
            "instance": instance,
            "user": user,
            "already_reported": True,
            "reported_at": report.reported_at,
        })

    now = datetime.now().isoformat()
    report.reported_at = now
    report.comment = comment

    # instance が in_progress でなければ更新
    if instance and instance.status == "pending":
        instance.status = "in_progress"

    db.flush()

    # 完了条件チェック
    if instance and task:
        assignees = db.query(TaskAssignee).filter(TaskAssignee.task_id == task.id).all()
        assignee_ids = {a.user_id for a in assignees}

        reported_user_ids = {
            r.user_id for r in db.query(Report)
            .filter(Report.instance_id == instance.id, Report.reported_at.isnot(None))
            .all()
        }
        all_done = assignee_ids.issubset(reported_user_ids)

        if all_done:
            instance.status = "completed"
            logger.info(f"タスクインスタンス {instance.id} が完了しました。")
        else:
            logger.info(f"{user.name if user else '?'} さんが完了報告しました（インスタンス {instance.id}）。")

    db.commit()

    return templates.TemplateResponse(request, "report/form.html", context={
        "token": token,
        "task": task,
        "instance": instance,
        "user": user,
        "already_reported": True,
        "reported_at": now,
        "just_submitted": True,
    })
