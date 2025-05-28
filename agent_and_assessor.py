import asyncio
import json
from dataclasses import dataclass
from typing import Optional, Literal

from agents import Agent, Runner, ItemHelpers

@dataclass
class VerificationFeedback:
    valid: bool
    issues: str

@dataclass
class EvaluationFeedback:
    score: Literal["pass", "needs_improvement", "fail"]
    feedback: str

async def single_agent_assessor_loop(
    generator_agent: Agent,
    verifier_agent: Agent,
    assessor_agent: Optional[Agent],
    initial_prompt: str,
    label: str,
    max_rounds: int = 3
) -> str:
    current_prompt = initial_prompt
    final_output = ""

    for round_num in range(1, max_rounds + 1):
        # 1) Generate
        gen_result = await Runner.run(
            generator_agent,
            input=[{"role": "user", "content": current_prompt}]
        )
        final_output = ItemHelpers.text_message_outputs(gen_result.new_items)
        print(f"[{label}] Round {round_num} - Generator output:\n{final_output}")

        # 2) Verify citations
        verify_input = (
            f"Below is the generator's output (with citations):\n\n"
            f"{final_output}\n\n"
            "Focus ONLY on verifying that each citation correctly supports its claim."
        )
        verifier_result = await Runner.run(
            verifier_agent,
            input=[{"role": "user", "content": verify_input}]
        )
        raw_vfb = ItemHelpers.text_message_outputs(verifier_result.new_items)
        try:
            vfb_data = json.loads(raw_vfb)
            vfb = VerificationFeedback(
                valid=vfb_data.get("valid", False),
                issues=vfb_data.get("issues", "")
            )
        except json.JSONDecodeError:
            vfb = VerificationFeedback(
                valid=False,
                issues=f"Invalid verifier response: {raw_vfb}"
            )
        print(f"[{label}] Round {round_num} - Citations valid? {vfb.valid}")
        if not vfb.valid:
            print(f"[{label}] Round {round_num} - Verification issues:\n{vfb.issues}")
            current_prompt += f"\n\nVerification issues:\n{vfb.issues}"
            continue

        # 3) Assess quality
        assess_input = (
            f"Below is the (verified) generator output:\n\n{final_output}\n\n"
            "Evaluate it; return a 'score' and 'feedback'."
        )
        assessor_result = await Runner.run(
            assessor_agent,
            input=[{"role": "user", "content": assess_input}]
        )
        afb: EvaluationFeedback = assessor_result.final_output
        print(f"[{label}] Round {round_num} - Assessor score: {afb.score}")
        print(f"[{label}] Round {round_num} - Assessor feedback: {afb.feedback}")

        if afb.score == "pass":
            print(f"[{label}] Passed on round {round_num}.\n")
            break
        else:
            current_prompt += f"\n\nAssessor Feedback:\n{afb.feedback}"

    return final_output

async def single_agent_verify_assess_loop(
    generator_agent: Agent,
    verifier_agent: Agent,
    assessor_agent: Optional[Agent],
    initial_prompt: str,
    label: str,
    max_rounds: int = 3
) -> str:
    current_prompt = initial_prompt
    final_output = ""

    for round_num in range(1, max_rounds + 1):
        gen_result = await Runner.run(
            generator_agent,
            input=[{"role": "user", "content": current_prompt}]
        )
        final_output = ItemHelpers.text_message_outputs(gen_result.new_items)
        print(f"[{label}] Round {round_num} - Generator output:\n{final_output}")

        assessment_input = (
            f"Below is the generator's output:\n\n{final_output}\n\n"
            f"Evaluate it; return a 'score' and 'feedback'."
        )
        if _assessor_is_none(assessor_agent):
            gen_result = await Runner.run(
                generator_agent,
                input=[{"role": "user", "content": initial_prompt}]
            )
            return ItemHelpers.text_message_outputs(gen_result.new_items)

        assessor_result = await Runner.run(
            assessor_agent,
            input=[{"role": "user", "content": assessment_input}]
        )
        feedback_obj: EvaluationFeedback = assessor_result.final_output
        print(f"[{label}] Round {round_num} - Assessor score: {feedback_obj.score}")
        print(f"[{label}] Round {round_num} - Assessor feedback: {feedback_obj.feedback}")

        if feedback_obj.score == "pass":
            print(f"[{label}] Passed on round {round_num}.\n")
            break
        else:
            current_prompt += f"\n\nAssessor Feedback:\n{feedback_obj.feedback}"

    return final_output

def run_single_workflow_with_verifier(
    generator_agent: Agent,
    verifier_agent: Agent,
    assessor_agent: Optional[Agent],  # ←
    initial_prompt: str,
    label: str = "Sync Workflow",
    max_rounds: int = 3
) -> str:
    return asyncio.run(
        single_agent_verify_assess_loop(
            generator_agent=generator_agent,
            verifier_agent=verifier_agent,
            assessor_agent=assessor_agent,
            initial_prompt=initial_prompt,
            label=label,
            max_rounds=max_rounds,
        )
    )

def run_single_workflow(
    generator_agent: Agent,
    assessor_agent: Optional[Agent],
    initial_prompt: str,
    label: str = "Sync Workflow",
    max_rounds: int = 3
) -> str:
    return asyncio.run(
        single_agent_assessor_loop(
            generator_agent=generator_agent,
            assessor_agent=assessor_agent,
            initial_prompt=initial_prompt,
            label=label,
            max_rounds=max_rounds,
        )
    )

async def run_agent_assessor_in_parallel(
    generator_agent: Agent,
    assessor_agent: Optional[Agent],
    initial_prompt: str,
    num_parallel_workflows: int = 3,
    max_rounds: int = 3
) -> list[str]:
    tasks = []
    for i in range(num_parallel_workflows):
        label = f"Workflow #{i+1}"
        tasks.append(asyncio.create_task(
            single_agent_assessor_loop(
                generator_agent=generator_agent,
                assessor_agent=assessor_agent,
                initial_prompt=initial_prompt,
                label=label,
                max_rounds=max_rounds
            )
        ))
    results = await asyncio.gather(*tasks)
    return results

def _assessor_is_none(assessor: Optional[Agent]) -> bool:
    return assessor is None