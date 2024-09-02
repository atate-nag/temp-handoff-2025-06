from decomp_task.base import BaseAgents
from decomp_task.writing.task import ConstrainedWritingTask
from decomp_task.writing.sections import (
    get_available_section_selector,
    sections_to_str,
    section_dict,
)
import json
from typing import List
from decomp_task.writing.decomp.unconstrained import (
    WritingTaskDecomp,
    WritingCondition,
    get_schema,
    create_decomposer,
)


class ConstrainedWritingTaskDecomp(WritingTaskDecomp):
    def __init__(self, company: str, iterative: int = 0, **other_args) -> None:
        super().__init__(company, **other_args)
        self.iterative_toggle = iterative

    def iterative(self, task: ConstrainedWritingTask) -> None:
        if self.iterative_toggle == 0:
            return False
        elif self.iterative_toggle == 1:
            return True
        elif self.iterative_toggle == -1:
            available_sections_type = get_available_section_selector(
                task.section_type, None, return_raw=True
            )
            return not (
                len(available_sections_type) == 1
                and available_sections_type[0].name == "standard"
            )
        else:
            raise IndexError

    def _generate_message(self, task: ConstrainedWritingTask) -> str:
        message = f"""{task.task_details_str(indent=1)}"""

        return message

    def _planning_decomp_single(self, message, task: ConstrainedWritingTask) -> None:
        if self.iterative_toggle == -1:
            agent_config, schema = create_decomposer()
            message = f"Decompose parent section:\n{message}"
        else:
            agent_config, schema = create_single_step_decomposer()
            available_sections_type = get_available_section_selector(
                task.section_type, None, return_raw=False, single=True
            )
            message = f"Decompose parent section:\n{message}\n\n\nSelect from {available_sections_type}"

        planing_results = BaseAgents(
            llm_config=self.setup_config["llm_config"],
            silent=self.setup_config["silent"],
            is_termination_msg=self.setup_config["is_termination_msg"],
            user_system_prompt=self.setup_config["user"],
            agents_config=[agent_config],
        ).convo_with_structure(
            agent_name=agent_config["name"], message=message, structure_schema=schema
        )[
            "sections"
        ]

        # planing_results = [ self._add_embeddings(res) for res in planing_results ]
        # for i in range( 1 , len(planing_results) ):
        #     others = [ x for j,x in enumerate(planing_results) if j != i ]
        # self._validate_result(task, others, planing_results[i])

        if self.iterative_toggle == -1:
            planing_results = [
                x | {"section_type": "standard"} for x in planing_results
            ]

        current = task
        for i, next_section_content in enumerate(planing_results):
            overriding_args = {
                "name": next_section_content["section_title"],
                "description": next_section_content["summary_section_content"],
                "objectives": [
                    f"A sub-section, titled '{next_section_content['section_title']}', of the parent section, titled '{task.name}'."
                ],
                "constraints": next_section_content["detailed_section_content"],
                "section_type": next_section_content["section_type"],
            }
            current = current.create_task(
                overriding_args, parent_or_previous=True if i == 0 else False
            )
            # current.constraint_embeddings = next_section_content["constraint_embeddings"]

    def _is_done(self, message, task: ConstrainedWritingTask):
        current_sequence = task._get_child_tasks()
        # Has next section type to choose from
        last_section = current_sequence[-1].section_type if task.child_task else None
        available_sections_type = get_available_section_selector(
            task.section_type, last_section, return_raw=True
        )

        if "Not a valid parent section name" in available_sections_type:
            raise Exception("Invalid Parent Section Type")
        elif "Parent section has no sub-section available" in available_sections_type:
            raise Exception("Condition failed")
        elif len(available_sections_type) == 0:
            return True

        return super()._is_done(message, task)

    def _get_next_sections_type(self, message, task: ConstrainedWritingTask):

        # create message
        current_sequence = task._get_child_tasks()
        last_section = current_sequence[-1].section_type if task.child_task else None
        available_sections_type = get_available_section_selector(
            task.section_type, last_section, return_raw=True
        )

        if type(available_sections_type) == str:
            raise Exception("Issues with parent section type")
        elif len(available_sections_type) == 0:
            raise Exception("Issues with Is Done should have caught this")
        elif len(available_sections_type) == 1:
            return {
                "section_type": available_sections_type[0].name,
                "section_type_reasoning": "Only one type remaining",
            }
        else:
            available_types = ", ".join([x.name for x in available_sections_type])
            available_types_str = sections_to_str(available_sections_type, False)

        message = (
            f"From available sub-section types: {available_types}; select the {'next' if task.child_task else 'first'} sub-section type."
            + "Only select from the available sub-section type. See below for further details on available sub-section types and parent section."
            + f"\n\n{available_types_str}"
            + f"\n\nParent Section:\n{message}"
        )
        if task.child_task:
            message = f"{message}\n\nCurrent sub-sections are:\n{task.child_task.workflow(as_string=True)}"
        system_message, schema = create_next_section_type_agent()

        output = {}
        most_common = None
        retries = 0
        while most_common is None:
            inter_llm_config = self.setup_config["llm_config"]
            if self.setup_config["llm_config"]["cache_seed"] is None:
                inter_llm_config["cache_seed"] = None
            else:
                inter_llm_config["cache_seed"] = (
                    10000 * (retries + 1)
                    + self.setup_config["llm_config"]["cache_seed"]
                )
            next_section_type = BaseAgents(
                llm_config=inter_llm_config,
                silent=self.setup_config["silent"],
                is_termination_msg=self.setup_config["is_termination_msg"],
                user_system_prompt=system_message,
            ).single_with_structure(message, schema)

            if next_section_type["section_type"] in section_dict and next_section_type[
                "section_type"
            ] in [x.name for x in available_sections_type]:
                output[next_section_type["section_type"]] = (
                    output.get(next_section_type["section_type"], 0) + 1
                )

            if sum(list(output.values())) >= 3:
                sorted_list = sorted(output.items(), key=lambda x: x[1])
                if len(sorted_list) == 1:
                    most_common = sorted_list[-1][0]
                elif sum(list(output.values())) >= 7:
                    most_common = sorted_list[-1][0]
                elif sorted_list[-1][1] > sorted_list[-2][1]:
                    most_common = sorted_list[-1][0]

            retries = retries + 1

        return {"section_type": most_common}

    def _get_section_content(self, message, task: ConstrainedWritingTask):
        next_section_type = self._get_next_sections_type(message, task)
        if next_section_type["section_type"] == "standard":
            results = super()._get_section_content(message, task)
            results = results | {"section_type": "standard"}
            return results

        message = (
            f"Selected section type is '{next_section_type['section_type']}'.\n\n"
            + f"Section Type Definition: {section_dict[next_section_type['section_type']].description}\n\n"
            + f"Create sub-section for parent section: {message}\n\n"
        )

        if task.child_task:
            message = f"{message}Complement current created sections are:\n{task.child_task.workflow(as_string=True)}"
            message = f"{message}\n\nAvoid overlap with previous section:\n{task._get_child_tasks()[-1].task_details_str(indent=1)} "

        agent_config, schema = create_iter_step_decomposer_constrained()
        results = BaseAgents(
            llm_config=self.setup_config["llm_config"],
            silent=self.setup_config["silent"],
            is_termination_msg=self.setup_config["is_termination_msg"],
            user_system_prompt=self.setup_config["user"],
            agents_config=[agent_config],
        ).convo_with_structure(
            agent_name=agent_config["name"], message=message, structure_schema=schema
        )
        # results = self._add_embeddings(results)
        return results

    def _get_next_step(self, message, task: ConstrainedWritingTask):
        next_section_content = self._get_section_content(message, task)
        # self._validate_result(task, task._get_child_tasks(), next_section_content)
        parent_or_previous = False if task.child_task else True
        overriding_args = {
            "name": next_section_content["section_title"],
            "description": next_section_content["summary_section_content"],
            "objectives": [
                f"A sub-section, titled '{next_section_content['section_title']}', of the parent section, titled '{task.name}'."
            ],
            "constraints": next_section_content["detailed_section_content"],
            "section_type": next_section_content["section_type"],
        }
        if parent_or_previous:
            new_task = task.create_task(
                overriding_args, parent_or_previous=parent_or_previous
            )
        else:
            new_task = task._get_child_tasks()[-1].create_task(
                overriding_args, parent_or_previous=parent_or_previous
            )

        # new_task.constraint_embeddings = next_section_content["constraint_embeddings"]


class ConstrainedWritingCondition(WritingCondition):
    def __init__(self, **other_args):
        super().__init__(**other_args)

    def __call__(self, task: ConstrainedWritingTask):
        available_types = get_available_section_selector(
            task.section_type, return_raw=True
        )

        if "Not a valid parent section name" in available_types:
            raise Exception("Not a valid parent section name")
        elif "Parent section has no sub-section available" in available_types:
            return {
                "decompose": False,
                "reasoning": "This section cannot be further decomposed per definition.",
            }
        elif task.section_type in ["strategy recommendation", "main body"]:
            return {
                "decompose": True,
                "reasoning": "This section must be further decomposed per user.",
            }

        reply = super().__call__(task)
        return reply


########################################################
def create_single_step_decomposer():
    structure, schema, desc = get_schema(add_section_type=True, ret_section=False)
    desc = [f"   {i+1}) {k}: {v}" for i, (k, v) in enumerate(desc.items())]
    desc = "\n".join(desc)
    system_message = (
        "You are a helpful assistant. Your task is to decompose the parent section into sub-sections based on criteria below.\n\n"
        + "The decomposition must adhere to the following criteria:\n"
        + "    - The sub-sections should related to each other and together form the parent section of the report.\n"
        + "    - There should be at most 4 sub-sections.\n"
        + "    - There is no need for any sections that are introduction or conclusions. Go straight to the addressing the topic.\n"
        + "    - Each decomposed sub-section should contain:\n"
        + desc
    )

    summary_prompt = f"""From the conversation above, extract the information to fill up the json structure.\n{json.dumps(structure,indent=4)}"""

    return {
        "name": "single_decomp",
        "system_message": system_message,
        "summary_method": "reflection_with_llm",
        "summary_args": {"summary_prompt": summary_prompt},
    }, schema


def create_iter_step_decomposer_constrained():

    structure, schema, desc = get_schema(add_section_type=True, ret_section=True)
    desc = "\n".join(
        [
            f"   {i+1}) {k}: {v}"
            for i, (k, v) in enumerate(desc.items())
            if k != "section_type"
        ]
    )
    system_message = f"""Based on the selected section type:\n{desc}"""
    system_message = (
        "You are a helpful assistant, regarding decomposing parent section into sub-sections.\n\n"
        + "Your task is to create one sub-section based on the following criteria"
        + "    - The sub-section must be based on the selected section type. \n"
        + "    - The sub-section must complement the created sub-sections, must not overlap with previous section, and related to the parent section. \n"
        + "    - There is no need for any sub-section that are introduction or conclusions. Go straight to the addressing the topic.\n"
        + "    - Each sub-section must contain:\n"
        + "\n".join(desc)
    )

    summary_prompt = f"""From the conversation above, extract the information to fill up the json structure.\n{json.dumps(structure,indent=4)}.\nDont forget the triple back tick."""

    return {
        "name": "iter_decomp",
        "system_message": system_message,
        "summary_method": "reflection_with_llm",
        "summary_args": {"summary_prompt": summary_prompt},
    }, schema


def create_is_done_agent():
    system_prompt = (
        "You are part of a process that decomposes a parent section into sub-sections."
        + "You will be given a list of created sub-sections and parent section, and will need to determine if additional sub-sections are needed."
        + "Additional sub-section are needed if the expected content constraints of the parent section are all met by the created sub-sections."
        + """Provide your reasoning and decision in the following json structure format: { "reasoning" : "" , "additional_sub_section" : "yes or no" }. Dont forget the triple back tick."""
    )

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
            },
            "additional_sub_section": {
                "type": "string",
                "enum": ["yes", "no", "Yes", "No"],
            },
        },
        "required": ["reasoning", "additional_sub_section"],
    }
    return system_prompt, schema


def create_next_section_type_agent():
    system_message = (
        "Your role is to select the most appropriate section type for the sub-section to be written. You may only select one type from the available section types.\n"
        + "Select the section type based on the below: \n"
        + "   1) The type must allow for expansion of the parent section content\n"
        + "   2) The type must follow from the content of the sub-section written\n"
        + '   3) If there are no suitable type, select type "end_section". \n'
        + 'Return your response in the following json structure format: { "section_type" : "" , "section_type_reasoning" : "" }. Dont forget the triple tick.'
    )

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            "section_type": {"type": "string"},
            "section_type_reasoning": {"type": "string"},
        },
        "required": ["section_type", "section_type_reasoning"],
    }

    return system_message, schema
