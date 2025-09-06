PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id TEXT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'whatsapp',
  direction TEXT NOT NULL CHECK (direction IN ('IN','OUT')),
  msg_sid TEXT,
  text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_user_ts ON messages(user_id, ts);

CREATE UNIQUE INDEX IF NOT EXISTS ux_messages_sid_dir
  ON messages(msg_sid, direction) WHERE msg_sid IS NOT NULL;
