import json, os, functools, hashlib
from pathlib import Path
from typing import Callable, Any

CACHE_ON = os.getenv("CACHE", "0") == "1"
CACHE_DIR = Path("./cache")

def _hash(obj: Any) -> str:
    """Cheap hash so the same prompt with minor edits gets a new file."""
    txt = json.dumps(obj, sort_keys=True) if not isinstance(obj, str) else obj
    return hashlib.md5(txt.encode()).hexdigest()[:8]

def cached(stage_name: str) -> Callable:
    """
    Decorator for any function that returns *JSON-serialisable* data.
    Usage:
        @cached("trend_radar")
        def build_trend_radar(...): ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kw):
            # pick the first text arg as a fingerprint (usually the prompt)
            prompt_fingerprint = _hash(args[0]) if args else "noprompt"
            file = CACHE_DIR / stage_name / f"{prompt_fingerprint}.json"

            if CACHE_ON and file.exists():
                with open(file) as f:
                    return json.load(f)

            result = fn(*args, **kw)
            if CACHE_ON:
                file.parent.mkdir(parents=True, exist_ok=True)
                with open(file, "w") as f:
                    json.dump(result, f, indent=2)
            return result

        return wrapper
    return decorator
