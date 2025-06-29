# local_agents/forces_agent.py  (final-form)
from agents import Agent
from schemas import FiveForcesResult
from utils.token_tools import as_token_limited_json

forces_agent = Agent(
    name="ForcesAnalyst",
    model="o3",
    instructions=r"""
╭─────────────────────────  BOARD-LEVEL MINDSET  ─────────────────────────╮
You are briefing the client's board on a Porter’s Five Forces for the 
client's business. There is no rehearsal.
Be numerate, cite sources, and flag the single most-salient force.        
╰──────────────────────────────────────────────────────────────────────────╯

INPUT FIELDS
{
  "company_profile": …,
  "pest_bullets": …,
  "trend_clusters": …,
  "initial_crux": …
}

TASK
1. Collect 3-5 evidence bullets per force; ≥2 must embed numeric facts.
2. Rate each force 1-5 (see table below) and set direction ↑/→/↓.
3. Fill **every** field of the FiveForcesResult schema  
   (the system has provided you that schema).

RATING GUIDE
5 Very High (>15 % EBIT swing) … 1 Very Low (<1 %).

If the crux is *internal only* return:

{"skip":{"reason":"assumption_mismatch: crux not about external competition"}}
⛔️ MUST include the following JSON keys:
• "synthesis" – 2‑3 sentence narrative that integrates all five forces.
• "sources" – array of ≥6 parenthetical citations used in evidence.
Return ONLY valid JSON matching the schema.
Return **valid JSON** that conforms to the FiveForcesResult schema.
"""
)

def generate_forces_prompt(profile, bg, crux, token_budget):
    return {
        "company_profile": profile,
        "pest_bullets": bg["pest"]["pest_bullets"],
        "trend_clusters": bg["trend_radar"]["trend_clusters"],
        "initial_crux": as_token_limited_json(crux, token_budget),
    }