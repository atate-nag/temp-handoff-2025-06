# pipeline/builders.py
import json
from typing import Dict, Any

from utils.cache_io import cached
from utils.normalise_forces import normalise_forces
from utils.normalise_cites import normalise_cites
from agent_and_assessor import run_single_workflow_with_verifier

# Import the agents once
from local_agents.background_agent       import background_agent
from local_agents.trend_radar_agent      import trend_radar_agent
from local_agents.pest_agent             import pest_agent
from local_agents.financial_screen_agent import financial_screener_agent
from local_agents.citation_verifier      import citation_verifier_agent
# pipeline/builders.py  (append to the bottom)

from local_agents.forces_agent         import forces_agent
from local_agents.VRIO_agent           import vrio_agent
from local_agents.blue_ocean_agent     import blue_ocean_agent
from local_agents.bcg_matrix_agent     import bcg_matrix_agent
from local_agents.initial_crux_agent import initial_crux_agent
from local_agents.value_chain_agent    import value_chain_agent
from local_agents.seven_s_agent        import seven_s_agent
from local_agents.ansoff_agent         import ansoff_agent
from local_agents.ge_mckinsey_agent    import ge_mckinsey_agent
from local_agents.core_competence_agent import core_competence_agent
from local_agents.bowman_clock_agent    import bowman_clock_agent
from local_agents.report_composer_agent import report_composer_agent
from local_agents.report_assessor_agent import report_assessor_agent
from local_agents.company_profile_agent import company_profile_agent

# ===========
from local_agents.five_forces_assessor_agent import five_forces_assessor_agent
from local_agents.generic_assessor_agent import generic_assessor_agent
from pathlib import Path

# ───────────────────────────────── helpers ──────────────────────────────────

import json, logging, re
log = logging.getLogger(__name__)

_BRACE_DUP_RE = re.compile(r'},\s*}')     # catches  "},}"  or  "}, }"  etc.

SMART_QUOTES   = re.compile(r'[“”]')
DANGLING_COMMA = re.compile(r',(\s*[}\]])')
EXTRA_BRACE    = re.compile(r'},\s*}')
EMPTY_VALUE    = re.compile(r'"(\w+)":\s*,')   # "over":"",  or  "overall_pressure":,

FORCES_SCHEMA = {
    "force_meta": dict,               # optional
    "analysis": list,                 # 5 items, each with keys →
    "overall_pressure": (int, type(None)),
    "synthesis": dict,                # optional
    "sources": list,                  # ≥5 APA-style strings
    "skip": (str, type(None)),        # optional
}
FORCE_NAMES = {
    "threat_of_entry",
    "supplier_power",
    "buyer_power",
    "threat_of_substitutes",
    "rivalry",
}
def clean_llm_json(text: str) -> str:
    """Idempotent, order-agnostic normaliser for almost-valid LLM JSON."""
    text = SMART_QUOTES.sub('"', text)
    text = EXTRA_BRACE.sub('},', text)
    text = EMPTY_VALUE.sub(r'"\1": null,', text)
    text = DANGLING_COMMA.sub(r'\1', text)
    return text.strip().strip('`')

def _safe_json(raw: str, label: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fixed = clean_llm_json(raw)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            log.error("%s – JSON still invalid after fix: %s", label, e)
            return {"error": "invalid_json", "raw": fixed}

ASSESSOR_MAP = {
    "forces":  five_forces_assessor_agent,
    "VRIO":      generic_assessor_agent,
    "Blue-Ocean":generic_assessor_agent,
    "BCG Matrix":generic_assessor_agent,
    "Value-Chain":generic_assessor_agent,
    "McKinsey 7-S":generic_assessor_agent,
    "Ansoff":    generic_assessor_agent,
    "GE/McKinsey":generic_assessor_agent,
    "Core-Competence":generic_assessor_agent,
    "Bowman Clock":generic_assessor_agent,
    # "Report Agent" handled separately below
}

# 3️⃣  drop-in replacement for _run()
def _run(agent, prompt: str, label: str, rounds: int = 1):
    """
    Call LLM generator + citation-verifier (+ optional assessor) and
    return parsed JSON/str.
    """
    assessor = ASSESSOR_MAP.get(label)
    raw = run_single_workflow_with_verifier(
        generator_agent=agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=assessor,
        initial_prompt=prompt,
        label=label,
        max_rounds=rounds,
    )

    # ── SPECIAL-CASE: Five Forces needs pre-normalisation ────────────
    # if label == "5-Forces":
    #     parsed = _safe_json(raw.strip("` \n"), label)
    #     # normalise BEFORE verifier / assessor results are surfaced
    #     return normalise_forces(parsed)

    return raw if isinstance(raw, dict) else _safe_json(raw, label)

# ───────────────────────────── cached builders ──────────────────────────────
# NB: the extra `*, refresh: bool = False` is only there so callers can supply
#     refresh=True; the value is stripped by the decorator wrapper.

@cached("background")
def build_background(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(background_agent, prompt, "Background")

from schemas import TrendRadarResult
@cached("trend_radar")
def build_trend_radar(prompt: str, *, refresh: bool = False) -> TrendRadarResult:
    res_dict = _run(trend_radar_agent, prompt, "Trend Radar")
    trend_radar = TrendRadarResult.model_validate(res_dict)
    (Path(".debug") / "trend_radar.json").write_text(trend_radar.model_dump_json(indent=2))
    return trend_radar

from schemas import PestResult
@cached("pest")
def build_pest(prompt: str, *, refresh: bool = False) -> PestResult:
    res_dict = _run(pest_agent, prompt, "PEST")
    pest =  PestResult.model_validate(res_dict)
    (Path(".debug") / "pest.json").write_text(pest.model_dump_json(indent=2))
    return pest


from schemas import InitialCruxResult
@cached("mini-crux")
def build_mini_crux(prompt: str, *, refresh: bool = False) -> InitialCruxResult:
    mini_crux_dict =_run(initial_crux_agent, prompt, "Mini Crux")
    mini_crux = InitialCruxResult.model_validate(mini_crux_dict)
    (Path(".debug") / "mini_crux.json").write_text(mini_crux.model_dump_json(indent=2))
    return mini_crux

@cached("framework-selector")
def build_framework_selector(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(pest_agent, prompt, "Framework Selector")

@cached("challenges")
def build_challenges(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(pest_agent, prompt, "Challenges")

# ───────────────────────────── cached builders ──────────────────────────────
# pipeline/builders.py  – replace the current build_synth

@cached("synth")
def build_synth(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    """
    Pull citations straight from the latest trend-radar payload.
    This avoids an unnecessary LLM call and guarantees we always
    have some citations for the report.
    """
    # 1️⃣ Ensure we use the most recent radar (respect refresh flag)
    radar_doc = build_trend_radar(prompt, refresh=refresh)

    # 2️⃣ Grep APA-style citations from the JSON dump
    import re, json
    APA_RE = re.compile(r"\([^)]+,\s?\d{4}\)")
    flat = json.dumps(radar_doc, ensure_ascii=False)
    cites = set(APA_RE.findall(flat))

    # 3️⃣ Return the same shape every caller already expects
    return {
        "synth_payload": radar_doc,                 # whatever we may need later
        "citations": cites,                         # usable programmatically
        "citations_md": " ".join(sorted(cites)),    # string for the doc template
    }



@cached("finance")
def build_finance(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(financial_screener_agent, prompt, "Financial Screener")

RATING_MAP = {
    "very low": 1, "low": 2, "medium": 3, "high": 4, "very high": 5
}

def _to_int_rating(val):
    """
    Ensure every rating is an int 1-5.
    Accepts words (Low, High, etc.) or numeric strings.
    """
    if isinstance(val, int):
        return max(1, min(5, val))
    if isinstance(val, str):
        val = val.strip().lower()
        if val in RATING_MAP:
            return RATING_MAP[val]
        if val.isdigit():
            return max(1, min(5, int(val)))
    raise ValueError(f"Unrecognised rating: {val!r}")


from schemas import FiveForcesResult, Artifact, ArtifactKind

@cached("forces")
def build_forces(prompt: str, *, refresh=False) -> Artifact:
    raw = _run(forces_agent, prompt, "5‑Forces")
    model = FiveForcesResult.model_validate(raw)

    return Artifact(
        id="forces",
        kind=ArtifactKind.ANALYSIS,
        payload=model.model_dump(mode="json"),
        sources=model.sources or [],
        tags=["porter", "competitive_dynamics"],
    )


@cached("vrio")
def build_vrio(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(vrio_agent, prompt, "VRIO")

@cached("blue")
def build_blue(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(blue_ocean_agent, prompt, "Blue-Ocean")

@cached("bcg")
def build_bcg(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(bcg_matrix_agent, prompt, "BCG Matrix")

@cached("value")
def build_value(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(value_chain_agent, prompt, "Value-Chain")

@cached("7s")
def build_7s(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(seven_s_agent, prompt, "McKinsey 7-S")

@cached("ansoff")
def build_ansoff(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(ansoff_agent, prompt, "Ansoff")

@cached("gem")
def build_gem(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(ge_mckinsey_agent, prompt, "GE/McKinsey")

@cached("core")
def build_core(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(core_competence_agent, prompt, "Core-Competence")

@cached("bowman")
def build_bowman(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(bowman_clock_agent, prompt, "Bowman Clock")


@cached("report")
def build_report(prompt: str, *, refresh: bool = False) -> str:
    report = run_single_workflow_with_verifier(
        generator_agent=report_composer_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=report_assessor_agent,
        initial_prompt=prompt,
        label="Report Agent",
        max_rounds=3,
    )
    return report

# pipeline/builders.py
@cached("company_profile")
def build_company_profile(prompt: str, *, refresh: bool = False):
    return _run(company_profile_agent, prompt, "Company Profile")

