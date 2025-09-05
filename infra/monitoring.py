# infra/monitoring.py

import json
import time

def health_payload(instance_label: str):
    return {
        "status": "ok",
        "instance": instance_label,
        "version": "0.1.0",
    }

def now() -> float:
    return time.time()

def log_json(event: str, **fields):
    obj = {"event": event, **fields}
    print(json.dumps(obj, ensure_ascii=False), flush=True)
