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
# Schemas
# ──────────────────────────────────────────────────────────────────────────────

from schemas import FiveForcesResult, PestResult, TrendRadarResult

# --- TEMPORARY BRIDGE UNTIL ALL BUILDERS RETURN Artifact -----------------
from schemas import Artifact, ArtifactKind, ArtifactCollection

# ---------------------------------------------------------------------------
# Canonical registry of all specialist frameworks
# ---------------------------------------------------------------------------
FRAMEWORK_REGISTRY: dict[str, tuple[Agent, Agent]] = {
    "forces":  (forces_agent, five_forces_assessor_agent),
    "pest":    (pest_agent,   generic_assessor_agent),
    "vrio":    (vrio_agent,   generic_assessor_agent),
    "blue":    (blue_ocean_agent,    generic_assessor_agent),
    "bcg":     (bcg_matrix_agent,    generic_assessor_agent),
    "value":   (value_chain_agent,   generic_assessor_agent),
    "7s":      (seven_s_agent,       generic_assessor_agent),
    "ansoff":  (ansoff_agent,        generic_assessor_agent),
    "gem":     (ge_mckinsey_agent,   generic_assessor_agent),
    "core":    (core_competence_agent, generic_assessor_agent),
    "bowman":  (bowman_clock_agent,  generic_assessor_agent),
}

def _ensure_artifact(id_: str, kind: ArtifactKind, obj) -> Artifact:
    """
    Convert legacy builder output (dict or Pydantic model) into an Artifact.
    If `obj` is already an Artifact, return as‑is.
    """
    if isinstance(obj, Artifact):
        return obj

    # Convert to JSON‑serialisable dict
    if hasattr(obj, "model_dump"):
        payload = obj.model_dump(mode="json")
    else:
        payload = obj

    sources = payload.get("sources", []) if isinstance(payload, dict) else []

    return Artifact(id=id_, kind=kind, payload=payload, sources=sources)

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

REFRESH_CACHE = True  # os.getenv("REFRESH_CACHE", "0") == "1"  # 1 - builders will run, 0 - use cached results
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

    trend_radar = build_trend_radar(tr_prompt, refresh=needs_refresh("trend_radar"))
    pest_prompt = (
            f"trend_radar : {trend_radar.model_dump(mode='json')} "
            f"Company Profile: {company_profile}\n"
    )
    pest_dict = build_pest(pest_prompt, refresh=needs_refresh("pest"))

    background_dict = build_background(bg_prompt, refresh=needs_refresh("background"))
    finance_dict = build_finance(fin_prompt, refresh=needs_refresh("finance"))

    # 3) draw radar image
    cats = {
        cl.short_name: [
            {
                "trend": t,
                "importance": cl.impact,
                "likelihood": 3,
                "readiness": 8 if cl.direction == "opportunity" else 5,
            }
            for t in cl.top_trends
        ]
        for cl in trend_radar.trend_clusters
    }
    print(json.dumps(cats, indent=2)[:800]) #sanity check of categories

    radar_path = save_trend_radar_png(cats, company_name)
    # 4) assemble bundle
    background_bundle = {
        "company_overview": company_profile.get("overview", ""),
        "company_profile": company_profile,
        "trend_radar": trend_radar.model_dump(mode='json'),
        "pest": pest_dict.model_dump(mode='json'),
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
    mini_crux = build_mini_crux(pre_prompt, refresh=needs_refresh("mini_crux"))
    pre_prompt = f"Background: {json.dumps(background_dict)}"
    logger.info("Initial Crux JSON: %s", mini_crux.model_dump(mode='json'))

    # ── 4.  Framework selector ----------------------------------------------
    sel_prompt = (
        f"Crux: {as_token_limited_json(mini_crux.model_dump(mode='json'), BG_TOKENS)}\n"
        f"Background: {as_token_limited_json(background_dict, BG_TOKENS)}"
    )
    selector_flags = build_framework_selector(sel_prompt, refresh=needs_refresh("framework_selector"))

    # OPTIONAL hard switch for a quick run
    if FORCES_ONLY:
        selected_slugs = ["forces"]
    else:
        # keep at least Five‑Forces; add any others the selector flagged True
        selected_slugs = ["forces"] + [
            slug for flag, slug in [
                ("use_pest", "pest"), ("use_vrio", "vrio"), ("use_blue_ocean", "blue"),
                ("use_bcg", "bcg"), ("use_value_chain", "value"), ("use_seven_s", "7s"),
                ("use_ansoff", "ansoff"), ("use_gem", "gem"), ("use_core_comp", "core"),
                ("use_bowman", "bowman")
            ] if selector_flags.get(flag)
        ]

    background_dict["frameworks_chosen"] = selected_slugs
    logger.info("→ specialist frameworks selected: %s", selected_slugs)

    # map slug → (agent, assessor)
    specialist_agents = {slug: FRAMEWORK_REGISTRY[slug] for slug in selected_slugs}

    # keep rationale for the report ----------------------------------------
    background_dict["frameworks_rationale_md"] = selector_flags.get(
        "rationale_md", "*Rationale unavailable*"
    )
    background_dict["frameworks_chosen"] = ["forces"] + [
        fw for fw in background_dict["frameworks_chosen"] if fw != "forces"
    ]

    spec_prompt = (
        f"Initial Crux: {as_token_limited_json(mini_crux.model_dump(mode='json'), BG_TOKENS)}\n"
        f"Company Profile: {json.dumps(company_profile, indent=2)}\n"
        f"Run analysis for {company_name}"
    )

    # ── 6. Build framework‑specific analyses  ────────────────────────────────────

    forces_prompt = generate_forces_prompt(
        company_profile,
        background_dict,
        mini_crux.model_dump(mode="json"),
        BG_TOKENS,
    )

    # Temporary bridge until every builder returns Artifact
    from schemas import Artifact, ArtifactKind

    def _ensure_artifact(art_id: str, kind: ArtifactKind, result_obj) -> Artifact:
        if isinstance(result_obj, Artifact):
            return result_obj
        if hasattr(result_obj, "model_dump"):
            payload = result_obj.model_dump(mode="json")
        else:
            payload = result_obj
        srcs = payload.get("sources", []) if isinstance(payload, dict) else []
        return Artifact(id=art_id, kind=kind, payload=payload, sources=srcs)

    artifacts: list[Artifact] = []

    # --- Forces (already migrated) ---------------------------------------------
    if "forces" in specialist_agents:
        forces_art = build_forces(forces_prompt, refresh=needs_refresh("forces"))
        forces_art.id = "forces"
        artifacts.append(forces_art)

    # --- Legacy builders still returning dict or Pydantic objects --------------
    if "vrio" in specialist_agents:
        vrio_raw = build_vrio(spec_prompt, refresh=needs_refresh("vrio"))
        artifacts.append(_ensure_artifact("vrio", ArtifactKind.ANALYSIS, vrio_raw))

    if "blue" in specialist_agents:
        blue_raw = build_blue(spec_prompt, refresh=needs_refresh("blue"))
        artifacts.append(_ensure_artifact("blue_ocean", ArtifactKind.ANALYSIS, blue_raw))

    if "bcg" in specialist_agents:
        bcg_raw = build_bcg(spec_prompt, refresh=needs_refresh("bcg"))
        artifacts.append(_ensure_artifact("bcg", ArtifactKind.ANALYSIS, bcg_raw))

    if "value" in specialist_agents:
        value_raw = build_value(spec_prompt, refresh=needs_refresh("value"))
        artifacts.append(_ensure_artifact("value_chain", ArtifactKind.ANALYSIS, value_raw))

    if "7s" in specialist_agents:
        seven_raw = build_7s(spec_prompt, refresh=needs_refresh("7s"))
        artifacts.append(_ensure_artifact("seven_s", ArtifactKind.ANALYSIS, seven_raw))

    if "ansoff" in specialist_agents:
        ansoff_raw = build_ansoff(spec_prompt, refresh=needs_refresh("ansoff"))
        artifacts.append(_ensure_artifact("ansoff", ArtifactKind.ANALYSIS, ansoff_raw))

    if "gem" in specialist_agents:
        gem_raw = build_gem(spec_prompt, refresh=needs_refresh("gem"))
        artifacts.append(_ensure_artifact("gem", ArtifactKind.ANALYSIS, gem_raw))

    if "core" in specialist_agents:
        core_raw = build_core(spec_prompt, refresh=needs_refresh("core_competence"))
        artifacts.append(_ensure_artifact("core_competence", ArtifactKind.ANALYSIS, core_raw))

    if "bowman" in specialist_agents:
        bowman_raw = build_bowman(spec_prompt, refresh=needs_refresh("bowman"))
        artifacts.append(_ensure_artifact("bowman_clock", ArtifactKind.ANALYSIS, bowman_raw))

    # Wrap results in a collection for easier lookup
    artifact_bundle = ArtifactCollection(artifacts=artifacts)

    # ── 7. Derive a shim `analyses` dict from current artifacts (temporary) -----
    analyses: Dict[str, Any] = {art.id: art.payload for art in artifact_bundle.artifacts}

    # ── 8. Build Challenges & Synth sections (still legacy) ---------------------

    serialisable_analyses = [a.payload for a in artifacts]

    challenge_prompt = (
        f"Initial Crux: {as_token_limited_json(mini_crux.model_dump(mode='json'), BG_TOKENS)}\n"
        f"Analyses: {json.dumps(serialisable_analyses)}\n"
        f"Trend Radar: {json.dumps(background_dict['trend_radar'])}"
    )

    challenge_dict = build_challenges(challenge_prompt, refresh=needs_refresh("challenges"))
    analyses["challenge_map"] = challenge_dict

    synth_prompt = (
        f"Initial Crux: {as_token_limited_json(mini_crux.model_dump(mode='json'), BG_TOKENS)}\n"
        f"Analyses: {json.dumps(serialisable_analyses, indent=2)}"
    )
    synth_dict = build_synth(synth_prompt, refresh=needs_refresh("synth"))
    analyses["synthesized_options"] = synth_dict

    # keep using `analyses` for the report_bundle and downstream logic unchanged
# ── 8.  Long‑form report (with Masters‑level assessor) -----------------
    report_bundle = {
        "company_overview": background_dict["company_overview"],
        "trend_radar": background_dict["trend_radar"],
        "crux": as_token_limited_json(mini_crux.model_dump(mode='json'), BG_TOKENS),
        "analyses": analyses,
        "challenge_map": analyses["challenge_map"],
        "synthesized_options": analyses["synthesized_options"],
        "frameworks_chosen": background_dict["frameworks_chosen"],
        "frameworks_rationale_md": background_dict["frameworks_rationale_md"],
    }

    report_bundle["forces"] = analyses.get("forces", {})
    challenge_tbl = report_bundle["challenge_map"].get("table_md", "*Data unavailable*")

    # --- 8.a · framework blocks -------------------------------------------------
    from utils.report_blocks import (
        forces_to_md, pest_to_md, challenges_to_table, grab_citations
    )
    sections = []

    print("DEBUG: Frameworks chosen:", background_dict["frameworks_chosen"])

    all_sources = []
    for key in background_dict["frameworks_chosen"]:
        art = artifact_bundle.lookup.get(key)
        if not art:
            print("DEBUG: No data for framework", key)
            sections.append(f"## {key.title()} – *Data unavailable*")
            continue

        data = art.payload
        all_sources.extend(art.sources)

        if key == "forces":
            body = forces_to_md(data)
            sections.append(f"## Porter’s Five Forces\n{body}")
        elif key == "pest":
            body = pest_to_md(data.get("pest_bullets", {}))
            sections.append(f"## PEST Highlights\n{body}")

        # elif blocks for future frameworks …

    frameworks_sections_md = "\n\n".join(sections) or "*Data unavailable*"
    frameworks_sections_md = fix_citations(frameworks_sections_md)
    # ---- 2.b · challenge_table_md ---------------------------------------------
    challenge_list = analyses.get("challenge_map", {}).get("challenges", [])
    challenge_table_md = challenges_to_table(challenge_list)

    # ---- 2.c · citation sanity check ------------------------------------------

    refs_md = "## Sources\n" + " ".join(sorted(set(all_sources)))
    frameworks_sections_md += "\n\n" + refs_md

    # now run the citation check
    citations = (
            grab_citations(frameworks_sections_md)
            | grab_citations(challenge_table_md)
            | grab_citations(background_dict["frameworks_rationale_md"])
    )

    logger.debug("Found %d citations: %s", len(citations), list(citations)[:10])

    if len(citations) < 8:
        logger.warning(
            "Only %d distinct citations – consider enriching analyses.", len(citations)
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

    # ── after the LLM has produced long_report ───────────────────────────
    long_report = fix_citations(build_report(report_prompt,
                                             refresh=needs_refresh("report")))

    # 1.  Add Porter (and any other frameworks) *if* they aren’t already there
    if "Porter’s Five Forces" not in long_report:
        long_report = frameworks_sections_md + "\n\n" + long_report


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

