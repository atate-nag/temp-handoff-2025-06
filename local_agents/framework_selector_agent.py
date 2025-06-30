from agents import Agent

framework_selector_agent = Agent(
    name="FrameworkSelector",
    # (model injected by wrapper)
    instructions="""
Input ➜ Initial-Crux JSON  +  Background JSON.

Return **only valid JSON** with EXACTLY these keys:

{
  "use_forces":       true|false,
  "use_pest":         true|false,
  "use_vrio":         true|false,
  "use_blue_ocean":   true|false,
  "use_bcg":          true|false,
  "use_value_chain":  true|false,
  "use_seven_s":      true|false,
  "use_ansoff":       true|false,
  "use_gem":          true|false,
  "use_core_comp":    true|false,
  "use_bowman":       true|false,

  "rationale": {      //  NEW  ▶  one short line per framework that is *true*
    "forces"      : "<≤30 words>",
    "pest"        : "<≤30 words>",
    "vrio"        : "<≤30 words>",
    "blue_ocean"  : "<…>",
    "bcg"         : "<…>",
    "value_chain" : "<…>",
    "seven_s"     : "<…>",
    "ansoff"      : "<…>",
    "gem"         : "<…>",
    "core_comp"   : "<…>",
    "bowman"      : "<…>"
  },

  "error": null
}

Rules
• A framework flag must be *true* to get a rationale line.  
• IMPORTANT: reply with the JSON ONLY – no markdown fence, no commentary.
• Omit or leave "" any rationale whose flag is false.  
• ≤30 words per rationale.  
• If you cannot decide, set all flags false and put
  {"error": "insufficient_information"}.
"""
)
