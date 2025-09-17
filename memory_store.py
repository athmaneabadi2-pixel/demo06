# Back-compat pour anciens imports: re-exporte les fonctions depuis core.memory
try:
    from core.memory import *  # noqa: F401,F403
except Exception as e:
    raise ImportError(f"Compat memory_store failed: {e}")  # aide au debug si structure inattendue
