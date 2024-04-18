from debug import dprint
from pydantic import BaseModel, FilePath, field_validator, validator, ValidationError, Field
from abc import ABC, abstractmethod
from openai import OpenAI
from filehandler import FileHandler
from typing import Any,Optional,List, Dict
import json
import re
import os
def assistant_file_accessible(client, file_id, agent_id):
    dprint(f"Retrieving file {file_id} for agent {agent_id}")
    asst_file = client.beta.assistants.files.retrieve(
        assistant_id=agent_id,
        file_id=file_id
    )
    dprint(f"asst_file {asst_file}")
    # content = client.files.retrieve_content(file)
    return asst_file is not None

class WorkFlowContextModel(BaseModel):
    client: Any
    file_handler: Any
    agent_type: str = Field()
    qm: bool
    # input_files: List = Field()
    @field_validator('client')
    def check_client_type(cls, v):
        dprint(f"Validating client")
        if not isinstance(v, OpenAI):
            raise ValueError("client must be an instance of OpenAI")
        return v

    @field_validator('file_handler')
    def check_file_handler(cls, v):
        dprint(f"Validating file handler")
        if not isinstance(v, FileHandler):
            raise ValueError("filehandler must be an instance of FileHandler")
        return v

    @field_validator('agent_type')
    def check_agent_type(cls, v):
        dprint(f"Validating agent type and known_agents")
        known_agents = AgentConfigs().get_known_agents()
        if v not in known_agents:
            raise ValueError(f"agent_type {v} is not valid. Must be one of {list(known_agents.keys())}")
        return v

class AgentConfigs:
    _instance = None
    _configs = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentConfigs, cls).__new__(cls)
            cls._instance.init_config()
        return cls._instance

    def init_config(self):
        if AgentConfigs._configs is None:
            AgentConfigs._configs = self.load_config("known_agents.json")

    def load_config(self, config_path):
        with open(config_path, 'r') as file:
            return json.load(file)

    def get_config(self, key):
        return AgentConfigs._configs.get(key)

    @classmethod
    def get_known_agents(cls):
        return cls().get_config('known_agents')

    @classmethod
    def get_agent_details(cls, agent_type):
        """Retrieve detailed configuration for a specific agent type."""
        known_agents = cls.get_known_agents()
        if agent_type not in known_agents:
            raise ValueError(f"Agent type {agent_type} is not valid. Must be one of {list(known_agents.keys())}.")
        return known_agents[agent_type]

class AgentContextModel(BaseModel):
    id: str = Field()
    description: str = Field()
    prompt: str = Field()
    output_schema: dict = Field()
    requirements: Optional[Dict] = None  # This field is optional and can be None

    @field_validator('id')
    def validate_id(cls, v):
        dprint("validating id", v)
        if not re.match(r"^asst_[A-Za-z0-9]{24}$", v):
            raise ValueError("ID must start with 'asst_' followed by 24 alphanumeric characters.")
        return v

    @field_validator('description', 'prompt')
    def validate_text_fields(cls, v):
        dprint("validating text fields")
        if not isinstance(v, str) or len(v.strip()) == 0:
            raise ValueError(f"{cls.__name__} must be a non-empty string.")
        return v

    @field_validator('output_schema')
    def validate_required_schema(cls, v):
        dprint("validating required schema")
        if v is None:
            raise ValueError("reqs_schema must be a valid JSON schema and cannot be None.")
        cls.validate_json_schema(v)
        return v

    @field_validator('requirements')
    def validate_optional_schema(cls, v):
        dprint("validating optional schema")
        if v is None:
            return v
        cls.validate_json_schema(v)
        return v

    @staticmethod
    def validate_json_schema(v):
        dprint("validating json_schema")
        try:
            json.dumps(v)  # Check if it's a valid JSON-able dictionary
        except TypeError:
            raise ValueError("Schema must be a valid JSON schema.")

    class Config:
        extra = 'allow'

class InputFilesModel(BaseModel):
    input_files: list = Field(default=[])
    @validator('input_files', each_item=True)
    def check_input_files(cls, v, values):
        if not isinstance(v, str):
            raise ValueError(f"v={v}: Each item in input_files must be a string representing a file path.")
        dprint(f"filepath OK")
        # Optional: Check if the file path exists in the filesystem
        if not os.path.exists(v):
            raise ValueError(f"File path {v} does not exist.")
        dprint(f"filepath exists")
        return v

        class Config:
            validate_assignment = True


"""Initialised State Validations """

class AsstFilesModel(BaseModel):
    client: Any  # Assuming this has a specific class that you have defined.
    agent_id: str = Field()
    asst_files: list = Field(default=[])

    @validator('asst_files', each_item=True)
    def check_asst_files(cls, v, values):
        if not isinstance(v, str):
            raise ValueError(f"v={v}: Each item in input_files must be a string representing a file path.")
        dprint(f"filepath OK")
        client = values['client']
        agent_id = values['agent_id']
        # Optional: Check if the file path exists in the filesystem
        if assistant_file_accessible(client,agent_id,v):
            dprint(f"asst_file exists and is accessible")
        return v

        class Config:
            validate_assignment = True


class BaseValidation(ABC):
    def __init__(self, agent, **kwargs):
        self.agent = agent
        self.params = kwargs  # Store additional parameters as a dictionary

    @abstractmethod
    def validate(self):
        """Implement validation logic that can use self.params"""
        pass

class InitialtoLoadedValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent
        self.agent_key = kwargs.get('input_files')
    def validate(self):
        return True

class LoadedtoRunningValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent

    def validate(self):
        return True


class RunningtoReturnedValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent

    def validate(self):
        return True


class ReturnedtoCompleteValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent

    def validate(self):
        return True
