"""統一リマインドロジック: 全タスク種別に共通のリマインドスケジュールを適用する。"""
import logging
import os
import uuid
from datetime import datetime, date, timedelta

from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from app.db.models import (
    Task, TaskInstance, TaskAssignee,
    AdminTask, UserTask, UserTaskAssignee,
    CheckFormInstance, CheckForm,
    User, NotificationQueue,
)

logger = logging.getLogger(__name__)

# ユーザーポータルのベースURL（完了報告・回答へのリンク）
_BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def _get_notify_type(start_date_str: str, end_date_str: str, today: date) -> str | None:
    """今日送るべき通知種別を返す。不要なら None。"""
    if not end_date_str:
        return None
    try:
        end = date.fromisoformat(end_date_str)
    except ValueError:
        return None

    # start_date がなければ end - 7日 を使う
    if start_date_str:
        try:
            start = date.fromisoformat(start_date_str)
        except ValueError:
            start = end - timedelta(days=7)
    else:
        start = end - timedelta(days=7)

    # 期限超過 → 毎週月曜
    if today > end:
        return "overdue" if today.weekday() == 0 else None

    # 期限日
    if today == end:
        return "deadline"

    # 3日前
    if (end - today).days == 3:
        return "pre_deadline"

    # 中間日
    span = (end - start).days
    if span > 0:
        mid = start + timedelta(days=span // 2)
        if today == mid:
            return "midpoint"

    # 開始日
    if today == start:
        return "start"

    return None


def _already_notified(db: Session, target_type: str, target_id: str,
                       user_id: str, notify_type: str, today: date) -> bool:
    """同日・同種別・同対象の通知が既存かチェック。"""
    return db.query(NotificationQueue).filter(
        NotificationQueue.target_type == target_type,
        NotificationQueue.target_id == target_id,
        NotificationQueue.target_user_id == user_id,
        NotificationQueue.message_body.contains(f"[{notify_type}]"),
        NotificationQueue.scheduled_at.like(f"{today.isoformat()}%"),
    ).first() is not None


def _queue(db: Session, target_type: str, target_id: str,
           user_id: str, notify_type: str, task_name: str,
           due_date: str, today: date, description: str = "", space_type: str = "member"):
    """通知をキューに追加（重複スキップ）。"""
    if _already_notified(db, target_type, target_id, user_id, notify_type, today):
        return

    report_url = f"{_BASE_URL}/user/mypage"

    try:
        from app.notifier.message_gen import generate_message
        user = db.query(User).filter(User.id == user_id).first()
        message_body = generate_message(
            task_name=task_name,
            task_description=description,
            assignee_name=user.name if user else "",
            due_date=due_date,
            notify_type=notify_type,
            report_url=report_url,
        )
    except Exception as e:
        logger.warning(f"AI生成失敗、テンプレート使用: {e}")
        labels = {
            "start": "開始",
            "midpoint": "中間リマインド",
            "week_before": "期限7日前",
            "pre_deadline": "前営業日",
            "deadline": "期限日",
            "overdue": "期限超過（未完了）",
            "daily_reminder": "回答リマインド",
        }
        label = labels.get(notify_type, notify_type)
        message_body = f"【{label}】{task_name}（期限: {due_date}）
{report_url}"

    db.add(NotificationQueue(
        id=str(uuid.uuid4()),
        target_type=target_type,
        target_id=target_id,
        target_user_id=user_id,
        space_type=space_type,
        message_body=message_body,
        status="approved",
        scheduled_at=today.isoformat(),
        created_at=datetime.now().isoformat(),
    ))
    logger.info(f"[{notify_type}] {task_name} → user:{user_id}")


def _get_admin_task_notify_type(due_date_str: str, today: date) -> str | None:
    """管理者向け個別タスク専用: 7日前・前営業日・当日・以降毎週月曜"""
    if not due_date_str:
        return None
    try:
        end = date.fromisoformat(due_date_str)
    except ValueError:
        return None

    # 期限超過 → 毎週月曜
    if today > end:
        return "overdue" if today.weekday() == 0 else None

    # 当日
    if today == end:
        return "deadline"

    # 前営業日（期限の直前の平日）
    prev_biz = end - timedelta(days=1)
    while prev_biz.weekday() >= 5:  # 土=5, 日=6
        prev_biz -= timedelta(days=1)
    if today == prev_biz:
        return "pre_deadline"

    # 7日前
    if (end - today).days == 7:
        return "week_before"

    return None


def run_daily_check(db: Session):
    today = date.today()
    users_map = {u.id: u for u in db.query(User).filter(User.is_active == 1).all()}
    queued = 0

    # ── 1. 年間全体タスク ──────────────────────────────────────
    tasks = db.query(Task).all()
    instances_map = {}
    for inst in db.query(TaskInstance).all():
        if inst.task_id not in instances_map or (inst.created_at or "") > (instances_map[inst.task_id].created_at or ""):
            instances_map[inst.task_id] = inst

    for task in tasks:
        notify_type = _get_notify_type(task.start_date or "", task.end_date or "", today)
        if not notify_type:
            continue

        inst = instances_map.get(task.id)
        if inst and inst.status == "completed":
            continue

        assignees = db.query(TaskAssignee).filter(TaskAssignee.task_id == task.id).all()
        for ta in assignees:
            _queue(db, "task", task.id, ta.user_id, notify_type,
                   task.name, task.end_date or "", today, task.description or "")
            queued += 1

    # ── 2. 管理者向け個別タスク（7日前・前営業日・当日・超過後毎週月曜）──
    admin_tasks = db.query(AdminTask).filter(AdminTask.status != "done").all()
    admin_users = [u for u in users_map.values() if u.role == "admin"]

    for task in admin_tasks:
        if not task.due_date:
            continue
        notify_type = _get_admin_task_notify_type(task.due_date, today)
        if not notify_type:
            continue
        for u in admin_users:
            _queue(db, "admin_task", task.id, u.id, notify_type,
                   task.title, task.due_date, today, task.description or "", space_type="admin")
            queued += 1

    # ── 3. ユーザー向け個別タスク ─────────────────────────────
    user_tasks = db.query(UserTask).filter(UserTask.status != "done").all()
    ut_assignees: dict[str, list[str]] = {}
    for ta in db.query(UserTaskAssignee).all():
        ut_assignees.setdefault(ta.task_id, []).append(ta.user_id)

    for task in user_tasks:
        notify_type = _get_notify_type(task.start_date or "", task.end_date or "", today)
        if not notify_type:
            continue
        for uid in ut_assignees.get(task.id, []):
            _queue(db, "user_task", task.id, uid, notify_type,
                   task.title, task.end_date or "", today, task.description or "")
            queued += 1

    # ── 4. 運用チェック ────────────────────────────────────────
    # 発信日（scheduled_date）当日 → "start" 通知
    # 発信日以降・未完了 → 毎日 "daily_reminder" 通知
    pending_instances = db.query(CheckFormInstance).filter(
        CheckFormInstance.status == "pending"
    ).all()
    forms_map = {f.id: f for f in db.query(CheckForm).all()}

    for inst in pending_instances:
        scheduled_str = inst.scheduled_date or inst.due_date or ""
        if not scheduled_str:
            continue
        try:
            scheduled = date.fromisoformat(scheduled_str)
        except ValueError:
            continue
        if today < scheduled:
            continue  # まだ発信日前

        form = forms_map.get(inst.form_id)
        task_name = form.title if form else "運用チェック"
        due_str = inst.due_date or scheduled_str

        if today == scheduled:
            notify_type = "start"
        else:
            notify_type = "daily_reminder"

        _queue(db, "check_form", inst.id, inst.user_id, notify_type,
               task_name, due_str, today)
        queued += 1

    db.commit()
    logger.info(f"run_daily_check: {queued}件の通知をキューに追加")

    # キュー送信
    try:
        from app.notifier.sender import flush_approved_queue
        flush_approved_queue(db)
    except Exception as e:
        logger.warning(f"flush_approved_queue スキップ: {e}")
