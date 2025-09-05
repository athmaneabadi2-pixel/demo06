import os
from flask import Flask, request, jsonify, Response
import html
import requests
from datetime import datetime
from dotenv import load_dotenv
from config import DISPLAY_NAME, INSTANCE_LABEL, TIMEZONE, FEATURES, PROFILE_PATH
from core.llm import safe_generate_reply
from core.memory import Memory
from infra.monitoring import health_payload, now, log_json

load_dotenv()

app = Flask(__name__)
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
    if not expected or provided != expected:
        return jsonify({"error": "forbidden"}), 403

    data = request.json or {}
    text = data.get("text", "Bonjour")
    profile = memory.get_profile()

    try:
        reply = generate_reply(text, profile)
    except Exception as e:
        # Fallback si OPENAI ou profil posent problème
        name = profile.get("display_name") if isinstance(profile, dict) else "Coach"
        reply = f"Salut ! Petit contretemps technique ({type(e).__name__}). Dis-moi ta priorité du jour et je t'aide. — {name} 🤝"

    if (request.args.get("format") or "").lower() == "text":
        return Response(reply, mimetype="text/plain; charset=utf-8"), 200
    return jsonify({"ok": True, "request_text": text, "reply": reply}), 200


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
        text = generate_reply(prompt, profile)
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
    incoming = request.form or request.json or {}
    text = (incoming.get("Body") or incoming.get("text") or "").strip() or "Salut"
    profile = memory.get_profile()
    reply = generate_reply(text, profile)
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{html.escape(reply)}</Message></Response>'
    return Response(twiml, mimetype="application/xml")
