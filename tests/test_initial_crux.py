import json
from schemas import InitialCruxResult


def _bucket() -> list[str]:
    return ["Ops complexity (FT, 2024)", "Legacy tech debt (Citi, 2023)"]

def test_initial_crux_schema_accepts_valid_payload():
    payload = {
        "crux": "Fee compression and rising cyber-spend push ROE below cost of equity (BIS, 2024).",
        "evidence": ["(BIS, 2024)", "(WEF, 2023)"],
        "why_it_matters": "Sustained sub-COE returns threaten capital access and investor confidence (FT, 2024).",
        "internal_vs_external": {
            "internal": _bucket(),
            "external": _bucket(),
        },
        "error": None
    }

    # should not raise
    model = InitialCruxResult.model_validate(payload)
    assert json.loads(model.model_dump_json())  # serialises cleanly
