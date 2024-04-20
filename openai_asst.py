from debug import dprint
import time
from pydantic import BaseModel, Field, validator
import time
from typing import Optional, List, Any


class AgentThread():

    """ A thread of execution and management of one Agent """
    def __init__(self, client, agent_id, initial_prompt):
        self.client = client
        self.agent_id = agent_id
        self.initial_prompt = initial_prompt
        self.state = 'inactive'
        self.run_prompt = None
        self.rubobj = None
        self.runobjs = []
        self.thread = self.client.beta.threads.create()
        dprint(f"created initial thread {self.thread.id}")

    def new_runobj(self,parent,input_files,retrieval_limit,requirements,output_schema):
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
        dprint(f"appended the runobjs list so that the end item is {self.runobjs[-1]}")
        return run

    # def retrieve(self):
    #     dprint(f"The end runobjs item is {self.runobjs[-1]}")
    #     self.runobjs[-1].run()

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


class RunObj(BaseModel):
    parent: Any
    input_files: Optional[List[str]] = None
    openai_run: Optional[str] = None
    retrieval_limit: int = Field(default=3, gt=0)
    run_prompt: Optional[str] = None
    ran: bool = Field(default=False)

    @validator('input_files', each_item=True, pre=True)
    def validate_file_ids(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("Each input file must be a string representing the file ID.")
        return v

    @validator('openai_run', always=True)
    def validate_openai_run(cls, v):
        if v is not None and not isinstance(v, ):
            raise ValueError("openai_run must be a dictionary.")
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
        print(f"Run {run_id} did not complete after {self.retrieval_limit} retries.")
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
