import sqlite3
import os
import json

db = os.path.join(os.path.dirname(__file__), '..', 'data', 'dedup.db')
db = os.path.abspath(db)
out = {"db_path": db, "exists": os.path.exists(db)}
if out["exists"]:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    try:
        cur.execute('SELECT COUNT(*) FROM events')
        out['unique_count'] = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM events WHERE topic=?', ('load',))
        out['load_count'] = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM events WHERE topic!=?', ('load',))
        out['other_count'] = cur.fetchone()[0]
    except Exception as e:
        out['error'] = str(e)
    conn.close()

print(json.dumps(out, indent=2))
