from pydantic import BaseModel, create_model, Field
from typing import Dict, List, Tuple, Optional
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_openai import ChatOpenAI
from datetime import time
from enum import Enum
import os
import logging
import logging.config
import json
from string import Template
from dotenv import load_dotenv
from chains import build_chain_action, build_writing_chain, build_assessing_chain
from utility import dict_to_plain_text, retry, invoke
from report import Report

load_dotenv()


from functools import wraps


class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    sky = "\x1b[36;20m"
    format = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: sky + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


from dotenv import load_dotenv
import threading
import uuid


class Agent:

    def __init__(self, name: str):
        self.name = name
        self.speaking_model = ChatOpenAI(model="gpt-4o", temperature=0.1)
        self.conversation_model = ChatOpenAI(model="gpt-4o", temperature=0.1)

        self.function = {}
        self.tools_output = {}
        self.report = Report()

    def update_report(self, update):
        """
        Updates the agent's report with the given update.

        Args:
            update (dict): The update to apply to the report.
        """
        self.report.update(update)

    def set_tools(self, tool_list):
        """
        Sets the tools available for the agent to use.

        Args:
            tool_list (list): A list of tools to set.
        """
        if isinstance(tool_list, list):
            tools = []
            potential_actions = []
            for tool in tool_list:
                if isinstance(tool, dict):
                    function = tool["function"]
                    name = tool["name"]
                    inputs = tool["inputs"]
                    description = tool["description"]

                    self.function[name] = function
                    action_schema = create_model(
                        name,
                        **{
                            "name": (
                                str,
                                Field(
                                    "the name you want to give to that function to identify the result afterward"
                                ),
                            ),
                            "inputs": (inputs[0], Field(description=inputs[1])),
                            "explanation": (
                                str,
                                Field(
                                    description="Explain why and how you use this function"
                                ),
                            ),
                        },
                    )
                    potential_actions.append(
                        {
                            "name": (
                                str,
                                Field(
                                    "the name you want to give to that function to identify the result afterward"
                                ),
                            ),
                            "inputs": (inputs[0], Field(description=inputs[1])),
                            "explanation": (
                                str,
                                Field(
                                    description="Explain why and how you use this function"
                                ),
                            ),
                        }
                    )
                    tools.append((name, action_schema))

            self.tools = create_model(
                "actionChoice",
                **{
                    name: (Optional[action_schema], Field(description=""))
                    for name, action_schema in tools
                },
            )

    def build(self):
        """
        Builds the agent's model, parser, and prompt.

        Args:
            speaker_instruction (str): The instruction for the speaker.
            planner_instruction (str): The instruction for the planner.
            action_instruction (str): The instruction for the action.
            extracter_instruction (str): The instruction for the extracter.
        """
        self.action_chain = build_chain_action(self.tools)
        self.writing_chain = build_writing_chain()

        self.assessing_chain = build_assessing_chain()

    @retry(number_of_retry=3)
    def call(self, query, history):
        """
        Makes a call to the agent with the given query and history.

        Args:
            query (str): The query to send to the agent.
            history (str): The conversation history.
        """

        thread = threading.Thread(
            target=self.thinking, args=(query, history), daemon=None
        )
        thread.start()

        logger.info(f"State of the tool use: {dict_to_plain_text(self.tools_output)}")
        # response = self.chain_speaker.invoke(
        #     {
        #         "query": query,
        #         "history": history,
        #         "tools_state": dict_to_plain_text(self.tools_output),
        #         "plan_instruction": self.current_instruction,
        #     }
        # )
        response = invoke(
            self.chain_speaker,
            {
                "query": query,
                "history": history,
                "tools_state": dict_to_plain_text(self.tools_output),
                "plan_instruction": self.current_instruction,
            },
        )

        return response

    def build_report(self):
        """
        Builds the agent's report.
        """
        self.report.build_table_content()


def get_subsections(data, section_name="content"):
    subsections = []

    if isinstance(data, dict):
        # debug logging removed
        if isinstance(data["content"], dict):
            if section_name in data["content"].keys():
                subsections.append((data["name"], data["content"][section_name]))
        else:
            for k, v in data.items():
                if isinstance(v, dict):
                    subsections.extend(get_subsections(v, section_name))
                elif isinstance(v, list):
                    for item in v:
                        subsections.extend(get_subsections(item, section_name))
    elif isinstance(data, list):
        for item in data:
            subsections.extend(get_subsections(item, section_name))
    return subsections


def find_and_fill(data, title, new_title, content, data_needed, content_statements):
    if isinstance(data, dict):

        if data.get("name", None) == title:
            data["content_generated"] = content
            data["name"] = new_title
            # data["data_needed"] = data_needed
            data["content_statements"] = content_statements
            return True

        for k, v in data.items():
            if isinstance(v, dict):
                find_and_fill(
                    v, title, new_title, content, data_needed, content_statements
                )
            elif isinstance(v, list):
                for item in v:
                    find_and_fill(
                        item, title, new_title, content, data_needed, content_statements
                    )
    elif isinstance(data, list):
        for item in data:
            find_and_fill(
                item, title, new_title, content, data_needed, content_statements
            )
    # return data


import json


def json_to_markdown(json_obj):
    markdown = ""

    for section in json_obj["TableOfContents"]:
        markdown += f"# {section['Section']}\n"
        for subsection in section["Subsections"]:
            markdown += f"## {subsection['Subsection']}\n"
            markdown += f"{subsection['content']}\n\n"
            # markdown += f"### Data needed\n"
            # markdown += f"{subsection['data_needed']}\n\n"
            markdown += f"### Statements\n"
            markdown += f"{subsection['content_statements']}\n\n"

    return markdown
