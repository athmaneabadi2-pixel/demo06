def health_payload(instance_label: str):
    return {
        "status": "ok",
        "instance": instance_label,
        "version": "0.1.0",
    }
