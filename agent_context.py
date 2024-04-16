from transitions import Machine
from pydantic import BaseModel, FilePath, validator, ValidationError, Field
from typing import Any,Optional,List, Dict
from openai import OpenAI
from agent_configs import AgentConfigs
from filehandler import FileHandler
import json
import re
class RunContext(BaseModel):
    run_id: str  # Unique identifier for the run
    instructions: str  # Instructions for this particular run
    input_files: List[str]  # Input files for this run
    response: Optional[Any]  # Response from the agent's run
    output: Optional[Any]  # Structured output from the agent's run
    # ... other relevant fields ...

class AgentContext(BaseModel):
    client: Any
    file_handler: Any
    agent_type: str = Field()
    qm: bool
    id: str = Field()
    description: str = Field()
    prompt: str = Field()
    reqs_schema: dict = Field()

    @validator('client')
    def check_client_type(cls, v):
        if not isinstance(v, OpenAI):
            raise ValueError("client must be an instance of OpenAI")
        return v

    @validator('file_handler')
    def check_file_handler(cls, v):
        if not isinstance(v, FileHandler):
            raise ValueError("filehandler must be an instance of FileHandler")
        return v

    @validator('agent_type')
    def check_agent_type(cls, v):
        return AgentConfigs.validate_agent_type(v)

    @validator('id')
    def validate_id(cls, v):
        if not re.match(r"^asst_[A-Za-z0-9]{24}$", v):
            raise ValueError("ID must start with 'asst_' followed by 24 alphanumeric characters.")
        return v

    @validator('description', 'prompt')
    def validate_text_fields(cls, v):
        if not isinstance(v, str) or len(v.strip()) == 0:
            raise ValueError(f"{cls.__name__} must be a non-empty string.")
        return v

    @validator('reqs_schema')
    def validate_schema(cls, v):
        try:
            json.dumps(v)  # This is a simple way to check if it's a valid JSON-able dictionary
            return v
        except TypeError:
            raise ValueError("Schema must be a valid JSON schema.")

    class Config:
        extra = 'allow'

    '''inputs: Any
    thread_obj: Any
    run_obj: Any
    status: str
    instruction: Any
    response: Any
    output: Any
    complete: bool
    return_obj: Any
    completion_obj: Any
    '''

#Define the base state class
class AgentInitModel(BaseModel):
    client: Any  # Specify the exact type if possible
    file_handler: Any  # Specify the exact type if possible
    agent_type: str = Field()
    qm: bool

    @validator('client')
    def check_client_type(cls, v):
        if not isinstance(v, OpenAI):
            raise ValueError("client must be an instance of OpenAI")
        return v

    @validator('file_handler')
    def check_file_handler(cls, v):
        if not isinstance(v, FileHandler):
            raise ValueError("filehandler must be an instance of FileHandler")
        return v

    @validator('agent_type')
    def check_agent_type(cls, v):
        return AgentConfigs.validate_agent_type(v)
class BaseState:
    def on_enter(self, context: AgentContext):
        pass  # Logic to execute when entering a state

    def on_exit(self, context: AgentContext):
        pass  # Logic to execute when exiting a state

# Define a class for each state with specific behaviors
class InitializeState(BaseState):
    pass  # Define specific behaviors and validations for initialization

class LoadState(BaseState):
    pass  # Define specific behaviors and validations for loading

class ZeroState(BaseState):
    def validate_input(self, client, file_handler, qm, agent_key):
        try:
            validated_input = AgentInitModel(client=client, file_handler=file_handler, agent_type=agent_key, qm=qm)
            print("Input validated successfully.")
            self.client = client
            return True
        except ValidationError as e:
            print(f"Validation error: {e}")
            return False