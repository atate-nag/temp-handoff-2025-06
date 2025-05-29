# utils/cache_io.py
from pathlib import Path
import hashlib, json, os, pickle, functools, logging

log = logging.getLogger(__name__)

# honour the global env-var or fall back to `.cache`
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)      # ← guarantee the folder

def _stable_hash(obj) -> str:
    return hashlib.md5(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:8]

def cached(tag: str):
    """Decorator that caches a pure-function call to disk."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, refresh: bool = False, **kw):
            # build file-name that’s unique for the function + its first arg
            key_hash   = _stable_hash(args[0])          # prompt is arg[0]
            fname      = f"{fn.__name__}_{tag}_{key_hash}.pkl"
            cache_file = CACHE_DIR / fname

            if cache_file.exists() and not refresh:
                log.info("🟢 cache-hit  %s", cache_file)
                return pickle.loads(cache_file.read_bytes())

            log.info("🔴 cache-miss %s  (building …)", cache_file)
            result = fn(*args, **kw)                    # call the real fn
            cache_file.parent.mkdir(parents=True, exist_ok=True)  # safety-net
            cache_file.write_bytes(pickle.dumps(result))
            log.info("💾 cached     %s", cache_file)
            return result
        return wrapper
    return decorator
