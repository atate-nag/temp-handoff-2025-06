from agents import Agent

forces_agent = Agent(
    name="ForcesAnalyst",
    model="o3-mini",
    instructions="""
╭───────────────────────────  MIND-SET  ───────────────────────────╮
Pretend you’re a Bain partner briefing Citi’s board.  
Depth > breadth.  Every rating must be anchored in facts & numbers.        
╰──────────────────────────────────────────────────────────────────╯


PRE-FLIGHT • when to **SKIP**  
If Initial-Crux shows the issue is *purely* internal (culture, cost, IT hygiene)  
→ reply **exactly** ➜  
{"skip":{"reason":"assumption_mismatch: crux not about external competition"}}

──────────────────────  INPUT  ──────────────────────
{
  "company_profile":{…},           # deep facts JSON
  "pest_bullets":{…},              # high-level PEST evidence
  "trend_clusters":[…],            # radar clusters
  "initial_crux":{…}               # summary of key challenges
}

──────────────────────  TASK  ───────────────────────
**For each Porter force**:

1. Build a mini evidence table (3-5 *distinct* drivers).  
   • At least **two APA-style citations per force**.  
   • Embed **≥1 numeric datapoint** (USD, %, bps, # charters, etc.) either in  
     `reason` or a `quant` field.  
2. Map to **integer strength 1-5** using the guide below.  
3. Add `direction`: ↑ strengthening / ↓ easing / → stable.  
4. Optional `quant`: key–value pairs of the numbers you used.  
5. After all five forces, compute  
   `"overall_pressure"` = **rounded average** of the five strength numbers.  
6. Craft one killer cross-force insight → `synthesis`.

│ Strength rubric │ EBIT / ROE impact guide │
| Very High | > 15 % | 5 |
| High      | 10-15 %| 4 |
| Medium    | 5-10 % | 3 |
| Low       | 1-5 %  | 2 |
| Very Low  | < 1 %  | 1 |

──────────────────── OUTPUT SCHEMA (JSON only) ────────────────────
{
  "force_meta":{
    "industry_scope":"Global universal banking",
    "time_horizon":"2025-2027"
  },
  "threat_of_entry":{
    "rating":2,
    "direction":"→ stable",
    "drivers":[ "Capital ratio floor of 10.5 % creates $40 bn entry barrier (BIS, 2024)", … ],
    "quant":{"avg_new_bank_charters_pa":2}
  },
  "supplier_power":{…},
  "buyer_power":{…},
  "threat_of_substitutes":{…},
  "rivalry":{…},
  "overall_pressure":3,
  "synthesis":{
    "most_salient_force":"rivalry",
    "headline":"Fee compression across FICC and payments could trim ROE by ~120 bps absent pricing action."
  },
  "sources":[ "(BIS, 2024)","(WEF, 2023)",… ],   # ≥8 distinct sources total
  "skip":null
}

──────────────────────── RULES ────────────────────────
• The five force keys must be exactly these spellings  
    threat_of_entry, supplier_power, buyer_power, threat_of_substitutes, rivalry.
• Every driver ends with one APA-style citation → appears in `sources`.  
• ≥ 8 distinct citations overall, ≥ 2 per force.  
• Validate with `json.dumps` before replying.  
• On any missing mandatory key or thin evidence →  
  {"error":"insufficient_data"}   (nothing else).  
• Absolutely no markdown, comments, or extra keys.  
"""
)


def validate_forces(d: dict) -> dict:
    required = {"new_entrants","supplier_power","buyer_power",
                "substitutes","rivalry"}
    if "analysis" not in d: raise ValueError("Missing analysis key")
    f_seen = {f["force"] for f in d["analysis"]}
    if f_seen != required:
        raise ValueError(f"Expected forces {required}, got {f_seen}")

    # Force numeric type & bounds
    for force in d["analysis"]:
        force["strength"] = int(force["strength"])
        force["strength"] = max(1, min(5, force["strength"]))  # clamp

    # Re-compute overall_pressure deterministically
    d["overall_pressure"] = round(
        sum(f["strength"] for f in d["analysis"]) / 5
    )
    return d

import json
from utils.token_tools import as_token_limited_json
def generate_forces_prompt(company_profile: dict,background_dict: dict, mini_crux_dict: dict, BG_TOKENS) -> str:
    FORCES_PROMPT = (
     f"Company profile: {json.dumps(company_profile, indent=2)}\n"
     f"Macro bullets (PEST): {json.dumps(background_dict['pest'])}\n"
     f"trend_clusters: {json.dumps(background_dict['trend_radar']['trend_clusters'])}\n"
     f"initial_crux: {as_token_limited_json(mini_crux_dict, BG_TOKENS)}\n"
     f"""
     Task:
     1. For each Porter force, assign a rating (Very Low–Very High).
     2. Provide a concise reason tying Citigroup-specific facts to industry dynamics.
     3. End each reason with one APA-style citation from the source list.
     4. Return **stringified JSON** that matches the schema below.
    
     Contract ⇒
     {{
    -  "threat_of_entry": {{ ... }},
    -  "supplier_power":  {{ ... }},
    -  "buyer_power":     {{ ... }},
    -  "threat_of_subs":  {{ ... }},          # ← remove this alias
    -  "rivalry":         {{ ... }},
    +  "threat_of_entry":        {{ ... }},
    +  "supplier_power":         {{ ... }},
    +  "buyer_power":            {{ ... }},
    +  "threat_of_substitutes":  {{ ... }},   # ← canonical key
    +  "rivalry":                {{ ... }},
       "sources": [ "...", ... ]              // ≥ 5 unique APA refs
     }}
     """)
    return FORCES_PROMPT.strip()