# utility.py
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

def to_decimal(value: Optional[float | int], digits: int = 2) -> Optional[float]:
    """
    Round a numeric value to <digits> decimal places using bankers-safe rounding.
    Returns None unchanged so callers don't need extra checks.
    """
    if value is None:
        return None
    q = Decimal(10) ** -digits          # 10^-digits
    return float(Decimal(value).quantize(q, rounding=ROUND_HALF_UP))
