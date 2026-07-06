import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, Text, create_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Text, primary_key=True)
    phase = Column(Text)
    name = Column(Text, nullable=False)
    description = Column(Text)
    start_date = Column(Text, default="")   # 開始日 ISO date
    end_date = Column(Text, default="")     # 終了日 ISO date
    url = Column(Text, default="")          # 外部リンク（スプシ等）
    created_at = Column(Text)
    updated_at = Column(Text)


class TaskAssignee(Base):
    __tablename__ = "task_assignees"

    id = Column(Text, primary_key=True)
    task_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    created_at = Column(Text)


class TaskInstance(Base):
    __tablename__ = "task_instances"

    id = Column(Text, primary_key=True)
    task_id = Column(Text, nullable=False)
    due_date = Column(Text)
    status = Column(Text, default="pending")
    completed_at = Column(Text, default="")
    completed_by = Column(Text, default="")  # user_id of admin who completed
    created_at = Column(Text)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Text, primary_key=True)
    instance_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    comment = Column(Text)
    reported_at = Column(Text)
    report_token = Column(Text)


class EscalationLog(Base):
    __tablename__ = "escalation_logs"

    id = Column(Text, primary_key=True)
    instance_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    level = Column(Integer)
    sent_at = Column(Text)


class User(Base):
    __tablename__ = "users"

    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    google_chat_user_id = Column(Text)
    role = Column(Text, default="member")
    is_active = Column(Integer, default=1)
    login_id = Column(Text, unique=True)       # ログインID
    password_hash = Column(Text)               # bcryptハッシュ
    last_login_at = Column(Text)
    emp_type = Column(Text, default="正社員")       # 社員区分
    emp_status = Column(Text, default="active")  # active / leave / retired
    emp_status_start = Column(Text)
    emp_status_end = Column(Text)
    org_name = Column(Text, default="")           # 組織名（部門）
    is_manager = Column(Integer, default=0)       # 責任者フラグ（0/1）


class HrEvent(Base):
    __tablename__ = "hr_events"

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False)
    event_type = Column(Text)
    event_date = Column(Text)
    created_at = Column(Text)


class NotificationQueue(Base):
    __tablename__ = "notification_queue"

    id = Column(Text, primary_key=True)
    instance_id = Column(Text)
    target_type = Column(Text, default="task")    # "task" / "admin_task" / "user_task" / "check_form"
    target_id = Column(Text, default="")          # ID of the target record
    target_user_id = Column(Text)
    space_type = Column(Text)
    message_body = Column(Text)
    status = Column(Text, default="draft")
    scheduled_at = Column(Text)
    sent_at = Column(Text)
    created_at = Column(Text)


class AuditLog(Base):
    """操作ログ：誰がいつ何をしたか"""
    __tablename__ = "audit_logs"

    id = Column(Text, primary_key=True)
    user_id = Column(Text)                     # 操作者ID（未ログイン時はNone）
    user_name = Column(Text)                   # 操作者名（スナップショット）
    action = Column(Text, nullable=False)      # login / logout / create / update / delete / approve / submit
    target = Column(Text)                      # 操作対象（例: task / check_answer / notification_queue）
    target_id = Column(Text)                   # 対象レコードID
    detail = Column(Text)                      # 詳細メモ（JSON or テキスト）
    ip_address = Column(Text)
    created_at = Column(Text, nullable=False)


class CheckQuestion(Base):
    """自己申告チェック質問マスター"""
    __tablename__ = "check_questions"

    id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)           # 質問タイトル
    description = Column(Text)                     # 補足説明
    answer_type = Column(Text, default="yes_no")   # yes_no / text / image
    eval_type = Column(Text, default="manager")    # ai / manager
    ai_criteria = Column(Text)                     # AI判定基準（eval_type=aiの場合）
    frequency = Column(Text, default="monthly")    # monthly / quarterly / yearly
    target_role = Column(Text, default="member")   # member / admin / all
    is_active = Column(Integer, default=1)
    created_at = Column(Text)
    updated_at = Column(Text)


class CheckInstance(Base):
    """自己申告チェックの発火インスタンス"""
    __tablename__ = "check_instances"

    id = Column(Text, primary_key=True)
    question_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    due_date = Column(Text)
    status = Column(Text, default="pending")       # pending / answered / evaluated
    answer_token = Column(Text)                    # 回答URL用トークン
    created_at = Column(Text)


class CheckAnswer(Base):
    """自己申告チェックの回答・評価"""
    __tablename__ = "check_answers"

    id = Column(Text, primary_key=True)
    instance_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    answer_text = Column(Text)                     # yes_no / テキスト回答
    image_path = Column(Text)                      # 画像ファイルパス
    answered_at = Column(Text)
    # AI評価
    ai_result = Column(Text)                       # ok / ng / pending
    ai_comment = Column(Text)
    ai_evaluated_at = Column(Text)
    # 管理者評価
    manager_result = Column(Text)                  # ok / ng
    manager_comment = Column(Text)
    manager_id = Column(Text)
    manager_evaluated_at = Column(Text)


class Service(Base):
    __tablename__ = "services"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=False)
    description = Column(Text, default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(Text, default=lambda: datetime.now().isoformat())


class UserService(Base):
    __tablename__ = "user_services"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Text, nullable=False)
    service_id = Column(Text, nullable=False)
    status = Column(Text, default="none")  # "active", "suspended", "none"
    note = Column(Text, default="")
    updated_at = Column(Text, default=lambda: datetime.now().isoformat())


class UserServiceHistory(Base):
    __tablename__ = "user_service_history"

    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Text, nullable=False)
    service_id = Column(Text, nullable=False)
    action = Column(Text, nullable=False)  # "activated", "suspended", "deactivated"
    changed_by = Column(Text, nullable=False)
    note = Column(Text, default="")
    created_at = Column(Text, default=lambda: datetime.now().isoformat())


class AlertTemplate(Base):
    """退職・休職時に発動するアラートタスクのテンプレート"""
    __tablename__ = "alert_templates"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)          # タスク名 e.g. "Google Workspaceアカウント停止"
    description = Column(Text, default="")
    trigger_event = Column(Text, default="retired")  # "retired" or "leave" or "both"
    sort_order = Column(Integer, default=0)
    assignee_role = Column(Text, default="admin")   # admin / member / all
    created_at = Column(Text, default=lambda: datetime.now().isoformat())


class UserTask(Base):
    """ユーザー向け不定期タスク"""
    __tablename__ = "user_tasks"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    description = Column(Text, default="")
    status = Column(Text, default="open")       # open / done
    start_date = Column(Text, default="")
    end_date = Column(Text, default="")
    url = Column(Text, default="")              # 外部リンク（着手ボタン用）
    completion_comment = Column(Text, default="")  # 完了報告コメント
    created_at = Column(Text, default=lambda: datetime.now().isoformat())
    updated_at = Column(Text, default=lambda: datetime.now().isoformat())


class UserTaskAssignee(Base):
    __tablename__ = "user_task_assignees"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    comment = Column(Text, default="")
    completed_at = Column(Text, default="")
    created_at = Column(Text, default=lambda: datetime.now().isoformat())


class AdminTask(Base):
    """管理者が実行すべきタスク（手動作成・退職/休職トリガーで自動生成）"""
    __tablename__ = "admin_tasks"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    description = Column(Text, default="")
    status = Column(Text, default="open")         # "open", "in_progress", "done"
    due_date = Column(Text, default="")
    trigger_event = Column(Text, default="manual")  # "manual", "retired", "leave"
    related_user_id = Column(Text, default="")    # user who retired/took leave
    related_user_name = Column(Text, default="")
    created_at = Column(Text, default=lambda: datetime.now().isoformat())
    updated_at = Column(Text, default=lambda: datetime.now().isoformat())


class CheckForm(Base):
    """運用チェックフォーム（複数質問を束ねるコンテナ）"""
    __tablename__ = "check_forms"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    description = Column(Text, default="")
    frequency = Column(Text, default="monthly")   # monthly/quarterly/yearly/weekly/once
    scheduled_month = Column(Text, default="")    # "1,4,7,10" for quarterly etc.
    due_day = Column(Integer, default=25)          # day of month for deadline
    target_role = Column(Text, default="all")     # all/admin/member
    is_active = Column(Integer, default=1)
    created_at = Column(Text, default=lambda: datetime.now().isoformat())
    updated_at = Column(Text, default=lambda: datetime.now().isoformat())
    # Googleカレンダー風繰り返し設定
    repeat_type = Column(Text, default="monthly")       # daily/weekly/monthly/monthly_nth/multi_month/once
    repeat_weekdays = Column(Text, default="")           # "mon,wed,fri" for weekly
    repeat_day = Column(Integer, default=25)             # day of month for monthly/multi_month
    repeat_nth_week = Column(Integer, default=0)         # 0=specific day, 1-5=nth weekday
    repeat_nth_weekday = Column(Text, default="")        # "mon"/"tue"/etc for nth weekday pattern
    repeat_months = Column(Text, default="")             # "1,4,7,10" for multi_month
    repeat_once_date = Column(Text, default="")          # ISO date for once
    pass_score = Column(Integer, default=80)             # passing percentage (0-100)


class CheckFormQuestion(Base):
    """フォーム内の個別質問"""
    __tablename__ = "check_form_questions"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    form_id = Column(Text, nullable=False)
    order_no = Column(Integer, default=0)
    title = Column(Text, nullable=False)           # 質問文
    description = Column(Text, default="")         # 補足説明
    question_type = Column(Text, default="radio")  # radio/checkbox/dropdown/text/textarea/file/scale
    options_json = Column(Text, default="[]")       # JSON array: ["はい","いいえ","N/A"]
    required = Column(Integer, default=1)           # 0=任意, 1=必須
    allow_file = Column(Integer, default=0)         # ファイル添付許可
    eval_type = Column(Text, default="none")        # none/manager/ai
    eval_criteria = Column(Text, default="")        # 評価基準テキスト
    question_eval_type = Column(Text, default="self")  # self=自己申告 / manager=評価者評価
    created_at = Column(Text, default=lambda: datetime.now().isoformat())
    # 採点設定
    score_weight = Column(Integer, default=10)              # points for this question
    correct_options_json = Column(Text, default="[]")       # correct answer(s) for auto-scoring
    pass_threshold = Column(Integer, default=0)             # for scale: minimum passing value


class CheckFormInstance(Base):
    """フォームの発火インスタンス（ユーザー×フォーム×期限）"""
    __tablename__ = "check_form_instances"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    form_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    due_date = Column(Text, default="")
    status = Column(Text, default="pending")       # pending/answered/evaluated
    answer_token = Column(Text, default="")        # URL token for user access
    created_at = Column(Text, default=lambda: datetime.now().isoformat())
    # スコア集計
    total_score = Column(Integer, default=0)        # actual total score
    max_score = Column(Integer, default=0)          # maximum possible score
    scheduled_date = Column(Text, default="")       # the specific date this was scheduled


class CheckFormAnswer(Base):
    """質問ごとの回答"""
    __tablename__ = "check_form_answers"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(Text, nullable=False)
    question_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    answer_value = Column(Text, default="")        # single answer (radio/dropdown/text/scale)
    answer_values_json = Column(Text, default="[]")# multiple answers (checkbox) as JSON
    file_path = Column(Text, default="")           # uploaded file path
    answered_at = Column(Text, default="")
    target_user_id = Column(Text, default="")       # 評価者評価時：評価される側のユーザーID
    evaluator_id = Column(Text, default="")         # 評価者評価時：評価する側のユーザーID
    # 評価
    manager_result = Column(Text, default="")      # ok/ng/
    manager_comment = Column(Text, default="")
    manager_id = Column(Text, default="")
    manager_evaluated_at = Column(Text, default="")
    ai_result = Column(Text, default="")
    ai_comment = Column(Text, default="")
    ai_evaluated_at = Column(Text, default="")
    # 採点
    score = Column(Integer, default=0)              # score received for this answer


class Asset(Base):
    """資産管理マスター"""
    __tablename__ = "assets"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=False)          # 資産名
    asset_type = Column(Text, default="PC")      # PC/モニター/スマートフォン/サーバー/ネットワーク機器/その他
    management_code = Column(Text, default="")   # 管理コード
    description = Column(Text, default="")
    assigned_user_id = Column(Text, default="")  # 使用者
    is_active = Column(Integer, default=1)
    created_at = Column(Text, default=lambda: datetime.now().isoformat())


class AssetInventory(Base):
    """資産棚卸（定期チェック）"""
    __tablename__ = "asset_inventories"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(Text, nullable=False)
    inventory_date = Column(Text, nullable=False)  # ISO date string e.g. "2026-06"
    status = Column(Text, default="unchecked")     # unchecked/confirmed/missing/disposed
    note = Column(Text, default="")
    checked_by = Column(Text, default="")          # user name who checked
    created_at = Column(Text, default=lambda: datetime.now().isoformat())


class TaskOwner(Base):
    """年間全体タスクの管理責任者（複数可）"""
    __tablename__ = "task_owners"
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    created_at = Column(Text, default=lambda: datetime.now().isoformat())


def get_engine(db_path: str = "isms.db"):
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
