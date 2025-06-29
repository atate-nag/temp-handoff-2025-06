import json, pathlib
from schemas import (TrendRadarResult, PestResult,
                     InitialCruxResult, FiveForcesResult)

def _load(name):
    p = pathlib.Path(".debug") / f"{name}.json"
    return json.loads(p.read_text())

def test_cached_payloads_validate():
    TrendRadarResult.model_validate(_load("trend_radar"))
    PestResult.model_validate(_load("pest"))
    InitialCruxResult.model_validate(_load("mini_crux"))
    FiveForcesResult.model_validate(_load("forces"))