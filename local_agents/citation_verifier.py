import asyncio
import json
from dataclasses import dataclass
from typing import Literal

from agents import Agent, Runner, ItemHelpers

@dataclass
class VerificationFeedback:
    """
    Returned by the citation verifier.
    """
    valid: bool
    issues: str

# Instantiate the citation verifier agent using the Agents SDK
citation_verifier_agent = Agent(
    name="Citation Verifier",
    model="o3-mini",
    instructions="""
You are a Citation Verifier. Your task is to analyze a generated text containing inline citations and verify that each citation
accurately supports its associated claim. Focus exclusively on citation validity, without altering the content.

For each claim in the text:
- If the citation correctly supports the claim, include it in your validation count.
- If the citation is incorrect, missing, or does not support the claim, record detailed issues.

Respond in JSON matching the VerificationFeedback schema:
{
  "valid": <true|false>,
  "issues": "<description of all issues>"
}
""",
)

async def verify_output_with_agent(
    output_text: str,
) -> VerificationFeedback:
    """
    Sends `output_text` to the citation_verifier_agent and returns a VerificationFeedback.
    """
    prompt = (
        f"Below is the generator's output with inline citations:\n\n{output_text}\n\n"
        "Verify that each citation correctly supports its claim, and respond in valid JSON."
    )
    result = await Runner.run(
        citation_verifier_agent,
        input=[{"role": "user", "content": prompt}]
    )
    # Extract the generated JSON text from the agent
    raw = ItemHelpers.text_message_outputs(result.new_items)
    try:
        data = json.loads(raw)
        return VerificationFeedback(valid=data.get("valid", False), issues=data.get("issues", ""))
    except json.JSONDecodeError:
        # In case of malformed JSON, return as invalid with raw text
        return VerificationFeedback(valid=False, issues=f"Invalid JSON response: {raw}")


def run_verification(
    output_text: str,
) -> VerificationFeedback:
    """
    Synchronous wrapper around the async citation verifier.
    """
    return asyncio.run(verify_output_with_agent(output_text))
