from debug import dprint
from pydantic import BaseModel, FilePath, field_validator, validator, ValidationError, Field
from abc import ABC, abstractmethod
from openai import OpenAI
from filehandler import FileHandler
from typing import Any,Optional,List, Dict
from openai_asst import AgentThread
from import_files import InputFilesModel, AsstFilesModel
import json
import re
import os

class AgentResponseModel(BaseModel):
    # Example fields expected in the JSON response
    completed: bool
    results: dict
    message: str

    @validator('results', pre=True)
    def validate_results(cls, v):
        if 'expected_field' not in v:
            raise ValueError("Results must include 'expected_field'")
        return v

# Model for validating file content
class AgentFileContentModel(BaseModel):
    data: list
    summary: str

class WorkFlowContextModel(BaseModel):
    client: Any
    file_handler: Any
    agent_type: str = Field()
    qm_id: Optional[str] = None
    create_new: Optional[bool] = None
    # input_files: List = Field()
    @field_validator('client')
    def check_client_type(cls, v):
        dprint(f"Validating client")
        if not isinstance(v, OpenAI):
            raise ValueError("client must be an instance of OpenAI")
        dprint(f"Validated client")
        return v

    @field_validator('file_handler')
    def check_file_handler(cls, v):
        dprint(f"Validating file handler")
        if not isinstance(v, FileHandler):
            raise ValueError("filehandler must be an instance of FileHandler")
        dprint(f"Validated filehander {v}")
        return v

    @field_validator('agent_type')
    def check_agent_type(cls, v):
        dprint(f"Validating agent type and known_agents")
        known_agents = AgentConfigs().get_known_agents()
        dprint(f"Known agents: {known_agents}")
        if v not in known_agents:
            raise ValueError(f"agent_type {v} is not valid. Must be one of {list(known_agents.keys())}")
        dprint(f" {v} is in known_agents")
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
    agent_id: str = Field()
    description: str = Field()
    prompt: str = Field()
    output_schema: dict = Field()
    requirements: Optional[Dict] = None  # This field is optional and can be None
    qm_id: Optional[str] = None
    instructions: Optional[str] = None
    @field_validator('agent_id')
    def validate_agent_id(cls, v):
        dprint("validating id", v)
        if not re.match(r"^asst_[A-Za-z0-9]{24}$", v):
            raise ValueError("ID must start with 'asst_' followed by 24 alphanumeric characters.")
        return v

    @validator('qm_id', always=True)
    def validate_qm_id(cls, v):
        if v is not None and not re.match(r"^asst_[A-Za-z0-9]{24}$", v):
            raise ValueError("QM ID must start with 'asst_' followed by 24 alphanumeric characters.")
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



""" Loaded State Validations """
class AgentThreadModel(BaseModel):
    agent_thread: Any
    @field_validator('agent_thread')
    def check_asst(cls, v):
        dprint(f"Validating AgentThread class")
        if not isinstance(v, AgentThread):
            raise ValueError("AgentThread must be an instance of AgentThread")
        if not v.client or not v.agent_id or not v.initial_prompt:
            raise ValueError("AgentThread class values not present")
            # TODSO add check for self.thread = None
        return v

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
