# Compat shim pour exposer l’API attendue par app.py
# - bootstrap_memory()
# - process_incoming(user_id, text, session_id, generate)
# - get_history(user_id, limit)

from typing import List, Dict, Callable, Optional

# Essaye d'utiliser le vrai backend mémoire
try:
    from .memory import add_message as _add_message
    from .memory import get_history as _get_history
    try:
        from .memory import bootstrap_memory as _bootstrap_memory  # optionnel
    except Exception:
        _bootstrap_memory = None
except Exception:
    # Fallback ultra-simple en mémoire (secours)
    _MEM: Dict[str, List[Dict]] = {}
    def _add_message(user_id: str, direction: str, text: str) -> None:
        _MEM.setdefault(user_id, []).append({"direction": direction, "text": text})
    def _get_history(user_id: str, limit: int = 10) -> List[Dict]:
        return _MEM.get(user_id, [])[-limit:]
    def _bootstrap_memory() -> None:
        pass

def bootstrap_memory() -> None:
    if callable(_bootstrap_memory):
        try:
            _bootstrap_memory()
        except Exception:
            # on ne bloque jamais le boot sur un souci de mémoire
            pass

def process_incoming(
    user_id: str,
    text: str,
    session_id: Optional[str],
    generate: Callable[[str, List[Dict]], str],
) -> str:
    _add_message(user_id, "IN", text)
    history = _get_history(user_id, 10)
    reply = ""
    try:
        reply = generate(text, history) or ""
    except Exception:
        reply = ""
    if reply:
        _add_message(user_id, "OUT", reply)
    return reply

def get_history(user_id: str, limit: int = 10) -> List[Dict]:
    return _get_history(user_id, limit)
