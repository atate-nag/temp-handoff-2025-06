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
    force_meta: dict
    analysis: List[Force]
    overall_pressure: Optional[int]
    synthesis: Synthesis
    sources: List[str] = Field(min_length=6)
    skip: Optional[dict] = None
# ── schemas.py ────────────────────────────────────────────────────────────────
# ── schemas.py ─────────────────────────────────────────────────────────────
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional

class _PestCategory(BaseModel):
    bullets: List[str] = Field(
        ...,
        min_length=4,
        max_length=4,
        example=[
            "Inflation hits 20-year high (IMF, 2024)",
            "T+1 settlement mandates raise liquidity risk (SEC, 2024)",
            "AI adoption accelerates cost cuts (McKinsey, 2023)",
            "Data unavailable",
        ],
    )
    quant: Optional[List[str]] = None

    # optional: still allow plain list input
    @model_validator(mode="before")
    @classmethod
    def wrap_plain_list(cls, v):
        if isinstance(v, list):
            return {"bullets": v, "quant": None}
        return v


class PestBullets(BaseModel):
    Political: _PestCategory
    Economic: _PestCategory
    Social: _PestCategory
    Technological: _PestCategory


class PestResult(BaseModel):
    pest_bullets: PestBullets
    sources: List[str] = Field(..., min_length=4)
    error: Optional[str] = None


# ── schemas.py (add after PestResult) ──────────────────────────────────────
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class TrendCluster(BaseModel):
    short_name: str = Field(..., min_length=2, max_length=60)
    impact: int = Field(..., ge=1, le=5,
                        description="1 = very low, 5 = very high")
    time_horizon: Literal["now", "mid", "long"]
    direction: Literal["opportunity", "threat", "mixed"]
    top_trends: List[str] = Field(..., min_length=1, max_length=10)
    evidence: List[str] = Field(..., min_length=1)

    # Optional helper: coerce lowercase etc.
    @model_validator(mode="after")
    def normalise_fields(self):
        self.short_name = self.short_name.strip()
        return self


class TrendRadarResult(BaseModel):
    trend_clusters: List[TrendCluster] = Field(..., min_length=3)
    sources: Optional[List[str]] = Field(
        None, description="Optional flat list of unique citations")
    error: Optional[str] = None
