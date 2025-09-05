-- Schéma minimal d'exemple (à adapter)
CREATE TABLE IF NOT EXISTS messages (
  id SERIAL PRIMARY KEY,
  direction TEXT,         -- 'in' | 'out'
  source TEXT,            -- 'webhook' | 'cron_weather' | ...
  msg_sid TEXT,
  content TEXT,
  content_hash TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_msgsid_dir
  ON messages (msg_sid, direction)
  WHERE msg_sid IS NOT NULL AND direction IS NOT NULL;
