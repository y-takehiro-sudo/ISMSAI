"""APSchedulerのジョブ定義。main.pyから start_scheduler() を呼ぶ。"""
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import get_session_factory

logger = logging.getLogger(__name__)

DAILY_HOUR = int(os.getenv("DAILY_CHECK_HOUR", "8"))
_WEEKDAY_MAP = {"monday": "mon", "tuesday": "tue", "wednesday": "wed",
                "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun"}
_raw_day = os.getenv("WEEKLY_CHECK_DAY", "monday").lower()
WEEKLY_DAY = _WEEKDAY_MAP.get(_raw_day, _raw_day)


def _daily_job():
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        from app.scheduler.task_checker import run_daily_check
        # エスカレーション機能は無効化中
        # from app.scheduler.escalation import run_escalation_check
        run_daily_check(db)
        # run_escalation_check(db)
    except Exception as e:
        logger.error(f"daily_job 例外: {e}")
    finally:
        db.close()


def _weekly_job():
    """毎週月曜: 未完了タスクのサマリーを管理者スペースに投稿する。
    リマインド通知は _daily_job が担うため、ここでは重複しない。"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        from app.db.models import TaskInstance, AdminTask, UserTask, CheckFormInstance
        from app.notifier.chat_client import send_notification
        from datetime import date

        today = date.today()

        task_pending  = db.query(TaskInstance).filter(TaskInstance.status.in_(["pending", "in_progress"])).count()
        admin_pending = db.query(AdminTask).filter(AdminTask.status != "done").count()
        user_pending  = db.query(UserTask).filter(UserTask.status != "done").count()
        check_pending = db.query(CheckFormInstance).filter(CheckFormInstance.status == "pending").count()

        message = "\n".join([
            f"【週次サマリー: {today.isoformat()}】",
            f"・年間全体タスク（未完了）: {task_pending}件",
            f"・管理者タスク（未完了）: {admin_pending}件",
            f"・ユーザータスク（未完了）: {user_pending}件",
            f"・運用チェック（未回答）: {check_pending}件",
        ])
        send_notification("", "admin", message)
        logger.info("weekly_job 完了")
    except Exception as e:
        logger.error(f"weekly_job 例外: {e}")
    finally:
        db.close()


def _monthly_job():
    """毎月1日: 月次サマリーを管理者スペースに投稿する。"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        from app.db.models import Task, TaskInstance
        from app.notifier.chat_client import send_notification
        from datetime import date

        today = date.today()
        month_str = today.strftime("%Y-%m")

        instances = db.query(TaskInstance).all()
        tasks_map = {t.id: t for t in db.query(Task).all()}

        completed = [i for i in instances if i.status == "completed" and (i.due_date or "").startswith(month_str)]
        pending   = [i for i in instances if i.status in ("pending", "in_progress") and (i.due_date or "").startswith(month_str)]

        lines = [
            f"【{today.month}月度サマリー】",
            f"完了: {len(completed)}件",
            f"未完了: {len(pending)}件",
        ]
        if pending:
            lines.append("未完了タスク:")
            for inst in pending[:5]:
                t = tasks_map.get(inst.task_id)
                if t:
                    lines.append(f"  ・{t.name}")

        send_notification("", "admin", "\n".join(lines))
        logger.info("monthly_job 完了")
    except Exception as e:
        logger.error(f"monthly_job 例外: {e}")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")

    # 毎朝8時：期限チェック＋エスカレーション
    scheduler.add_job(
        _daily_job,
        CronTrigger(hour=DAILY_HOUR, minute=0),
        id="daily_check",
        replace_existing=True,
    )

    # 毎週月曜8時：今週のタスク一覧投稿
    scheduler.add_job(
        _weekly_job,
        CronTrigger(day_of_week=WEEKLY_DAY, hour=DAILY_HOUR, minute=0),
        id="weekly_summary",
        replace_existing=True,
    )

    # 毎月1日8時：月次サマリー投稿
    scheduler.add_job(
        _monthly_job,
        CronTrigger(day=1, hour=DAILY_HOUR, minute=0),
        id="monthly_summary",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"スケジューラー起動: daily={DAILY_HOUR}時, weekly={WEEKLY_DAY}, monthly=1日")
    return scheduler
