# core/memory.py
import os, sqlite3, threading

DB_PATH = os.getenv("DB_PATH", "local.db")
_lock = threading.Lock()

def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def bootstrap_memory():
    with _get_conn() as c, _lock:
        c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT NOT NULL,
            ts        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            direction TEXT CHECK(direction IN ('IN','OUT')) NOT NULL,
            text      TEXT NOT NULL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_ts ON messages(user_id, ts)")
    return True

def add_message(user_id: str, direction: str, text: str):
    with _get_conn() as c, _lock:
        c.execute("INSERT INTO messages (user_id, direction, text) VALUES (?,?,?)",
                  (user_id, direction, text))
    return True

def get_history(user_id: str, limit: int = 20):
    with _get_conn() as c, _lock:
        cur = c.execute(
            "SELECT direction, text FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cur.fetchall()
    rows.reverse()
    return [{"direction": d, "text": t} for (d, t) in rows]

def clear_history(user_id: str):
    with _get_conn() as c, _lock:
        c.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
    return True
