# core/__init__.py — Patch minimal "stricte mais compatible"
from typing import List, Dict, Callable, Optional
import sys
import traceback

# 1) Import du backend officiel (SQLite) — fallback seulement si ImportError
try:
    from .memory import (
        add_message as _add_message,
        get_history as _get_history,
        clear_history as _clear_history,
        bootstrap_memory as _bootstrap_memory,
    )
    _USING_FALLBACK = False
except ImportError:
    # Fallback RAM minimal (pour ne pas bloquer en dev si le module manque)
    _USING_FALLBACK = True
    print("[WARN] core.memory introuvable — fallback RAM activé (dev only).", file=sys.stderr)
    _store = {}  # type: Dict[str, List[Dict]]

    def _bootstrap_memory() -> bool:
        # Rien à faire en RAM
        return True

    def _add_message(user_id: str, direction: str, text: str) -> bool:
        lst = _store.setdefault(user_id, [])
        lst.append({"direction": direction, "text": text})
        return True

    def _get_history(user_id: str, limit: int = 20) -> List[Dict]:
        lst = _store.get(user_id, [])
        return lst[-limit:]

    def _clear_history(user_id: str) -> bool:
        _store[user_id] = []
        return True

# 2) API exposée (mêmes noms partout dans l’app)
def bootstrap_memory() -> bool:
    # Si le backend officiel est présent, on l’utilise sans try/except global
    return _bootstrap_memory()

def add_message(user_id: str, direction: str, text: str) -> bool:
    return _add_message(user_id, direction, text)

def get_history(user_id: str, limit: int = 10) -> List[Dict]:
    return _get_history(user_id, limit)

def clear_history(user_id: str) -> bool:
    return _clear_history(user_id)

def process_incoming(
    user_id: str,
    text: str,
    session_id: Optional[str],
    generate: Callable[[str, List[Dict]], str],
) -> str:
    """
    Orchestrateur standard :
    - Log IN
    - Récupère 10 derniers
    - Appelle la génération
    - Log OUT si reply non vide
    - Renvoie reply
    """
    add_message(user_id, "IN", text)
    history = get_history(user_id, 10)

    # 3) Ne pas avaler l’erreur de génération : on log + on relance
    reply: str
    try:
        reply = generate(text, history) or ""
    except Exception as e:
        traceback.print_exc()
        # Relancer pour que l’erreur soit visible dans les logs/smokes
        raise

    if reply:
        add_message(user_id, "OUT", reply)
    return reply
