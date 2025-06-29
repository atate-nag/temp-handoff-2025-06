# tests/test_trend_radar_schema.py
from schemas import TrendRadarResult

def _dummy_cluster():
    return {
        "short_name": "Digital Payments",
        "impact": 5,
        "time_horizon": "now",
        "direction": "opportunity",
        "top_trends": ["RTP rails expanding", "QR codes mainstream"],
        "evidence": ["(WEF, 2024)"]
    }

def test_trend_radar_schema_accepts_valid_payload():
    data = {
        "trend_clusters": [_dummy_cluster() for _ in range(3)],
        "sources": ["(WEF, 2024)", "(McKinsey, 2023)"],
        "error": None
    }
    assert TrendRadarResult.model_validate(data)
