"""ユーザーマイページ・運用チェックフォーム"""
import os, uuid, shutil, logging, json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import (
    User, Task, TaskInstance, TaskAssignee, Report,
    CheckInstance, CheckAnswer, CheckQuestion,
    CheckFormInstance, CheckFormAnswer, CheckFormQuestion, CheckForm,
    UserTask, UserTaskAssignee,
)
from app.db.session import get_db
from app.auth import get_current_user
from app.web.deps import templates, UPLOAD_DIR

router = APIRouter(prefix="/user")
logger = logging.getLogger(__name__)


# ── マイページ（セッション認証） ──────────────────────────
@router.get("/mypage", response_class=HTMLResponse)
def my_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login?next=/user/mypage", status_code=302)

    # ── 未完了タスク ──────────────────────────────────────
    assignee_task_ids = {a.task_id for a in db.query(TaskAssignee).filter(TaskAssignee.user_id == user.id).all()}
    pending_instances = db.query(TaskInstance).filter(
        TaskInstance.task_id.in_(assignee_task_ids),
        TaskInstance.status.in_(["pending", "in_progress"]),
    ).order_by(TaskInstance.due_date).all()

    tasks_map = {t.id: t for t in db.query(Task).all()}
    reports_map = {
        r.instance_id: r for r in
        db.query(Report).filter(Report.user_id == user.id).all()
    }

    pending_tasks = []
    for inst in pending_instances:
        task = tasks_map.get(inst.task_id)
        rep = reports_map.get(inst.id)
        if rep and rep.reported_at:
            continue  # 自分が報告済みなら未完了一覧に出さない
        pending_tasks.append({
            "instance": inst,
            "task": task,
            "report": rep,
            "report_url": f"/report/{rep.report_token}" if rep and rep.report_token else None,
        })

    # ── 個別タスク（UserTask）──────────────────────────────
    my_ut_assignees = db.query(UserTaskAssignee).filter(UserTaskAssignee.user_id == user.id).all()
    my_ut_assignees_map = {a.task_id: a for a in my_ut_assignees}
    ut_assignee_task_ids = set(my_ut_assignees_map.keys())
    # 自分がまだ完了していない個別タスクのみ表示
    pending_user_tasks = []
    if ut_assignee_task_ids:
        for ut in db.query(UserTask).filter(UserTask.id.in_(ut_assignee_task_ids)).order_by(UserTask.end_date).all():
            a = my_ut_assignees_map.get(ut.id)
            if a and not a.completed_at:
                pending_user_tasks.append(ut)

    # ── 未対応調査（旧: 自己申告）─────────────────────────
    # 旧 CheckInstance
    pending_old = db.query(CheckInstance).filter(
        CheckInstance.user_id == user.id,
        CheckInstance.status == "pending",
    ).order_by(CheckInstance.due_date).all()
    questions_map = {q.id: q for q in db.query(CheckQuestion).all()}

    pending_surveys = [
        {
            "title": questions_map[ci.question_id].title if ci.question_id in questions_map else "?",
            "due_date": ci.due_date,
            "answer_url": f"/user/check/{ci.answer_token}" if ci.answer_token else None,
        }
        for ci in pending_old
    ]

    # 新 CheckFormInstance
    pending_new = db.query(CheckFormInstance).filter(
        CheckFormInstance.user_id == user.id,
        CheckFormInstance.status == "pending",
    ).order_by(CheckFormInstance.due_date).all()
    forms_map = {f.id: f for f in db.query(CheckForm).all()}

    for fi in pending_new:
        form = forms_map.get(fi.form_id)
        pending_surveys.append({
            "title": form.title if form else "?",
            "due_date": fi.due_date,
            "answer_url": f"/user/check/{fi.answer_token}" if fi.answer_token else None,
        })

    # 期限順で並び替え
    pending_surveys.sort(key=lambda x: x["due_date"] or "")

    # ── 過去実績 ──────────────────────────────────────────
    # 完了タスク：自分が報告済みのもの（他の担当者の完了待ちでも表示）
    my_reports = db.query(Report).filter(
        Report.user_id == user.id,
        Report.reported_at.isnot(None),
    ).order_by(Report.reported_at.desc()).limit(20).all()

    past_tasks = []
    for rep in my_reports:
        inst = db.query(TaskInstance).filter(TaskInstance.id == rep.instance_id).first()
        if not inst:
            continue
        task = tasks_map.get(inst.task_id)
        past_tasks.append({
            "name": task.name if task else "?",
            "due_date": inst.due_date,
            "reported_at": rep.reported_at[:10] if rep.reported_at else None,
        })
    # 個別タスクの完了実績を追加
    for task_id, a in my_ut_assignees_map.items():
        if a.completed_at:
            ut = db.query(UserTask).filter(UserTask.id == task_id).first()
            past_tasks.append({
                "name": ut.title if ut else "?",
                "due_date": ut.end_date if ut else "",
                "reported_at": a.completed_at[:10],
            })
    past_tasks.sort(key=lambda x: x["reported_at"] or "", reverse=True)
    past_tasks = past_tasks[:20]

    # 過去の運用チェック回答（旧）
    past_old_inst = db.query(CheckInstance).filter(
        CheckInstance.user_id == user.id,
        CheckInstance.status.in_(["answered", "evaluated"]),
    ).order_by(CheckInstance.due_date.desc()).limit(20).all()

    old_inst_ids = {ci.id for ci in past_old_inst}
    answers_map_old = {a.instance_id: a for a in db.query(CheckAnswer).filter(CheckAnswer.instance_id.in_(old_inst_ids)).all()}

    past_surveys = []
    for ci in past_old_inst:
        ans = answers_map_old.get(ci.id)
        result = (ans.manager_result or ans.ai_result) if ans else None
        past_surveys.append({
            "title": questions_map[ci.question_id].title if ci.question_id in questions_map else "?",
            "due_date": ci.due_date,
            "result": result,
            "answered_at": ans.answered_at[:10] if ans and ans.answered_at else None,
        })

    # 過去の運用チェック回答（新）
    past_new_inst = db.query(CheckFormInstance).filter(
        CheckFormInstance.user_id == user.id,
        CheckFormInstance.status.in_(["answered", "evaluated"]),
    ).order_by(CheckFormInstance.due_date.desc()).limit(20).all()

    for fi in past_new_inst:
        form = forms_map.get(fi.form_id)
        # スコア率計算
        score_pct = None
        if fi.max_score and fi.max_score > 0:
            score_pct = round(fi.total_score / fi.max_score * 100)
        past_surveys.append({
            "title": form.title if form else "?",
            "due_date": fi.due_date,
            "result": "ok" if (score_pct is not None and score_pct >= (form.pass_score if form else 80)) else ("ng" if score_pct is not None else None),
            "answered_at": fi.due_date,
            "score_pct": score_pct,
        })

    past_surveys.sort(key=lambda x: x["due_date"] or "", reverse=True)
    past_surveys = past_surveys[:20]

    return templates.TemplateResponse(request, "user/mypage.html", context={
        "user": user,
        "pending_tasks": pending_tasks,
        "pending_user_tasks": pending_user_tasks,
        "pending_surveys": pending_surveys,
        "past_tasks": past_tasks,
        "past_surveys": past_surveys,
    })


# ── タスクインスタンス：着手 ──────────────────────────────
@router.post("/task-start")
def task_instance_start(
    request: Request,
    instance_id: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    inst = db.query(TaskInstance).filter(TaskInstance.id == instance_id).first()
    redirect_url = "/user/mypage"
    if inst:
        task = db.query(Task).filter(Task.id == inst.task_id).first()
        if task and task.url:
            redirect_url = task.url
        if inst.status == "pending":
            assignee_ids = {a.user_id for a in db.query(TaskAssignee).filter(TaskAssignee.task_id == inst.task_id).all()}
            if user.id in assignee_ids:
                inst.status = "in_progress"
                db.commit()

    return RedirectResponse(redirect_url, status_code=303)


# ── タスクインスタンス：完了報告 ─────────────────────────
@router.post("/task-complete")
def task_instance_complete(
    request: Request,
    instance_id: str = Form(...),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    inst = db.query(TaskInstance).filter(TaskInstance.id == instance_id).first()
    if not inst:
        return RedirectResponse("/user/mypage", status_code=303)

    assignee_ids = {a.user_id for a in db.query(TaskAssignee).filter(TaskAssignee.task_id == inst.task_id).all()}
    if user.id not in assignee_ids:
        return RedirectResponse("/user/mypage", status_code=303)

    # Report レコードを取得または作成
    rep = db.query(Report).filter(Report.instance_id == instance_id, Report.user_id == user.id).first()
    if not rep:
        rep = Report(
            id=str(uuid.uuid4()),
            instance_id=instance_id,
            user_id=user.id,
            report_token=str(uuid.uuid4()),
        )
        db.add(rep)

    if not rep.reported_at:
        now = datetime.now().isoformat()
        rep.reported_at = now
        rep.comment = comment

        if inst.status == "pending":
            inst.status = "in_progress"

        db.flush()

        # 全担当者が報告済みなら completed に
        reported_ids = {
            r.user_id for r in db.query(Report)
            .filter(Report.instance_id == instance_id, Report.reported_at.isnot(None))
            .all()
        }
        if assignee_ids.issubset(reported_ids):
            inst.status = "completed"
            logger.info(f"タスクインスタンス {instance_id} が完了しました。")

        db.commit()

    return RedirectResponse("/user/mypage", status_code=303)


# ── 個別タスク（UserTask）：着手 ─────────────────────────
@router.post("/user-task-start")
def user_task_start(
    request: Request,
    task_id: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    task = db.query(UserTask).filter(UserTask.id == task_id).first()
    redirect_url = task.url if task and task.url else "/user/mypage"
    return RedirectResponse(redirect_url, status_code=303)


# ── 個別タスク（UserTask）：完了報告 ────────────────────
@router.post("/user-task-done")
def user_task_done(
    request: Request,
    task_id: str = Form(...),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    assignees = db.query(UserTaskAssignee).filter(UserTaskAssignee.task_id == task_id).all()
    my_assignee = next((a for a in assignees if a.user_id == user.id), None)
    if not my_assignee or my_assignee.completed_at:
        return RedirectResponse("/user/mypage", status_code=303)

    now = datetime.now().isoformat()
    my_assignee.comment = comment
    my_assignee.completed_at = now
    db.flush()

    # 全員完了したら task.status → "done"
    all_done = all(a.completed_at for a in assignees)
    task = db.query(UserTask).filter(UserTask.id == task_id).first()
    if task and all_done:
        task.status = "done"
        task.updated_at = now
    db.commit()
    return RedirectResponse("/user/mypage", status_code=303)


# ── 運用チェックフォーム ──────────────────────────────────
@router.get("/check/{token}", response_class=HTMLResponse)
def check_form(token: str, request: Request, db: Session = Depends(get_db)):
    # 新 CheckFormInstance
    form_inst = db.query(CheckFormInstance).filter(CheckFormInstance.answer_token == token).first()
    if form_inst:
        form = db.query(CheckForm).filter(CheckForm.id == form_inst.form_id).first()
        questions = db.query(CheckFormQuestion).filter(
            CheckFormQuestion.form_id == form_inst.form_id
        ).order_by(CheckFormQuestion.order_no).all()
        user = db.query(User).filter(User.id == form_inst.user_id).first()
        already_answered = form_inst.status in ("answered", "evaluated")
        answers = db.query(CheckFormAnswer).filter(CheckFormAnswer.instance_id == form_inst.id).all()
        ans_map = {a.question_id: a for a in answers}

        questions_data = []
        for q in questions:
            try:
                opts = json.loads(q.options_json or "[]")
            except Exception:
                opts = []
            questions_data.append({"q": q, "opts": opts})
        return templates.TemplateResponse(request, "user/check_form_new.html", context={
            "form_inst": form_inst, "form": form, "questions_data": questions_data,
            "user": user, "already_answered": already_answered, "ans_map": ans_map,
        })

    # 旧 CheckInstance
    ci = db.query(CheckInstance).filter(CheckInstance.answer_token == token).first()
    if not ci:
        return HTMLResponse("無効なURLです", status_code=404)

    question = db.query(CheckQuestion).filter(CheckQuestion.id == ci.question_id).first()
    user = db.query(User).filter(User.id == ci.user_id).first()
    already_answered = ci.status in ("answered", "evaluated")
    answer = db.query(CheckAnswer).filter(CheckAnswer.instance_id == ci.id).first()

    return templates.TemplateResponse(request, "user/check_form.html", context={
        "ci": ci, "question": question, "user": user,
        "already_answered": already_answered, "answer": answer,
    })


@router.post("/check/{token}")
async def check_submit(
    token: str,
    request: Request,
    answer_text: str = Form(""),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    # 新 CheckFormInstance
    form_inst = db.query(CheckFormInstance).filter(CheckFormInstance.answer_token == token).first()
    if form_inst:
        if form_inst.status in ("answered", "evaluated"):
            return RedirectResponse(f"/user/check/{token}", status_code=303)
        form_data = await request.form()
        questions = db.query(CheckFormQuestion).filter(
            CheckFormQuestion.form_id == form_inst.form_id
        ).order_by(CheckFormQuestion.order_no).all()
        now = datetime.now().isoformat()

        for q in questions:
            field_name = f"q_{q.id}"
            if q.question_type == "checkbox":
                vals = form_data.getlist(field_name)
                db.add(CheckFormAnswer(
                    id=str(uuid.uuid4()),
                    instance_id=form_inst.id,
                    question_id=q.id,
                    user_id=form_inst.user_id,
                    answer_value="",
                    answer_values_json=json.dumps(vals, ensure_ascii=False),
                    answered_at=now,
                ))
            else:
                val = form_data.get(field_name, "")
                db.add(CheckFormAnswer(
                    id=str(uuid.uuid4()),
                    instance_id=form_inst.id,
                    question_id=q.id,
                    user_id=form_inst.user_id,
                    answer_value=str(val),
                    answered_at=now,
                ))
        form_inst.status = "answered"
        db.commit()
        return RedirectResponse(f"/user/check/{token}", status_code=303)

    # 旧 CheckInstance
    ci = db.query(CheckInstance).filter(CheckInstance.answer_token == token).first()
    if not ci or ci.status in ("answered", "evaluated"):
        return RedirectResponse(f"/user/check/{token}", status_code=303)

    question = db.query(CheckQuestion).filter(CheckQuestion.id == ci.question_id).first()
    now = datetime.now().isoformat()

    image_path = None
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1]
        filename = f"{ci.id}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        with open(save_path, "wb") as f:
            shutil.copyfileobj(image.file, f)
        image_path = f"/uploads/{filename}"

    answer = CheckAnswer(
        id=str(uuid.uuid4()),
        instance_id=ci.id,
        user_id=ci.user_id,
        answer_text=answer_text,
        image_path=image_path,
        answered_at=now,
    )
    db.add(answer)
    ci.status = "answered"
    db.flush()

    if question and question.eval_type == "ai":
        _run_ai_evaluation(answer, question, image_path)
        ci.status = "evaluated"

    db.commit()
    return RedirectResponse(f"/user/check/{token}", status_code=303)


# ── 評価者評価 ────────────────────────────────────────────
@router.get("/manager-eval", response_class=HTMLResponse)
def manager_eval_get(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login?next=/user/manager-eval", status_code=302)
    if not user.is_manager:
        return HTMLResponse("権限がありません", status_code=403)

    subordinates = db.query(User).filter(
        User.org_name == user.org_name,
        User.id != user.id,
        User.is_active == 1,
    ).all()

    # マネージャー自身に割り当てられた pending インスタンスを取得
    instances = db.query(CheckFormInstance).filter(
        CheckFormInstance.user_id == user.id,
        CheckFormInstance.status == "pending",
    ).all()

    eval_items = []
    for inst in instances:
        form = db.query(CheckForm).filter(CheckForm.id == inst.form_id).first()
        if not form:
            continue
        questions = db.query(CheckFormQuestion).filter(
            CheckFormQuestion.form_id == inst.form_id,
            CheckFormQuestion.question_eval_type == "manager",
        ).order_by(CheckFormQuestion.order_no).all()
        if not questions:
            continue

        # 既存回答マップ: (instance_id, question_id, target_user_id) -> CheckFormAnswer
        existing_answers = db.query(CheckFormAnswer).filter(
            CheckFormAnswer.instance_id == inst.id,
            CheckFormAnswer.evaluator_id == user.id,
        ).all()
        answers_map = {(a.instance_id, a.question_id, a.target_user_id): a for a in existing_answers}

        # options マップ: question_id -> list[str]
        opts_map = {}
        for q in questions:
            try:
                opts_map[q.id] = json.loads(q.options_json or "[]")
            except Exception:
                opts_map[q.id] = []

        eval_items.append({
            "form": form,
            "instance": inst,
            "questions": questions,
            "answers_map": answers_map,
            "opts_map": opts_map,
        })

    return templates.TemplateResponse(request, "user/manager_eval.html", context={
        "user": user,
        "subordinates": subordinates,
        "eval_items": eval_items,
    })


@router.post("/manager-eval")
async def manager_eval_post(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login?next=/user/manager-eval", status_code=302)
    if not user.is_manager:
        return HTMLResponse("権限がありません", status_code=403)

    form_data = await request.form()
    instance_id = form_data.get("instance_id", "")
    inst = db.query(CheckFormInstance).filter(
        CheckFormInstance.id == instance_id,
        CheckFormInstance.user_id == user.id,
    ).first()
    if not inst:
        return RedirectResponse("/user/mypage", status_code=303)

    subordinates = db.query(User).filter(
        User.org_name == user.org_name,
        User.id != user.id,
        User.is_active == 1,
    ).all()

    questions = db.query(CheckFormQuestion).filter(
        CheckFormQuestion.form_id == inst.form_id,
        CheckFormQuestion.question_eval_type == "manager",
    ).all()

    now = datetime.now().isoformat()
    for q in questions:
        for sub in subordinates:
            field_name = f"ans_{q.id}_{sub.id}"
            val = form_data.get(field_name, "")
            if not val:
                continue
            # 既存チェック
            existing = db.query(CheckFormAnswer).filter(
                CheckFormAnswer.instance_id == inst.id,
                CheckFormAnswer.question_id == q.id,
                CheckFormAnswer.target_user_id == sub.id,
                CheckFormAnswer.evaluator_id == user.id,
            ).first()
            if existing:
                existing.answer_value = str(val)
                existing.answered_at = now
            else:
                db.add(CheckFormAnswer(
                    id=str(uuid.uuid4()),
                    instance_id=inst.id,
                    question_id=q.id,
                    user_id=user.id,
                    evaluator_id=user.id,
                    target_user_id=sub.id,
                    answer_value=str(val),
                    answered_at=now,
                ))

    inst.status = "answered"
    db.commit()
    return RedirectResponse("/user/mypage", status_code=303)


def _run_ai_evaluation(answer: CheckAnswer, question: CheckQuestion, image_path: Optional[str]):
    """OpenAI GPT-4o-mini（ビジョン対応）で回答をOK/NG判定する。"""
    try:
        import base64
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        criteria = question.ai_criteria or "内容を確認してOK/NGを判定してください。"
        text_part = (
            f"質問: {question.title}\n"
            f"判定基準: {criteria}\n"
        )
        if answer.answer_text:
            text_part += f"回答: {answer.answer_text}\n"
        text_part += "\nOKまたはNGで判定し、理由を1〜2文で説明してください。最初の行に「OK」または「NG」とだけ書いてください。"

        content = []
        if image_path:
            full_path = os.path.abspath(os.path.join(UPLOAD_DIR, os.path.basename(image_path)))
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    img_data = base64.standard_b64encode(f.read()).decode()
                ext = os.path.splitext(full_path)[1].lower()
                media_type = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
                }.get(ext, "image/png")
                content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_data}"}})

        content.append({"type": "text", "text": text_part})

        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            max_tokens=300,
            messages=[{"role": "user", "content": content}],
        )
        result_text = resp.choices[0].message.content.strip()
        first_line = result_text.split("\n")[0].strip().upper()
        answer.ai_result = "ok" if "OK" in first_line else "ng"
        answer.ai_comment = result_text
        answer.ai_evaluated_at = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"AI評価失敗: {e}")
        answer.ai_result = "pending"
        answer.ai_comment = f"AI評価エラー: {e}"
