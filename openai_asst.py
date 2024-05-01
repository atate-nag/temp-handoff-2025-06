from debug import dprint
import time
from pydantic import BaseModel, Field, validator
import time
from typing import Optional, List, Any
from import_files import InputFilesModel, AsstFilesModel
import uuid

class AgentThread():

    """ A thread of execution and management of one Agent """
    def __init__(self, client, agent_id, initial_prompt, file_handler):
        self.client = client
        self.agent_id = agent_id
        self.id = uuid.uuid4()  # Generates a unique identifier
        self.initial_prompt = initial_prompt
        self.state = 'inactive'
        self.run_prompt = None
        self.runobjs = []
        self.returnobjs = []
        self.file_handler = file_handler
        self.thread = self.client.beta.threads.create()
        dprint(f"created initial thread {self.thread.id}")
        self.last_timestamp = 0


    def new_runobj(self,
                   parent,
                   retrieval_limit,
                   input_files,
                   agent_response,
                   agent_output,
                   agent_requirements,
                   output_schema,
                   agent_schema_errors,
                   prompt=None):
        run = RunObj(
            parent=parent,
            input_files=input_files,
            retrieval_limit=retrieval_limit)
        if prompt is None:
            prompt = self.initial_prompt
        run_prompt = run.generate_runtime_prompt(
            prompt,
            input_files=input_files,
            agent_response=agent_response,
            agent_output=agent_output,
            agent_requirements=agent_requirements,
            agent_schema_errors=agent_schema_errors)
        self.add_message(run_prompt)
        run.create_run()
        self.runobjs.append(run)
        return run

    def get_output(self):
        # The only valid output is the one that specifically relates to the last
        if self.runobjs[-1].ran :
            rtuple = self.returnobjs[-1]
            return rtuple
        else:
            dprint("Error: The runobj did not run yet")
        return

    def retrieve(self, qm_id=None):
        """ retrieves an existing run via the runobj
            and extracts the response, output and json """
        self.runobjs[-1].retrieve()
        # switch the runobj to ran state, can't be modified or reran
        self.runobjs[-1].ran = True
        # should we retrieve from qm_id or agent_id?
        if qm_id:
            target_id = qm_id
        else:
            target_id = self.agent_id
        asst_file_agent_output = self.file_handler.retrieve_output_file_id(
            self.client,
            self.agent_id,
            self.thread,
            target_id,
            f"output_file_Run{self.runobjs[-1].id}",
        )
        agent_response = self.get_new_messages()
        asst_file_response = self.file_handler.txt_to_asst_file(
            self.client,
            agent_response,
            "agent_response",
            target_id)
        structured_output = self.file_handler.retrieve_direct_agent_content(
            self.client,
            self.agent_id,
            agent_response,
            asst_file_agent_output,
            f"_runobj{self.runobjs[-1].id}")
        if structured_output is None:
            dprint(f"No JSON in responses, need to reissue")
            self.output_dict = None
            self.returnobjs.append(None)
            return None
        # TODO structured_output could be too large to be passed in a dict and
        #  should be a new assistant_file ?
        self.output_dict = {
            'run_obj': self.runobjs[-1],
            'response_file': asst_file_response.id,
            'output_file': asst_file_agent_output,
            'structured_output': structured_output
        }
        self.returnobjs.append(self.output_dict)
        return self.output_dict

    def add_message(self, instructions, input_files=None):
        """
            add a message {prompt} to the thread
        """
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=instructions
        )

    def get_new_messages(self):
        """
            just return the latest messages, i.e the last response
        """
        # Fetch all messages from the thread
        messages = self.client.beta.threads.messages.list(thread_id=self.thread.id).data
        # Sort the messages by the created_at timestamp just in case they are not in order
        messages.sort(key=lambda msg: msg.created_at)
        # Gather new messages
        new_messages = [msg for msg in messages if msg.created_at > self.last_timestamp]
        response = ""
        for message in new_messages:
            if message.role == "assistant" and message.content[0].type == "text":
                response += message.content[0].text.value
        # Update the last timestamp
        if new_messages:
            self.last_timestamp = new_messages[-1].created_at
        return response

class RunObj(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    parent: Any
    input_files: Optional[List[str]] = None
    openai_run: Optional[str] = None
    retrieval_limit: int = Field(default=3, gt=0)
    run_prompt: Optional[str] = None
    ran: bool = Field(default=False)

    # @validator('input_files', pre=True)
    # def check_input_files(cls, v):
    #     t = AsstFilesModel(input_files=v)
    #     return v

    @validator('openai_run', always=True)
    def validate_openai_run(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("openai_run must be a valid run identifier string.")
        return v

    @validator('run_prompt', always=True)
    def validate_run_prompt(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("run_prompt must be a string.")
        return v

    def set_openai_run(self, run_details: dict):
        self.openai_run = run_details  # Validation triggered here

    def set_run_prompt(self, prompt: str):
        self.run_prompt = prompt  # Validation triggered here

    def create_run(self):
        if self.openai_run is None:
            client = self.parent.client
            openai_run = client.beta.threads.runs.create(
                thread_id=self.parent.thread.id,
                assistant_id=self.parent.agent_id,
                model="gpt-4-turbo-preview",
                tools=[{"type": "code_interpreter"}],
            )
            self.set_openai_run(openai_run)
            print(f"Created run {self.openai_run}")
        else:
            print("Run already created.")


    def retrieve(self):
        print(f"Attempting to run: {self.openai_run}")
        if not self.ran:
            self.retrieve_run()
            self.ran = True
        else:
            print("Run has already been executed; RunObj cannot be reused.")

    def retrieve_run(self):
        if self.openai_run is None:
            print("No run to retrieve.")
            return None
        start_time = time.time()
        retrieve = self.retrieve_run_and_wait(self.openai_run.id)
        end_time = time.time()
        print("Retrieve time: " + str(end_time - start_time))
        return retrieve

    def retrieve_run_and_wait(self, run_id):
        retries = 0
        client = self.parent.client
        thread_id = self.parent.thread.id
        while retries < self.retrieval_limit:
            try:
                retrieve = client.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run_id
                )
                print(f"Assistant status: {retrieve.status}")
                if retrieve.status == "completed":
                    return retrieve
                elif retrieve.status in ["failed", "expired"]:
                    print(f"Run {run_id} failed.")
                    return None
                time.sleep(5)
            except Exception as e:
                print(f"Error retrieving run {run_id} for thread {thread_id}: {e}")
                retries += 1
                time.sleep(5)
        print(f"Run {run_id} did not complete after {self.retrieval_limit} queries.")
        return None

    def generate_runtime_prompt(self, prompt,input_files=None, agent_response=None,agent_output=None,
                                agent_requirements=None, agent_schema_errors=None):
        """
            Generate a prompt using runtime information. Note placeholder values
            appear in the prompt in known_agents.json in the "prompt" field.
        """
        placeholder_values = {
            "INPUT_FILES": input_files,
            "AGENT_RESPONSE": agent_response,
            "AGENT_OUTPUT" : agent_output,
            "AGENT_REQUIREMENTS": agent_requirements,
            "AGENT_SCHEMA_ERRORS": agent_schema_errors
        }
        # Prepare the prompt by replacing placeholders with actual runtime values
        for placeholder, value in placeholder_values.items():
            # Convert list to string if necessary
            if isinstance(value, list):
                value_str = ', '.join(map(str, value))  # Ensure all elements are converted to strings
            else:
                value_str = str(value)
            prompt = prompt.replace(f"{{{placeholder}}}", value_str)
        self.set_run_prompt(prompt)
        return prompt
    class Config:
        arbitrary_types_allowed = True  # Allows 'Any' and other arbitrary types


def clone_assistant(client, source_assistant_id):
    # Retrieve the list of assistants
    my_assistants = client.beta.assistants.list(order="desc",limit=100).data
    # Find the assistant by IDg
    source_assistant = None
    for assistant in my_assistants:
        if assistant.id == source_assistant_id:
            source_assistant = assistant
            break

    if source_assistant is None:
        print("Assistant not found.")
        return

    # Prepare the payload for creating a new assistant
    # Copy all relevant fields except the ID and created_at
    assistant_data = {
        "name": "Cloned Agent",
        "description": source_assistant.description,
        "model": source_assistant.model,
        "instructions": source_assistant.instructions,
        "tools": source_assistant.tools,
       # "metadata": source_assistant.metadata,
       #"top_p": source_assistant.top_p,
       # "temperature": source_assistant.temperature,
       # "response_format": source_assistant.response_format
    }

    # Create a new assistant with the copied data
    new_assistant = client.beta.assistants.create(**assistant_data)
    return new_assistant