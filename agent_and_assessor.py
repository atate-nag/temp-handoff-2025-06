import asyncio
from dataclasses import dataclass
from typing import Literal

from agents import Agent, Runner, ItemHelpers, TResponseInputItem

@dataclass
class EvaluationFeedback:
    """
    Returned by the assessor.
    """
    rating: Literal["pass", "needs_improvement", "fail"]
    score: int
    feedback: str


async def single_agent_assessor_loop(
    generator_agent: Agent,
    assessor_agent: Agent[EvaluationFeedback],
    initial_prompt: str,
    label: str,
    max_rounds: int = 3
) -> str:
    """
    Runs a generate→evaluate loop for a single workflow:
      - The generator uses the current prompt to produce an output.
      - The assessor agent evaluates it; if "pass", we stop.
      - Otherwise, we incorporate feedback & repeat (up to max_rounds).
    Returns the final generator output (whether or not it ultimately passed).
    """
    current_prompt = initial_prompt
    final_output = ""

    for round_num in range(1, max_rounds + 1):
        # 1) Generate
        gen_result = await Runner.run(
            generator_agent,
            input=[{"role": "user", "content": current_prompt}]
        )
        final_output = ItemHelpers.text_message_outputs(gen_result.new_items)
        print(f"\n[{label}] Round {round_num} - Generator output:\n{final_output}")

        # 2) Assess
        assessment_input = (
            f"Below is the generator's output:\n\n{final_output}\n\n"
            f"Evaluate it; return a 'score' and 'feedback'."
        )
        assessor_result = await Runner.run(
            assessor_agent,
            input=[{"role": "user", "content": assessment_input}]
        )
        feedback_obj = assessor_result.final_output
        print(f"[{label}] Round {round_num} - Assessor score: {feedback_obj.score}")
        print(f"[{label}] Round {round_num} - Assessor feedback: {feedback_obj.feedback}")

        if feedback_obj.score == "pass":
            print(f"[{label}] Passed on round {round_num}.\n")
            break
        else:
            # Incorporate feedback into the prompt
            current_prompt += f"\n\nAssessor Feedback:\n{feedback_obj.feedback}"

    return final_output

import asyncio
from dataclasses import dataclass
from typing import Literal

from agents import Agent, Runner, ItemHelpers, TResponseInputItem

@dataclass
class EvaluationFeedback:
    """
    Returned by the assessor.
    """
    score: Literal["pass", "needs_improvement", "fail"]
    feedback: str


async def single_agent_assessor_loop(
    generator_agent: Agent,
    assessor_agent: Agent[EvaluationFeedback],
    initial_prompt: str,
    label: str,
    max_rounds: int = 3
) -> str:
    """
    Runs a generate→evaluate loop for a single workflow:
      - The generator uses the current prompt to produce an output.
      - The assessor agent evaluates it; if "pass", we stop.
      - Otherwise, we incorporate feedback & repeat (up to max_rounds).
    Returns the final generator output (whether or not it ultimately passed).
    """
    current_prompt = initial_prompt
    final_output = ""

    for round_num in range(1, max_rounds + 1):
        # 1) Generate
        gen_result = await Runner.run(
            generator_agent,
            input=[{"role": "user", "content": current_prompt}]
        )
        final_output = ItemHelpers.text_message_outputs(gen_result.new_items)
        print(f"\n[{label}] Round {round_num} - Generator output:\n{final_output}")

        # 2) Assess
        assessment_input = (
            f"Below is the generator's output:\n\n{final_output}\n\n"
            f"Evaluate it; return a 'score' and 'feedback'."
        )
        assessor_result = await Runner.run(
            assessor_agent,
            input=[{"role": "user", "content": assessment_input}]
        )
        feedback_obj = assessor_result.final_output
        print(f"[{label}] Round {round_num} - Assessor score: {feedback_obj.score}")
        print(f"[{label}] Round {round_num} - Assessor feedback: {feedback_obj.feedback}")

        if feedback_obj.score == "pass":
            print(f"[{label}] Passed on round {round_num}.\n")
            break
        else:
            # Incorporate feedback into the prompt
            current_prompt += f"\n\nAssessor Feedback:\n{feedback_obj.feedback}"

    return final_output

async def run_agent_assessor_in_parallel(
    generator_agent: Agent,
    assessor_agent: Agent[EvaluationFeedback],
    initial_prompt: str,
    num_parallel_workflows: int = 3,
    max_rounds: int = 3
) -> list[str]:
    """
    Launches `num_parallel_workflows` tasks in parallel, each one:
      - does its own loop of generator→assessor until pass or max_rounds.
    Returns a list of final outputs, one per workflow.
    """
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
    return results  # each item is the final output from that workflow

#
# from __future__ import annotations
#
# import asyncio
# from dataclasses import dataclass
# from typing import Literal
# from dotenv import load_dotenv
#
# load_dotenv()
#
# from agents import Agent, ItemHelpers, Runner, TResponseInputItem, trace
# @dataclass
# class EvaluationFeedback:
#     """
#     Example format for the assessor's output.
#     You can rename or extend this to suit your needs.
#     """
#     feedback: str
#     score: Literal["pass", "needs_improvement", "fail"]
#
#
# async def run_exchange(
#     generator_agent: Agent,
#     assessor_agent: Agent[EvaluationFeedback],
#     initial_prompt: str
# ) -> str:
#     """
#     1) Takes a user prompt (initial_prompt).
#     2) Uses `generator_agent` to produce output.
#     3) Uses `assessor_agent` to evaluate/score the output.
#     4) If the assessor says "pass," we end. Otherwise, we keep looping
#        and feed back the assessor's feedback to the generator_agent.
#     5) Returns the final output from the generator_agent.
#     """
#
#     # Convert the initial user prompt into the input format for the generator
#     input_items: list[TResponseInputItem] = [
#         {"content": initial_prompt, "role": "user"}
#     ]
#     latest_output: str | None = None
#
#     # We'll trace the entire "judge loop" session
#     with trace("Agent-Assessor Loop"):
#         while True:
#             # 1) Run the generator agent
#             generator_result = await Runner.run(generator_agent, input_items)
#             # Extract the newly generated text
#             latest_output = ItemHelpers.text_message_outputs(generator_result.new_items)
#             print(f"{generator_agent.name} output:\n{latest_output}\n")
#
#             # 2) Evaluate with the assessor agent
#             #    The assessor is typed to return an EvaluationFeedback object
#             assessor_result = await Runner.run(assessor_agent, generator_result.to_input_list())
#             evaluation: EvaluationFeedback = assessor_result.final_output
#             print(f"{assessor_agent.name} score: {evaluation.score}")
#             print(f"{assessor_agent.name} feedback: {evaluation.feedback}\n")
#
#             # 3) Check assessor's decision
#             if evaluation.score == "pass":
#                 print("Assessor passed the output. Exiting loop.")
#                 break
#             elif evaluation.score in ("needs_improvement", "fail"):
#                 print("Re-running generator with assessor feedback...\n")
#                 # Append the assessor's feedback as an additional user message
#                 input_items = generator_result.to_input_list() + [
#                     {"content": f"Feedback: {evaluation.feedback}", "role": "user"}
#                 ]
#             else:
#                 # If you had other statuses, handle them here
#                 pass
#
#     return latest_output or ""
#
#
# #
# # EXAMPLE USAGE
# #
# # If you had, for example, two pre-defined Agents in your code:
# #   – “my_generator_agent” with instructions for creating short stories (or solutions, etc.)
# #   – “my_assessor_agent” that returns an EvaluationFeedback object
# #
# # they might look like this:
# #
#
# my_generator_agent = Agent(
#     name="my_generator_agent",
#     instructions=(
#         "You produce a concise story outline based on the user's input.\n"
#         "If there is any feedback provided (by the assessor), incorporate it."
#     ),
#     model = "o3-mini",
#     # ... plus any other agent configuration ...
# )
#
# my_assessor_agent = Agent[EvaluationFeedback](
#     name="my_assessor_agent",
#     instructions=(
#         """You evaluate a story outline and decide if it's good enough.
#         If it's not good enough, you provide feedback on what needs to be improved.
#         Never give it a pass on the first try. But be fair, and as a guide try to
#         create something of a level that is equivalent to a UK GCSE English class, not greater.
#         When something is approaching A-level English standard, it should be given a pass.
#         You will give feedback in the format of "pass", "needs_improvement", "fail". Internally, keep a score
#         and then you can see whether the agent's work is converging to the score over time. We cannot entertain getting
#         involved in endless iterations witht eh agent.
#         """
#     ),
#     model = "o3-mini",
#     output_type=EvaluationFeedback,
#     # ... plus any other agent configuration ...
# )
#
# async def main():
#     user_input = input("What topic would you like to hear about? ")
#
#     final_result = await run_exchange(
#         generator_agent=my_generator_agent,
#         assessor_agent=my_assessor_agent,
#         initial_prompt=user_input
#     )
#
#     print("\nFinal agent output:")
#     print(final_result)
#
# if __name__ == "__main__":
#     asyncio.run(main())
