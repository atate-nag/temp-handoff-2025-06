import copy
from statistics import mean

# ---------------------------------------------------------------------
# canonical spellings so the UI downstream can rely on exact keys
_CANON = {
    "threat_of_entry": "threat_of_entry",
    "threat_of_new_entry": "threat_of_entry",
    "threat_of_new_entrants": "threat_of_entry",
    "supplier_power": "supplier_power",
    "bargaining_power_of_suppliers": "supplier_power",
    "buyer_power": "buyer_power",
    "bargaining_power_of_buyers": "buyer_power",
    "threat_of_substitutes": "threat_of_substitutes",
    "rivalry": "rivalry",
    "industry_rivalry": "rivalry",
    "competitive_rivalry": "rivalry",
}


def _canon_name(name: str) -> str:
    return _CANON.get(name.lower().replace(" ", "_"), name)


def _coerce_int(x):
    """Best-effort conversion – returns None if it can’t be int-ified."""
    try:
        return int(round(float(x)))
    except (TypeError, ValueError):
        return None


def normalise_forces(raw: dict) -> dict:
    """
    Guarantee a *uniform* structure so that later rendering /
    analytics don’t blow up.

    Expected output schema
    ----------------------
    {
      "force_meta": {...},               # kept verbatim
      "analysis": [
           {
             "force":           one of canonical names,
             "rating":          1-5  (int)
             "strength":        1-5  (int, duplicated from rating)
             "direction":       '↑ strengthening' | '→ stable' | '↓ weakening'
             "drivers":         [str, ...]
             "quant":           {...}      # optional, kept as-is
           },
           ...
      ],
      "overall_pressure": 1-5 (int),
      "synthesis": {...},                # kept verbatim
      "sources":   [...],                # kept verbatim
    }
    """
    if not isinstance(raw, dict):
        raise ValueError("normalise_forces expects a parsed dict")

    out = copy.deepcopy(raw)

    # ---------- 1. canonicalise each force block ---------------------
    normalised_blocks = []
    for blk in out.get("analysis", []):
        blk = copy.deepcopy(blk)

        # 1.a   force name
        blk["force"] = _canon_name(blk.get("force", ""))

        # 1.b   rating / strength
        rating = _coerce_int(blk.get("rating"))
        strength = _coerce_int(blk.get("strength"))

        if rating is None and strength is not None:
            rating = strength
        if strength is None and rating is not None:
            strength = rating

        # clamp to 1-5
        if rating is not None:
            rating = max(1, min(5, rating))
        if strength is not None:
            strength = max(1, min(5, strength))

        blk["rating"] = rating
        blk["strength"] = strength

        # 1.c   direction – normalise arrow glyphs & wording
        dir_raw = (blk.get("direction") or "").strip().lower()
        if dir_raw.startswith("↑") or "strengthen" in dir_raw:
            blk["direction"] = "↑ strengthening"
        elif dir_raw.startswith("↓") or "weaken" in dir_raw:
            blk["direction"] = "↓ weakening"
        else:
            blk["direction"] = "→ stable"

        # 1.d   drivers list always exists
        blk["drivers"] = blk.get("drivers") or []

        normalised_blocks.append(blk)

    out["analysis"] = normalised_blocks

    # ---------- 2. compute overall_pressure if missing --------------
    if out.get("overall_pressure") is None:
        vals = [b["strength"] for b in normalised_blocks if b["strength"]]
        out["overall_pressure"] = _coerce_int(mean(vals)) if vals else None

    return out
