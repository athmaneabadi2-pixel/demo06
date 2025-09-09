# core/llm.py
import os, json, textwrap, time
from datetime import datetime
from openai import OpenAI
from infra.monitoring import log_json as _log

# ---------- Chargement profil ----------
def load_profile(path: str = "profile.json") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # fallback minimal
        return {
            "display_name": "Ami",
            "language": "fr",
            "timezone": "Europe/Paris",
            "tone": "chaleureux, clair, sans jargon",
            "short_sentences": True,
            "signature": "— Bot 🤝",
            "features": {"weather": False, "sports": [], "checkin": {"enabled": False}},
            "preferences": {"reply_max_chars": 400, "emoji_level": "léger"},
        }

def _ensure_profile(profile_or_path) -> dict:
    """Accepte soit un dict, soit un chemin vers le JSON."""
    if isinstance(profile_or_path, dict):
        return profile_or_path
    return load_profile(profile_or_path or "profile.json")

# ---------- Prompt ----------
def base_prompt() -> str:
    try:
        with open("LLM_SYSTEM_PROMPT.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "Parle français. Phrases courtes. Ton chaleureux, clair, sans jargon."

def build_system_prompt(profile: dict) -> str:
    tone = profile.get("tone", "chaleureux, clair, sans jargon")
    lang = profile.get("language", "fr")
    short = profile.get("short_sentences", True)
    signature = profile.get("signature", "")
    interests = ", ".join(profile.get("interests", [])) or "—"
    boundaries = " ".join(f"- {b}" for b in profile.get("boundaries", [])) or "-"
    features = profile.get("features", {})
    feats = []
    if features.get("weather"): feats.append("weather")
    if features.get("sports"): feats.append("sports")
    if features.get("checkin", {}).get("enabled"): feats.append("checkin")
    feat_line = ", ".join(feats) or "aucune"

    prefs = profile.get("preferences", {})
    max_chars = int(prefs.get("reply_max_chars", 400))
    emoji_level = prefs.get("emoji_level", "léger")
    persona = profile.get("persona", "")

    sys = f"""
{base_prompt()}

Tu es "{profile.get('display_name','Compagnon')}".
Langue: {lang}. Ton: {tone}. Phrases courtes: {short}.
Persona: {persona}
Signature à la fin: "{signature}" (toujours).
Intérêts utilisateur: {interests}.
Fonctionnalités actives: {feat_line}.
Limites / Boundaries:
{boundaries}

Règles de style:
- ≤ {max_chars} caractères par réponse.
- Niveau d'emoji: {emoji_level} (n'en abuse pas).
- Pas de jargon. Concret. Actionnable tout de suite.
- Si tu n'es pas sûr, demande une précision en UNE phrase.
- N'invente pas de faits externes (pas de météo live si non fournie).
- Salut simple → 1 phrase perso + 1 petite question contextuelle.
- Ne répète pas la même phrase d’accueil plus d’une fois par conversation.
- “ça va ?” → réponds bref + propose une action utile (priorité / rappel / note).
"""
    return textwrap.dedent(sys).strip()

def enforce_style(text: str, profile: dict) -> str:
    sig = profile.get("signature", "")
    max_chars = int(profile.get("preferences", {}).get("reply_max_chars", 400))
    text = (text or "").strip()
    if len(text) > max_chars:
        text = text[:max_chars - 1].rstrip() + "…"
    if sig and not text.endswith(sig):
        if not text.endswith("\n"): text += "\n"
        text += sig
    return text

# ---------- Client OpenAI avec timeout & retries ----------
_client = None
def client():
    """Client OpenAI robuste: timeout global + 2 retries SDK."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=15.0,      # secondes
            max_retries=2      # le SDK retente automatiquement
        )
    return _client

# ---------- Générateurs ----------
def generate_reply(user_text: str, profile_or_path="profile.json") -> str:
    profile = _ensure_profile(profile_or_path)
    system = build_system_prompt(profile)
    rsp = client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        temperature=0.7,
    )
    return enforce_style(rsp.choices[0].message.content, profile)

def generate_checkin(profile_or_path="profile.json", weather_hint=None) -> str:
    profile = _ensure_profile(profile_or_path)
    system = build_system_prompt(profile)
    now = datetime.now().strftime("%A %d %B, %H:%M")
    u = "Fais un check-in du matin (bref). Format: bonjour bref + météo (si dispo) + 1–2 priorités + 1 conseil."
    if weather_hint:
        u += f" Météo: {weather_hint}."
    u += f" Date/heure: {now}. Utilise mes intérêts si utile."
    rsp = client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": u},
        ],
        temperature=0.6,
    )
    return enforce_style(rsp.choices[0].message.content, profile)

# ---------- Wrapper sûr (retry + fallback) ----------
def safe_generate_reply(user_text: str, profile_or_path="profile.json") -> str:
    """
    Appelle generate_reply avec:
      - 1 retry si rate-limit/timeout,
      - fallback poli en cas d'échec.
    """
    last_err = None
    for attempt in range(2):
        try:
            return generate_reply(user_text, profile_or_path)
        except Exception as e:
            last_err = e
            msg = str(e)
            if attempt == 0 and any(x in msg for x in ("429", "Rate limit", "timeout", "Timeout")):
                _log("retry", where="openai", reason="rate_limit_or_timeout")
                time.sleep(2)
                continue
            break
    _log("error", where="openai", error=str(last_err))
    profile = _ensure_profile(profile_or_path)
    name = profile.get("display_name", "Ami")
    return f"Désolé, je ne peux pas répondre pour le moment. — {name} 🤝"

# --- Jour 2: génération AVEC historique ---
def generate_reply_with_history(user_text: str, history, profile_or_path="profile.json") -> str:
    """
    history: liste [(direction, text, ts), ...] du plus ancien au plus récent
    """
    profile = _ensure_profile(profile_or_path)
    system = build_system_prompt(profile)
    messages = [{"role": "system", "content": system}]
    hist = history[-16:] if history else []
    for direction, txt, ts in hist:
        role = "user" if direction == "IN" else "assistant"
        messages.append({"role": role, "content": str(txt or "")})
    messages.append({"role": "user", "content": user_text})

    rsp = client().chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
    )
    return enforce_style(rsp.choices[0].message.content, profile)

def safe_generate_reply_with_history(user_text: str, history, profile_or_path="profile.json") -> str:
    last_err = None
    for attempt in range(2):
        try:
            return generate_reply_with_history(user_text, history, profile_or_path)
        except Exception as e:
            last_err = e
            msg = str(e)
            if attempt == 0 and any(x in msg for x in ("429", "Rate limit", "timeout", "Timeout")):
                _log("retry", where="openai", reason="rate_limit_or_timeout")
                time.sleep(2)
                continue
            break
    _log("error", where="openai", error=str(last_err))
    profile = _ensure_profile(profile_or_path)
    name = profile.get("display_name", "Ami")
    return f"Désolé, je ne peux pas répondre pour le moment. — {name} 🤝"
