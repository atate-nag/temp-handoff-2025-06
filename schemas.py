# socrates/schemas.py
from __future__ import annotations
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

# --------------------------------------------------------------------------
# Five‑Forces sub‑model (NEW)
# --------------------------------------------------------------------------

class _ForceItem(BaseModel):
    """One competitive force analysis row."""
    force: str
    rating: int = Field(ge=1, le=5)   # 1‑5 inclusive
    rationale: str
    direction: str
    evidence: list[str] | None = None
# ---------- top-level result ----------------------------------------------
class FiveForcesResult(BaseModel):
    force_meta: dict | None
    analysis: list[_ForceItem]
    overall_pressure: int | None
    synthesis: str | None
    sources: list[str] = Field(min_length=6)
    skip: dict | None
# ── schemas.py ─────────────────────────────────────────────────────────────
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
# schemas.py
from typing import Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ArtifactKind(str, Enum):
    ANALYSIS = "analysis"          # e.g. 5‑Forces, PEST, Trend Radar
    DATASET  = "dataset"           # e.g. raw table, CSV, graph
    TEXT     = "text"              # free‑form markdown, executive summary
    OTHER    = "other"


class Artifact(BaseModel):
    id: str                        # short slug, e.g. "5-forces"
    kind: ArtifactKind
    payload: dict                  # always JSON‑serialisable
    sources: list[str] = Field(default_factory=list)
    tags: list[str]   = Field(default_factory=list)
    meta: dict[str, Any] = Field(  # size, model name, whatever
        default_factory=lambda: {"created": datetime.utcnow().isoformat()}
    )

class ArtifactCollection(BaseModel):
    artifacts: list[Artifact]

    @property
    def lookup(self) -> dict[str, Artifact]:
        """Quick dict access by id."""
        return {a.id: a for a in self.artifacts}

    @property
    def all_sources(self) -> list[str]:
        return sorted({src for a in self.artifacts for src in a.sources})

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

from typing import List, Optional
from pydantic import BaseModel, Field, constr, field_validator


# ──────────────────────────────────────────────────────────────────────────────
# Helper: the nested Internal / External bullets
# ──────────────────────────────────────────────────────────────────────────────
class _InVsEx(BaseModel):
    """Two short bullet lists that locate the crux’s drivers."""
    internal: List[str] = Field(..., min_length=1, max_length=5)
    external: List[str] = Field(..., min_length=1, max_length=5)


# ──────────────────────────────────────────────────────────────────────────────
# Main result object returned by `initial_crux_agent`
# ──────────────────────────────────────────────────────────────────────────────
class InitialCruxResult(BaseModel):
    """
    A single, board-level statement of the company’s strategic crux,
    with tightly-sourced support and a split of internal vs external factors.
    """
    crux: constr(min_length=1, max_length=600)  # ≈ 75 words
    evidence: List[str] = Field(
        ...,
        min_length=2,
        description="APA-style citations e.g. '(BIS, 2024)'"
    )
    why_it_matters: constr(min_length=1, max_length=400)  # ≈ 50 words max
    internal_vs_external: _InVsEx
    error: Optional[str] = Field(
        default=None,
        description='Present *only* when the agent could not find sufficient evidence'
    )

    # ── quick sanity-check: every evidence item looks like "(Source, 2024)"
    @field_validator("evidence")
    @classmethod
    def _validate_citation_format(cls, v: List[str]) -> List[str]:
        import re
        apa = re.compile(r"\([^)]+,\s?\d{4}\)")
        if any(not apa.fullmatch(item.strip()) for item in v):
            raise ValueError("All evidence items must match '(Source, YYYY)'")
        return v
