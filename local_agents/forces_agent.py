from agents import Agent
# local_agents/forces_agent.py
from agents import Agent, ModelSettings

forces_agent = Agent(
    name="ForcesAnalyst",
    model="o3",
    # temperature=0.3,
    # model_settings=ModelSettings(temperature=0.3, top_p=0.9),
    instructions=r"""
╭─────────────────────────  BOARD-LEVEL MINDSET  ─────────────────────────╮
You are briefing Citigroup’s board on Porter’s Five Forces.  
Your analysis must feel like a Bain red-team review: numerate, sourced,
explicit about momentum, and laser-focused on how *external* structure
constrains the strategic crux.                                               
╰──────────────────────────────────────────────────────────────────────────╯

Return **valid JSON only**. If you don’t know a value, set it to null (not an empty string) and DO NOT OMIT KEYS.


PRE-FLIGHT ── when to **skip**
If the Initial Crux shows the problem is purely internal (culture,
cost hygiene, IT plumbing) reply **exactly**:
{"skip":{"reason":"assumption_mismatch: crux not about external competition"}}

INPUT JSON
{
  "company_profile": …,        # deep profile (financials, segments, ROE…)
  "pest_bullets": …,           # top-down macro bullets
  "trend_clusters": …,         # radar
  "initial_crux": …            # summarised challenge
}

TASK (silent)
1. Build a mini evidence table for each force: **3–5 distinct drivers**.
   • At least one driver must cite a *quantitative datapoint* (market-share %, $bn, bps, CAGR, etc.).
   • Summarise the datapoint in a short `quant` dict (omit if none).

2. In the final JSON (`analysis` array) **EVERY force object MUST include**:
   • `rating` 1-5  
   • `direction` ("↑ strengthening", "↓ easing", "→ stable")  
   • `drivers` (3-5 strings; each ends with a citation)  
   • optional `quant`

3. You may write a separate “scratch” JSON first, but the **last JSON in the reply** is the one the validator will parse; ensure it follows the schema exactly.


TASK  (think step-by-step, output once)
0. Before drafting JSON, draft a private table with ** ≥3 numeric facts** per force. 
Do NOT put this table in the final answer; use it to justify your ratings.

1. **Scope check**  
   – If Citigroup’s crux is external → continue.  
   – Else → return the skip object.

2. **Evidence table (silent scratchpad)**  
   For each force collect 3-5 bullets.  ≥2 bullets must be *quant* (%
   share, bps, USD bn, CAGR, cost premium…).  Pull data from any input.

3. **Rate each force**  
   Map quantitative EBIT impact to strength:

   | label       | EBIT impact guide | numeric (`rating`) |
   |-------------|------------------|--------------------|
   | Very High   | >15 %            | 5 |
   | High        | 10-15 %          | 4 |
   | Medium      | 5-10 %           | 3 |
   | Low         | 1-5 %            | 2 |
   | Very Low    | <1 %             | 1 |
4. require direction (↑/→/↓) for every force again
   ↑ strengthening • ↓ easing • → stable

5. **JSON output (exact schema)**  

{
"force_meta":{"industry_scope":"Global universal banking",
"time_horizon":"2025-2027"},
"analysis":[
{"force":"threat_of_entry",
"rating":2, # 1-5 integer
"direction":"→ stable",
"drivers":[
"10.5 % CET1 floor translates to ≈$40 bn entry capital (BIS, 2024)",
"8-10 % incremental compliance cost from FRTB & Basel III (GS_US_Outlook_2024, 2024)",
…],
"quant":{"capital_requirement_pct":10.5,"entry_capital_usd_bn":40}},
… four more forces …
],
"overall_pressure":<int>, # leave blank → we’ll calculate
"synthesis":{
"most_salient_force":"rivalry",
"headline":"Fee compression >120 bps across FICC/payments is the dominant squeeze on ROE."
},
"sources":[ "(BIS, 2024)", "(GS_US_Outlook_2024, 2024)", … ], # ≥6 unique
"skip":null
}

Flag any reinforcing loops (e.g., ‘High buyer power amplifies fee compression → higher rivalry’). Keep it one sentence.

RULES
• rating MUST be an unquoted integer 1-5; no strings like "Low".
• **Every** driver ends with an APA-style citation and each citation appears
  in `"sources"`.  
• ≥6 distinct citations overall.  
• `rating` **must be an integer 1-5**; include `"strength"` **only if you
  wish**—the pipeline can derive it if absent.  
• Omitting any required key → respond exactly `{"error":"insufficient_data"}`  
• No markdown, no commentary outside the JSON.

TIPS FOR DEEPER INSIGHT
• **Threat of Entry** – quote Citigroup’s Tier-1 ratio, Fed SIFI surcharge,
  typical challenger bank capital raise sizes, or banking charter approvals/yr.  
• **Supplier Power** – quantify tech‐vendor lock-in (e.g. % of cloud spend
  with top-2 hyperscalers) and wholesale funding mix.  
• **Buyer Power** – contrast switching costs of mass-market card customers
  vs. price-sensitive institutional clients; cite share‐of-wallet surveys.  
• **Substitutes** – size fintech wallet share, CBDC pilots, P2P lending volumes.  
• **Rivalry** – use peer ROE dispersion, fee compression (bps), or M&A
  consolidation ratios to ground a 4/5 rating.

Validate with `json.dumps` before you send.
"""
)


def validate_forces(d: dict) -> dict:
    required = {"threat_of_entry","supplier_power","buyer_power",
                "threat_of_substitutes","rivalry"}

    # ── convert flat → legacy, if needed ─────────────────────────────────
    if "analysis" not in d:
        missing = required - d.keys()
        if missing:
            raise ValueError(f"Missing forces {missing}")

        def _to_strength(rating: str) -> int:
            table = {"very low":1,"low":2,"medium":3,"high":4,"very high":5}
            return table.get(rating.lower(),3)

        d["analysis"] = []
        for fkey in required:
            f      = d[fkey]
            strength = int(f.get("strength", _to_strength(f.get("rating","medium"))))
            strength = max(1, min(5, strength))
            d["analysis"].append({
                "force":     fkey,
                "strength":  strength,              # ← now present
                "drivers":   f.get("drivers", []),
                "evidence":  f.get("evidence", []),
                "direction": f.get("direction", "→ stable"),
                "quant":     f.get("quant", None),
            })

    # ── verify & post-process ────────────────────────────────────────────
    f_seen = {f["force"] for f in d["analysis"]}
    if f_seen != required:
        raise ValueError(f"Expected forces {required}, got {f_seen}")

    def _rating_to_strength(r: str | int) -> int:
        tbl = {"very low": 1, "low": 2, "medium": 3, "high": 4, "very high": 5}
        if isinstance(r, (int, float)):  # agent already used numbers
            return max(1, min(5, int(r)))
        return tbl.get(str(r).lower(), 3)

    # ── verify & post-process ──────────────────────────────────────────────
    for force in d["analysis"]:
        # add this shim
        if "strength" not in force:
            force["strength"] = _rating_to_strength(force.get("rating", "medium"))
        # now the key is guaranteed
        force["strength"] = max(1, min(5, int(force["strength"])))

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