from debug import dprint
import time
from pydantic import BaseModel, Field, validator
import time
from typing import Optional, List, Any
from import_files import InputFilesModel, AsstFilesModel
import uuid
from datetime import datetime, timedelta
from agent_configs import AgentConfigs


class AgentThread:
    """A thread of execution and management of one Agent"""

    def __init__(self, connector, agent_id, initial_prompt, file_handler):
        self.connector = connector
        self.client = connector.client
        self.agent_id = agent_id
        self.id = uuid.uuid4()  # Generates a unique identifier
        self.initial_prompt = initial_prompt
        self.state = "inactive"
        self.run_prompt = None
        self.runobjs = []
        self.returnobjs = []
        self.file_handler = file_handler
        self.thread = self.client.beta.threads.create()
        dprint(f"created initial thread {self.thread.id}")
        # self.last_timestamp = 0
        self.full_response = []

    def runs_made(self):
        return len(self.runobjs)

    def new_runobj(
        self,
        parent,
        retrieval_limit,
        input_files,
        agent_response,
        agent_output,
        agent_requirements,
        output_schema,
        agent_schema_errors,
        prompt=None,
        file_paths=None,
    ):
        dprint("creating new run")
        file_ids = []

        connector = parent.connector

        if input_files:
            file_ids.extend(input_files)

        if agent_response:
            print("agent_response to pass to run is detected")
            file_ids.append(agent_response)

        if agent_output:
            print("agent_output to pass to run is detected")
            file_ids.append(agent_output)

        if file_ids:
            my_updated_assistant = connector.upload_file_ids(agent_id=self.agent_id, file_ids=file_ids)

        run = RunObj(
            parent=parent, input_files=input_files, retrieval_limit=retrieval_limit
        )
        dprint(f"created new run")
        if prompt is None:
            prompt = self.initial_prompt
        dprint(f"creating new run prompt")

        run_prompt = run.generate_runtime_prompt(
            prompt,
            input_files=input_files,
            agent_response=agent_response,
            agent_output=agent_output,
            agent_requirements=agent_requirements,
            agent_schema_errors=agent_schema_errors,
            file_paths=file_paths,
        )
        dprint(f"created new run prompt")
        self.add_message(run_prompt)
        run.create_run()
        dprint(f"created new run")
        self.runobjs.append(run)
        dprint(f"appended runobj")

        return run

    def get_output(self):
        # The only valid output is the one that specifically relates to the last run
        if self.runobjs[-1].ran:
            rtuple = self.returnobjs[-1]
            return rtuple
        else:
            dprint("Error: The runobj did not run yet")
        return

    def retrieve(self, qm_id=None):
        """retrieves an existing run via the runobj
        and extracts the response, output and inline json. If Qm then it also
        sets the completion structure """
        self.runobjs[-1].retrieve()
        # switch the runobj to ran state, can't be modified or reran
        self.runobjs[-1].ran = True
        try:
            agent_output = self.connector.agent_retrieve(self.agent_id, self.thread)
            dprint(f"structured output is #{agent_output}")
        except Exception as e:
            dprint(f"Error retrieving output: {e}")
            agent_output = None
        dprint(f"structured_output: {agent_output}")
        if agent_output is None:
            dprint(f"No JSON in responses, need to reissue")
            self.output_dict = None
            self.returnobjs.append(None)
            return None

        self.output_dict = {
            "run_obj": self.runobjs[-1],
            "response_file": agent_output["response_file"],
            "output_file": agent_output["output_file"],
            "inline_dict": agent_output["inline_dict"],
        }
        self.returnobjs.append(self.output_dict)
        self.full_response.append(agent_output["response_file"])
        #dprint(f"output dict is {self.output_dict}, returning it")
        #print(f"output dict is {self.output_dict}, returning it")
        return self.output_dict

    def add_message(self, instructions, input_files=None):
        """
        add a message {prompt} to the thread
        """
        # TODO move into connector

        self.client.beta.threads.messages.create(
            thread_id=self.thread.id, role="user", content=instructions
        )

class RunObj(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    parent: Any
#    input_files: Optional[List[str]] = None
    input_files: Any
    model_run: Optional[str] = None
    retrieval_limit: int = Field(default=3, gt=0)
    run_prompt: Optional[str] = None
    ran: bool = Field(default=False)

    # @validator('input_files', pre=True)
    # def check_input_files(cls, v):
    #     t = AsstFilesModel(input_files=v)
    #     return v

    @validator("model_run", always=True)
    def validate_model_run(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("model_run must be a valid run identifier string.")
        return v

    @validator("run_prompt", always=True)
    def validate_run_prompt(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("run_prompt must be a string.")
        return v

    def set_model_run(self, run_details: dict):
        self.model_run = run_details  # Validation triggered here

    def set_run_prompt(self, prompt: str):
        self.run_prompt = prompt  # Validation triggered here

    def create_run(self):
        if self.model_run is None:
            client = self.parent.client
            # TODO replace with connector.run
            model_run = client.beta.threads.runs.create(
                thread_id=self.parent.thread.id,
                assistant_id=self.parent.agent_id,
                # model="gpt-4-turbo-preview",
                tools=[{"type": "code_interpreter"}],
            )
            self.set_model_run(model_run)
            print(f"Created run {self.model_run.id}")
        else:
            print("Run already created.")

    def retrieve(self):
        if not self.ran:
            self.retrieve_run()
            self.ran = True
        else:
            print("Run has already been executed; RunObj cannot be reused.")

    def retrieve_run(self):
        if self.model_run is None:
            print("No run to retrieve.")
            return None
        start_time = time.time()
        retrieve = self.retrieve_run_and_wait(self.model_run.id)
        end_time = time.time()
        print("Retrieve time: " + str(end_time - start_time))
        return retrieve

    def retrieve_run_and_wait(self, run_id):
        retries = 0
        client = self.parent.client
        thread_id = self.parent.thread.id
        while retries < self.retrieval_limit:
            try:
                retrieve = self.parent.connector.retrieve(
                    thread_id=thread_id, run_id=run_id
                )
                # retrieve = client.beta.threads.runs.retrieve(
                #     thread_id=thread_id, run_id=run_id
                # )
                dprint(f"Assistant status: {retrieve.status}")
                if retrieve.status == "completed":
                    return retrieve
                elif retrieve.status in ["failed", "incomplete", "expired"]:
                    dprint(f"Run {run_id} failed.")
                    return "Run {run_id} failed."
                time.sleep(5)
            except Exception as e:
                print(f"Error retrieving run {run_id} for thread {thread_id}: {e}")
                retries += 1
                time.sleep(5)
        print(f"Run {run_id} did not complete after {self.retrieval_limit} queries.")
        return None

    def generate_runtime_prompt(
        self,
        prompt,
        input_files=None,
        agent_response=None,
        agent_output=None,
        agent_requirements=None,
        agent_schema_errors=None,
        file_paths=None,
    ):
        """
        Generate a prompt using runtime information. Note placeholder values
        appear in the prompt in known_agents.json in the "prompt" field.
        """

        if file_paths is None:
            doc_path = ""
        else:
            doc_path = input_files[0]
        placeholder_values = {
            "INPUT_FILES": input_files,
            "AGENT_RESPONSE": agent_response,
            "AGENT_OUTPUT": agent_output,
            "AGENT_REQUIREMENTS": agent_requirements,
            "AGENT_SCHEMA_ERRORS": agent_schema_errors,
            "DOC_NAME": doc_path,
        }
        # Prepare the prompt by replacing placeholders with actual runtime values
        for placeholder, value in placeholder_values.items():
            # Convert list to string if necessary
            if isinstance(value, list):
                value_str = ", ".join(
                    map(str, value)
                )  # Ensure all elements are converted to strings
            else:
                value_str = str(value)
            prompt = prompt.replace(f"{{{placeholder}}}", value_str)
        self.set_run_prompt(prompt)
        return prompt

    class Config:
        arbitrary_types_allowed = True  # Allows 'Any' and other arbitrary types


# def clone_assistant(client, source_assistant_id):
#     # Retrieve the list of assistants
#     # TODO replace with connector.clone
#     my_assistants = client.beta.assistants.list(order="desc", limit=100).data
#     # Find the assistant by IDg
#     source_assistant = None
#     for assistant in my_assistants:
#         if assistant.id == source_assistant_id:
#             source_assistant = assistant
#             break
#
#     if source_assistant is None:
#         print("Assistant not found.")
#         return
#
#     # Prepare the payload for creating a new assistant
#     # Copy all relevant fields except the ID and created_at
#     assistant_data = {
#         "name": "Adrian Cloned Agent",
#         "description": source_assistant.description,
#         "model": "gpt-4o",  #'gpt-3.5-turbo', #"gpt-4o",
#         "instructions": source_assistant.instructions,
#         "tools": [{"type": "code_interpreter"}],
#         "temperature": source_assistant.temperature,
#         "top_p": source_assistant.top_p,
#     }
#     # model = "gpt-4o",
#     # tools = [{"type": "code_interpreter"}]
#     # TODO there is a bug in assistants API, how to set temperature?
#     # modify_data = {
#     #     "temperature": 0.5,
#     #     "top_p": 1.0,
#     #     "response_format": source_assistant.response_format
#     # }
#     # Create a new assistant with the copied data
#     new_assistant = client.beta.assistants.create(**assistant_data)
#     # # copy any uploaded files to the new assistant
#     #
#     # my_updated_assistant = client.beta.assistants.update(
#     #     new_assistant.id,
#     #     tool_resources={
#     #         "code_interpreter": {
#     #             "file_ids": source_assistant.tool_resources.code_interpreter.file_ids
#     #         }
#     #     }
#     # )    # my_updated_assistant = client.beta.assistants.update(**modify_data, id=new_assistant.id)
#     return new_assistant


def delete_existing_assistant_files(client, agent_id):
    """Manage existing assistant files in OpenAI"""
    asst_files = client.beta.assistants.files.list(
        assistant_id=agent_id,
    )
    dprint(f"Assistant files: {asst_files}")
    for asst_file in asst_files.data:
        try:
            client.beta.assistants.files.delete(
                assistant_id=agent_id, file_id=asst_file.id
            )
            dprint(f"Deleted Assistant file")
        except Exception as e:
            dprint(f"Error deleting Assistant file {e}")


def delete_oldest_assistant_files(client, agent_id, max_files=6):
    """Manage existing assistant files by keeping only the latest 'max_files'."""
    dprint("delete_oldest_assistant_files")
    try:
        # Retrieve list of assistant files
        asst_files = client.beta.assistants.files.list(
            assistant_id=agent_id,
        )
        dprint(f"Total assistant files: {len(asst_files.data)} on {agent_id}")
        # Check if the number of files exceeds the maximum allowed
        if len(asst_files.data) > max_files:
            sorted_files = sorted(asst_files.data, key=lambda x: x.created_at)
            files_to_delete = sorted_files[: len(asst_files.data) - max_files]

            # Delete the oldest files
            for asst_file in files_to_delete:
                client.beta.assistants.files.delete(
                    assistant_id=agent_id, file_id=asst_file.id
                )
                dprint(f"Deleted Assistant file-id: {asst_file.id}")
    except Exception as e:
        dprint(f"Error managing Assistant files: {e}")


def delete_files_older_than_x_days(client, days_old=30):
    # Calculate the cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_old)

    try:
        # List all files
        files = client.files.list()

        for file in files.data:
            # The created_at field is in ISO 8601 format
            file_creation_date = datetime.fromtimestamp(file.created_at)
            if file_creation_date < cutoff_date:
                # Delete file
                client.files.delete(file_id=file.id)

                print(f"Deleted file: {file.id}, created at {file.created_at}")
        print("Deletion process completed.")
    except Exception as e:
        print(f"An error occurred: {e}")


def delete_files_less_than_1_hour(client):
    # Calculate the cutoff date
    cutoff_date = datetime.now() - timedelta(hours=1)

    try:
        # List all files
        files = client.files.list()
        deleted = 0
        for file in files.data:
            # The created_at field is in ISO 8601 format
            file_creation_date = datetime.fromtimestamp(file.created_at)
            if file_creation_date > cutoff_date:
                # Delete file
                client.files.delete(file_id=file.id)
                deleted += 1
                print(f"Deleted file: {file.id}, created at {file.created_at}")
        print("Deletion process completed.")
        return deleted
    except Exception as e:
        print(f"An error occurred: {e}")


def delete_not_known_assistants(client):
    config_manager = AgentConfigs()
    known_agent_ids = config_manager.get_all_known_agent_ids()
    dprint(f"known agents are {known_agent_ids}")
    try:
        # List all assistants
        assistants = client.beta.assistants.list(limit=100)
        print(f"Number of assistants is {len(assistants.data)}")

        for assistant in assistants.data:
            # Check if the assistant's ID is not in the list of known agent IDs and name is "Cloned Agent"
            if assistant.id not in known_agent_ids:
                print(f"Assistant with name {assistant.name} will be deleted.")
                client.beta.assistants.delete(assistant_id=assistant.id)
                print(
                    f"Deleted assistant: {assistant.id}, created at {assistant.created_at}"
                )

        print("Deletion process completed.")
    except Exception as e:
        print(f"An error occurred: {e}")


def delete_assistants_clones(client):

    tag = "Cloned"
    try:
        # List all files
        assistants = client.beta.assistants.list(limit=100)
        dprint(f"Number of assistants is {len(assistants.data)}")
        for ass in assistants.data:
            if ass.name == "Adrian Cloned Agent":
                dprint(f"Assistant with name {ass.name}")
                client.beta.assistants.delete(assistant_id=ass.id)
                print(f"Deleted ass: {ass.id}, created at {ass.created_at}")
        print("Deletion process completed.")
    except Exception as e:
        print(f"An error occurred: {e}")
    assistants = client.beta.assistants.list(limit=100)
    dprint(f"Number of assistants is now {len(assistants.data)}")


def delete_all_uploaded_files(client):
    # Calculate the cutoff date
    try:
        # List all files
        files = client.files.list()
        dprint(f"found {len(files.data)} files")
        deleted = 0
        for file in files.data:
            # The created_at field is in ISO 8601 format
            # Delete file
            client.files.delete(file_id=file.id)
            deleted += 1
            if deleted % 20 == 0:
                dprint(f"Deleted {deleted} files")
        files = client.files.list()
        print(
            f"Deletion process completed and deleted {deleted} files and now there are {len(files.data)}"
        )
        return deleted
    except Exception as e:
        print(f"An error occurred in file deletion: {e}")


def delete_assistants_less_than_x_days(client, days_old=100):
    # Calculate the cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_old)

    try:
        # List all files
        assistants = client.beta.assistants.list()
        for ass in assistants:
            print(f"found the assistant {ass}")
            ass_creation_date = datetime.fromtimestamp(ass.created_at)
            if ass_creation_date > cutoff_date:
                # Delete file
                client.beta.assistants.delete(assistant_id=ass.id)
                print(f"Deleted ass: {ass.id}, created at {ass.created_at}")
        print("Deletion process completed.")
    except Exception as e:
        print(f"An error occurred: {e}")
