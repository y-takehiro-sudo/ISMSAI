"""運用チェック：フォーム管理・回答確認・評価"""
import os, uuid, json
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import CheckForm, CheckFormQuestion, CheckFormInstance, CheckFormAnswer, User
from app.db.session import get_db
from app.web.deps import templates

router = APIRouter(prefix="/admin")


# ── フォーム一覧 ──────────────────────────────────────
@router.get("/checks", response_class=HTMLResponse)
def check_list(
    request: Request,
    frequency: str = "",
    target_role: str = "",
    is_active: str = "",
    db: Session = Depends(get_db),
):
    q = db.query(CheckForm).order_by(CheckForm.created_at.desc())
    if frequency:
        q = q.filter(CheckForm.frequency == frequency)
    if target_role:
        q = q.filter(CheckForm.target_role == target_role)
    if is_active != "":
        q = q.filter(CheckForm.is_active == int(is_active))
    forms = q.all()
    stats = {}
    for f in forms:
        total = db.query(CheckFormInstance).filter(CheckFormInstance.form_id == f.id).count()
        answered = db.query(CheckFormInstance).filter(
            CheckFormInstance.form_id == f.id,
            CheckFormInstance.status.in_(["answered", "evaluated"])
        ).count()
        q_count = db.query(CheckFormQuestion).filter(CheckFormQuestion.form_id == f.id).count()
        stats[f.id] = {"total": total, "answered": answered, "q_count": q_count}
    return templates.TemplateResponse(request, "admin/check/list.html", context={
        "forms": forms, "stats": stats,
        "filter_freq": frequency,
        "filter_role": target_role,
        "filter_active": is_active,
    })


# ── フォーム作成 ──────────────────────────────────────
@router.get("/checks/new", response_class=HTMLResponse)
def check_new_form(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == 1).all()
    return templates.TemplateResponse(request, "admin/check/form_edit.html", context={
        "form": None, "questions_data": [], "users": users, "title": "新規チェックフォーム作成"
    })


@router.post("/checks/new")
async def check_create(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    frequency: str = Form("monthly"),
    scheduled_month: str = Form(""),
    due_day: int = Form(25),
    target_role: str = Form("all"),
    is_active: int = Form(1),
    repeat_type: str = Form("monthly"),
    repeat_day: int = Form(25),
    repeat_nth_week: int = Form(0),
    repeat_nth_weekday: str = Form(""),
    repeat_once_date: str = Form(""),
    pass_score: int = Form(80),
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    # Collect weekdays from checkboxes
    wd_list = [wd for wd in ['mon','tue','wed','thu','fri','sat','sun'] if form_data.get(f'repeat_weekdays_{wd}')]
    repeat_weekdays = ','.join(wd_list)
    # Collect months from checkboxes
    m_list = [str(m) for m in range(1,13) if form_data.get(f'repeat_months_{m}')]
    repeat_months = ','.join(m_list)
    # For multi_month, use repeat_day_multi if provided
    if repeat_type == 'multi_month' and form_data.get('repeat_day_multi'):
        try:
            repeat_day = int(form_data.get('repeat_day_multi'))
        except (ValueError, TypeError):
            pass

    now = datetime.now().isoformat()
    form = CheckForm(
        id=str(uuid.uuid4()),
        title=title, description=description,
        frequency=frequency, scheduled_month=scheduled_month,
        due_day=due_day, target_role=target_role, is_active=is_active,
        repeat_type=repeat_type, repeat_weekdays=repeat_weekdays,
        repeat_day=repeat_day, repeat_nth_week=repeat_nth_week,
        repeat_nth_weekday=repeat_nth_weekday, repeat_months=repeat_months,
        repeat_once_date=repeat_once_date, pass_score=pass_score,
        created_at=now, updated_at=now,
    )
    db.add(form)
    db.commit()
    return RedirectResponse(f"/admin/checks/{form.id}", status_code=303)


# ── フォーム詳細・編集（質問管理） ───────────────────
@router.get("/checks/{form_id}", response_class=HTMLResponse)
def check_form_detail(form_id: str, request: Request, db: Session = Depends(get_db)):
    form = db.query(CheckForm).filter(CheckForm.id == form_id).first()
    if not form:
        return HTMLResponse("フォームが見つかりません", status_code=404)
    questions = db.query(CheckFormQuestion).filter(
        CheckFormQuestion.form_id == form_id
    ).order_by(CheckFormQuestion.order_no).all()
    users = db.query(User).filter(User.is_active == 1).all()

    questions_data = []
    for q in questions:
        try:
            opts = json.loads(q.options_json or "[]")
        except Exception:
            opts = []
        questions_data.append({"q": q, "opts": opts})

    return templates.TemplateResponse(request, "admin/check/form_edit.html", context={
        "form": form, "questions_data": questions_data, "users": users,
        "title": f"編集: {form.title}"
    })


@router.post("/checks/{form_id}/update")
async def check_form_update(
    form_id: str,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    frequency: str = Form("monthly"),
    scheduled_month: str = Form(""),
    due_day: int = Form(25),
    target_role: str = Form("all"),
    is_active: int = Form(1),
    repeat_type: str = Form("monthly"),
    repeat_day: int = Form(25),
    repeat_nth_week: int = Form(0),
    repeat_nth_weekday: str = Form(""),
    repeat_once_date: str = Form(""),
    pass_score: int = Form(80),
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    # Collect weekdays from checkboxes
    wd_list = [wd for wd in ['mon','tue','wed','thu','fri','sat','sun'] if form_data.get(f'repeat_weekdays_{wd}')]
    repeat_weekdays = ','.join(wd_list)
    # Collect months from checkboxes
    m_list = [str(m) for m in range(1,13) if form_data.get(f'repeat_months_{m}')]
    repeat_months = ','.join(m_list)
    # For multi_month, use repeat_day_multi if provided
    if repeat_type == 'multi_month' and form_data.get('repeat_day_multi'):
        try:
            repeat_day = int(form_data.get('repeat_day_multi'))
        except (ValueError, TypeError):
            pass

    form = db.query(CheckForm).filter(CheckForm.id == form_id).first()
    if form:
        form.title = title; form.description = description
        form.frequency = frequency; form.scheduled_month = scheduled_month
        form.due_day = due_day; form.target_role = target_role
        form.is_active = is_active
        form.repeat_type = repeat_type; form.repeat_weekdays = repeat_weekdays
        form.repeat_day = repeat_day; form.repeat_nth_week = repeat_nth_week
        form.repeat_nth_weekday = repeat_nth_weekday; form.repeat_months = repeat_months
        form.repeat_once_date = repeat_once_date; form.pass_score = pass_score
        form.updated_at = datetime.now().isoformat()
        db.commit()
    return RedirectResponse(f"/admin/checks/{form_id}", status_code=303)


@router.post("/checks/{form_id}/dispatch")
def check_form_dispatch(
    form_id: str,
    due_date: str = Form(""),
    db: Session = Depends(get_db),
):
    """フォームを対象ユーザー全員に今すぐ配信（CheckFormInstance を生成）。"""
    from datetime import date as date_cls
    form = db.query(CheckForm).filter(CheckForm.id == form_id).first()
    if not form:
        return RedirectResponse("/admin/checks", status_code=303)
    users = db.query(User).filter(User.is_active == 1).all()
    if form.target_role != "all":
        users = [u for u in users if u.role == form.target_role]
    now = datetime.now().isoformat()
    today_str = date_cls.today().isoformat()
    scheduled_date = today_str
    created = 0
    for u in users:
        existing = db.query(CheckFormInstance).filter(
            CheckFormInstance.form_id == form_id,
            CheckFormInstance.user_id == u.id,
            CheckFormInstance.status == "pending",
        ).first()
        if not existing:
            db.add(CheckFormInstance(
                id=str(uuid.uuid4()),
                form_id=form_id,
                user_id=u.id,
                due_date=due_date or "",
                status="pending",
                answer_token=str(uuid.uuid4()),
                scheduled_date=scheduled_date,
                created_at=now,
            ))
            created += 1
    db.commit()
    return RedirectResponse(f"/admin/checks/{form_id}", status_code=303)


@router.post("/checks/{form_id}/delete")
def check_form_delete(form_id: str, db: Session = Depends(get_db)):
    form = db.query(CheckForm).filter(CheckForm.id == form_id).first()
    if form:
        db.query(CheckFormQuestion).filter(CheckFormQuestion.form_id == form_id).delete()
        db.delete(form)
        db.commit()
    return RedirectResponse("/admin/checks", status_code=303)


@router.post("/checks/{form_id}/duplicate")
def check_form_duplicate(form_id: str, db: Session = Depends(get_db)):
    """フォームと質問を複製する（インスタンスはコピーしない）。"""
    form = db.query(CheckForm).filter(CheckForm.id == form_id).first()
    if not form:
        return RedirectResponse("/admin/checks", status_code=303)
    now = datetime.now().isoformat()
    new_form = CheckForm(
        id=str(uuid.uuid4()),
        title=form.title + " (コピー)",
        description=form.description,
        frequency=form.frequency,
        scheduled_month=form.scheduled_month,
        due_day=form.due_day,
        target_role=form.target_role,
        is_active=0,  # 複製は無効状態で作成
        repeat_type=form.repeat_type,
        repeat_weekdays=form.repeat_weekdays,
        repeat_day=form.repeat_day,
        repeat_nth_week=form.repeat_nth_week,
        repeat_nth_weekday=form.repeat_nth_weekday,
        repeat_months=form.repeat_months,
        repeat_once_date=form.repeat_once_date,
        pass_score=form.pass_score,
        created_at=now, updated_at=now,
    )
    db.add(new_form)
    db.flush()
    # 質問もコピー
    questions = db.query(CheckFormQuestion).filter(CheckFormQuestion.form_id == form_id).order_by(CheckFormQuestion.order_no).all()
    for q in questions:
        db.add(CheckFormQuestion(
            id=str(uuid.uuid4()),
            form_id=new_form.id,
            order_no=q.order_no,
            title=q.title, description=q.description,
            question_type=q.question_type,
            options_json=q.options_json,
            required=q.required,
            allow_file=q.allow_file,
            eval_type=q.eval_type,
            eval_criteria=q.eval_criteria,
            question_eval_type=getattr(q, 'question_eval_type', 'self'),
            score_weight=q.score_weight,
            correct_options_json=q.correct_options_json,
            pass_threshold=q.pass_threshold,
            created_at=now,
        ))
    db.commit()
    return RedirectResponse(f"/admin/checks/{new_form.id}", status_code=303)


# ── 質問追加 ──────────────────────────────────────────
@router.post("/checks/{form_id}/questions/add")
def add_question(
    form_id: str,
    title: str = Form(...),
    description: str = Form(""),
    question_type: str = Form("radio"),
    options_json: str = Form("[]"),
    required: int = Form(1),
    allow_file: int = Form(0),
    eval_type: str = Form("none"),
    eval_criteria: str = Form(""),
    question_eval_type: str = Form("self"),
    score_weight: int = Form(10),
    correct_options_json: str = Form("[]"),
    pass_threshold: int = Form(0),
    db: Session = Depends(get_db),
):
    if question_type in ("radio", "checkbox", "dropdown"):
        try:
            json.loads(options_json)  # already JSON
        except Exception:
            lines = [l.strip() for l in options_json.splitlines() if l.strip()]
            options_json = json.dumps(lines, ensure_ascii=False)
    else:
        options_json = "[]"

    # Normalize correct_options_json
    if correct_options_json:
        try:
            json.loads(correct_options_json)
        except Exception:
            items = [i.strip() for i in correct_options_json.split(',') if i.strip()]
            correct_options_json = json.dumps(items, ensure_ascii=False)
    else:
        correct_options_json = "[]"

    max_order = db.query(CheckFormQuestion).filter(
        CheckFormQuestion.form_id == form_id
    ).count()
    now = datetime.now().isoformat()
    db.add(CheckFormQuestion(
        id=str(uuid.uuid4()),
        form_id=form_id,
        order_no=max_order,
        title=title, description=description,
        question_type=question_type,
        options_json=options_json,
        required=required,
        allow_file=allow_file,
        eval_type=eval_type,
        eval_criteria=eval_criteria,
        question_eval_type=question_eval_type,
        score_weight=score_weight,
        correct_options_json=correct_options_json,
        pass_threshold=pass_threshold,
        created_at=now,
    ))
    db.commit()
    return RedirectResponse(f"/admin/checks/{form_id}", status_code=303)


# ── 質問削除 ──────────────────────────────────────────
@router.post("/checks/{form_id}/questions/{q_id}/delete")
def delete_question(form_id: str, q_id: str, db: Session = Depends(get_db)):
    q = db.query(CheckFormQuestion).filter(CheckFormQuestion.id == q_id).first()
    if q:
        db.delete(q)
        db.commit()
    return RedirectResponse(f"/admin/checks/{form_id}", status_code=303)


# ── 回答一覧 ──────────────────────────────────────────
@router.get("/checks/{form_id}/answers", response_class=HTMLResponse)
def form_answers(form_id: str, request: Request, db: Session = Depends(get_db)):
    form = db.query(CheckForm).filter(CheckForm.id == form_id).first()
    if not form:
        return HTMLResponse("Not found", status_code=404)
    questions = db.query(CheckFormQuestion).filter(
        CheckFormQuestion.form_id == form_id
    ).order_by(CheckFormQuestion.order_no).all()
    instances = db.query(CheckFormInstance).filter(
        CheckFormInstance.form_id == form_id
    ).order_by(CheckFormInstance.due_date.desc()).all()
    users_map = {u.id: u for u in db.query(User).all()}

    rows = []
    for inst in instances:
        answers = db.query(CheckFormAnswer).filter(
            CheckFormAnswer.instance_id == inst.id
        ).all()
        ans_map = {a.question_id: a for a in answers}
        # Compute scores
        total = 0
        max_total = 0
        for q in questions:
            max_total += q.score_weight or 0
            ans = ans_map.get(q.id)
            if ans:
                total += ans.score or 0
        pass_pct = round(total / max_total * 100) if max_total > 0 else None
        passed = pass_pct is not None and pass_pct >= (form.pass_score or 80)
        rows.append({
            "inst": inst,
            "user": users_map.get(inst.user_id),
            "ans_map": ans_map,
            "total_score": total,
            "max_score": max_total,
            "pass_pct": pass_pct,
            "passed": passed,
        })

    # Build monthly trend
    trend_months_set = set()
    user_monthly = defaultdict(lambda: defaultdict(lambda: {"total": 0, "passed": 0, "scores": []}))
    for row in rows:
        inst = row["inst"]
        month_key = (inst.due_date or inst.created_at or "")[:7]  # "2026-06"
        if month_key:
            trend_months_set.add(month_key)
            uid = inst.user_id
            user_monthly[uid][month_key]["total"] += 1
            if row.get("passed"):
                user_monthly[uid][month_key]["passed"] += 1
            if row.get("pass_pct") is not None:
                user_monthly[uid][month_key]["scores"].append(row["pass_pct"])

    trend_months = sorted(trend_months_set)
    trend_data = {}
    for uid, monthly in user_monthly.items():
        trend_data[uid] = {}
        for mkey, mdata in monthly.items():
            avg_score = round(sum(mdata["scores"]) / len(mdata["scores"])) if mdata["scores"] else 0
            trend_data[uid][mkey] = {
                "total": mdata["total"],
                "passed": mdata["passed"],
                "passed_pct": avg_score,
            }

    return templates.TemplateResponse(request, "admin/check/form_answers.html", context={
        "form": form,
        "questions": questions,
        "rows": rows,
        "users_map": users_map,
        "trend_data": trend_data,
        "trend_months": trend_months,
    })


# ── 管理者評価 ────────────────────────────────────────
@router.post("/checks/answers/{ans_id}/evaluate")
def evaluate_answer(
    ans_id: str,
    manager_result: str = Form(...),
    manager_comment: str = Form(""),
    request: Request = None,
    db: Session = Depends(get_db),
):
    ans = db.query(CheckFormAnswer).filter(CheckFormAnswer.id == ans_id).first()
    if ans:
        ans.manager_result = manager_result
        ans.manager_comment = manager_comment
        ans.manager_evaluated_at = datetime.now().isoformat()
        db.commit()
    referer = request.headers.get("referer", "/admin/checks") if request else "/admin/checks"
    return RedirectResponse(referer, status_code=303)
