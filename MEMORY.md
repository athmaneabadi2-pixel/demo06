\# MEMORY.md — Compagnon (SQLite dev / Postgres prod)



\## But

\- Persister chaque message IN/OUT.

\- Réinjecter les derniers échanges dans le prompt (≈8 tours).

\- Préparer l’idempotence (msg\_sid Twilio).



\## Fichiers

\- `db/schema.sql` — schéma SQLite (dev).

\- `db/db.py` — DAO: `init\_schema`, `add\_message`, `get\_history`, `normalize\_user\_id`.

\- `app.py` — hooks DB sur `/internal/send` et `/whatsapp/webhook`.

\- `core/llm.py` — génération avec historique: `safe\_generate\_reply\_with\_history`.



\## Schéma (SQLite)

```sql

PRAGMA journal\_mode=WAL;



CREATE TABLE IF NOT EXISTS messages (

&nbsp; id INTEGER PRIMARY KEY AUTOINCREMENT,

&nbsp; ts TIMESTAMP NOT NULL DEFAULT CURRENT\_TIMESTAMP,

&nbsp; user\_id TEXT NOT NULL,

&nbsp; channel TEXT NOT NULL DEFAULT 'whatsapp',

&nbsp; direction TEXT NOT NULL CHECK (direction IN ('IN','OUT')),

&nbsp; msg\_sid TEXT,

&nbsp; text TEXT NOT NULL

);



CREATE INDEX IF NOT EXISTS idx\_messages\_user\_ts ON messages(user\_id, ts);

CREATE UNIQUE INDEX IF NOT EXISTS ux\_messages\_sid\_dir

&nbsp; ON messages(msg\_sid, direction) WHERE msg\_sid IS NOT NULL;



