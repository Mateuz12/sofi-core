from pathlib import Path
import sqlite3
db_path = Path(__file__).resolve().parent.parent / "core" / "database" / "sofi.db"
conn = sqlite3.connect(str(db_path))
rows = conn.execute(
    "SELECT modulo, status, mensagem, timestamp FROM execution_logs "
    "WHERE modulo IN ('Scheduler','Notifier') ORDER BY id DESC LIMIT 40"
).fetchall()
for r in rows:
    print(f"{r[3]} | {r[0]:12s} | {r[1]:10s} | {r[2][:160]}")
conn.close()
