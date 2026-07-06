"""モックデータ一括投入スクリプト"""
import sys, os, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from app.db.models import (
    Base, User, Task, TaskAssignee, TaskInstance, Report,
    EscalationLog, NotificationQueue, HrEvent,
    CheckQuestion, CheckInstance, CheckAnswer,
    get_engine,
)

engine = get_engine("isms.db")
Base.metadata.create_all(engine)

def uid(): return str(uuid.uuid4())
def now(): return datetime.now().isoformat()
def dstr(d): return d.isoformat()
today = date.today()

with Session(engine) as db:

    # ── 既存データ削除（tasks以外）──────────────────────────
    for model in [CheckAnswer, CheckInstance, CheckQuestion,
                  EscalationLog, Report, NotificationQueue,
                  TaskInstance, TaskAssignee, HrEvent, User]:
        db.query(model).delete()
    db.commit()

    # ── ユーザー ─────────────────────────────────────────
    users = [
        User(id=uid(), name="武廣 太郎",   google_chat_user_id="users/111111111", role="admin",  is_active=1),
        User(id=uid(), name="橋元 花子",   google_chat_user_id="users/222222222", role="member", is_active=1),
        User(id=uid(), name="田中 一郎",   google_chat_user_id="users/333333333", role="member", is_active=1),
        User(id=uid(), name="鈴木 美咲",   google_chat_user_id="users/444444444", role="member", is_active=1),
        User(id=uid(), name="佐藤 健二",   google_chat_user_id="users/555555555", role="member", is_active=1),
    ]
    for u in users: db.add(u)
    db.flush()
    admin, hanako, tanaka, suzuki, sato = users

    # ── タスクにアサイン ───────────────────────────────────
    tasks = db.query(Task).all()
    assignee_pairs = []
    for i, task in enumerate(tasks):
        member = [hanako, tanaka, suzuki, sato][i % 4]
        assignee_pairs.append((task, member))
        if i % 5 == 0:
            assignee_pairs.append((task, tanaka))

    for task, member in assignee_pairs:
        db.add(TaskAssignee(id=uid(), task_id=task.id, user_id=member.id, created_at=now()))
    db.flush()

    # ── タスクインスタンス ────────────────────────────────
    instance_data = []

    # 完了済み（過去）
    for task in tasks[:8]:
        due = dstr(today - timedelta(days=30 + (tasks.index(task) * 3)))
        inst = TaskInstance(id=uid(), task_id=task.id, due_date=due,
                            status="completed", triggered_by="schedule", created_at=now())
        db.add(inst)
        instance_data.append((inst, task, "completed"))

    # 進行中（今月期限）
    for task in tasks[8:16]:
        due = dstr(today + timedelta(days=(tasks.index(task) % 14) + 1))
        inst = TaskInstance(id=uid(), task_id=task.id, due_date=due,
                            status="in_progress", triggered_by="schedule", created_at=now())
        db.add(inst)
        instance_data.append((inst, task, "in_progress"))

    # 期限切れ・エスカレーション中
    for task in tasks[16:20]:
        due = dstr(today - timedelta(days=5 + tasks.index(task)))
        inst = TaskInstance(id=uid(), task_id=task.id, due_date=due,
                            status="escalated", triggered_by="schedule", created_at=now())
        db.add(inst)
        instance_data.append((inst, task, "escalated"))

    # pending（来月）
    for task in tasks[20:25]:
        due = dstr(today + timedelta(days=20 + tasks.index(task)))
        inst = TaskInstance(id=uid(), task_id=task.id, due_date=due,
                            status="pending", triggered_by="schedule", created_at=now())
        db.add(inst)
        instance_data.append((inst, task, "pending"))

    db.flush()

    # ── 完了報告（completedインスタンスに） ──────────────
    member_list = [hanako, tanaka, suzuki, sato]
    for inst, task, status in instance_data:
        assignees_for_task = [p[1] for p in assignee_pairs if p[0].id == task.id]
        for i, member in enumerate(assignees_for_task):
            token = uid()
            reported_at = None
            if status == "completed":
                reported_at = dstr(today - timedelta(days=28 - i))
            elif status == "in_progress" and i == 0:
                reported_at = dstr(today - timedelta(days=2))
            db.add(Report(
                id=uid(), instance_id=inst.id, user_id=member.id,
                comment="確認しました。対応完了です。" if reported_at else None,
                reported_at=reported_at, report_token=token,
            ))

    db.flush()

    # ── エスカレーションログ ──────────────────────────────
    for inst, task, status in instance_data:
        if status == "escalated":
            db.add(EscalationLog(id=uid(), instance_id=inst.id,
                                 user_id=tanaka.id, level=1,
                                 sent_at=dstr(today - timedelta(days=3))))
            db.add(EscalationLog(id=uid(), instance_id=inst.id,
                                 user_id=tanaka.id, level=2,
                                 sent_at=dstr(today - timedelta(days=1))))

    # ── 通知キュー ────────────────────────────────────────
    queue_items = [
        ("【ISMS】「パスワードポリシー確認」の期限が3日後に迫っています。\n✅ 完了報告: http://localhost:8000/report/xxx", "dm",    hanako.id,  "draft"),
        ("【ISMS】「アクセス権限レビュー」の実施をお願いします。期限: 今週金曜", "dm",    tanaka.id,  "draft"),
        ("【週次サマリー】今週期限のタスクが5件あります。ご確認ください。",       "group",  admin.id,   "draft"),
        ("【リマインド】「セキュリティ教育実施」の期限まで7日です。",            "dm",    suzuki.id,  "approved"),
        ("【エスカレーション】「脆弱性対応記録」が5日間未完了です。",            "group",  admin.id,   "sent"),
    ]
    for msg, stype, target, status in queue_items:
        db.add(NotificationQueue(
            id=uid(), instance_id=None, target_user_id=target,
            space_type=stype, message_body=msg, status=status,
            scheduled_at=now(), created_at=now(),
        ))

    # ── 入退社イベント ────────────────────────────────────
    db.add(HrEvent(id=uid(), user_id=sato.id,   event_type="hire",       event_date=dstr(today + timedelta(days=10)), created_at=now()))
    db.add(HrEvent(id=uid(), user_id=suzuki.id, event_type="retirement", event_date=dstr(today + timedelta(days=30)), created_at=now()))

    # ── 自己申告 質問 ────────────────────────────────────
    questions = [
        CheckQuestion(id=uid(), title="デスクトップの整理整頓",
                      description="デスクトップに業務データ・個人ファイルが放置されていないか確認してください。",
                      answer_type="image", eval_type="ai",
                      ai_criteria="デスクトップにショートカット・ゴミ箱以外のファイルやフォルダが見えていたらNG。整理されていればOK。",
                      frequency="monthly", target_role="member", is_active=1, created_at=now(), updated_at=now()),
        CheckQuestion(id=uid(), title="画面ロックの設定確認",
                      description="離席時に自動で画面ロックがかかる設定になっているか確認してください。",
                      answer_type="yes_no", eval_type="manager",
                      frequency="quarterly", target_role="all", is_active=1, created_at=now(), updated_at=now()),
        CheckQuestion(id=uid(), title="パスワードの定期変更",
                      description="主要システムのパスワードを直近3ヶ月以内に変更しましたか？",
                      answer_type="yes_no", eval_type="ai",
                      ai_criteria="はい（yes）と回答していればOK。いいえ（no）の場合はNG。",
                      frequency="quarterly", target_role="member", is_active=1, created_at=now(), updated_at=now()),
        CheckQuestion(id=uid(), title="不審メール対応の自己確認",
                      description="今月、不審なメール・フィッシングと思われるメールを受け取った場合、適切に報告・対応しましたか？",
                      answer_type="text", eval_type="manager",
                      frequency="monthly", target_role="all", is_active=1, created_at=now(), updated_at=now()),
        CheckQuestion(id=uid(), title="施錠確認（退勤時）",
                      description="退勤時にキャビネット・引き出しの施錠を毎日実施していますか？",
                      answer_type="yes_no", eval_type="manager",
                      frequency="monthly", target_role="member", is_active=1, created_at=now(), updated_at=now()),
    ]
    for q in questions: db.add(q)
    db.flush()
    q_desktop, q_lock, q_pw, q_mail, q_key = questions

    # ── 自己申告インスタンス・回答 ────────────────────────
    check_scenarios = [
        # (question, user, status, answer_text, ai_result, manager_result)
        (q_desktop, hanako, "evaluated", None,     "ok",  None,   "デスクトップが整理されており問題なし"),
        (q_desktop, tanaka, "evaluated", None,     "ng",  None,   "複数のファイルがデスクトップに散乱しています。整理してください。"),
        (q_desktop, suzuki, "answered",  None,     None,  None,   None),
        (q_lock,    hanako, "evaluated", "yes",    None,  "ok",   None),
        (q_lock,    tanaka, "evaluated", "no",     None,  "ng",   "設定されていない場合は速やかに対応してください"),
        (q_lock,    sato,   "pending",   None,     None,  None,   None),
        (q_pw,      hanako, "evaluated", "yes",    "ok",  None,   None),
        (q_pw,      suzuki, "evaluated", "no",     "ng",  None,   "パスワードを変更していない場合は早急に対応してください"),
        (q_mail,    hanako, "evaluated", "今月は不審メールなし。念のためIT部門に確認済み。", None, "ok", "適切な対応です"),
        (q_mail,    tanaka, "answered",  "特に問題のあるメールはなかった。",                None, None, None),
        (q_key,     hanako, "evaluated", "yes",    None,  "ok",   None),
        (q_key,     sato,   "pending",   None,     None,  None,   None),
    ]

    for q, user, ci_status, ans_text, ai_res, mgr_res, comment in check_scenarios:
        token = uid()
        due = dstr(today - timedelta(days=5) if ci_status != "pending" else today + timedelta(days=10))
        ci = CheckInstance(id=uid(), question_id=q.id, user_id=user.id,
                           due_date=due, status=ci_status, answer_token=token, created_at=now())
        db.add(ci)
        db.flush()

        if ci_status in ("answered", "evaluated"):
            img_path = "/uploads/mock_screenshot.png" if q.answer_type == "image" else None
            ans = CheckAnswer(
                id=uid(), instance_id=ci.id, user_id=user.id,
                answer_text=ans_text, image_path=img_path,
                answered_at=dstr(today - timedelta(days=3)),
                ai_result=ai_res,
                ai_comment=comment if ai_res else None,
                ai_evaluated_at=now() if ai_res else None,
                manager_result=mgr_res,
                manager_comment=comment if mgr_res else None,
                manager_evaluated_at=now() if mgr_res else None,
            )
            db.add(ans)

    db.commit()

    import sqlite3, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("[OK] モックデータ投入完了!")
    print()
    conn = sqlite3.connect("isms.db")
    tables = ["users","task_instances","reports","notification_queue",
              "hr_events","check_questions","check_instances","check_answers","escalation_logs"]
    for t in tables:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {cnt}件")
    print()
    print("-- ユーザーマイページURL --")
    rows = conn.execute("SELECT id, name FROM users").fetchall()
    for r in rows:
        print(f"  {r[1]}: http://localhost:8000/user/{r[0]}")
