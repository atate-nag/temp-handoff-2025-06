# tests/test_pest_schema.py
from schemas import PestResult
# tests/test_pest_schema.py
def _dummy_bucket() -> dict:
    """Return a valid _PestCategory-shaped bucket."""
    return {
        "bullets": [
            "Some macro bullet (SourceA, 2024)",
            "Another point (SourceB, 2023)",
            "Numeric datapoint (SourceC, 2022)",
            "Data unavailable"
        ],
        "quant": None           # could also omit; field is optional
    }


def test_pest_schema_accepts_valid_payload():
    data = {
        "pest_bullets": {
            "Political": _dummy_bucket(),
            "Economic":  _dummy_bucket(),
            "Social":    _dummy_bucket(),
            "Technological": _dummy_bucket(),
        },
        "sources": [f"(Source{i}, 2024)" for i in range(6)],
        "error": None
    }

    # should not raise
    result = PestResult.model_validate(data)
    assert result.pest_bullets.Political.bullets[0].endswith("2024)")