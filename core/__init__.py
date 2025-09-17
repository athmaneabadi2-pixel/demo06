"""
core package bootstrap — compat demo06
- Fournit bootstrap_memory() appelé par app.py au démarrage.
- Essaie d'initialiser le schéma de mémoire si disponible (core.memory.init_schema).
- Ne casse jamais le boot si non présent.
"""

from importlib import import_module
from typing import List, Dict, Any

def bootstrap_memory() -> None:
    """Initialise la mémoire si possible ; sinon ignore proprement."""
    try:
        mem = import_module("core.memory")
        if hasattr(mem, "init_schema"):
            mem.init_schema()  # type: ignore[attr-defined]
    except Exception as e:
        # Best-effort : on log en stdout, mais on ne lève pas.
        print(f"[core.bootstrap_memory] skip ({e})")

# Petit raccourci utile (facultatif) : expose get_history si disponible.
def get_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    try:
        mem = import_module("core.memory")
        if hasattr(mem, "get_history"):
            return mem.get_history(user_id, limit)  # type: ignore[attr-defined]
        if hasattr(mem, "read_history"):
            return mem.read_history(user_id, n=limit)  # type: ignore[attr-defined]
        if hasattr(mem, "load_history"):
            data = mem.load_history(user_id)  # type: ignore[attr-defined]
            if isinstance(data, list):
                return data[-limit:]
    except Exception:
        pass
    return []

__all__ = ["bootstrap_memory", "get_history"]
