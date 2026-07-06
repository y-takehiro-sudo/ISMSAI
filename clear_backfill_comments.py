import sqlite3
con = sqlite3.connect("isms.db")
cur = con.cursor()
cur.execute("UPDATE user_task_assignees SET comment = '' WHERE comment != ''")
print("Cleared", cur.rowcount, "rows")
con.commit()
con.close()
