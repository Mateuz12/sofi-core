import sqlite3
conn = sqlite3.connect(r'c:\Users\Administrator\Documents\GitHub\sofi-core\core\database\sofi.db')
rows = conn.execute(
    "SELECT modulo, status, mensagem, timestamp FROM execution_logs "
    "WHERE modulo IN ('Scheduler','Notifier') ORDER BY id DESC LIMIT 40"
).fetchall()
for r in rows:
    print(f"{r[3]} | {r[0]:12s} | {r[1]:10s} | {r[2][:160]}")
conn.close()
