import hashlib
import json

def generate_key(prefix: str, data) -> str:
    raw = json.dumps(data, sort_keys=True)
    hash_val = hashlib.sha256(raw.encode()).hexdigest()
    return f"{prefix}:{hash_val}"