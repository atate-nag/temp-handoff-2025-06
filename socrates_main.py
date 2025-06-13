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
import re
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
from local_agents.forces_agent import forces_agent, generate_forces_prompt
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

from company_data import get_gics_code_and_name

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
    _ag.model = "o3"

forces_agent.model = "o3"


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

file_handler = FileHandler()

BG_TOKENS = MAX_PROMPT_TOKENS - 5_000

REFRESH_ONLY = {
    s.strip().lower()
    for s in os.getenv("REFRESH_ONLY", "").split(",")
    if s.strip()
}
def needs_refresh(tag: str) -> bool:
    # global REFRESH_CACHE retains the old “force everything” switch
    return REFRESH_CACHE or tag in REFRESH_ONLY

REFRESH_CACHE = False  # os.getenv("REFRESH_CACHE", "0") == "1"  # 1 - builders will run, 0 - use cached results
def _cache_path(company: str, tag: str) -> Path:
    return CACHE_DIR / f"{company.replace(' ', '_')}_{tag}.pkl"
def fix_citations(md:str)->str:
    md = re.sub(r'\(([A-Za-z0-9_]+),\s*([0-9]{4})\)',
                lambda m: f'({m.group(1).replace("_","")}, {m.group(2)})',
                md)
    return md

from typing import Dict, Any, Tuple
from utils.trend_radar import save_trend_radar_png
from utils.token_tools import as_token_limited_json
import pipeline.builders as builders
from pipeline.builders import (
    build_background, build_trend_radar, build_pest, build_finance,
    build_forces, build_vrio, build_blue, build_bcg, build_value, build_framework_selector,
    build_7s, build_ansoff, build_gem, build_core, build_bowman, build_mini_crux, build_challenges,
    build_synth, build_report, build_company_profile
)

import json, hashlib


def build_background_bundle(
            company_name: str,
            company_profile: Dict[str, Any],  # renamed
            trends: list[str],
    ) -> Tuple[Dict[str, Any], str]:
    # 1) prompts
    bg_prompt = f"Company Profile: {company_profile}\nTrends: {trends}"
    tr_prompt = f"Company Profile: {company_profile}\nAll Trends: {trends}"
    fin_prompt = f"Company Profile: {company_profile}"

    # 2) run (cached) builders
    trend_radar_dict = builders.build_trend_radar(tr_prompt,
                                                  refresh=needs_refresh("trend_radar"))
    pest_prompt = f"trend_radar : {trend_radar_dict} Company Profile: {company_profile}\n"
    pest_dict = build_pest(pest_prompt, refresh=needs_refresh("pest"))
    background_dict = build_background(bg_prompt, refresh=needs_refresh("background"))
    finance_dict = build_finance(fin_prompt, refresh=needs_refresh("finance"))

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
    background_bundle = {
        "company_overview": company_profile.get("overview", ""),
        "company_profile": company_profile,
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
    frameworks = ["forces", "pest", "vrio", "blue_ocean", "bcg", "value_chain",
                  "seven_s", "ansoff", "gem", "core_competence", "bowman_clock"]

    # ── 1.  Load local data --------------------------------------------------
    cname = company_name.replace(" ", "_").replace("'", "")
    pfp, tfp, cfp = get_file_paths(cname, problems_file, file_handler)
    trends = file_handler.local_json_read(tfp)
    company_data = file_handler.local_json_read(cfp)
    codes, gics_names = get_gics_code_and_name(company_name)

    if isinstance(company_data, list):
        first = company_data[0] if company_data else ""
        overview = first.get("statement") if isinstance(first, dict) else str(first)[:200]
        company_data = {"overview": overview, "data": company_data}

    ticker = ticker_map.get(company_name, "")
    company_data.setdefault("financials", fetch_basic_financials(ticker))

    profile_payload = json.dumps({
        "company_name": company_name,
        "condensed_company_text": company_data,  # what you already pulled from Neo4j
        "gics_names": gics_names  # if you have them; else []
    })

    company_profile = builders.build_company_profile(
        profile_payload,
        refresh=needs_refresh("company_profile")  # same helper you use elsewhere
    )

    print("Company Profile:", json.dumps(company_profile, indent=2))

    # ── 2.  Build / load background bundle ----------------------------------
    background_dict, radar_path = build_background_bundle(
        company_name,
        company_profile,
        trends
    )

    # ── 3.  MINI‑CRUX --------------------------------------------------------
    pre_prompt = f"Background: {json.dumps(background_dict)}"
    f"Company Profile: {json.dumps(company_profile)}\n"
    mini_crux_dict = build_mini_crux(pre_prompt, refresh=needs_refresh("mini_crux"))
    pre_prompt = f"Background: {json.dumps(background_dict)}"
    logger.info("Initial Crux JSON: %s", mini_crux_dict)

    # ── 4.  Framework selector ----------------------------------------------
    sel_prompt = (
        f"Crux: {as_token_limited_json(mini_crux_dict, BG_TOKENS)}\n "
        f"Background: {as_token_limited_json(background_dict, BG_TOKENS)}\n"
    )
    selector_raw = build_framework_selector(sel_prompt, refresh=needs_refresh("framework_selector"))

    logger.info(f"Framework selector output (raw): {selector_raw}")
    flags = selector_raw
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

    spec_prompt = (
        f"Initial Crux: {as_token_limited_json(mini_crux_dict, BG_TOKENS)}\n"
        f"Company Profile: {json.dumps(company_profile, indent=2)}\n"
        f"Run analysis for {company_name}"
    )

    forces_prompt = generate_forces_prompt(company_profile, background_dict, mini_crux_dict, BG_TOKENS)

    analyses: Dict[str, Any] = {}
    if "forces" in specialist_agents:
        out = build_forces(forces_prompt, refresh=True)
        print("Porter’s Five Forces output:", out)
        analyses["forces"] = out
        print("Porter’s Five Forces analysis:", analyses["forces"])
    if "vrio" in specialist_agents:
        analyses["vrio"] = build_vrio(spec_prompt, refresh=needs_refresh("vrio"))
        print("VRIO analysis:", analyses["vrio"])
    if "blue" in specialist_agents:
        analyses["blue_ocean"] = build_blue(spec_prompt, refresh=needs_refresh("blue"))
        print("Blue Ocean analysis:", analyses["blue_ocean"])
    if "bcg" in specialist_agents:
        analyses["bcg"] = build_bcg(spec_prompt, refresh=needs_refresh("bcg"))
        print("BCG Matrix analysis:", analyses["bcg"])
    if "value" in specialist_agents:
        analyses["value_chain"] = build_value(spec_prompt, refresh=needs_refresh("value"))
        print("Value Chain analysis:", analyses["value_chain"])
    if "7s" in specialist_agents:
        analyses["seven_s"] = build_7s(spec_prompt, refresh=needs_refresh("7s"))
        print("7S analysis:", analyses["seven_s"])
    if "ansoff" in specialist_agents:
        analyses["ansoff"] = build_ansoff(spec_prompt, refresh=needs_refresh("ansoff"))
        print("Ansoff Matrix analysis:", analyses["ansoff"])
    if "gem" in specialist_agents:
        analyses["gem"] = build_gem(spec_prompt, refresh=needs_refresh("gem"))
        print("GE/McKinsey Matrix analysis:", analyses["gem"])
    if "core" in specialist_agents:
        analyses["core_competence"] = build_core(spec_prompt, refresh=needs_refresh("core_competence"))
        print("Core Competence analysis:", analyses["core_competence"])
    if "bowman" in specialist_agents:
        analyses["bowman_clock"] = build_bowman(spec_prompt, refresh=needs_refresh("bowman"))
        print("Bowman’s Clock analysis:", analyses["bowman_clock"])

    challenge_prompt = (
        f"Initial Crux: {as_token_limited_json(mini_crux_dict, BG_TOKENS)}\nAnalyses: {json.dumps(analyses)}\n"
        f"Trend Radar: {json.dumps(background_dict['trend_radar'])}"
    )
    challenge_dict = build_challenges(challenge_prompt, refresh=needs_refresh("challenges"))
    analyses["challenge_map"] = challenge_dict

    synth_prompt = (
        f"Initial Crux: {as_token_limited_json(mini_crux_dict, BG_TOKENS)}\nAnalyses: {json.dumps(analyses, indent=2)}"
    )
    synth_dict = build_synth(synth_prompt, refresh=needs_refresh("synth"))
    analyses["synthesized_options"] = synth_dict

    # ── 8.  Long‑form report (with Masters‑level assessor) -----------------
    report_bundle = {
        "company_overview": background_dict["company_overview"],
        "trend_radar": background_dict["trend_radar"],
        "crux": as_token_limited_json(mini_crux_dict, BG_TOKENS),
        "analyses": analyses,
        "challenge_map": analyses["challenge_map"],
        "synthesized_options": analyses["synthesized_options"],
        "frameworks_chosen": background_dict["frameworks_chosen"],
        "frameworks_rationale_md": background_dict["frameworks_rationale_md"],
    }

    framework_md = ""
    for fw in frameworks:  # frameworks = list like ["forces","pest"]
        sec = report_bundle["analyses"].get(fw, {})
        if not sec:
            framework_md += f"## {fw.title()} – *Data unavailable*\n"
        else:
            if fw == "forces":
                # inside run_strategy after you’ve loaded forces_json
                forces = analyses["forces"]  # new nested structure
                key_map = {
                    "threat_of_entry": "Threat of new entrants",
                    "supplier_power": "Supplier power",
                    "buyer_power": "Buyer power",
                    "threat_of_subs": "Threat of substitutes",
                    "rivalry": "Rivalry",
                }
                bullets = []
                for k, label in key_map.items():
                    if k not in forces:
                        continue
                    meta = forces[k]  # {'rating':'Low','reason':'...'}
                    bullets.append(f"- **{label} – {meta['rating'].title()}**: {meta['reason']}")
                framework_md = "\n".join(bullets)
            elif fw == "pest":
                framework_md += "## PEST Highlights\n" + sec.get("pest_summary_md", "*Data unavailable*") + "\n"
            else:
                framework_md += f"## {fw.upper()} Summary\n{sec.get('summary', '*Data unavailable*')}\n"

    challenge_tbl = report_bundle["challenge_map"].get("table_md", "*Data unavailable*")

    from utils.report_blocks import forces_to_md, challenges_to_table

    # --- 8.a · framework blocks -------------------------------------------------
    from utils.report_blocks import (
        forces_to_md, pest_to_md, challenges_to_table, grab_citations
    )

    # ---- 2.a · frameworks_sections_md -----------------------------------------
    sections = []
    for key in background_dict["frameworks_chosen"]:
        data = analyses.get(key, {})
        if not data:
            sections.append(f"## {key.title()} – *Data unavailable*")
            continue

        if key == "forces":
            body = forces_to_md(data)
            sections.append(f"## Porter’s Five Forces\n{body}")

        elif key == "pest":
            body = pest_to_md(data.get("pest_bullets", {}))
            sections.append(f"## PEST Highlights\n{body}")

        # add elif blocks for vrio / value_chain / etc. when they come online

    frameworks_sections_md = "\n\n".join(sections) or "*Data unavailable*"

    # ---- 2.b · challenge_table_md ---------------------------------------------
    challenge_list = analyses.get("challenge_map", {}).get("challenges", [])
    challenge_table_md = challenges_to_table(challenge_list)

    # ---- 2.c · citation sanity check ------------------------------------------
    citations = (
            grab_citations(frameworks_sections_md)
            | grab_citations(challenge_table_md)
            | grab_citations(background_dict["frameworks_rationale_md"])
    )
    if len(citations) < 8:
        logger.warning("Only %d distinct citations – consider enriching analyses.", len(citations))

    frameworks_sections_md = "\n\n".join(sections)

    # --- 8.b · challenge table --------------------------------------------------
    challenge_map = analyses.get("challenge_map", {}).get("challenges", [])
    challenge_table_md = (
        challenges_to_table(challenge_map) if challenge_map else "*Data unavailable*"
    )

    # ---------- final prompt ----------
    report_prompt = as_token_limited_json(
        {
            "bundle": report_bundle,
            "frameworks": background_dict["frameworks_chosen"],
            "fw_rationale_md": background_dict["frameworks_rationale_md"],
            "frameworks_sections_md": frameworks_sections_md,
            "challenge_table_md": challenge_table_md,
            "financials": background_dict["finance"],
        },
        MAX_PROMPT_TOKENS - 5_000,
    )
    long_report = fix_citations(build_report(report_prompt,refresh=needs_refresh("report")))

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

def _extract_framework_rationale(flags: dict[str, Any]) -> tuple[list[str], str]:
    chosen = [k.split("_", 1)[1]          # "forces" / "pest" / …
              for k, v in flags.items() if k.startswith("use_") and v]

    rationale_lines = []
    for fw in chosen:
        reason = flags.get("rationale", {}).get(fw)
        if not reason:                     # fallback
            reason = {
                "forces": "Assesses competitive pressure and margin squeeze.",
                "pest":   "Maps macro trends and regulatory headwinds.",
                # … add the rest once
            }.get(fw, "No rationale provided.")
        rationale_lines.append(f"* **{fw.capitalize()}** – {reason}")

    return chosen, "\n".join(rationale_lines)


def main():
    company = os.getenv("COMPANY_NAME", "Citigroup")
    problems_file = os.getenv("PROBLEMS_FILE", "./problem_statements.json")
    run_strategy(company, problems_file)


if __name__ == "__main__":
    main()
