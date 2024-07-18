from pydantic import BaseModel, FilePath, validator, ValidationError, Field
from typing import List, Any
from transitions import Machine, MachineError, EventData
from openai import OpenAI
from filehandler import FileHandler
from agent_configs import AgentConfigs
from debug import dprint


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
    prompt: str = Field()
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


class AgentInputModel(BaseModel):
    input_files: list
    qm: bool

    @validator("input_files")
    def check_input_files(cls, v):
        if not v or not all(isinstance(file_id, str) for file_id in v):
            raise ValueError("input_files must be a list of non-empty strings")
        return v

    @validator("qm")
    def check_qm(cls, v):
        if not isinstance(v, bool):
            raise ValueError("qm must be a boolean value")
        return v


class AgentOutputModel(BaseModel):
    output_json: str
    additional_data: dict

    @validator("output_json")
    def validate_json(cls, value):
        import json

        try:
            # This will ensure the JSON is parseable
            json.loads(value)
            return value
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON output")


# Define a separate state manager class
class AgentStateManager:
    """
    StateManager concepts:

    Conditions:
            Purpose: Conditions are meant to be checks that either allow or prevent a transition from occurring.
                    They should be pure functions that do not cause side effects.
            Return Type: Conditions should return a boolean value. True allows the transition, and false prevents it.
    Actions:
            Purpose: Actions (like before, after, prepare, etc.) are intended to perform operations or
                      side effects, such as setting values, updating a database, loading configurations, etc.
            Handling Side Effects: Actions might include operations that could fail (e.g., file loading,
                       network requests), and these should be managed within action methods rather than conditions.

        All the power of transitions are in the automated "hooks" of add_transition:
            self.machine.add_transition(
                            trigger='start_process',        <class method that will invoke this>
                            source='initial',               <state that we are moving from>
                            dest='processing',              <state that we are moving to>
                            prepare=self.prepare_process,   <runs before the conditions are attempted>
                            before=self.before_starting,    <runs before the transition but after conditions>
                            conditions=self.check_resources,<checks to make sure that transition is safe>
                            after=self.after_starting,      <runs after the transition>
                            on_error=self.handle_error)     <error handle>
    """

    def __init__(self, agent):
        self.agent = agent
        self.machine = Machine(
            model=self,
            states=["INITIAL", "INITIALISED", "LOADED", "RUNNING"],
            initial="INITIAL",
        )
        self.machine.add_transition(
            trigger="initialise",
            source="INITIAL",
            dest="INITIALISED",
            conditions=["validate_input"],
            before="load_agent_details",
        )
        self.machine.add_transition(
            trigger="load",
            source="INITIALISED",
            dest="LOADED",
            conditions=["validate_input_files"],
            after="generate_thread",
        )
        self.machine.add_transition(
            trigger="run", source="LOADED", dest="RUNNING", conditions=[], after=""
        )
        # how to store necessary information in the stateManager?
        self.client = None

    def validate_input(self, client, file_handler, qm, agent_key):
        try:
            validated_input = AgentInitModel(
                client=client, file_handler=file_handler, agent_type=agent_key, qm=qm
            )
            print("Input validated successfully.")
            self.client = client
            return True
        except ValidationError as e:
            print(f"Validation error: {e}")
            return False

    def validate_input_files(self, input_files, prompt, agent_id):
        dprint(
            f"Validating input files {input_files} with agent_id {agent_id} and client = {self.client}"
        )
        try:
            validated_input = AgentInputFilesModel(
                client=self.client,
                input_files=input_files,
                agent_id=agent_id,
                prompt=prompt,
            )
            print("Input validated successfully.")
            return True
        except ValidationError as e:
            print(f"Validation error: {e}")
            return False

    def generate_thread(self, input_files, prompt, agent_id):
        dprint("Generating thread")
        self.agent.generate_thread(prompt)

    def load_agent_details(self, client, file_handler, qm, agent_key):
        """
        Load and validate agent configuration details.
        """
        try:
            agent_config = AgentConfigs().get_agent_details(agent_key)
            self.agent.setup_agent(
                client,
                file_handler,
                qm,
                agent_key,
                agent_config["id"],
                agent_config["description"],
                agent_config.get("prompt", ""),
                agent_config.get("output_schema", None),
            )
            print("Agent details loaded and validated, transitioning to INITIALISED.")
        except ValueError as e:
            print(f"Failed to load agent details: {e}")
