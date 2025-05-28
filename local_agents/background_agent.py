from agents import Agent

background_agent = Agent(
    name="Background",
    model="o3-mini",
    instructions="""
Read the raw company facts and trend bullets provided.
Return JSON:
{
  "company_overview": "<≤120 words>",
  "key_trends": [ { "trend": "...", "impact": "up/down", "evidence": "(source,YYYY)" }, ... ],
  "evidence": ["(source,YYYY)", "..."],
  "error": null   # or string if data missing
}
"""
)