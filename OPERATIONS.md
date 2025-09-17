\# OPERATIONS — demo06 (production)



\## Endpoints \& URLs

\- Base URL (Render): https://demo06.onrender.com

\- Health: `GET /health` → 200

\- Internal Send: `POST /internal/send?format=text` (header obligatoire `X-Token`)

\- WhatsApp Webhook: `POST /whatsapp/webhook`



\## Secrets \& ENV (Render → Settings → Environment)

\- `OPENAI\_API\_KEY` = \*\*\*\*\*\*\*\* (UI Render uniquement)

\- `INTERNAL\_TOKEN` = \*\*\*\*\*\*\*\* (token prod)

\- `VERIFY\_TWILIO\_SIGNATURE` = `true`

\- `TWILIO\_AUTH\_TOKEN` = \*\*\*\*\*\*\*\* (Twilio Console)



\## Twilio WhatsApp Sandbox

\- Numéro Sandbox: +1 415 523 8886

\- Join (1ʳᵉ fois): `join <YOUR\_CODE>`

\- Webhook: `POST https://demo06.onrender.com/whatsapp/webhook`



\## Procédure de test (prod)

1\. `curl -s -o NUL -w "HEALTH %{http\_code}\\n" https://demo06.onrender.com/health`

2\. `curl -s -o NUL -w "INTERNAL %{http\_code} time\_total %{time\_total}s\\n" -X POST "https://demo06.onrender.com/internal/send?format=text" -H "X-Token: <INTERNAL\_TOKEN>" -H "Content-Type: application/json" -d "{\\"text\\":\\"ping\\"}"`

3\. Envoyer `ping` sur WhatsApp (Sandbox) → Logs: `POST /whatsapp/webhook 200` (~1.657s)



\## Latence de référence

\- Cold (J6-3): ~6.8s

\- Warm (J6-3): ~4.4s

\- Webhook (J6-4): ~1.657s



\## Runbook incident

\- `503` au réveil: ping `/health` puis retester.

\- `401` webhook: vérifier `TWILIO\_AUTH\_TOKEN` + `VERIFY\_TWILIO\_SIGNATURE=true`.

\- `404` webhook: route `POST /whatsapp/webhook`.



\## Déploiement

\- Branch: `deploy-j6`

\- Build: `pip install -r requirements.txt`

\- Start: `gunicorn app:app`



