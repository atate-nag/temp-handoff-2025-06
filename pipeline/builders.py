# pipeline/builders.py
import json
from typing import Dict, Any

from utils.cache_io import cached
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

from local_agents.forces_agent import validate_forces

# ───────────────────────────────── helpers ──────────────────────────────────

import json, logging, re
log = logging.getLogger(__name__)

def _safe_json(s: str, label: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        log.warning("%s – JSON parse failed: %s…", label, e)
        # attempt simple fix – replace smart quotes & strip trailing commas
        cleaned = re.sub(r"[“”]", '"', s).rstrip(", \n")
        try:
            return json.loads(cleaned)
        except Exception:
            return {"error": "invalid_json", "raw": cleaned}

# def _run(agent, prompt: str, label: str, rounds: int = 1):
#     raw = run_single_workflow_with_verifier(...)
#     if label == "5-Forces":          # nested dict expected
#         return _safe_json(raw.strip("` \n"), label)
#     return raw if isinstance(raw, dict) else _safe_json(raw, label)


def _run(agent, prompt: str, label: str, rounds: int = 1):
    """
    Call the LLM agent + citation-verifier and return parsed JSON/str.
    If `raw` looks like JSON → dict; otherwise → untouched string.
    """
    raw = run_single_workflow_with_verifier(
        generator_agent=agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=prompt,
        label=label,
        max_rounds=rounds,
    )
    if label == "5-Forces":          # nested dict expected
        return _safe_json(raw.strip("` \n"), label)
    return raw if isinstance(raw, dict) else _safe_json(raw, label)

    # normalise citations (this keeps the type – str in, str out)
    # if isinstance(raw, str):
    #     raw = normalise_cites(raw)
    #
    # # ------------------------------------------------------------------
    # # Safe JSON sniffing
    # # ------------------------------------------------------------------
    # if isinstance(raw, dict):
    #     return raw
    # try:
    #     return json.loads(raw)
    # except json.JSONDecodeError:
    #     return json.loads(raw.strip("` \n"))

    # stripped = raw.lstrip()
    # if stripped.startswith("{") or stripped.startswith("["):
    #     try:
    #         return json.loads(stripped)   # happy path
    #     except json.JSONDecodeError as err:
    #         print(f"{label}: Looks like JSON but failed to parse – "
    #                        f"{err}. Returning raw string.")





# ───────────────────────────── cached builders ──────────────────────────────
# NB: the extra `*, refresh: bool = False` is only there so callers can supply
#     refresh=True; the value is stripped by the decorator wrapper.

@cached("background")
def build_background(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(background_agent, prompt, "Background")

@cached("trend_radar")
def build_trend_radar(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(trend_radar_agent, prompt, "Trend Radar")

@cached("pest")
def build_pest(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(pest_agent, prompt, "PEST")

@cached("mini-crux")
def build_mini_crux(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(pest_agent, prompt, "Mini Crux")

@cached("framework-selector")
def build_framework_selector(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(pest_agent, prompt, "Framework Selector")

@cached("challenges")
def build_challenges(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(pest_agent, prompt, "Challenges")

@cached("synth")
def build_synth(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(pest_agent, prompt, "Synthesizer")

@cached("finance")
def build_finance(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(financial_screener_agent, prompt, "Financial Screener")

def build_forces(prompt: str, *, refresh: bool = False) -> dict:
    raw = _run(forces_agent, prompt, "5-Forces")
    data = raw if isinstance(raw, dict) else json.loads(raw)

    # ⇣ accept flat OR wrapped schema
    if "analysis" not in data:
        # convert flat ⇒ wrapped
        forces_keys = [
            "threat_of_entry","supplier_power","buyer_power",
            "threat_of_substitutes","rivalry"
        ]
        analysis = []
        for k in forces_keys:
            if k not in data:
                raise ValueError(f"Missing {k}")
            entry = data.pop(k)
            entry["force"] = k
            analysis.append(entry)
        data = {
            "analysis": analysis,
            "overall_pressure": int(round(sum(e["rating"] for e in analysis)/len(analysis))),
            "skip": None,
            **data      # keeps synthesis, sources, etc.
        }

    data = validate_forces(data)          # now passes
    return data


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

