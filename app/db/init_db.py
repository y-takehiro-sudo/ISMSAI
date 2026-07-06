"""DBの初期化スクリプト。isms.db を生成し全テーブルを作成する。"""
import sys
import os
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.db.models import Base, get_engine


def _add_column_if_missing(conn, table, column, col_type, default=""):
    """ALTER TABLE でカラムを追加。既存の場合はスキップ。"""
    try:
        if default != "":
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}")
        else:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()
        print(f"  [migration] {table}.{column} 追加")
    except sqlite3.OperationalError:
        pass  # already exists


def init_db(db_path: str = "isms.db"):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    print(f"[OK] isms.db を初期化しました: {db_path}")
    for table in Base.metadata.sorted_tables:
        print(f"  テーブル作成: {table.name}")

    # ─── マイグレーション: 既存DBへのカラム追加 ───────────────
    conn = sqlite3.connect(db_path)
    try:
        # tasks テーブル
        _add_column_if_missing(conn, "tasks", "start_date", "TEXT", "''")
        _add_column_if_missing(conn, "tasks", "end_date", "TEXT", "''")

        # users テーブル
        _add_column_if_missing(conn, "users", "emp_status", "TEXT", "'active'")
        _add_column_if_missing(conn, "users", "emp_status_start", "TEXT", "")
        _add_column_if_missing(conn, "users", "emp_status_end", "TEXT", "")
        _add_column_if_missing(conn, "users", "emp_type", "TEXT", "'正社員'")
        _add_column_if_missing(conn, "users", "login_id", "TEXT", "")
        _add_column_if_missing(conn, "users", "password_hash", "TEXT", "")
        _add_column_if_missing(conn, "users", "org_name", "TEXT", "''")
        _add_column_if_missing(conn, "users", "is_manager", "INTEGER", "0")

        # task_instances テーブル
        _add_column_if_missing(conn, "task_instances", "completed_at", "TEXT", "''")
        _add_column_if_missing(conn, "task_instances", "completed_by", "TEXT", "''")

        # check_forms テーブル
        _add_column_if_missing(conn, "check_forms", "repeat_type", "TEXT", "'monthly'")
        _add_column_if_missing(conn, "check_forms", "repeat_weekdays", "TEXT", "''")
        _add_column_if_missing(conn, "check_forms", "repeat_day", "INTEGER", "25")
        _add_column_if_missing(conn, "check_forms", "repeat_nth_week", "INTEGER", "0")
        _add_column_if_missing(conn, "check_forms", "repeat_nth_weekday", "TEXT", "''")
        _add_column_if_missing(conn, "check_forms", "repeat_months", "TEXT", "''")
        _add_column_if_missing(conn, "check_forms", "repeat_once_date", "TEXT", "''")
        _add_column_if_missing(conn, "check_forms", "pass_score", "INTEGER", "80")

        # check_form_questions テーブル
        _add_column_if_missing(conn, "check_form_questions", "score_weight", "INTEGER", "10")
        _add_column_if_missing(conn, "check_form_questions", "correct_options_json", "TEXT", "'[]'")
        _add_column_if_missing(conn, "check_form_questions", "pass_threshold", "INTEGER", "0")
        _add_column_if_missing(conn, "check_form_questions", "question_eval_type", "TEXT", "'self'")

        # check_form_answers テーブル
        _add_column_if_missing(conn, "check_form_answers", "target_user_id", "TEXT", "''")
        _add_column_if_missing(conn, "check_form_answers", "evaluator_id", "TEXT", "''")

        # check_form_instances テーブル
        _add_column_if_missing(conn, "check_form_instances", "total_score", "INTEGER", "0")
        _add_column_if_missing(conn, "check_form_instances", "max_score", "INTEGER", "0")
        _add_column_if_missing(conn, "check_form_instances", "scheduled_date", "TEXT", "''")

        # check_form_answers テーブル
        _add_column_if_missing(conn, "check_form_answers", "score", "INTEGER", "0")

        # alert_templates テーブル
        _add_column_if_missing(conn, "alert_templates", "assignee_role", "TEXT", "'admin'")

        # notification_queue テーブル
        _add_column_if_missing(conn, "notification_queue", "target_type", "TEXT", "'task'")
        _add_column_if_missing(conn, "notification_queue", "target_id", "TEXT", "''")
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "isms.db"
    init_db(db_path)
