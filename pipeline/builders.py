# pipeline/builders.py
import json
from typing import Dict, Any

from utils.cache_io import cached
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

# ───────────────────────────────── helpers ──────────────────────────────────
def _run(agent, prompt: str, label: str, rounds: int = 1) -> Dict[str, Any]:
    """Call the LLM agent + citation-verifier and return parsed JSON."""
    raw = run_single_workflow_with_verifier(
        generator_agent=agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=prompt,
        label=label,
        max_rounds=rounds,
    )
    return json.loads(raw)


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

@cached("finance")
def build_finance(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(financial_screener_agent, prompt, "Financial Screener")

@cached("forces")        # → .cache/build_forces_*.pkl
def build_forces(prompt: str, *, refresh: bool = False) -> Dict[str, Any]:
    return _run(forces_agent, prompt, "5-Forces")

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
