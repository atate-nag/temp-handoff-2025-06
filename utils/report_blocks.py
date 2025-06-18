# pipeline/utils/report_blocks.py
from textwrap import indent
import re

# 5 Forces → bullets ----------------------------------------------------------
# utils/report_blocks.py
def forces_to_md(forces_json: dict) -> str:
    """Convert the *new* forces JSON into a short bullet summary."""
    key_map = {
        "threat_of_entry": "Threat of new entrants",
        "supplier_power": "Supplier power",
        "buyer_power": "Buyer power",
        "threat_of_substitutes": "Threat of substitutes",
        "rivalry": "Rivalry among incumbents",
    }

    # ---- NEW: build lookup {force_key: rating_number} ----------------------
    rating_lookup = {
        item["force"]: item["rating"]
        for item in forces_json.get("analysis", [])
    }

    out = []
    for k, label in key_map.items():
        rating_num = rating_lookup.get(k)
        if rating_num is None:
            out.append(f"- **{label}** – *Data unavailable*")
        else:
            qualitative = {1: "Very low", 2: "Low", 3: "Moderate",
                           4: "High", 5: "Very high"}[rating_num]
            out.append(f"- **{label} – {qualitative} ({rating_num}/5)**")
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


import re
from typing import Set

_CITATION_RE = re.compile(
    r"\([^\n()]+?,\s*(?:19|20)\d{2}\)",
    re.UNICODE,
)

def grab_citations(text: str) -> Set[str]:
    """
    Return **unique raw citation strings** like '(WEF, 2024)'.

    • Matches tokens containing letters, digits, dots, underscores,
      ampersands, hyphens and spaces.
    • Allows any amount of whitespace after the comma.
    • Safely handles file extensions ('.pdf') that sometimes follow the
      source token.
    """
    return set(_CITATION_RE.findall(text))


print(grab_citations("(BIS, 2024) (S&P_Global_M&A_2024,2024)"))