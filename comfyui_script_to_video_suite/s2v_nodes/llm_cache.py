
import os
import json
import hashlib

CACHE_DIR = os.path.join(os.path.dirname(__file__), "llm_cache")


def _disabled() -> bool:
    return os.environ.get("S2V_DISABLE_LLM_CACHE") == "1"


def _path(kind: str, parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8", "replace"))
        h.update(b"\x00")
    return os.path.join(CACHE_DIR, f"{kind}_{h.hexdigest()}.json")


def load(kind: str, *parts):
  
    if _disabled():
        return None
    path = _path(kind, parts)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)["result"]
    except Exception as e:
        print(f"⚠️ S2V cache read failed ({e}), regenerating.")
        return None


def save(kind: str, result, *parts):
    if _disabled():
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_path(kind, parts), "w", encoding="utf-8") as f:
            json.dump({"result": result}, f)
    except Exception as e:
        print(f"⚠️ S2V cache write failed: {e}")
