#!/usr/bin/env python3
"""Refactored Socrates main entry‑point.

* Caches the *expensive* background + trend‑radar + PEST + finance bundle so that
  rapid iterations on the downstream specialist‑analysis / report‑writing steps
  take seconds, not ~20 minutes.
* Keeps **one file** to avoid a multi‑module diff‑fest while we continue to
  iterate quickly. When it stabilises we can split the builders into a separate
  `pipeline_builders.py`.

Environment flags
-----------------
* `CACHE_DIR`   folder where cached JSON blobs live   (default: `.cache`)
* `REFRESH_CACHE=1`   force a rebuild even if a cache file exists
* `FORCES_ONLY=1`    handy debug: only run Porter 5‑Forces
"""

from __future__ import annotations

import asyncio, datetime, json, logging.config, os, pickle
from pathlib import Path
from typing import Any, Dict, Tuple, Callable

from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────────────────────
# Local imports (unchanged from your original file)
# ──────────────────────────────────────────────────────────────────────────────
from agents import Agent
from agent_and_assessor import (
    run_single_workflow_with_verifier,
    single_agent_verify_assess_loop,
)
from company_data import fetch_basic_financials, get_file_paths, ticker_map
from filehandler import FileHandler
from model_connector import ModelConnectorFactory
from utils.capability_plot import generate_capability_plot
from utils.md_to_docx import md_to_docx, write_markdown
from utils.token_tools import as_token_limited_json, MAX_PROMPT_TOKENS

# All the AI agents -----------------------------------------------------------
from local_agents.background_agent import background_agent
from local_agents.bcg_matrix_agent import bcg_matrix_agent
from local_agents.blue_ocean_agent import blue_ocean_agent
from local_agents.bowman_clock_agent import bowman_clock_agent
from local_agents.challenge_processing_agent import challenge_processing_agent
from local_agents.citation_verifier import citation_verifier_agent
from local_agents.core_competence_agent import core_competence_agent
from local_agents.five_forces_assessor_agent import five_forces_assessor_agent
from local_agents.financial_screen_agent import financial_screener_agent
from local_agents.forces_agent import forces_agent
from local_agents.framework_selector_agent import framework_selector_agent
from local_agents.generic_assessor_agent import generic_assessor_agent
from local_agents.ge_mckinsey_agent import ge_mckinsey_agent
from local_agents.initial_crux_agent import initial_crux_agent
from local_agents.pest_agent import pest_agent
from local_agents.report_assessor_agent import report_assessor_agent
from local_agents.report_composer_agent import report_composer_agent
from local_agents.seven_s_agent import seven_s_agent
from local_agents.synthesizer_agent import synthesizer_agent
from local_agents.trend_radar_agent import trend_radar_agent
from local_agents.value_chain_agent import value_chain_agent
from local_agents.VRIO_agent import vrio_agent
from local_agents.ansoff_agent import ansoff_agent

# ──────────────────────────────────────────────────────────────────────────────
# GLOBALS & one‑off setup
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
CACHE_DIR.mkdir(exist_ok=True)

# quick way to switch every generator to the new model
o3_agents = [
    trend_radar_agent,
    pest_agent,
    financial_screener_agent,
    initial_crux_agent,
    forces_agent,
    vrio_agent,
    challenge_processing_agent,
    synthesizer_agent,
    report_composer_agent,
    generic_assessor_agent,
    bcg_matrix_agent,
    blue_ocean_agent,
    value_chain_agent,
    seven_s_agent,
    ansoff_agent,
    ge_mckinsey_agent,
    core_competence_agent,
    bowman_clock_agent,
    report_assessor_agent,
]
for _ag in o3_agents:
    _ag.model = "o3-mini"

# logging ---------------------------------------------------------------------
if "socrates_main" not in logging.root.manager.loggerDict:
    logging.config.fileConfig(
        "config/logging_config_socrates.ini",
        defaults={"date": datetime.datetime.now()},
        disable_existing_loggers=True,
    )
logger = logging.getLogger("socrates_main")
logger.info("Started Socrates Main")
import logging, utils.cache_io

logging.getLogger(utils.cache_io.__name__).setLevel(logging.INFO)

# model‑connector (unchanged) -------------------------------------------------
# model_config = {
#     "model_type": "openai_assistants",
#     "api_key": os.getenv("OPENAI_API_KEY"),
#     "model": "gpt-o3",
# }
file_handler = FileHandler()
REFRESH_CACHE = False  # os.getenv("REFRESH_CACHE", "0") == "1"  # 1 - builders will run, 0 - use cached results


# ──────────────────────────────────────────────────────────────────────────────
# Helper builders with caching
# ──────────────────────────────────────────────────────────────────────────────


def _cache_path(company: str, tag: str) -> Path:
    return CACHE_DIR / f"{company.replace(' ', '_')}_{tag}.pkl"


from typing import Dict, Any, Tuple
from utils.trend_radar import save_trend_radar_png
from utils.token_tools import as_token_limited_json
import pipeline.builders as builders
from pipeline.builders import (
    build_background, build_trend_radar, build_pest, build_finance,
    build_forces, build_vrio, build_blue, build_bcg, build_value,
    build_7s, build_ansoff, build_gem, build_core, build_bowman,
)

import json, hashlib


def stable_json(obj: Any) -> str:
    """JSON dump with guaranteed key order and no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def build_background_bundle(
        company_name: str,
        company_data: Dict[str, Any],
        trends: list[str],
) -> Tuple[Dict[str, Any], str]:
    # 1) prompts
    bg_prompt = f"Company Data:{company_data} Trends:{trends}"
    tr_prompt = f"Company Data:{company_data} All Trends:{trends}"
    fin_prompt = f"company_data: {company_data} "

    # 2) run (cached) builders
    trend_radar_dict = builders.build_trend_radar(tr_prompt,
                                                  refresh=REFRESH_CACHE)
    pest_prompt = f"trend_radar : {trend_radar_dict} company_data: {company_data}"
    pest_dict = build_pest(pest_prompt, refresh=REFRESH_CACHE)
    background_dict = build_background(bg_prompt, refresh=REFRESH_CACHE)
    finance_dict = build_finance(fin_prompt, refresh=REFRESH_CACHE)

    # 3) draw radar image
    cats = {
        c["short_name"]: [
            {
                "trend": t,
                "importance": c["impact"],
                "likelihood": 3,
                "readiness": 8 if c["direction"] == "opportunity" else 5,
            }
            for t in c["top_trends"]
        ]
        for c in trend_radar_dict["trend_clusters"]
    }
    radar_path = save_trend_radar_png(cats, company_name)

    # 4) assemble bundle
    background_bundle: Dict[str, Any] = {
        "company_overview": background_dict.get("company_overview", ""),
        "trend_radar": trend_radar_dict,
        "pest": pest_dict,
        "finance": finance_dict,
        "frameworks_chosen": [],
        "frameworks_rationale_md": "",
    }

    return background_bundle, radar_path


# ──────────────────────────────────────────────────────────────────────────────
# CORE PIPELINE (run_strategy)
# ──────────────────────────────────────────────────────────────────────────────

def run_strategy(company_name: str, problems_file: str, *, max_rounds: int = 3) -> None:
    """High‑level orchestration – now ~3× faster on reruns thanks to caching."""

    logger.info("Running strategy for %s", company_name)
    FORCES_ONLY = os.getenv("FORCES_ONLY", "0") == "1"

    # ── 1.  Load local data --------------------------------------------------
    cname = company_name.replace(" ", "_").replace("'", "")
    pfp, tfp, cfp = get_file_paths(cname, problems_file, file_handler)
    trends = file_handler.local_json_read(tfp)
    company_data = file_handler.local_json_read(cfp)

    if isinstance(company_data, list):
        first = company_data[0] if company_data else ""
        overview = first.get("statement") if isinstance(first, dict) else str(first)[:200]
        company_data = {"overview": overview, "data": company_data}

    ticker = ticker_map.get(company_name, "")
    company_data.setdefault("financials", fetch_basic_financials(ticker))

    # ── 2.  Build / load background bundle ----------------------------------
    background_dict, radar_path = build_background_bundle(
        company_name, company_data, trends
    )

    # ── 3.  MINI‑CRUX --------------------------------------------------------
    pre_prompt = f"Background: {json.dumps(background_dict)}"
    initial_crux_json = run_single_workflow_with_verifier(
        generator_agent=initial_crux_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=pre_prompt,
        label="Initial Crux",
        max_rounds=1,
    )
    logger.info("Initial Crux JSON: %s", initial_crux_json)

    # ── 4.  Framework selector ----------------------------------------------
    sel_prompt = (
        f"Crux: {initial_crux_json}\n"
        f"Background: {json.dumps(background_dict)[:8000]}"
    )
    selector_raw = run_single_workflow_with_verifier(
        generator_agent=framework_selector_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=sel_prompt,
        label="Framework Selector",
        max_rounds=1,
    )
    try:
        flags: Dict[str, Any] = json.loads(selector_raw)
    except json.JSONDecodeError:
        logger.warning("Selector JSON failed – defaulting to Porter + PEST")
        flags = {"use_porter": True, "use_pest": True, "rationale": {}}

    # ── 5.  Map flags → specialist agents -----------------------------------
    flag_to_agent: Dict[str, Tuple[str, Agent, Agent]] = {
        "use_porter": ("forces", forces_agent, generic_assessor_agent),
        "use_pest": ("pest", pest_agent, generic_assessor_agent),
        "use_vrio": ("vrio", vrio_agent, generic_assessor_agent),
        "use_blue_ocean": ("blue", blue_ocean_agent, generic_assessor_agent),
        "use_bcg": ("bcg", bcg_matrix_agent, generic_assessor_agent),
        "use_value_chain": ("value", value_chain_agent, generic_assessor_agent),
        "use_seven_s": ("7s", seven_s_agent, generic_assessor_agent),
        "use_ansoff": ("ansoff", ansoff_agent, generic_assessor_agent),
        "use_gem": ("gem", ge_mckinsey_agent, generic_assessor_agent),
        "use_core_comp": ("core", core_competence_agent, generic_assessor_agent),
        "use_bowman": ("bowman", bowman_clock_agent, generic_assessor_agent),
    }

    specialist_agents: Dict[str, Tuple[Agent, Agent]] = {}
    if FORCES_ONLY:
        specialist_agents["forces"] = (forces_agent, five_forces_assessor_agent)
    else:
        for flag, trip in flag_to_agent.items():
            if flags.get(flag):
                key, agent, assessor = trip
                specialist_agents[key] = (agent, assessor)

    if not specialist_agents:
        specialist_agents["forces"] = (forces_agent, generic_assessor_agent)

    print("→ specialist frameworks selected:", list(specialist_agents.keys()))

    # keep rationale for the report ----------------------------------------
    chosen_fw, rationale_md = _extract_framework_rationale(flags)
    background_dict.update({
        "frameworks_chosen": chosen_fw,
        "frameworks_rationale_md": rationale_md,
    })

    BG_TOKENS = MAX_PROMPT_TOKENS - 5_000
    spec_prompt = (
        f"Initial Crux: {initial_crux_json}\n"
        f"Background: {as_token_limited_json(background_dict, BG_TOKENS)}\n"
        f"Run analysis for {company_name}"
    )

    analyses: Dict[str, Any] = {}
    if "forces" in specialist_agents:
        analyses["forces"] = build_forces(spec_prompt, refresh=REFRESH_CACHE)
    if "vrio" in specialist_agents:
        analyses["vrio"] = build_vrio(spec_prompt, refresh=REFRESH_CACHE)
    if "blue" in specialist_agents:
        analyses["blue_ocean"] = build_blue(spec_prompt, refresh=REFRESH_CACHE)
    if "bcg" in specialist_agents:
        analyses["bcg"] = build_bcg(spec_prompt, refresh=REFRESH_CACHE)
    if "value" in specialist_agents:
        analyses["value_chain"] = build_value(spec_prompt, refresh=REFRESH_CACHE)
    if "7s" in specialist_agents:
        analyses["seven_s"] = build_7s(spec_prompt, refresh=REFRESH_CACHE)
    if "ansoff" in specialist_agents:
        analyses["ansoff"] = build_ansoff(spec_prompt, refresh=REFRESH_CACHE)
    if "gem" in specialist_agents:
        analyses["gem"] = build_gem(spec_prompt, refresh=REFRESH_CACHE)
    if "core" in specialist_agents:
        analyses["core_competence"] = build_core(spec_prompt, refresh=REFRESH_CACHE)
    if "bowman" in specialist_agents:
        analyses["bowman_clock"] = build_bowman(spec_prompt, refresh=REFRESH_CACHE)

    challenge_prompt = (
        f"Initial Crux: {initial_crux_json}\nAnalyses: {json.dumps(analyses)}\n"
        f"Trend Radar: {json.dumps(background_dict['trend_radar'])}"
    )
    challenge_json = run_single_workflow_with_verifier(
        generator_agent=challenge_processing_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=challenge_prompt,
        label="Challenge Processing",
        max_rounds=2,
    )
    analyses["challenge_map"] = json.loads(challenge_json)

    synth_prompt = (
        f"Initial Crux: {initial_crux_json}\nAnalyses: {json.dumps(analyses, indent=2)}"
    )
    synth_json = run_single_workflow_with_verifier(
        generator_agent=synthesizer_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=synth_prompt,
        label="Synthesizer",
        max_rounds=2,
    )
    analyses["synthesized_options"] = json.loads(synth_json)

    # ── 8.  Long‑form report (with Masters‑level assessor) -----------------
    report_bundle = {
        "company_overview": background_dict["company_overview"],
        "trend_radar": background_dict["trend_radar"],
        "crux": json.loads(initial_crux_json),
        "analyses": analyses,
        "challenge_map": analyses["challenge_map"],
        "synthesized_options": analyses["synthesized_options"],
        "frameworks_chosen": background_dict["frameworks_chosen"],
        "frameworks_rationale_md": background_dict["frameworks_rationale_md"],
    }

    long_report = asyncio.run(
        single_agent_verify_assess_loop(
            generator_agent=report_composer_agent,
            verifier_agent=citation_verifier_agent,
            assessor_agent=report_assessor_agent,
            initial_prompt=f"DATA BUNDLE:\n{report_bundle}",
            label="Long‑Form Report",
            max_rounds=3,
        )
    )
    print("\n=== LONG‑FORM STRATEGY REPORT (markdown) ===\n")
    print(long_report)

    # images
    if vrio_tbl := analyses.get("vrio", {}).get("vrio_table", []):
        cap_path = generate_capability_plot(vrio_tbl, company_name)
        long_report += f"\n\n![Capability Map]({os.path.basename(cap_path)})\n"
    if radar_path:
        long_report += f"\n\n![Trend‑Radar]({os.path.basename(radar_path)})\n"

    md_path = write_markdown(long_report, company_name)
    docx_path = md_to_docx(md_path, company_name)
    print("\nWord report saved →", docx_path)


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry‑point
# ──────────────────────────────────────────────────────────────────────────────

def _extract_framework_rationale(flags: Dict[str, Any]):
    name_map = {
        "porter": "Porter’s 5 Forces",
        "pest": "PEST",
        "vrio": "VRIO",
        "blue_ocean": "Blue‑Ocean",
        "bcg": "BCG Matrix",
        "value_chain": "Value‑Chain",
        "seven_s": "McKinsey 7‑S",
        "ansoff": "Ansoff Matrix",
        "gem": "GE/McKinsey 9‑Cell",
        "core_comp": "Core‑Competence",
        "bowman": "Bowman Clock",
    }
    chosen, md = [], []
    for k, pretty in name_map.items():
        if flags.get(f"use_{k}"):
            chosen.append(pretty)
            md.append(f"* **{pretty}** – {flags.get('rationale', {}).get(k, '')}")
    return chosen, "\n".join(md)


def main():
    company = os.getenv("COMPANY_NAME", "Citigroup")
    problems_file = os.getenv("PROBLEMS_FILE", "./problem_statements.json")
    run_strategy(company, problems_file)


if __name__ == "__main__":
    main()
