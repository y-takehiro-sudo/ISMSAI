"""
初回起動時のみ実行される管理者ユーザー初期化スクリプト。
DB に admin ロールのユーザーが1人もいない場合のみ作成する。
環境変数 BOOTSTRAP_ADMIN_ID / BOOTSTRAP_ADMIN_PASSWORD で上書き可能。
"""
import os, sys, uuid
from datetime import datetime

sys.path.insert(0, "/app")

from app.db.models import User, get_engine, Base
from app.auth import hash_password
from sqlalchemy.orm import sessionmaker

DB_PATH = os.getenv("DB_PATH", "isms.db")
engine = get_engine(DB_PATH)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
db = Session()

admin_exists = db.query(User).filter(User.role == "admin", User.is_active == 1).first()
if admin_exists:
    print(f"[bootstrap] 管理者が既に存在します ({admin_exists.login_id}) → スキップ")
    db.close()
    sys.exit(0)

login_id = os.getenv("BOOTSTRAP_ADMIN_ID", "admin")
password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMe123!")

user = User(
    id=str(uuid.uuid4()),
    name="管理者",
    login_id=login_id,
    password_hash=hash_password(password),
    role="admin",
    is_active=1,
    emp_type="正社員",
    org_name="管理",
    is_manager=1,
)
db.add(user)
db.commit()
db.close()

print(f"[bootstrap] 初期管理者を作成しました: login_id={login_id}")
print(f"[bootstrap] ※ 初回ログイン後に必ずパスワードを変更してください")
