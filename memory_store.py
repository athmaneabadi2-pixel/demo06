"""
Shim de compatibilité pour l'historique.
- Essaie plusieurs signatures possibles dans core.memory
- Fournit un fallback sans échec (liste vide) pour ne JAMAIS casser le boot
"""

from typing import List, Dict, Any

def get_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retourne une liste d'événements [{"direction":"IN|OUT","text":"..."}]
    Fallback: [] si core.memory n'a pas d'API compatible.
    """
    try:
        # Cas 1: core.memory expose get_history(user_id, limit)
        from core.memory import get_history as gh  # type: ignore
        return gh(user_id, limit)  # pragma: no cover
    except Exception:
        pass

    try:
        # Cas 2: core.memory expose read_history(user_id, n=limit)
        from core.memory import read_history  # type: ignore
        return read_history(user_id, n=limit)  # pragma: no cover
    except Exception:
        pass

    try:
        # Cas 3: core.memory expose load_history(user_id) et on tronque
        from core.memory import load_history  # type: ignore
        data = load_history(user_id)
        if isinstance(data, list):
            return data[-limit:]
    except Exception:
        pass

    # Fallback sûr: aucun historique, on ne bloque jamais le boot.
    return []
