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


    def new_runobj(self,parent,input_files,retrieval_limit,requirements,output_schema):
        dprint(f"Creating new runobj with inputs {input_files}")
        run = RunObj(
            parent=parent,
            input_files=input_files,
            retrieval_limit=retrieval_limit)
        dprint(f"New run object created {run}")
        prompt = run.generate_runtime_prompt(
            self.initial_prompt,
            input_files=input_files,
            input_response=None,
            agent_output=output_schema,
            requirements=requirements)
        dprint(f"Generated new runtime information for {run}")
        self.add_message(prompt)
        dprint(f"Added message {run.run_prompt}")
        run.create_run()
        self.runobjs.append(run)
        dprint(f"appended the runobjs list so that the end item is {self.runobjs[-1].id}")
        return run

    def get_output(self):
        # The only valid output is the one that specifically relates to the last
        # RubObj (which could be empty)
        if self.runobjs[-1].ran :
            rtuple = self.returnobjs[-1]
            dprint(f"Agent did run and returned tuple {rtuple}")
            return rtuple
        else:
            dprint("Error: The runobj did not run yet")
        return



    def retrieve(self, debug=False):
        if debug:
            debug_string = '{"debug": "This is a debug entry"}\n'  # JSONL format requires new lines
            with open(f"debug_{self.id}.json", "w") as file:
                file.write(debug_string)
            with open(f"debug_{self.id}.json", "rb") as local_file:
                uploaded_file = self.client.files.create(
                    file=local_file,
                    purpose="assistants"
                )
                asst_file = self.client.beta.assistants.files.create(
                    assistant_id=self.agent_id,
                    file_id=uploaded_file.id
                )
            self.output_dict = {
                'run_obj': self.runobjs[-1],
                'response_file': asst_file,
                'output_file': asst_file
            }
            return self.output_dict
        else:
            dprint(f"The end runobjs item is {self.runobjs[-1]}")
            self.runobjs[-1].retrieve()
            # switch the runobj to ran state, can't be modified or reran
            self.runobjs[-1].ran = True
            asst_file_agent_output = self.file_handler.retrieve_and_create_asst_file(
                self.client,
                self.agent_id,
                self.thread,
                f"output_file_Run{self.runobjs[-1].id}",
            )
            response = self.get_new_messages()
            # response_asst_file = self.file_handler.txt_to_asst_file(
            #     self.client,
            #     response,
            #     f"response_runobj{self.runobjs[-1].id}",
            #     self.agent_id)
            # dprint(f"response from Agent = {response}")
            structured_output = self.file_handler.retrieve_direct_agent_content(
                self.client,
                self.agent_id,
                self.thread.id,
                response,
                asst_file_agent_output,
                f"_runobj{self.runobjs[-1].id}")
            dprint(f"structured output from Agent = {structured_output}")
            dprint(f"Updating returnobjs with {response, asst_file_agent_output}")
            self.output_dict = {
                'run_obj': self.runobjs[-1],
                'response_file': response,
                'output_file': asst_file_agent_output,
                'structured_output': structured_output
            }
            self.returnobjs.append(self.output_dict)
        return self.output_dict


    def generate_thread(self):
        if self.run_prompt is None:
            print("Error: Running agent with empty Prompt")
        prompt = self.run_prompt
        self.thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )
        dprint(f"generated thread {self.thread.id}")
        return

    def add_message(self, instructions, input_files=None):
        """
            add a message {prompt} to the thread
        """
        dprint(f"Adding message [{instructions}] to thread {self.thread.id}")
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=instructions
        )
        dprint(f"Added message [{instructions}] to thread {self.thread.id}")

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

    def retrieve_direct_agent_content(self, str=None, tag=""):
        """
            given an asst-file-id, return the file content as a dictionary
        """
        if str:
            return self.file_handler.retrieve_direct_agent_content(self.client, self.agent_id, self.active_thread(),
                                                   str, self.active_output_file(), "")
        else:
            # TODO need to pass string instead of response file
            dprint(f"retrieve needs fixing")
            return self.file_handler.retrieve_direct_agent_content( self.client, self.agent_id, self.active_thread(),
                                                               self.response_file, self.active_output_file(), "")


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

    def generate_runtime_prompt(self,prompt,input_files=None,input_response=None,agent_output=None, requirements=None):
        """
            Generate a prompt using runtime information. Note placeholder values
            appear in the prompt in known_agents.json in the "prompt" field.
        """
        placeholder_values = {
            "INPUT_FILES": input_files,
            "AGENT_RESPONSE": input_response,
            "AGENT_OUTPUT" : agent_output,
            "AGENT_REQUIREMENTS": requirements,
        }
        # Prepare the prompt by replacing placeholders with actual runtime values
        dprint("placeholder values:", placeholder_values)
        for placeholder, value in placeholder_values.items():
            # Convert list to string if necessary
            if isinstance(value, list):
                value_str = ', '.join(map(str, value))  # Ensure all elements are converted to strings
            else:
                value_str = str(value)
            prompt = prompt.replace(f"{{{placeholder}}}", value_str)
        dprint(f"End self-prompt is {prompt}")
        self.set_run_prompt(prompt)
        return prompt
    class Config:
        arbitrary_types_allowed = True  # Allows 'Any' and other arbitrary types
