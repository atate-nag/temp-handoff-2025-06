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
            fname = f"{fn.__name__}_{tag}.pkl"
            cache_file = CACHE_DIR / fname

            if cache_file.exists() and not refresh:
                print(f"🟢 cache-HIT%  {cache_file.name}")
                return pickle.loads(cache_file.read_bytes())

            print(f"🔴 cache-MISS%  (building …){cache_file.name}")
            result = fn(*args, **kw)                    # call the real fn
            cache_file.parent.mkdir(parents=True, exist_ok=True)  # safety-net
            cache_file.write_bytes(pickle.dumps(result))
            print(f"💾 cached %    {cache_file.name}")
            return result
        return wrapper
    return decorator
