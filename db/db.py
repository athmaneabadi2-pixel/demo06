import os, sqlite3
from contextlib import contextmanager
from typing import Optional, List, Tuple

DB_PATH = os.getenv("SQLITE_PATH", "local.db")

@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init_schema():
    # crée le dossier cible si DB_PATH contient un chemin
    if os.path.dirname(DB_PATH):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as con, open("db/schema.sql", "r", encoding="utf-8") as f:
        con.executescript(f.read())

def normalize_user_id(raw: str) -> str:
    if not raw: 
        return "unknown"
    return raw.replace("whatsapp:", "").strip()

def add_message(user_id: str, direction: str, text: str,
                msg_sid: Optional[str] = None, channel: str = "whatsapp") -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO messages(user_id, channel, direction, msg_sid, text) VALUES (?,?,?,?,?)",
            (user_id, channel, direction, msg_sid, text)
        )

def get_history(user_id: str, limit: int = 20) -> List[Tuple[str, str, str]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT direction, text, ts FROM messages WHERE user_id=? ORDER BY ts DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    return list(reversed(rows))
def has_incoming_sid(msg_sid: str) -> bool:
    if not msg_sid:
        return False
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM messages WHERE msg_sid=? AND direction='IN' LIMIT 1",
            (msg_sid,)
        ).fetchone()
    return bool(row)
