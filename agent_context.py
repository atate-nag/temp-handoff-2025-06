from pydantic import (
    BaseModel,
    FilePath,
    field_validator,
    validator,
    ValidationError,
    Field,
)
from typing import Any, Optional, List, Dict
from openai import OpenAI
from agent_configs import AgentConfigs
from filehandler import FileHandler
from debug import dprint
import json
import re


class RunContext(BaseModel):
    run_id: str  # Unique identifier for the run
    instructions: str  # Instructions for this particular run
    input_files: List[str]  # Input files for this run
    response: Optional[Any]  # Response from the agent's run
    output: Optional[Any]  # Structured output from the agent's run
    # ... other relevant fields ...


def assistant_file_accessible(client, file_id, agent_id):
    dprint(f"Retrieving file {file_id} for agent {agent_id}")
    asst_file = client.beta.assistants.files.retrieve(
        assistant_id=agent_id, file_id=file_id
    )
    dprint(f"asst_file {asst_file}")
    # content = client.files.retrieve_content(file)
    return asst_file is not None


class AgentInputFilesModel(BaseModel):
    client: Any  # can assume already checked in previous state
    agent_id: str = Field()
    input_files: list

    @validator("input_files", each_item=True)
    def check_input_files(cls, v, values, **kwargs):
        dprint(f"Validating input files {v}")
        agent_id = values.get("agent_id")
        client = values.get("client")
        dprint(f"Agent id: {agent_id}")
        dprint(f"client = {client}")
        if not v or not all(isinstance(file_id, str) for file_id in v):
            raise ValueError("input_files must be a list of non-empty strings")
        if not assistant_file_accessible(client, v, agent_id):
            raise ValueError(f"File ID {v} is not accessible by agent ID {agent_id}")
        return v


class AgentRequirements(BaseModel):
    reqs_schema: dict = Field()

    @validator("reqs_schema")
    def validate_schema(cls, v):
        try:
            json.dumps(v)
            return v
        except TypeError:
            raise ValueError("Schema must be a valid JSON schema.")


class AgentContext(BaseModel):
    client: Any
    file_handler: Any
    agent_type: str = Field()
    qm: bool
    id: str = Field()
    description: str = Field()
    prompt: str = Field()
    reqs_schema: dict = Field()
    qm_reqs_schema: Optional[Dict] = None  # This field is optional and can be None

    @validator("client")
    def check_client_type(cls, v):
        if not isinstance(v, OpenAI):
            raise ValueError("client must be an instance of OpenAI")
        return v

    @validator("file_handler")
    def check_file_handler(cls, v):
        if not isinstance(v, FileHandler):
            raise ValueError("filehandler must be an instance of FileHandler")
        return v

    @validator("agent_type")
    def check_agent_type(cls, v):
        return AgentConfigs.validate_agent_type(v)

    @validator("id")
    def validate_id(cls, v):
        if not re.match(r"^asst_[A-Za-z0-9]{24}$", v):
            raise ValueError(
                "ID must start with 'asst_' followed by 24 alphanumeric characters."
            )
        return v

    @validator("description", "prompt")
    def validate_text_fields(cls, v):
        if not isinstance(v, str) or len(v.strip()) == 0:
            raise ValueError(f"{cls.__name__} must be a non-empty string.")
        return v

    @validator("reqs_schema")
    def validate_required_schema(cls, v):
        if v is None:
            raise ValueError(
                "reqs_schema must be a valid JSON schema and cannot be None."
            )
        cls.validate_json_schema(v)
        return v

    @field_validator("qm_reqs_schema")
    def validate_optional_schema(cls, v):
        if v is None:
            return v
        cls.validate_json_schema(v)
        return v

    @staticmethod
    def validate_json_schema(v):
        try:
            json.dumps(v)  # Check if it's a valid JSON-able dictionary
        except TypeError:
            raise ValueError("Schema must be a valid JSON schema.")

    class Config:
        extra = "allow"

    """inputs: Any
    thread_obj: Any
    run_obj: Any
    status: str
    instruction: Any
    response: Any
    output: Any
    complete: bool
    return_obj: Any
    completion_obj: Any
    """


# Define the base state class
class AgentInitModel(BaseModel):
    client: Any  # Specify the exact type if possible
    file_handler: Any  # Specify the exact type if possible
    agent_type: str = Field()
    qm: bool

    @validator("client")
    def check_client_type(cls, v):
        if not isinstance(v, OpenAI):
            raise ValueError("client must be an instance of OpenAI")
        return v

    @validator("file_handler")
    def check_file_handler(cls, v):
        if not isinstance(v, FileHandler):
            raise ValueError("filehandler must be an instance of FileHandler")
        return v

    @validator("agent_type")
    def check_agent_type(cls, v):
        return AgentConfigs.validate_agent_type(v)


# class BaseState:
#     def on_enter(self, context: AgentContext):
#         pass  # Logic to execute when entering a state
#
#     def on_exit(self, context: AgentContext):
#         pass  # Logic to execute when exiting a state

# # Define a class for each state with specific behaviors
# class InitializeState(BaseState):
#     pass  # Define specific behaviors and validations for initialization
#
# class LoadState(BaseState):
#     pass  # Define specific behaviors and validations for loading
#
# class ZeroState(BaseState):
#     def validate_input(self, client, file_handler, qm, agent_key):
#         try:
#             validated_input = AgentInitModel(client=client, file_handler=file_handler, agent_type=agent_key, qm=qm)
#             print("Input validated successfully.")
#             self.client = client
#             return True
#         except ValidationError as e:
#             print(f"Validation error: {e}")
#             return False
