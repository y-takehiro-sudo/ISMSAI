"""user_task_assignees に comment / completed_at カラムを追加"""
import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "isms.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

cols = [row[1] for row in cur.execute("PRAGMA table_info(user_task_assignees)").fetchall()]

if "comment" not in cols:
    cur.execute("ALTER TABLE user_task_assignees ADD COLUMN comment TEXT DEFAULT ''")
    print("Added column: comment")

if "completed_at" not in cols:
    cur.execute("ALTER TABLE user_task_assignees ADD COLUMN completed_at TEXT DEFAULT ''")
    print("Added column: completed_at")

con.commit()
con.close()
print("Done")
