"""
テストデータ挿入スクリプト
実行方法: python insert_test_data.py
"""
import sys
import os
import uuid
import json
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(__file__))

import bcrypt

from app.db.init_db import init_db
from app.db.session import get_session_factory
from app.db.models import (
    User, Task, TaskAssignee, TaskInstance, Report,
    CheckForm, CheckFormQuestion, CheckFormInstance, CheckFormAnswer,
    AdminTask, Service, UserService, Asset, AssetInventory,
)

DB_PATH = "isms.db"


def now_iso():
    return datetime.now().isoformat()


def date_iso(y, m, d):
    return date(y, m, d).isoformat()


def uid():
    return str(uuid.uuid4())


def hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ─── メインデータ定義 ────────────────────────────────────────────

USERS_DATA = [
    {"name": "山田 太郎", "login_id": "yamada.taro", "role": "admin",
     "emp_type": "正社員", "org_name": "情報システム部", "is_manager": 1,
     "google_chat_user_id": "users/123456"},
    {"name": "佐藤 花子", "login_id": "sato.hanako", "role": "member",
     "emp_type": "正社員", "org_name": "情報システム部", "is_manager": 0,
     "google_chat_user_id": None},
    {"name": "鈴木 一郎", "login_id": "suzuki.ichiro", "role": "member",
     "emp_type": "契約社員/嘱託社員", "org_name": "営業部", "is_manager": 0,
     "google_chat_user_id": None},
    {"name": "田中 美咲", "login_id": "tanaka.misaki", "role": "member",
     "emp_type": "正社員", "org_name": "総務部", "is_manager": 1,
     "google_chat_user_id": None},
    {"name": "高橋 健二", "login_id": "takahashi.kenji", "role": "admin",
     "emp_type": "正社員", "org_name": "情報システム部", "is_manager": 0,
     "google_chat_user_id": None},
]

TASKS_DATA = [
    {
        "wbs_no": "T-001", "category": "定期", "phase": "定期イベント",
        "name": "情報セキュリティ研修",
        "description": "全社員を対象とした情報セキュリティ研修の実施・受講確認",
        "frequency": "年次", "scheduled_month": "6", "due_day": 30,
        "execution_mode": "approve", "completion_rule": "all",
        "notify_space": "dm", "remind_days_before": "14,7,3",
        "escalation_days": "3,7,14", "is_active": 1,
    },
    {
        "wbs_no": "T-002", "category": "定期", "phase": "定常業務",
        "name": "アクセスログ確認",
        "description": "社内システムのアクセスログを確認し、不審なアクセスがないか点検する",
        "frequency": "月次", "scheduled_month": "1,2,3,4,5,6,7,8,9,10,11,12",
        "due_day": 25, "execution_mode": "auto", "completion_rule": "any",
        "notify_space": "dm", "remind_days_before": "7,3",
        "escalation_days": "3,7", "is_active": 1,
    },
    {
        "wbs_no": "T-003", "category": "定期", "phase": "定期イベント",
        "name": "脆弱性診断の実施",
        "description": "Webシステムおよびネットワークの脆弱性診断を実施する",
        "frequency": "半期", "scheduled_month": "4,10", "due_day": 28,
        "execution_mode": "approve", "completion_rule": "all",
        "notify_space": "group", "remind_days_before": "14,7,3",
        "escalation_days": "3,7,14", "is_active": 1,
    },
    {
        "wbs_no": "T-004", "category": "定期", "phase": "定常業務",
        "name": "バックアップ確認",
        "description": "データバックアップの正常完了と復元可能性を確認する",
        "frequency": "月次", "scheduled_month": "1,2,3,4,5,6,7,8,9,10,11,12",
        "due_day": 15, "execution_mode": "auto", "completion_rule": "any",
        "notify_space": "dm", "remind_days_before": "7,3",
        "escalation_days": "3,7", "is_active": 1,
    },
    {
        "wbs_no": "T-005", "category": "トリガー", "phase": "随時業務",
        "name": "新入社員アカウント作成",
        "description": "入社者のGoogle Workspace・社内システムアカウントを作成し、初期設定を行う",
        "frequency": "随時", "scheduled_month": "", "due_day": 0,
        "execution_mode": "approve", "completion_rule": "all",
        "notify_space": "dm", "remind_days_before": "3",
        "escalation_days": "1,3", "is_active": 1,
    },
]

FORMS_DATA = [
    {
        "title": "月次セキュリティセルフチェック",
        "description": "毎月の情報セキュリティ遵守状況を確認するチェックです",
        "frequency": "monthly", "repeat_type": "monthly",
        "repeat_day": 25, "due_day": 25, "target_role": "all",
        "pass_score": 80, "is_active": 1,
        "repeat_months": "", "scheduled_month": "",
    },
    {
        "title": "四半期リスクアセスメント",
        "description": "四半期ごとのリスク評価チェックリストです",
        "frequency": "quarterly", "repeat_type": "multi_month",
        "repeat_months": "3,6,9,12", "repeat_day": 20,
        "due_day": 20, "target_role": "all", "pass_score": 70,
        "is_active": 1, "scheduled_month": "3,6,9,12",
    },
]

MONTHLY_QUESTIONS = [
    {
        "order_no": 1,
        "title": "デスクトップやダウンロードフォルダに個人情報を含むファイルを放置していませんか？",
        "description": "",
        "question_type": "radio",
        "options_json": json.dumps(["はい（放置していない）", "いいえ（放置している）"], ensure_ascii=False),
        "correct_options_json": json.dumps(["はい（放置していない）"], ensure_ascii=False),
        "score_weight": 30,
        "eval_type": "none",
        "question_eval_type": "self",
        "required": 1,
    },
    {
        "order_no": 2,
        "title": "パスワードは他者と共有していませんか？",
        "description": "",
        "question_type": "radio",
        "options_json": json.dumps(["はい（共有していない）", "いいえ（共有している）"], ensure_ascii=False),
        "correct_options_json": json.dumps(["はい（共有していない）"], ensure_ascii=False),
        "score_weight": 40,
        "eval_type": "none",
        "question_eval_type": "self",
        "required": 1,
    },
    {
        "order_no": 3,
        "title": "業務用PCを離席する際はスクリーンロックをしていますか？",
        "description": "",
        "question_type": "radio",
        "options_json": json.dumps(["常に実施", "時々し忘れる", "ほとんどしていない"], ensure_ascii=False),
        "correct_options_json": json.dumps(["常に実施"], ensure_ascii=False),
        "score_weight": 30,
        "eval_type": "none",
        "question_eval_type": "self",
        "required": 1,
    },
]

QUARTERLY_QUESTIONS = [
    {
        "order_no": 1,
        "title": "担当システムのアクセス権限は最小権限の原則に基づいて付与されていますか？",
        "description": "不要な権限が残存していないかも確認してください",
        "question_type": "radio",
        "options_json": json.dumps(["はい、適切に管理されている", "一部見直しが必要", "見直しできていない"], ensure_ascii=False),
        "correct_options_json": json.dumps(["はい、適切に管理されている"], ensure_ascii=False),
        "score_weight": 40,
        "eval_type": "none",
        "question_eval_type": "self",
        "required": 1,
    },
    {
        "order_no": 2,
        "title": "過去四半期でセキュリティインシデントやヒヤリハット事例はありましたか？",
        "description": "",
        "question_type": "radio",
        "options_json": json.dumps(["なし", "あり（報告済み）", "あり（未報告）"], ensure_ascii=False),
        "correct_options_json": json.dumps(["なし", "あり（報告済み）"], ensure_ascii=False),
        "score_weight": 30,
        "eval_type": "none",
        "question_eval_type": "self",
        "required": 1,
    },
    {
        "order_no": 3,
        "title": "社外秘情報の取り扱い手順を遵守していますか？",
        "description": "メール誤送信・クラウドストレージの共有設定なども含めて確認してください",
        "question_type": "radio",
        "options_json": json.dumps(["常に遵守している", "概ね遵守している", "遵守できていない"], ensure_ascii=False),
        "correct_options_json": json.dumps(["常に遵守している", "概ね遵守している"], ensure_ascii=False),
        "score_weight": 30,
        "eval_type": "none",
        "question_eval_type": "self",
        "required": 1,
    },
]

ADMIN_TASKS_DATA = [
    {
        "title": "Google Workspaceアカウント停止",
        "description": "退職者のGoogleアカウントを停止してください",
        "status": "open", "priority": "high", "trigger_event": "retired",
        "related_user_name": "前田 二郎", "due_date": "2026-06-20",
    },
    {
        "title": "社内Slackアカウント無効化",
        "description": "退職者のSlackアカウントを無効化してください",
        "status": "in_progress", "priority": "high", "trigger_event": "retired",
        "related_user_name": "前田 二郎", "due_date": "2026-06-20",
    },
    {
        "title": "貸与PC回収",
        "description": "退職者から会社貸与PCを回収し、初期化を実施してください",
        "status": "done", "priority": "medium", "trigger_event": "retired",
        "related_user_name": "前田 二郎", "due_date": "2026-06-18",
    },
    {
        "title": "産休中のアクセス権限確認",
        "description": "休職中のメンバーのシステムアクセス権限を確認・制限してください",
        "status": "open", "priority": "medium", "trigger_event": "leave",
        "related_user_name": "小林 直子", "due_date": "2026-06-30",
    },
]

SERVICES_DATA = [
    {"name": "Google Workspace", "sort_order": 1},
    {"name": "Slack", "sort_order": 2},
    {"name": "GitHub", "sort_order": 3},
    {"name": "AWS", "sort_order": 4},
]

ASSETS_DATA = [
    {"name": "ThinkPad X1 Carbon (山田)", "asset_type": "PC",
     "management_code": "PC-001", "assigned_user": "山田 太郎"},
    {"name": "MacBook Pro 14 (佐藤)", "asset_type": "PC",
     "management_code": "PC-002", "assigned_user": "佐藤 花子"},
    {"name": "Dell 27インチモニター", "asset_type": "モニター",
     "management_code": "MN-001", "assigned_user": "山田 太郎"},
    {"name": "iPhone 14 (業務用)", "asset_type": "スマートフォン",
     "management_code": "SP-001", "assigned_user": "高橋 健二"},
    {"name": "NAS サーバー (共用)", "asset_type": "サーバー",
     "management_code": "SV-001", "assigned_user": ""},
]

# user_service status matrix: [yamada, sato, suzuki, tanaka, takahashi]
USER_SERVICE_MATRIX = {
    "Google Workspace": ["active", "active", "active", "active", "active"],
    "Slack":            ["active", "active", "suspended", "active", "active"],
    "GitHub":           ["active", "active", "none", "none", "active"],
    "AWS":              ["active", "none", "none", "none", "active"],
}


# ─── 挿入関数 ────────────────────────────────────────────────────

def insert_users(session):
    existing = session.query(User).count()
    if existing > 0:
        print(f"  [SKIP] ユーザーは既に {existing} 件存在します。スキップします。")
        return {u.name: u for u in session.query(User).all()}

    print("  ユーザーを挿入中...")
    pw_hash = hash_pw("password123")
    user_map = {}
    for d in USERS_DATA:
        u = User(
            id=uid(),
            name=d["name"],
            login_id=d["login_id"],
            role=d["role"],
            emp_type=d["emp_type"],
            org_name=d["org_name"],
            is_manager=d["is_manager"],
            google_chat_user_id=d.get("google_chat_user_id"),
            password_hash=pw_hash,
            emp_status="active",
            is_active=1,
            created_at=now_iso(),  # noqa: not a model field but harmless
        )
        session.add(u)
        user_map[u.name] = u
    session.flush()
    print(f"  [OK] {len(USERS_DATA)} 件のユーザーを追加しました。")
    return user_map


def insert_tasks(session, user_map):
    existing = session.query(Task).count()
    if existing > 0:
        print(f"  [SKIP] タスクは既に {existing} 件存在します。スキップします。")
        tasks = session.query(Task).all()
        return {d["wbs_no"]: t for d, t in zip(TASKS_DATA, tasks)}

    print("  タスクを挿入中...")
    task_map = {}
    for d in TASKS_DATA:
        t = Task(
            id=uid(),
            phase=d["phase"],
            name=d["name"],
            description=d["description"],
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        session.add(t)
        task_map[d["wbs_no"]] = t

    # TaskAssignees: assign all users to each task
    session.flush()
    for t in task_map.values():
        for u in user_map.values():
            session.add(TaskAssignee(
                id=uid(), task_id=t.id, user_id=u.id, created_at=now_iso()
            ))

    print(f"  [OK] {len(TASKS_DATA)} 件のタスクを追加しました。")
    return task_map


def insert_task_instances(session, task_map, user_map):
    existing = session.query(TaskInstance).count()
    if existing > 0:
        print(f"  [SKIP] タスクインスタンスは既に {existing} 件存在します。スキップします。")
        return

    print("  タスクインスタンス・レポートを挿入中...")

    # T-001: 年次研修 - 2 instances (past done, current pending)
    t001 = task_map["T-001"]
    inst_001_past = TaskInstance(
        id=uid(), task_id=t001.id, due_date="2025-06-30",
        status="done", created_at="2025-06-01T09:00:00",
    )
    inst_001_cur = TaskInstance(
        id=uid(), task_id=t001.id, due_date="2026-06-30",
        status="pending", created_at="2026-06-01T09:00:00",
    )
    session.add(inst_001_past)
    session.add(inst_001_cur)
    session.flush()
    # Report for past instance
    for u in list(user_map.values())[:3]:
        session.add(Report(
            id=uid(), instance_id=inst_001_past.id, user_id=u.id,
            comment="受講完了しました。",
            reported_at="2025-06-25T14:00:00",
            report_token=uid(),
        ))

    # T-002: 月次アクセスログ - 3 instances
    t002 = task_map["T-002"]
    for month, status, approved in [
        (4, "done", True), (5, "done", True), (6, "pending", False)
    ]:
        inst = TaskInstance(
            id=uid(), task_id=t002.id,
            due_date=f"2026-{month:02d}-25",
            status=status,
            created_at=f"2026-{month:02d}-01T09:00:00",
        )
        session.add(inst)
        session.flush()
        if approved:
            for u in list(user_map.values())[:2]:
                session.add(Report(
                    id=uid(), instance_id=inst.id, user_id=u.id,
                    comment=f"{month}月のアクセスログ確認完了。異常なし。",
                    reported_at=f"2026-{month:02d}-18T10:30:00",
                    report_token=uid(),
                ))

    # T-004: 月次バックアップ確認 - 3 instances
    t004 = task_map["T-004"]
    for month, status, approved in [
        (4, "done", True), (5, "done", True), (6, "pending", False)
    ]:
        inst = TaskInstance(
            id=uid(), task_id=t004.id,
            due_date=f"2026-{month:02d}-15",
            status=status,
            created_at=f"2026-{month:02d}-01T09:00:00",
        )
        session.add(inst)
        session.flush()
        if approved:
            u = list(user_map.values())[0]
            session.add(Report(
                id=uid(), instance_id=inst.id, user_id=u.id,
                comment=f"{month}月バックアップ正常完了。全データ復元テスト済み。",
                reported_at=f"2026-{month:02d}-12T09:00:00",
                report_token=uid(),
            ))

    print("  [OK] タスクインスタンス・レポートを追加しました。")


def insert_check_forms(session, user_map):
    existing = session.query(CheckForm).count()
    if existing > 0:
        print(f"  [SKIP] チェックフォームは既に {existing} 件存在します。スキップします。")
        return

    print("  チェックフォーム・質問・回答を挿入中...")
    users = list(user_map.values())

    form_question_sets = [
        (FORMS_DATA[0], MONTHLY_QUESTIONS, "2026-06-25"),
        (FORMS_DATA[1], QUARTERLY_QUESTIONS, "2026-06-20"),
    ]

    for form_data, questions_data, due_date in form_question_sets:
        form = CheckForm(
            id=uid(),
            title=form_data["title"],
            description=form_data["description"],
            frequency=form_data["frequency"],
            repeat_type=form_data["repeat_type"],
            repeat_day=form_data["repeat_day"],
            repeat_months=form_data.get("repeat_months", ""),
            scheduled_month=form_data.get("scheduled_month", ""),
            due_day=form_data["due_day"],
            target_role=form_data["target_role"],
            pass_score=form_data["pass_score"],
            is_active=form_data["is_active"],
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        session.add(form)
        session.flush()

        # Questions
        q_objs = []
        for qd in questions_data:
            q = CheckFormQuestion(
                id=uid(),
                form_id=form.id,
                order_no=qd["order_no"],
                title=qd["title"],
                description=qd["description"],
                question_type=qd["question_type"],
                options_json=qd["options_json"],
                correct_options_json=qd["correct_options_json"],
                score_weight=qd["score_weight"],
                eval_type=qd["eval_type"],
                question_eval_type=qd["question_eval_type"],
                required=qd["required"],
                created_at=now_iso(),
            )
            session.add(q)
            q_objs.append(q)
        session.flush()

        max_score = sum(q.score_weight for q in q_objs)

        # Instances + Answers per user
        for i, user in enumerate(users):
            answered = i < 3  # first 3 users have answered
            status = "answered" if answered else "pending"
            inst = CheckFormInstance(
                id=uid(),
                form_id=form.id,
                user_id=user.id,
                due_date=due_date,
                status=status,
                answer_token=uid(),
                created_at=now_iso(),
                scheduled_date=due_date,
                max_score=max_score if answered else 0,
            )
            if answered:
                # Alternate: users 0,2 answer correctly, user 1 misses Q3
                total = 0
                answers = []
                for j, q in enumerate(q_objs):
                    correct_opts = json.loads(q.correct_options_json)
                    options = json.loads(q.options_json)
                    if i == 1 and j == len(q_objs) - 1:
                        # user 1 (sato) answers incorrectly on last Q
                        chosen = options[1] if len(options) > 1 else options[0]
                        score = 0
                    else:
                        chosen = correct_opts[0]
                        score = q.score_weight
                    total += score
                    answers.append((q, chosen, score))

                inst.total_score = total
                session.add(inst)
                session.flush()

                for q, chosen, score in answers:
                    session.add(CheckFormAnswer(
                        id=uid(),
                        instance_id=inst.id,
                        question_id=q.id,
                        user_id=user.id,
                        answer_value=chosen,
                        answer_values_json="[]",
                        answered_at=f"2026-06-{15 + i:02d}T10:00:00",
                        score=score,
                    ))
            else:
                session.add(inst)

    print("  [OK] チェックフォームを追加しました。")


def insert_admin_tasks(session):
    existing = session.query(AdminTask).count()
    if existing > 0:
        print(f"  [SKIP] 管理者タスクは既に {existing} 件存在します。スキップします。")
        return

    print("  管理者タスクを挿入中...")
    for d in ADMIN_TASKS_DATA:
        session.add(AdminTask(
            id=uid(),
            title=d["title"],
            description=d["description"],
            status=d["status"],
            trigger_event=d["trigger_event"],
            related_user_name=d["related_user_name"],
            due_date=d["due_date"],
            created_at=now_iso(),
            updated_at=now_iso(),
        ))
    print(f"  [OK] {len(ADMIN_TASKS_DATA)} 件の管理者タスクを追加しました。")


def insert_services_and_user_services(session, user_map):
    existing = session.query(Service).count()
    if existing > 0:
        print(f"  [SKIP] サービスは既に {existing} 件存在します。スキップします。")
        return

    print("  サービス・ユーザーサービスを挿入中...")
    users_ordered = [
        user_map.get("山田 太郎"),
        user_map.get("佐藤 花子"),
        user_map.get("鈴木 一郎"),
        user_map.get("田中 美咲"),
        user_map.get("高橋 健二"),
    ]
    service_map = {}
    for sd in SERVICES_DATA:
        svc = Service(
            id=uid(),
            name=sd["name"],
            sort_order=sd["sort_order"],
            created_at=now_iso(),
        )
        session.add(svc)
        service_map[svc.name] = svc
    session.flush()

    for svc_name, statuses in USER_SERVICE_MATRIX.items():
        svc = service_map[svc_name]
        for user, status in zip(users_ordered, statuses):
            if user is None:
                continue
            session.add(UserService(
                id=uid(),
                user_id=user.id,
                service_id=svc.id,
                status=status,
                note="",
                updated_at=now_iso(),
            ))

    print(f"  [OK] {len(SERVICES_DATA)} 件のサービスを追加しました。")


def insert_assets(session, user_map):
    existing = session.query(Asset).count()
    if existing > 0:
        print(f"  [SKIP] 資産は既に {existing} 件存在します。スキップします。")
        return

    print("  資産・棚卸データを挿入中...")
    name_to_user = {u.name: u for u in user_map.values()}

    inventory_months = ["2026-04", "2026-05", "2026-06"]
    inv_statuses = ["confirmed", "confirmed", "unchecked"]

    for d in ASSETS_DATA:
        assigned_user = name_to_user.get(d["assigned_user"])
        asset = Asset(
            id=uid(),
            name=d["name"],
            asset_type=d["asset_type"],
            management_code=d["management_code"],
            assigned_user_id=assigned_user.id if assigned_user else "",
            is_active=1,
            created_at=now_iso(),
        )
        session.add(asset)
        session.flush()

        for inv_month, inv_status in zip(inventory_months, inv_statuses):
            checked_by = assigned_user.name if assigned_user else "管理者"
            session.add(AssetInventory(
                id=uid(),
                asset_id=asset.id,
                inventory_date=inv_month,
                status=inv_status,
                note="" if inv_status == "confirmed" else "今月は未確認",
                checked_by=checked_by if inv_status == "confirmed" else "",
                created_at=now_iso(),
            ))

    print(f"  [OK] {len(ASSETS_DATA)} 件の資産を追加しました。")


# ─── エントリーポイント ───────────────────────────────────────────

def main():
    print("=" * 60)
    print("ISMS テストデータ挿入スクリプト")
    print("=" * 60)

    # DB初期化
    print("\n[1/8] DBを初期化...")
    init_db(DB_PATH)

    # セッション取得
    print("\n[2/8] セッションを取得...")
    SessionFactory = get_session_factory(DB_PATH)
    session = SessionFactory()

    try:
        print("\n[3/8] ユーザーを挿入...")
        user_map = insert_users(session)

        print("\n[4/8] タスクを挿入...")
        task_map = insert_tasks(session, user_map)

        print("\n[5/8] タスクインスタンス・レポートを挿入...")
        insert_task_instances(session, task_map, user_map)

        print("\n[6/8] チェックフォーム・質問・回答を挿入...")
        insert_check_forms(session, user_map)

        print("\n[7/8] 管理者タスクを挿入...")
        insert_admin_tasks(session)

        print("\n[8/8] サービス・資産データを挿入...")
        insert_services_and_user_services(session, user_map)
        insert_assets(session, user_map)

        session.commit()
        print("\n" + "=" * 60)
        print("[完了] 全テストデータの挿入が完了しました。")
        print("  ログイン情報: login_id=yamada.taro / password=password123")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] エラーが発生しました: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
