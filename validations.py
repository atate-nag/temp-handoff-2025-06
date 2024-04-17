from debug import dprint
from pydantic import BaseModel, FilePath, field_validator, validator, ValidationError, Field
from abc import ABC, abstractmethod
from openai import OpenAI
from filehandler import FileHandler
from typing import Any,Optional,List, Dict
import json
import re
def assistant_file_accessible(client, file_id, agent_id):
    dprint(f"Retrieving file {file_id} for agent {agent_id}")
    asst_file = client.beta.assistants.files.retrieve(
        assistant_id=agent_id,
        file_id=file_id
    )
    dprint(f"asst_file {asst_file}")
    # content = client.files.retrieve_content(file)
    return asst_file is not None

class ZerotoInitialValidationModel(BaseModel):
    client: Any
    file_handler: Any
    agent_type: str = Field()
    qm: bool
    # input_files: List = Field()
    @field_validator('client')
    def check_client_type(cls, v):
        if not isinstance(v, OpenAI):
            raise ValueError("client must be an instance of OpenAI")
        return v

    @field_validator('file_handler')
    def check_file_handler(cls, v):
        if not isinstance(v, FileHandler):
            raise ValueError("filehandler must be an instance of FileHandler")
        return v

    @field_validator('agent_type')
    def check_agent_type(cls, v):
        known_agents = AgentConfigs().get_known_agents()
        if v not in known_agents:
            raise ValueError(f"agent_type {v} is not valid. Must be one of {list(known_agents.keys())}")
        return v

    # @field_validator('input_files')
    # def check_input_files(cls, v, values, **kwargs):
    #     dprint(f"Validating input files {v}")
    #     agent_id = values.get('agent_id')
    #     client = values.get('client')
    #     dprint(f"Agent id: {agent_id}")
    #     dprint(f"client = {client}")
    #     if not v or not all(isinstance(file_id, str) for file_id in v):
    #         raise ValueError("input_files must be a list of non-empty strings")
    #     if not assistant_file_accessible(client, v, agent_id):
    #         raise ValueError(f"File ID {v} is not accessible by agent ID {agent_id}")
    #     return v

# class ZerotoInitialValidation(BaseValidation):
#     def __init__(self, agent, **kwargs):
#         super().__init__(agent)
#         self.agent = agent
#         self.agent_key = kwargs.get('agent_key')
#         self.client = kwargs.get('client')
#         self.file_handler = kwargs.get('file_handler')
#         self.agent_type = kwargs.get('agent_type')
#         self.qm = kwargs.get('qm')
#
#     def validate(self):
#         # Example: Access a parameter named 'threshold'
#         dprint("in validate for ZerotoInitial")
#         agent_config = AgentConfigs().get_agent_details(self.agent_type)
#         try:
#             context = AgentContext(
#                 client=self.client,
#                 file_handler=self.file_handler,
#                 agent_type=self.agent_type,
#                 qm=self.qm,
#                 id=agent_config['id'],
#                 description=agent_config['description'],
#                 prompt=agent_config['prompt'],
#                 reqs_schema=agent_config.get('output_schema', None),
#                 qm_reqs_schema=self.params.get('requirements')
#             )
#             dprint(f"Validated ZerotoInitialState")
#             return True
#         except Exception as e:
#             dprint(f"Failed Validation of InitialState")
#             return False

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

class ZerotoInitialConfigModel(BaseModel):
    agent_type: str

    @field_validator('agent_type')
    def validate_agent_type(cls, v):
        known_agents = AgentConfigs.get_known_agents()
        if v not in known_agents:
            raise ValueError(f"Agent type {v} is not valid. Must be one of {list(known_agents.keys())}")
        return v

    def get_agent_details(self):
        """Return detailed configuration for a validated agent type."""
        return AgentConfigs.get_known_agents()[self.agent_type]

class ZerotoInitialContextModel(BaseModel):
    id: str = Field()
    description: str = Field()
    prompt: str = Field()
    reqs_schema: dict = Field()
    qm_reqs_schema: Optional[Dict] = None  # This field is optional and can be None

    @field_validator('id')
    def validate_id(cls, v):
        if not re.match(r"^asst_[A-Za-z0-9]{24}$", v):
            raise ValueError("ID must start with 'asst_' followed by 24 alphanumeric characters.")
        return v

    @field_validator('description', 'prompt')
    def validate_text_fields(cls, v):
        if not isinstance(v, str) or len(v.strip()) == 0:
            raise ValueError(f"{cls.__name__} must be a non-empty string.")
        return v

    @field_validator('reqs_schema')
    def validate_required_schema(cls, v):
        if v is None:
            raise ValueError("reqs_schema must be a valid JSON schema and cannot be None.")
        cls.validate_json_schema(v)
        return v

    @field_validator('qm_reqs_schema')
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
        extra = 'allow'

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
