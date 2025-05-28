"""
Utilities for (1) choosing the right tokenizer, (2) counting tokens,
and (3) trimming any JSON/text so it never exceeds the model’s limit.
"""

from __future__ import annotations
import json, tiktoken, logging

# ------------------------------------------------------------------
# pick a tokenizer --------------------------------------------------
# ------------------------------------------------------------------
try:
    ENC = tiktoken.encoding_for_model("o3-mini")          # will work once tiktoken updates
except KeyError:                                          # …until then:
    logging.getLogger(__name__).info(
        "o3-mini not in tiktoken yet – falling back to o200k_base."
    )
    ENC = tiktoken.get_encoding("o200k_base")             # 200 000-token context

# 200 000 context − a bit of head-room for system / tool messages
MAX_PROMPT_TOKENS: int = 190_000                          # exported constant


# ------------------------------------------------------------------
# helper functions --------------------------------------------------
# ------------------------------------------------------------------
def n_tokens(text: str) -> int:
    """Return how many tokens `text` will use with the current encoding."""
    return len(ENC.encode(text))


def trim_to_tokens(text: str, limit: int = MAX_PROMPT_TOKENS) -> str:
    """Return `text`, cut cleanly at a token boundary so it fits `limit` tokens."""
    tokens = ENC.encode(text)
    if len(tokens) <= limit:
        return text
    return ENC.decode(tokens[:limit])


def as_token_limited_json(obj, limit: int = MAX_PROMPT_TOKENS) -> str:
    """
    `json.dumps` the python object, and make sure the result never
    exceeds `limit` tokens.  Uses `trim_to_tokens` on the *string*
    rather than trying to mutate the object.
    """
    raw = json.dumps(obj, default=str, ensure_ascii=False)
    return trim_to_tokens(raw, limit)
