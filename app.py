import os, html, time, uuid, requests, hmac, hashlib, base64
from datetime import datetime
from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv

# Charger l'environnement AVANT toute lecture d'ENV
load_dotenv()

from config import DISPLAY_NAME, INSTANCE_LABEL, TIMEZONE, FEATURES, PROFILE_PATH
from core.llm import safe_generate_reply, safe_generate_reply_with_history
from core.memory import Memory
from infra.monitoring import now, log_json, health_payload
from db.db import init_schema, add_message, get_history, normalize_user_id, has_incoming_sid

app = Flask(__name__)

# --- Mini rate-limit (mémoire-process) ---
LAST_SEEN = {}
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "1.5"))

# --- Init DB tolérante ---
try:
    init_schema()
except Exception as e:
    log_json("db_init_error", error=str(e))

# --- Init mémoire tolérante au profil cassé ---
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

# --- Helper HTTP Twilio avec retries (429/5xx) ---
def _post_twilio_with_retry(url, data, auth, timeout=15, retries=2):
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, data=data, auth=auth, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return r
        except requests.RequestException:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise

# --- Vérification optionnelle de signature Twilio (HMAC-SHA1/Base64) ---
def _verify_twilio_sig(req) -> bool:
    if os.getenv("VERIFY_TWILIO_SIGNATURE", "false").lower() not in ("1", "true", "yes"):
        return True  # désactivé (local/sandbox)
    auth_token = os.getenv("TWILIO_AUTH_TOKEN") or ""
    public_url = (os.getenv("PUBLIC_WEBHOOK_URL") or "").rstrip("/")
    sig = req.headers.get("X-Twilio-Signature") or ""
    if not auth_token or not public_url or not sig:
        return False
    if req.form:
        parts = "".join(v for k, v in sorted(req.form.items()))
        data = public_url + parts
    else:
        # Twilio envoie du form-urlencoded ; fallback JSON au cas où
        data = public_url + (req.get_data(as_text=True) or "")
    mac = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1)
    expected = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(sig, expected)

# ------------------- Routes -------------------

@app.get("/health")
def health():
    return jsonify(health_payload(instance_label=INSTANCE_LABEL)), 200

@app.post("/internal/send")
def internal_send():
    expected = os.getenv("INTERNAL_TOKEN")
    provided = request.headers.get("X-Token")
    if not expected or provided != expected:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "Bonjour").strip()
    profile = memory.get_profile()

    req_id = str(uuid.uuid4())
    t0 = now()

    # IN -> DB
    user_id = "local"
    try:
        add_message(user_id, "IN", user_text, msg_sid=None, channel="internal")
    except Exception as e:
        log_json("db_write_error", where="internal_send_IN", error=str(e), req_id=req_id)

    # Historique
    try:
        history = get_history(user_id, limit=16)
    except Exception as e:
        history = []
        log_json("db_read_error", where="internal_get_history", error=str(e), req_id=req_id)

    # LLM (+fallback)
    try:
        reply = safe_generate_reply_with_history(user_text, history, profile)
        ok = True
    except Exception as e:
        log_json("error", where="internal_send_llm", error=str(e), req_id=req_id)
        name = profile.get("display_name") if isinstance(profile, dict) else "Coach"
        reply, ok = f"Désolé, je ne peux pas répondre pour le moment. — {name} 🤝", False

    # OUT -> DB
    try:
        add_message(user_id, "OUT", reply, msg_sid=None, channel="internal")
    except Exception as e:
        log_json("db_write_error", where="internal_send_OUT", error=str(e), req_id=req_id)

    lat = round(now() - t0, 3)
    log_json("internal_send_done", req_id=req_id, status="ok" if ok else "fail", latency=lat)

    if (request.args.get("format") or "").lower() == "text":
        return Response(reply, mimetype="text/plain; charset=utf-8"), 200
    return jsonify({"ok": ok, "reply": reply, "latency": lat}), 200

@app.post("/internal/checkin")
def internal_checkin():
    expected = os.getenv("INTERNAL_TOKEN")
    provided = request.headers.get("X-Token")
    if not expected or provided != expected:
        return jsonify({"error": "forbidden"}), 403

    t0 = now()

    body = request.get_json(silent=True) or {}
    to = body.get("to") or os.getenv("USER_WHATSAPP_TO")
    weather_hint = body.get("weather") or os.getenv("WEATHER_SUMMARY")

    profile = memory.get_profile()
    now_str = datetime.now().strftime("%A %d %B, %H:%M")
    prompt = ("Fais un check-in du matin (bref). "
              "Format: bonjour bref + météo (si fournie) + 1–2 priorités + 1 conseil.")
    if weather_hint:
        prompt += f" Météo: {weather_hint}."
    prompt += f" Date/heure: {now_str}. Utilise mes intérêts si utile."

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
            r = _post_twilio_with_retry(url, {"From": from_wa, "To": to, "Body": text},
                                        auth=(sid, tok), timeout=15, retries=2)
            try:
                js = r.json()
            except Exception:
                js = {"status_code": r.status_code, "text": r.text[:200]}
            log_json("checkin_done", status="sent", latency=round(now()-t0,3))
            return jsonify({"status": "sent", "twilio": js}), 200
        except Exception as e:
            log_json("checkin_done", status="twilio-error", error=str(e), latency=round(now()-t0,3))
            return jsonify({"status": "twilio-error",
                            "error": f"{type(e).__name__}: {str(e)[:160]}",
                            "dry_run_text": text}), 200

    log_json("checkin_done", status="dry-run", latency=round(now()-t0,3))
    return jsonify({"status": "dry-run", "text": text}), 200

@app.post("/whatsapp/webhook")
def whatsapp_webhook():
    t0 = now()

    # (option) vérifier la signature Twilio
    if not _verify_twilio_sig(request):
        log_json("twilio_sig_invalid")
        return Response('<?xml version="1.0" encoding="UTF-8"?><Response/>',
                        mimetype="application/xml", status=403)

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

    # 1) enregistrer IN
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

    LAST_SEEN[user_id] = now()

    # 3) historique + LLM
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
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    # Host 127.0.0.1 en local; en prod Render, c'est gunicorn qui sert.
    app.run(host="127.0.0.1", port=port, debug=True)
