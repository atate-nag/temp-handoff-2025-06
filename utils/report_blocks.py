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
import re

#  (SomeSource, 2024)          ✔
#  (Some-Source_123.pdf,2024)  ✔
#  (WEF,2024a)                 ✔
#  (foo bar)                   ✘  (no comma + year → ignored)
CITE_RE = re.compile(
    r"""\(
        (?P<source>[A-Z][A-Za-z0-9_.-]+)   # 1+ word chars / _ . -
        ,\s*                               # comma + optional space
        (?P<year>\d{4}[a-z]? )             # 4-digit year, optional letter
        \)""",
    re.VERBOSE,
)

def grab_citations(text: str) -> set[str]:
    """
    Return every distinct citation string that looks like
    '(SomeSource, 2024)'.
    The whole '(Source, YYYY)' block is kept so the caller’s behaviour
    stays unchanged.
    """
    return {m.group(0) for m in CITE_RE.finditer(text)}
