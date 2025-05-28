#!/usr/bin/env python3
import os
import json
import datetime
import logging.config

from agents import Agent
import asyncio
from dotenv import load_dotenv
from filehandler import FileHandler
from model_connector import ModelConnectorFactory
from config.conf import read_config, setup_config
from company_data import get_file_paths
from typing import Any

from agent_and_assessor import run_single_workflow_with_verifier, single_agent_verify_assess_loop

# AI Agents
from local_agents.initial_crux_agent import initial_crux_agent

from local_agents.citation_verifier import citation_verifier_agent
from local_agents.background_agent import background_agent
from local_agents.framework_selector_agent import framework_selector_agent
from local_agents.trend_radar_agent import trend_radar_agent
from local_agents.challenge_processing_agent import challenge_processing_agent
from local_agents.report_composer_agent import report_composer_agent


from local_agents.generic_assessor_agent import generic_assessor_agent
# future specialist agents (uncomment when implemented)
from local_agents.forces_agent import forces_agent as forces_agent
from local_agents.five_forces_assessor_agent import five_forces_assessor_agent
from local_agents.pest_agent import pest_agent
from local_agents.financial_screen_agent import financial_screener_agent
from local_agents.VRIO_agent import vrio_agent
from local_agents.bcg_matrix_agent import bcg_matrix_agent
from local_agents.blue_ocean_agent import blue_ocean_agent
from local_agents.value_chain_agent import value_chain_agent
from local_agents.seven_s_agent import seven_s_agent
from local_agents.ansoff_agent import ansoff_agent
from local_agents.ge_mckinsey_agent import ge_mckinsey_agent
from local_agents.core_competence_agent import core_competence_agent
from local_agents.bowman_clock_agent import bowman_clock_agent

# from local_agents.vrio_analyst_agent import vrio_analyst_agent
# from local_agents.vrio_assessor import vrio_assessor_agent
# from local_agents.finance_assessor import finance_assessor_agent
from local_agents.report_assessor_agent import report_assessor_agent

from local_agents.synthesizer_agent import synthesizer_agent
from local_agents.summariser_agent import summariser_agent

for _agent in [
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
    seven_s_agent ,
    ansoff_agent ,
    ge_mckinsey_agent,
    core_competence_agent,
    bowman_clock_agent,
    report_assessor_agent
]:
    _agent.model = "o3-mini"

from utils.md_to_docx import write_markdown, md_to_docx
from utils.token_tools import as_token_limited_json, MAX_PROMPT_TOKENS
from utils.capability_plot import generate_capability_plot
from company_data import fetch_basic_financials, ticker_map
# ----------------------------------------------------------------------------
# ENV + LOGGING
# ----------------------------------------------------------------------------
load_dotenv()
if "socrates_main" not in logging.root.manager.loggerDict:
    logging.config.fileConfig(
        "config/logging_config_socrates.ini",
        defaults={"date": datetime.datetime.now()},
        disable_existing_loggers=True,
    )
logger = logging.getLogger("socrates_main")
logger.info("Started Socrates Main")

# ----------------------------------------------------------------------------
# MODEL CONNECTOR
# ----------------------------------------------------------------------------
model_config = {
    "model_type": "openai_assistants",
    "api_key": os.getenv("OPENAI_API_KEY"),
    "model": "gpt-o3",
}
file_handler = FileHandler()
connector = ModelConnectorFactory.create_connector(model_config, file_handler)

# ----------------------------------------------------------------------------
# GICS & Data Loaders
# ----------------------------------------------------------------------------
from graph_workflow.full_graph import (
    get_trends_from_gics_code, get_curated_trend_data,
    get_condensed_trend_data, save_curated_trend_data,
    save_condensed_trend_data, get_condensed_company_data,
)

gics_mapping = {10:"Energy",15:"Materials",20:"Industrials",25:"Consumer Discretionary",
30:"Consumer Staples",35:"Health Care",40:"Financials",45:"Information Technology",
50:"Communication Services",55:"Utilities",60:"Real Estate"}
company_to_gics = { ... }  # same mapping as before

def get_gics_code_and_name(company_name: str):
    key = company_name.replace(" ","_").replace("'","")
    codes = company_to_gics.get(key)
    if not codes: raise KeyError(f"No GICS mapping for {company_name}")
    return codes, [gics_mapping.get(c,"Unknown") for c in codes]

def get_problem(company_name: str, problems_file: str) -> str:
    with open(problems_file) as f:
        all_probs = json.load(f)
    key = company_name.replace(" ","_").replace("'","")
    stmt = all_probs.get(key)
    if stmt is None: raise KeyError(f"No problem statement for {company_name}")
    return stmt

# ----------------------------------------------------------------------------
# CORE WORKFLOW
# ----------------------------------------------------------------------------
def run_strategy(
    companyName: str,
    problemsFile: str,
    max_rounds: int = 3
):
    logger.info(f"Running strategy for {companyName}")
    FORCES_ONLY = os.getenv("FORCES_ONLY", "1") == "0"  # default = on for now
    # normalize names & load data
    cname = companyName.replace(" ","_").replace("'","")
    pfp, tfp, cfp = get_file_paths(cname, problemsFile, file_handler)
    trends = file_handler.local_json_read(tfp)
    company_data = file_handler.local_json_read(cfp)

    # Normalise company_data → always a dict with an "overview" field
    if isinstance(company_data, list):
        first = company_data[0] if company_data else ""
        if isinstance(first, dict) and "statement" in first:
            overview = first["statement"]
        else:  # list of strings (or mixed)
            overview = str(first)[:200]  # take first string, truncate to 200 chars
        company_data = {"overview": overview, "data": company_data}

    ticker = ticker_map.get(companyName, "")
    basic_fin = fetch_basic_financials(ticker)


    # 1) merge into company_data so the Screener sees it
    company_data.setdefault("financials", basic_fin)


    # 1) BACKGROUND AGENT

    bg_prompt = f"Company Data: {company_data}\nTrends: {trends}"
    assert background_agent is not None, f"{background_agent} generator is None"

    background_json = run_single_workflow_with_verifier(
        generator_agent=background_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=bg_prompt,
        label="Background",
        max_rounds=1
    )

    # ----------------------------------------------------------------------
    # 1) TREND RADAR  — exhaustive trend clustering / impact scoring
    # ----------------------------------------------------------------------
    trend_prompt = (
        f"Company Data: {company_data}\nAll Trends: {trends}"
    )
    trend_radar_json = run_single_workflow_with_verifier(
        generator_agent=trend_radar_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=trend_prompt,
        label="Trend Radar",
        max_rounds=1,
    )

    # -------------- after trend_radar_json is returned ------------------
    trend_dict = json.loads(trend_radar_json)  # already a dict
    cats = {
        cluster["short_name"]: [
            {
                "trend": t,
                "importance": cluster["impact"],  # crude mapping
                "likelihood": 3,  # placeholder
                "readiness": 8 if cluster["direction"] == "opportunity" else 5
            }
            for t in cluster["top_trends"]
        ]
        for cluster in trend_dict["trend_clusters"]
    }

    from utils.trend_radar import save_trend_radar_png
    radar_path = save_trend_radar_png(cats, companyName)

    # ----------------------------------------------------------------------
    # 2) PEST ANALYSIS  — four bullets per P,E,S,T
    # ----------------------------------------------------------------------
    pest_prompt = f"trend_clusters: {trend_radar_json}"
    pest_json = run_single_workflow_with_verifier(
        generator_agent=pest_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=pest_prompt,
        label="PEST Scan",
        max_rounds=1,
    )
    try:
        _pest = json.loads(pest_json)
        for section, bullets in _pest.get("pest_bullets", {}).items():
            _pest["pest_bullets"][section] = [
                b for b in bullets if "Data unavailable" not in b
            ]
        pest_json = json.dumps(_pest)
    except Exception as err:  # keep going even if something is odd
        logger.warning(f"Couldn’t scrub PEST placeholders: {err}")


# ----------------------------------------------------------------------
# 3) FINANCIAL SCREENER  — high-level KPIs vs peers
# --------------------------------------------------------------------
    finance_prompt = (
            "company_data: " + as_token_limited_json(company_data)  # ← token-safe
    )
    finance_json = run_single_workflow_with_verifier(
        generator_agent=financial_screener_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=finance_prompt,
        label="Financial Screener",
        max_rounds=1,
    )

    # ----------------------------------------------------------------------
    # 4) BACKGROUND BUNDLE  — feeds Mini-Crux & final report
    # ----------------------------------------------------------------------
    background_json = json.dumps({
        "company_overview": company_data.get("overview", ""),
        "trend_radar": json.loads(trend_radar_json),
        "pest": json.loads(pest_json),
        "finance": json.loads(finance_json)
    })

    # ----------------------------------------------------------------------
    # 5) MINI-CRUX DISCOVERY
    # ----------------------------------------------------------------------
    pre_prompt = f"Background: {background_json}"
    initial_crux_json = run_single_workflow_with_verifier(
        generator_agent=initial_crux_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=pre_prompt,
        label="Initial Crux",
        max_rounds=1,
    )
    logger.info(f"Initial Crux JSON: {initial_crux_json}")

    # ----------------------------------------------------------------------
    # (everything below — framework selection / specialist analyses /
    #  challenge_processing_agent / synthesizer_agent / report_composer_agent —
    #  remains exactly as in your current file)

    # 1) PRE-CRUX DIAGNOSIS
    pre_prompt = f"Background: {background_json}"
    assert initial_crux_agent is not None, f"{initial_crux_agent} generator is None"
    initial_crux_json = run_single_workflow_with_verifier(
        generator_agent=initial_crux_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=pre_prompt,
        label="Initial Crux",
        max_rounds=1
    )
    logger.info(f"Initial Crux JSON: {initial_crux_json}")

    sel_prompt = f"Crux: {initial_crux_json}\nBackground: {background_json}"
    assert framework_selector_agent is not None, f"{framework_selector_agent} generator is None"

    # ------------------------------------------------------------------
    # 2) SPECIALIST ANALYSES
    # ------------------------------------------------------------------

    # ------------- make background_json mutable -----------------------
    # ----------------------------------------------------------------------
    # (keep the code that builds background_json + initial_crux_json)
    # ----------------------------------------------------------------------

    # ------------- make background_json mutable ---------------------------
    if isinstance(background_json, str):
        try:
            background_json = json.loads(background_json)
        except json.JSONDecodeError:
            background_json = {"raw": background_json}

    # ----------------------------------------------------------------------
    #  A. framework-selector  → flags
    # ----------------------------------------------------------------------
    sel_prompt = f"Crux: {initial_crux_json}\nBackground: {json.dumps(background_json)[:8000]}"
    selector_raw = run_single_workflow_with_verifier(
        generator_agent=framework_selector_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=sel_prompt,
        label="Framework Selector",
        max_rounds=1,
    )
    try:
        flags: dict[str, Any] = json.loads(selector_raw)
    except json.JSONDecodeError:
        logger.warning("Selector failed JSON-parse ⇒ default to Porter + PEST")
        flags = {"use_porter": True, "use_pest": True, "rationale": {}}

    # ----------------------------------------------------------------------
    #  B. helper → pick pretty names + rationale-lines
    # ----------------------------------------------------------------------
    def _extract_framework_rationale(flag_blob: dict[str, Any]) -> tuple[list[str], str]:
        name_map = {
            "porter": "Porter’s 5 Forces",
            "pest": "PEST",
            "vrio": "VRIO",
            "blue_ocean": "Blue-Ocean",
            "bcg": "BCG Matrix",
            "value_chain": "Value-Chain",
            "seven_s": "McKinsey 7-S",
            "ansoff": "Ansoff Matrix",
            "gem": "GE/McKinsey 9-Cell",
            "core_comp": "Core-Competence",
            "bowman": "Bowman Clock",
        }
        chosen, md_lines = [], []
        for short_key, pretty in name_map.items():
            if flag_blob.get(f"use_{short_key}"):
                chosen.append(pretty)
                expl = flag_blob.get("rationale", {}).get(short_key, "")
                md_lines.append(f"* **{pretty}** – {expl}")
        return chosen, "\n".join(md_lines)

    chosen_fw, rationale_md = _extract_framework_rationale(flags)
    background_json.update(
        {
            "frameworks_chosen": chosen_fw,
            "frameworks_rationale_md": rationale_md,
        }
    )

    # ----------------------------------------------------------------------
    #  C. catalogue  flag → (dict-key, agent, assessor)
    # ----------------------------------------------------------------------
    flag_to_agent: dict[str, tuple[str, Agent, Agent]] = {
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

    # ----------------------------------------------------------------------
    #  D. build specialist_agents dict
    # ----------------------------------------------------------------------
    specialist_agents: dict[str, tuple[Agent, Agent]] = {}

    FORCES_ONLY = os.getenv("FORCES_ONLY", "0") == "1"
    if FORCES_ONLY:
        specialist_agents["forces"] = (forces_agent, five_forces_assessor_agent)
    else:
        for flag, triplet in flag_to_agent.items():
            if flags.get(flag):
                key, agent, assessor = triplet
                specialist_agents[key] = (agent, assessor)

    if not specialist_agents:  # failsafe
        specialist_agents["forces"] = (forces_agent, generic_assessor_agent)

    # ----------------------------------------------------------------------
    #  E. run each specialist analysis (with per-framework timeout)
    # ----------------------------------------------------------------------
    PER_FRAMEWORK_TIMEOUT = 300
    analyses: dict[str, Any] = {}

    for key, (agent, assessor) in specialist_agents.items():
        BG_TOKENS = MAX_PROMPT_TOKENS - 5_000  # ≈ 185 000 if you kept defaults

        spec_prompt = (
            f"Initial Crux: {initial_crux_json}\n"
            f"Background: {as_token_limited_json(background_json, BG_TOKENS)}\n"
            f"Run {key} analysis for {companyName}"
        )
        try:
            raw = asyncio.run(
                asyncio.wait_for(
                    single_agent_verify_assess_loop(
                        generator_agent=agent,
                        verifier_agent=citation_verifier_agent,
                        assessor_agent=assessor,
                        initial_prompt=spec_prompt,
                        label=f"{key.capitalize()} Analysis",
                        max_rounds=max_rounds,
                    ),
                    timeout=PER_FRAMEWORK_TIMEOUT,
                )
            )
            parsed = json.loads(raw)
        except asyncio.TimeoutError:
            logger.warning(f"{key} timed-out after {PER_FRAMEWORK_TIMEOUT}s")
            continue
        except Exception as exc:
            logger.warning(f"{key} failed ⇒ {exc}")
            continue

        if parsed.get("skip"):
            logger.info(f"Skipping {key}: {parsed['skip'].get('reason', '')}")
            continue

        analyses[key] = parsed

    # 3) CHALLENGES

    challenge_prompt = (
        f"Initial Crux: {initial_crux_json}\nAnalyses: {json.dumps(analyses)}\n"
        f"Trend Radar: {trend_radar_json}"
    )
    assert challenge_processing_agent is not None, f"{challenge_processing_agent} generator is None"
    challenge_json = run_single_workflow_with_verifier(
        generator_agent=challenge_processing_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=challenge_prompt,
        label="Challenge Processing",
        max_rounds=2
    )
    analyses["challenge_map"] = json.loads(challenge_json)

    # 4) SYNTHESIZER

    synth_prompt = (
        f"Initial Crux: {initial_crux_json}\nAnalyses: {json.dumps(analyses,indent=2)}"
    )
    assert synthesizer_agent is not None, f"{synthesizer_agent} generator is None"
    synth_json = run_single_workflow_with_verifier(
        generator_agent=synthesizer_agent,
        verifier_agent=citation_verifier_agent,
        assessor_agent=None,
        initial_prompt=synth_prompt,
        label="Synthesizer",
        max_rounds=2
    )
    analyses["synthesized_options"] = json.loads(synth_json)

    # 5) STRATEGY MEMO

    report_bundle = {
        # replace this ↓↓↓
        # "company_overview": company_data.get("overview",""),
        # with this:
        "company_overview": (
            company_data[0]["statement"] if isinstance(company_data, list) else
            company_data.get("overview", "")
        ),
        "trend_radar": json.loads(trend_radar_json),
        "crux": json.loads(initial_crux_json),
        "analyses": analyses,
        "challenge_map": analyses["challenge_map"],
        "synthesized_options": analyses["synthesized_options"],
        "frameworks_chosen": background_json.get("frameworks_chosen", []),
        "frameworks_rationale_md": background_json.get(
            "frameworks_rationale_md", "*Selector returned no rationales*"
        ),
    }

    # 6) LONG-FORM REPORT

    # ------------------------------------------------------------
    # 5) LONG-FORM REPORT  (generator + verifier + MASTERS assessor)
    # ------------------------------------------------------------
    report_prompt = f"DATA BUNDLE:\n{report_bundle}"

    long_report = asyncio.run(
        single_agent_verify_assess_loop(
            generator_agent=report_composer_agent,
            verifier_agent=citation_verifier_agent,
            assessor_agent=report_assessor_agent,  # ★ NEW ★
            initial_prompt=report_prompt,
            label="Long-Form Report",
            max_rounds=3,  # up to three drafts until the assessor scores ≥70
        )
    )
    print("\n=== LONG-FORM STRATEGY REPORT (markdown) ===\n")
    print(long_report)

    # --- Embed capability & radar plots -----------------------------------
    vrio_tbl = analyses.get("vrio", {}).get("vrio_table", [])
    if vrio_tbl:
        cap_path = generate_capability_plot(vrio_tbl, companyName)
        long_report += f"\n\n![Capability Map]({os.path.basename(cap_path)})\n"

    if radar_path:
        long_report += f"\n\n![Trend-Radar]({os.path.basename(radar_path)})\n"

    # --- Write .md and convert via Pandoc --------------------------------
    md_path = write_markdown(long_report, companyName)
    docx_path = md_to_docx(md_path, companyName)
    print(f"\nWord report saved → {docx_path}")

# ----------------------------------------------------------------------------
# ENTRYPOINT
# ----------------------------------------------------------------------------
def main():
    setup_config(**{"run_id": f"runStrategy_{datetime.datetime.now()}"})
    company = os.getenv("COMPANY_NAME", "Citigroup")
    problems_file = os.getenv("PROBLEMS_FILE", "./problem_statements.json")
    run_strategy(company, problems_file)

if __name__ == "__main__":
    main()
