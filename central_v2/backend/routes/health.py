import json


def health_response():
    payload = {
        "status": "ok",
        "app": "central-v2",
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")
