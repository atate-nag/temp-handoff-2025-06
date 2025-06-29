# tests/test_forces_schema.py
import pytest
from schemas import FiveForcesResult
from copy import deepcopy

def _dummy_force(name: str):
    return {
        "force": name,
        "rating": 3,
        "direction": "→ stable",
        "drivers": ["Dummy driver 1 (Source, 2024)",
                    "Dummy driver 2 (Source, 2024)",
                    "Dummy driver 3 (Source, 2024)"],
        "quant": {"example_metric": 42}
    }

BASE_PAYLOAD = {
    "force_meta": {"industry_scope": "Test", "time_horizon": "2025-2027"},
    "analysis": [_dummy_force(f) for f in [
        "threat_of_entry", "supplier_power", "buyer_power",
        "threat_of_substitutes", "rivalry"
    ]],
    "overall_pressure": 3,
    "synthesis": "Rivalry among large global banks is intensifying, squeezing Citi’s margins.",
    "sources": [f"(Source{i}, 2024)" for i in range(6)],
    "skip": None
}

def test_schema_accepts_valid_payload():
    result = FiveForcesResult.model_validate(deepcopy(BASE_PAYLOAD))
    assert result.overall_pressure == 3

def test_rating_out_of_range_fails():
    bad = deepcopy(BASE_PAYLOAD)
    bad["analysis"][0]["rating"] = 7          # invalid
    with pytest.raises(Exception):
        FiveForcesResult.model_validate(bad)

def test_too_few_sources_fails():
    bad = deepcopy(BASE_PAYLOAD)
    bad["sources"] = ["(OnlyOne, 2024)"]
    with pytest.raises(Exception):
        FiveForcesResult.model_validate(bad)
