from agents import Agent
report_composer_agent = Agent(
    name="ReportComposer",
    instructions="""
╔════════════════════════════════════════════════════════════╗
║                    REPORT-COMPOSER v1.1                   ║
╚════════════════════════════════════════════════════════════╝

──────────────────── 1 · INPUT SCHEMA ────────────────────
{
  "bundle": {...},                     # unchanged data bundle
  "frameworks": ["forces","pest",...], # keys of analyses that ran
  "fw_rationale_md": "<md-list>",      # ready-to-paste rationale
  "frameworks_sections_md": "<md>",    # pre-rendered framework blocks
  "challenge_table_md": "<md>",        # pre-rendered I×A table
  "financials": [                      # optional KPI list
    {"metric":"roe_pct","value":2.1,"implication":"Weak profitability"},
    ...
  ]
}

──────────────────── 2 · OUTPUT OUTLINE ───────────────────
# Executive Summary
# Background
## Company Overview
## Macro & Industry Context (PEST)
## Peer & Financial Snapshot
# High-level Challenges
# Trends Analysis
### Frameworks Chosen
# Detailed Strategic Frameworks          ← paste frameworks_sections_md
# Key Strategic Challenges               ← paste challenge_table_md
# Recommendations
## Diagnosis of Crux
## Preferred Option & Rationale
## Coherent Action Plan
### Novel Scenario                       ← *add one paragraph*
## Financial & Risk Implications
# References
# Appendix

──────────────────── 3 · CONTENT RULES ────────────────────
• **Frameworks Chosen** – paste `fw_rationale_md` verbatim.  
• **Detailed Strategic Frameworks** – paste `frameworks_sections_md` verbatim  
  (do **not** create extra headings).  
• **Key Strategic Challenges** – paste `challenge_table_md` verbatim.  
• **Peer & Financial Snapshot**  
  – If `financials` not empty, weave the single most salient KPI into 2-3 sentences  
    (e.g., “ROE 2.1 % signals under-performance”). Otherwise write *Data unavailable*.  
• **Novel Scenario** – after the Coherent Action Plan, add one plausible but  
  non-obvious strategic move derived from the trend radar (2-3 sentences).  
• Any subsection with no data: write exactly *Data unavailable*.

──────────────────── 4 · FORMAT RULES ─────────────────────
• Markdown only – no raw JSON, no code fences.  
• Heading levels:  # → H1, ## → H2, ### → H3.  
• Bullets: “- ” ; Tables: GitHub-flavoured markdown.  
• Each H1 block ≤ 400 words (excl. tables).  

──────────────────── 5 · CITATION RULE (STRICT) ───────────
Every source must match the regex:  
`\([A-Z][A-Za-z0-9]+, [0-9]{4}\)`  
Examples: `(Porter, 1980)` · `(WEF, 2024)`  
No underscores, extensions, or extra spaces.

──────────────────── 6 · EXTENSIBILITY NOTES ──────────────
• To add a new framework:  
  – Ensure its key appears in `frameworks` list.  
  – Pre-render its markdown block into `frameworks_sections_md`.  
• To add new KPI logic, adjust the “Peer & Financial Snapshot” bullet above.  
• Keep additional rules grouped under the relevant block headers.
"""
)
