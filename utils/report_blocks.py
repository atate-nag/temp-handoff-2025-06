# pipeline/utils/report_blocks.py
from textwrap import indent
import re

# 5 Forces → bullets ----------------------------------------------------------
def forces_to_md(forces: dict) -> str:
    nice = {
        "threat_of_entry":  "Threat of new entrants",
        "supplier_power":   "Supplier power",
        "buyer_power":      "Buyer power",
        "threat_of_subs":   "Threat of substitutes",
        "rivalry":          "Rivalry",
    }
    out = []
    for key, label in nice.items():
        level = forces.get(key, "Data unavailable").title()
        out.append(f"- **{label} – {level}**")
    return "\n".join(out)


# PEST bullets → short table --------------------------------------------------
def pest_to_md(pest: dict) -> str:
    rows = []
    for p, bullets in pest.items():
        if bullets:
            rows.append(f"- **{p}** – {bullets[0]}")
    return "\n".join(rows) if rows else "*Data unavailable*"


# Challenge list → markdown table --------------------------------------------
def challenges_to_table(ch_list: list[dict]) -> str:
    if not ch_list:
        return "*Data unavailable*"
    header   = "| ID | Statement | Impact | Addressability | Priority |"
    divider  = "|----|-----------|:------:|:--------------:|:--------:|"
    rows = [
        f"| {c['id']} | {c['statement']} | {c['impact']} "
        f"| {c['addressability']} | {c['priority']} |"
        for c in ch_list
    ]
    return "\n".join([header, divider, *rows])


# Utility to extract APA-style citations -------------------------------------
def grab_citations(text: str) -> set[str]:
    return set(re.findall(r"\([A-Z][A-Za-z0-9]+, \d{4}\)", text))
