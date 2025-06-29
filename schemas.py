# socrates/schemas.py
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# ---------- nested helper models ------------------------------------------
class Force(BaseModel):
    force: Literal[
        "threat_of_entry",
        "supplier_power",
        "buyer_power",
        "threat_of_substitutes",
        "rivalry",
    ]
    rating: int = Field(ge=1, le=5)
    direction: Literal["↑ strengthening", "↓ easing", "→ stable"]
    drivers: List[str]
    quant: Optional[dict] = None
    strength: Optional[int] = None

class Synthesis(BaseModel):
    most_salient_force: str
    headline: str

# ---------- top-level result ----------------------------------------------
class FiveForcesResult(BaseModel):
    force_meta: dict                # keep loose; may extend later
    analysis: List[Force]
    overall_pressure: Optional[int]
    synthesis: Synthesis
    sources: List[str] = Field(min_length=6)
    skip: Optional[dict] = None
