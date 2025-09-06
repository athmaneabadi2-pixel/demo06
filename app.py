import os
from flask import Flask, request, jsonify, Response
import html
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()  # <-- déplacer ici

from config import DISPLAY_NAME, INSTANCE_LABEL, TIMEZONE, FEATURES, PROFILE_PATH
from core.llm import safe_generate_reply, safe_generate_reply_with_history
...
import uuid
from db.db import init_schema, add_message, get_history, normalize_user_id, has_incoming_sid

# mini rate-limit (par user, mémoire-process)
LAST_SEEN = {}
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "1.5"))




load_dotenv()

app = Flask(__name__)
# -- Jour 2: init DB schema (tolérant) --
try:
    init_schema()
except Exception as e:
    log_json("db_init_error", error=str(e))
# -- fin --
# -- Jour 1: init mémoire tolérante au profil cassé --
try:
    memory = Memory(profile_path=PROFILE_PATH)
except Exception as e:
    print(f"⚠️ Profil invalide ou introuvable ({e}) → fallback par défaut")
    class _Dummy:
        def get_profile(self):
            return {
                "display_name": "Ami",
                "language": "fr",
                "timezone": "Europe/Paris",
                "tone": "chaleureux",
                "short_sentences": True,
            }
    memory = _Dummy()
# -- fin ajout --

# -- ajoute ça une seule fois au niveau module (pas dans une route) --
def _env_flags():
    keys = [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_SANDBOX_FROM",
        "USER_WHATSAPP_TO",
        "OPENAI_API_KEY",
    ]
    return {k: bool(os.getenv(k)) for k in keys}


@app.get("/health")
def health():
    return jsonify(health_payload(instance_label=INSTANCE_LABEL)), 200

@app.post("/internal/send")
def internal_send():
    expected = os.getenv("INTERNAL_TOKEN")
    provided = request.headers.get("X-Token")
    if expected and provided != expected:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "Bonjour").strip()
    profile = memory.get_profile()
    user_id = "local"

        # IN → DB
    try:
        add_message(user_id, "IN", user_text, msg_sid=None, channel="internal")
    except Exception as e:
        log_json("db_write_error", where="internal_send_IN", error=str(e))

    # Historique pour l'utilisateur local
    try:
        history = get_history(user_id, limit=16)
    except Exception as e:
        history = []
        log_json("db_read_error", where="internal_get_history", error=str(e))

    # LLM (avec historique, retry + fallback)
    try:
        reply = safe_generate_reply_with_history(user_text, history, profile)
    except Exception as e:
        log_json("error", where="internal_send_llm", error=str(e))
        name = profile.get("display_name") if isinstance(profile, dict) else "Coach"
        reply = f"Désolé, je ne peux pas répondre pour le moment. — {name} 🤝"



    # OUT → DB
    try:
        add_message(user_id, "OUT", reply, msg_sid=None, channel="internal")
    except Exception as e:
        log_json("db_write_error", where="internal_send_OUT", error=str(e))

    if (request.args.get("format") or "").lower() == "text":
        return Response(reply, mimetype="text/plain; charset=utf-8"), 200
    return jsonify({"ok": True, "request_text": user_text, "reply": reply}), 200


@app.post("/internal/checkin")
def internal_checkin():
    expected = os.getenv("INTERNAL_TOKEN")
    provided = request.headers.get("X-Token")
    if not expected or provided != expected:
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(silent=True) or {}
    to = body.get("to") or os.getenv("USER_WHATSAPP_TO")
    weather_hint = body.get("weather") or os.getenv("WEATHER_SUMMARY")

    profile = memory.get_profile()
    now = datetime.now().strftime("%A %d %B, %H:%M")
    prompt = ("Fais un check-in du matin (bref). "
              "Format: bonjour bref + météo (si fournie) + 1–2 priorités + 1 conseil.")
    if weather_hint:
        prompt += f" Météo: {weather_hint}."
    prompt += f" Date/heure: {now}. Utilise mes intérêts si utile."

    try:
        text = safe_generate_reply(prompt, profile)

    except Exception as e:
        name = (profile or {}).get("display_name", "Coach") if isinstance(profile, dict) else "Coach"
        text = (f"Bonjour ! Petit check-in rapide. Deux priorités + un conseil pour lancer la journée. "
                f"({type(e).__name__})\n— {name} 🤝")

    sid = os.getenv("TWILIO_ACCOUNT_SID")
    tok = os.getenv("TWILIO_AUTH_TOKEN")
    from_wa = os.getenv("TWILIO_SANDBOX_FROM", "whatsapp:+14155238886")

    if sid and tok and to:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
            r = requests.post(url, data={"From": from_wa, "To": to, "Body": text}, auth=(sid, tok), timeout=15)
            try:
                js = r.json()
            except Exception:
                js = {"status_code": r.status_code, "text": r.text[:200]}
            return jsonify({"status": "sent", "twilio": js}), 200
        except Exception as e:
            return jsonify({"status": "twilio-error",
                            "error": f"{type(e).__name__}: {str(e)[:160]}",
                            "dry_run_text": text}), 200

    return jsonify({"status": "dry-run", "text": text}), 200



@app.post("/whatsapp/webhook")
def whatsapp_webhook():
    t0 = now()
    incoming = request.form or request.json or {}
    text = (incoming.get("Body") or incoming.get("text") or "").strip() or "Salut"
    from_raw = incoming.get("From") or incoming.get("from") or "unknown"
    user_id = normalize_user_id(from_raw)
    msg_sid = incoming.get("MessageSid") or incoming.get("messageSid")
    req_id = msg_sid or str(uuid.uuid4())

    # 0) dédup strict (avant tout traitement)
    if msg_sid and has_incoming_sid(msg_sid):
        log_json("dedup_skip", req_id=req_id, user_id=user_id, msg_sid=msg_sid)
        return Response('<?xml version="1.0" encoding="UTF-8"?><Response/>',
                        mimetype="application/xml", status=200)

    # 1) on enregistre IN (prépare l'idempotence DB)
    try:
        add_message(user_id, "IN", text, msg_sid=msg_sid, channel="whatsapp")
    except Exception as e:
        log_json("db_write_error", where="webhook_IN", error=str(e), req_id=req_id)

    # 2) mini rate-limit (cooldown)
    last = LAST_SEEN.get(user_id, 0.0)
    if now() - last < RATE_LIMIT_SECONDS:
        reply = "Merci 🙂 je traite ton message, j’arrive…"
        try:
            add_message(user_id, "OUT", reply, msg_sid=None, channel="whatsapp")
        except Exception as e:
            log_json("db_write_error", where="webhook_OUT_rl", error=str(e), req_id=req_id)
        twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{html.escape(reply)}</Message></Response>'
        log_json("rate_limit", req_id=req_id, user_id=user_id, latency=round(now()-t0,3))
        return Response(twiml, mimetype="application/xml", status=200)

    # autoriser le prochain message après ce traitement
    LAST_SEEN[user_id] = now()

    # 3) historique + LLM (retry/fallback)
    try:
        history = get_history(user_id, limit=16)
    except Exception as e:
        history = []
        log_json("db_read_error", where="get_history", error=str(e), req_id=req_id)

    profile = memory.get_profile()
    try:
        reply = safe_generate_reply_with_history(text, history, profile)
    except Exception as e:
        log_json("error", where="webhook_llm", error=str(e), req_id=req_id)
        name = profile.get("display_name") if isinstance(profile, dict) else "Coach"
        reply = f"Désolé, je ne peux pas répondre pour le moment. — {name} 🤝"

    # 4) OUT -> DB
    try:
        add_message(user_id, "OUT", reply, msg_sid=None, channel="whatsapp")
    except Exception as e:
        log_json("db_write_error", where="webhook_OUT", error=str(e), req_id=req_id)

    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{html.escape(reply)}</Message></Response>'
    log_json("webhook_done", req_id=req_id, user_id=user_id, latency=round(now()-t0,3))
    return Response(twiml, mimetype="application/xml")
