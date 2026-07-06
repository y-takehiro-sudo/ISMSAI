"""
done 状態の UserTask の completion_comment を
UserTaskAssignee.comment / completed_at に移行する
"""
import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "isms.db")
con = sqlite3.connect(db_path)
con.row_factory = sqlite3.Row
cur = con.cursor()

done_tasks = cur.execute(
    "SELECT id, completion_comment, updated_at FROM user_tasks WHERE status = 'done'"
).fetchall()

updated = 0
for t in done_tasks:
    assignees = cur.execute(
        "SELECT id, completed_at FROM user_task_assignees WHERE task_id = ?", (t["id"],)
    ).fetchall()
    for a in assignees:
        if not a["completed_at"]:
            cur.execute(
                "UPDATE user_task_assignees SET completed_at = ?, comment = ? WHERE id = ?",
                (t["updated_at"] or "", t["completion_comment"] or "", a["id"]),
            )
            updated += 1

con.commit()
con.close()
print(f"Updated {updated} assignee records")
