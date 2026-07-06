"""評価ダッシュボード・カレンダービュー・KPI・トップページ"""
from datetime import datetime, date, timedelta
from collections import defaultdict
from calendar import monthrange

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import (
    User, Task, TaskInstance, TaskAssignee, Report,
    CheckInstance, CheckAnswer, CheckQuestion, EscalationLog,
)
from app.db.session import get_db
from app.web.deps import templates

router = APIRouter(prefix="/admin")


def _build_kpi_stats(db: Session):
    """KPI集計ロジック（dashboard/kpi/top で共有）"""
    users = db.query(User).filter(User.is_active == 1).all()
    all_instances = db.query(TaskInstance).all()
    all_reports = db.query(Report).all()
    all_check_instances = db.query(CheckInstance).all()
    all_check_answers = db.query(CheckAnswer).all()
    all_assignees = db.query(TaskAssignee).all()

    stats = []
    for user in users:
        user_task_ids = {a.task_id for a in all_assignees if a.user_id == user.id}
        user_instances = [i for i in all_instances if i.task_id in user_task_ids]
        completed = [i for i in user_instances if i.status == "completed"]
        task_total = len(user_instances)
        task_done = len(completed)
        task_rate = round(task_done / task_total * 100) if task_total else None

        response_days = []
        for inst in user_instances:
            if inst.status == "completed" and inst.due_date:
                rep = next(
                    (r for r in all_reports
                     if r.instance_id == inst.id and r.user_id == user.id and r.reported_at),
                    None,
                )
                if rep:
                    due = date.fromisoformat(inst.due_date)
                    reported = date.fromisoformat(rep.reported_at[:10])
                    diff = (reported - due).days
                    response_days.append(diff)
        avg_response = round(sum(response_days) / len(response_days), 1) if response_days else None

        user_checks = [i for i in all_check_instances if i.user_id == user.id]
        check_answered = [i for i in user_checks if i.status in ("answered", "evaluated")]
        check_total = len(user_checks)
        check_done = len(check_answered)
        check_rate = round(check_done / check_total * 100) if check_total else None

        user_ans_ids = {i.id for i in user_checks}
        evaluated = [
            a for a in all_check_answers
            if a.instance_id in user_ans_ids and (a.manager_result or a.ai_result)
        ]
        ok_count = sum(1 for a in evaluated if (a.manager_result or a.ai_result) == "ok")
        ok_rate = round(ok_count / len(evaluated) * 100) if evaluated else None

        esc_count = db.query(EscalationLog).filter(EscalationLog.user_id == user.id).count()

        stats.append({
            "user": user,
            "task_total": task_total,
            "task_done": task_done,
            "task_rate": task_rate,
            "avg_response": avg_response,
            "check_total": check_total,
            "check_done": check_done,
            "check_rate": check_rate,
            "ok_rate": ok_rate,
            "esc_count": esc_count,
        })
    return users, stats, all_instances, all_assignees


def _build_trend(users, all_instances, all_assignees):
    today = date.today()
    months = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append((y, m))

    trend_rows = []
    for user in users:
        user_task_ids = {a.task_id for a in all_assignees if a.user_id == user.id}
        row = {"user": user, "monthly": []}
        for (y, m) in months:
            first = date(y, m, 1)
            last = date(y, m, monthrange(y, m)[1])
            month_insts = [
                i for i in all_instances
                if i.task_id in user_task_ids
                and i.due_date
                and first.isoformat() <= i.due_date <= last.isoformat()
            ]
            total = len(month_insts)
            done = sum(1 for i in month_insts if i.status == "completed")
            rate = round(done / total * 100) if total else None
            row["monthly"].append({"year": y, "month": m, "rate": rate, "total": total, "done": done})
        trend_rows.append(row)
    return months, trend_rows


# ── 旧ダッシュボード → KPIにリダイレクト ─────────────
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect(request: Request):
    return RedirectResponse("/admin/kpi", status_code=301)


# ── KPI管理ページ ───────────────────────────────────
@router.get("/kpi", response_class=HTMLResponse)
def kpi_page(request: Request, db: Session = Depends(get_db)):
    users, stats, all_instances, all_assignees = _build_kpi_stats(db)
    months, trend_rows = _build_trend(users, all_instances, all_assignees)
    return templates.TemplateResponse(request, "admin/kpi.html", context={
        "stats": stats,
        "trend_rows": trend_rows,
        "trend_months": months,
    })


# ── トップページ ──────────────────────────────────────
@router.get("/top", response_class=HTMLResponse)
def top_page(request: Request, year: int = None, month: int = None, db: Session = Depends(get_db)):
    today = date.today()
    year = year or today.year
    month = month or today.month

    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    prev = (first_day - timedelta(days=1))
    next_ = (last_day + timedelta(days=1))

    instances = db.query(TaskInstance).filter(
        TaskInstance.due_date >= first_day.isoformat(),
        TaskInstance.due_date <= last_day.isoformat(),
    ).all()
    tasks_map = {t.id: t for t in db.query(Task).all()}
    check_instances = db.query(CheckInstance).filter(
        CheckInstance.due_date >= first_day.isoformat(),
        CheckInstance.due_date <= last_day.isoformat(),
    ).all()
    questions_map = {q.id: q for q in db.query(CheckQuestion).all()}
    users_map = {u.id: u for u in db.query(User).all()}

    events_by_date = defaultdict(list)
    for inst in instances:
        if not inst.due_date:
            continue
        task = tasks_map.get(inst.task_id)
        label = task.name if task else "（不明）"
        events_by_date[inst.due_date].append({"type": "task_due", "label": f"📋 {label}", "status": inst.status, "color": "blue"})

    for ci in check_instances:
        if not ci.due_date:
            continue
        q = questions_map.get(ci.question_id)
        u = users_map.get(ci.user_id)
        label = f"{q.title if q else '申告'} / {u.name if u else '?'}"
        events_by_date[ci.due_date].append({"type": "check", "label": f"✅ {label}", "status": ci.status, "color": "green"})

    # 日本の祝日（固定観察日ベース簡易版）
    def _jp_holidays(y):
        hols = {
            date(y, 1, 1), date(y, 2, 11), date(y, 2, 23),
            date(y, 3, 20), date(y, 4, 29), date(y, 5, 3),
            date(y, 5, 4), date(y, 5, 5), date(y, 7, 21),
            date(y, 8, 11), date(y, 9, 15), date(y, 9, 23),
            date(y, 10, 13), date(y, 11, 3), date(y, 11, 23),
        }
        return hols

    holidays = _jp_holidays(year)

    start = first_day - timedelta(days=first_day.weekday())  # 月曜始まり
    weeks = []
    cur = start
    while cur <= last_day or len(weeks) < 6:
        week = []
        for _ in range(7):
            is_weekend = cur.weekday() >= 5  # 土=5, 日=6
            is_holiday = cur in holidays
            week.append({
                "date": cur,
                "in_month": cur.month == month,
                "is_today": cur == today,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "events": events_by_date.get(cur.isoformat(), []),
            })
            cur += timedelta(days=1)
        weeks.append(week)
        if cur > last_day and len(weeks) >= 4:
            break

    # 運用評価（全データ）
    users_kpi, stats, all_instances, all_assignees = _build_kpi_stats(db)
    trend_months, trend_rows = _build_trend(users_kpi, all_instances, all_assignees)

    return templates.TemplateResponse(request, "admin/top.html", context={
        "weeks": weeks,
        "year": year,
        "month": month,
        "month_label": f"{year}年{month}月",
        "prev_year": prev.year, "prev_month": prev.month,
        "next_year": next_.year, "next_month": next_.month,
        "stats": stats,
        "trend_months": trend_months,
        "trend_rows": trend_rows,
    })




# ── カレンダービュー ──────────────────────────────────
@router.get("/calendar", response_class=HTMLResponse)
def calendar_view(request: Request, year: int = None, month: int = None, db: Session = Depends(get_db)):
    today = date.today()
    year = year or today.year
    month = month or today.month

    # 表示月の1日〜末日
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    # 前月・次月
    prev = (first_day - timedelta(days=1))
    next_ = (last_day + timedelta(days=1))

    # 月内のタスクインスタンスを取得
    instances = db.query(TaskInstance).filter(
        TaskInstance.due_date >= first_day.isoformat(),
        TaskInstance.due_date <= last_day.isoformat(),
    ).all()
    tasks_map = {t.id: t for t in db.query(Task).all()}

    # 月内の自己申告インスタンスを取得
    check_instances = db.query(CheckInstance).filter(
        CheckInstance.due_date >= first_day.isoformat(),
        CheckInstance.due_date <= last_day.isoformat(),
    ).all()
    questions_map = {q.id: q for q in db.query(CheckQuestion).all()}
    users_map = {u.id: u for u in db.query(User).all()}

    # リマインド日も計算してカレンダーイベントに追加
    events_by_date = defaultdict(list)

    for inst in instances:
        if not inst.due_date:
            continue
        task = tasks_map.get(inst.task_id)
        label = task.name if task else "（不明）"
        events_by_date[inst.due_date].append({
            "type": "task_due",
            "label": f"📋 {label}",
            "status": inst.status,
            "color": "blue",
        })

    for ci in check_instances:
        if not ci.due_date:
            continue
        q = questions_map.get(ci.question_id)
        u = users_map.get(ci.user_id)
        label = f"{q.title if q else '申告'} / {u.name if u else '?'}"
        events_by_date[ci.due_date].append({
            "type": "check",
            "label": f"✅ {label}",
            "status": ci.status,
            "color": "green",
        })

    # カレンダーグリッド生成（6週分）
    start = first_day - timedelta(days=first_day.weekday())  # 月曜始まり
    weeks = []
    cur = start
    while cur <= last_day or len(weeks) < 6:
        week = []
        for _ in range(7):
            week.append({
                "date": cur,
                "in_month": cur.month == month,
                "is_today": cur == today,
                "events": events_by_date.get(cur.isoformat(), []),
            })
            cur += timedelta(days=1)
        weeks.append(week)
        if cur > last_day and len(weeks) >= 4:
            break

    return templates.TemplateResponse(request, "admin/calendar.html", context={
        "weeks": weeks,
        "year": year,
        "month": month,
        "month_label": f"{year}年{month}月",
        "prev_year": prev.year, "prev_month": prev.month,
        "next_year": next_.year, "next_month": next_.month,
    })
