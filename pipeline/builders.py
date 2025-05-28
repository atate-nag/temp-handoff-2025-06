# pipeline/builders.py
import json
from typing import Dict, Any

from utils.cache_io import cached
from agent_and_assessor import run_single_workflow_with_verifier

# 👉 import the agents only once here
from local_agents.background_agent       import background_agent
from local_agents.trend_radar_agent      import trend_radar_agent
from local_agents.pest_agent             import pest_agent
from local_agents.financial_screen_agent import financial_screener_agent
from local_agents.citation_verifier      import citation_verifier_agent

# ----------------------------- helpers ---------------------------------- #

def _run(agent, prompt: str, label: str, rounds: int = 1) -> Dict[str, Any]:
    """Shared thin wrapper around the run_single_workflow_with_verifier call."""
    raw = run_single_workflow_with_verifier(
        generator_agent=agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=prompt,
        label=label,
        max_rounds=rounds,
    )
    return json.loads(raw)

# ------------------------- cached builders ------------------------------ #

@cached("background")
def build_background(prompt: str) -> Dict[str, Any]:
    return _run(background_agent, prompt, "Background")

@cached("trend_radar")
def build_trend_radar(prompt: str) -> Dict[str, Any]:
    return _run(trend_radar_agent, prompt, "Trend Radar")

@cached("pest")
def build_pest(prompt: str) -> Dict[str, Any]:
    return _run(pest_agent, prompt, "PEST")

@cached("finance")
def build_finance(prompt: str) -> Dict[str, Any]:
    return _run(financial_screener_agent, prompt, "Financial Screener")
