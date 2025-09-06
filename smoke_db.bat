@echo off
REM --- Smoke DB local: affiche les 20 derniers messages ---
REM Nécessite Python (ta venv peut être activée)
python -c "import sqlite3; c=sqlite3.connect('local.db'); print(c.execute(\"SELECT id, ts, direction, user_id, IFNULL(msg_sid,'-') AS sid, substr(text,1,80) AS txt FROM messages ORDER BY id DESC LIMIT 20\").fetchall())"
