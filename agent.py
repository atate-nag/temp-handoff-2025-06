
import json
import time
import sys

from filehandler import retrieve_from_file_or_text
from quality_manager import QualityManager
from debug import dprint
class Agent:
    def __init__(self, client, filehandler, agent_key=None, requirements=None):
        self.config = self.load_config("known_agents.json")
        self.known_agents = self.config['known_agents']
        self.client = client
        self.qm = None
        self.max_retries = 4
        self.filehandler = filehandler
        if agent_key and agent_key in self.known_agents:
            self.agent_id = self.known_agents[agent_key]['id']
            self.description = self.known_agents[agent_key]['description']
            if self.known_agents[agent_key]['prompt']:
                self.prompt = self.known_agents[agent_key]['prompt']
            if self.known_agents[agent_key]['output_schema']:
                self.output_schema = self.known_agents[agent_key]['output_schema']
        else:
            self.create_new_assistant(client)
        self.threads = []
        self.thread_details = {}  # notused yet: A dictionary to map threads to their details
        self.input_files = []
        self.requirements = requirements
    @staticmethod
    def load_config(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)

    def get_thread_details(self, thread_id):
        # Retrieve details for a specific thread by ID
        return self.thread_details.get(thread_id)

    def set_prompt(self, prompt):
        self.prompt = prompt

    def active_thread(self):
        return self.threads[-1]

    def set_input_files(self, input_files):
        for file in input_files:
            self.input_files.append(file)

    def generate_runtime_prompt(self):
        placeholder_values = {
            "INPUT_FILES": self.input_files,
            "AGENT_REQUIREMENTS": self.requirements,
        }
        # Prepare the prompt by replacing placeholders with actual runtime values
        dprint("placeholder values:", placeholder_values)
        prompt = self.prompt
        for placeholder, value in placeholder_values.items():
            # Convert list to string if necessary
            if isinstance(value, list):
                value_str = ', '.join(map(str, value))  # Ensure all elements are converted to strings
            else:
                value_str = str(value)
            prompt = prompt.replace(f"{{{placeholder}}}", value_str)
        self.prompt = prompt
        dprint(f"End self-prompt is {self.prompt}")
        return

    def setup_run(self, input_files=None, runtime_values=False, qm=True, max_retries=4):
        self.max_retries = max_retries
        dprint(f"input files: {input_files}")
        if input_files:
            thread = self.create_thread(self.prompt, input_files)
            dprint(f"generated thread: {thread}")
        else:
            thread = self.create_thread(self.prompt)
            dprint(f"generated thread: {thread}")
        dprint(f"Running agent with prompt {self.prompt}")
        dprint(f"Thread input files: {self.input_files}")
        # build a QM instance
        self.threads.append(thread)
        if qm:
            # create two types of QM agent - run and output
            qm_run_agent = Agent(self.client, self.filehandler, "qm_agent")
            qm_output_agent = Agent(self.client, self.filehandler, "qm_output_agent", requirements=self.output_schema)
            self.qm = QualityManager(self, qm_run_agent, qm_output_agent )
            dprint(f"setup_run created a QM instance with run_agent{self.qm.qm_run_agent} and "
                  f"{self.qm.qm_output_agent}")
        # create a real prompt from generic prompt that has unresolved parameters possibly in it
        return

    def run_agent(self):
        # 1) run the agent
        retrieve = self.run_and_retrieve_thread()
        # 2) optionally run the QM if enabled
        if self.qm:
            # 2.1 Check for output
            # agent_output_file = self.retrieve_output()
            # if agent_output_file:
            #     # 2.2 Check the output file for quality and quantity
            #     dprint("Check output consistency")
            #     validated_output_file = self.qm.assess_output_quality(self, agent_output_file, self.active_thread())
            #     if validated_output_file:
            #         dprint("Output file is validated by QM-Output")
            #         return validated_output_file
            # else:
            #     # 2.3 If no output then see what else was up with agent and repeat
            agent_output_file = self.qm.assess_run_quality(self.active_thread())
            if agent_output_file:
                dprint("output_file ")
                validated_output_file = self.qm.assess_output_quality(self, agent_output_file, self.active_thread())
                return validated_output_file
        else:
            dprint("QM is not enabled")
            # agent_output_file = self.retrieve_output()
            file = self.retrieve_output_or_reissue(self.active_thread())
            if file:
                return file
        dprint("No good file came from any agent interaction")
        return None

    def run_and_retrieve_thread(self):
        client = self.client
        run = client.beta.threads.runs.create(
            thread_id=self.active_thread().id,
            assistant_id=self.agent_id,
            model="gpt-4-turbo-preview",
            tools=[{"type": "code_interpreter"}],
        )
        start_time = time.time()
        retrieve = self.retrieve_run(run.id)
        end_time = time.time()
        dprint("Retrieve time: " + str(end_time - start_time))
        return retrieve

    def retrieve_run(self, run_id ):
        retries = 0
        client = self.client
        thread_id = self.active_thread().id
        while retries < self.max_retries:
            try:
                retrieve = client.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run_id
                )
                dprint(f" Assistant {self.description} status: {retrieve.status}")
                if retrieve.status == "completed":
                    return retrieve
                elif retrieve.status == "failed" or retrieve.status == "expired":
                    dprint(f"Run {run_id} failed.")
                    return None
                time.sleep(5)
            except Exception as e:
                dprint(f"Error retrieving run {run_id} for thread {thread_id}: {e}")
                retries += 1
                time.sleep(5)  # Wait before retrying
        dprint(f"Run {run_id} did not complete after {self.max_retries} retries.")
        return None

    def retrieve_file_content(self, file):
        content = json.loads(self.client.files.retrieve_content(file))
        return content
    def get_messages(self, thread):
        messages = self.client.beta.threads.messages.list(thread_id=thread.id).data
        response = ""
        for message in messages:
            if message.role == "assistant" and message.content[0].type == "text":
                dprint(message.content[0])
                dprint(message.content[0].text.value)
                response += message.content[0].text.value
        return response

    def add_message(self, thread_id, prompt, input_files=None):
        if input_files:
            self.append_input_files(input_files)
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=prompt,
                file_ids=self.input_files
            )
        else:
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=prompt
            )

    def retrieve_output_or_reissue(self, thread):
        client = self.client
        dprint(f" thread {thread}")
        file = retrieve_from_file_or_text(self.client,thread)
        dprint(f"file is {file}")
        if file:
            dprint(f"good file retrieved")
            return file
        else:
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content="Please write your required output to an external JSON file for processing by the agent team"
            )
            dprint("updated message to ask for output")
            response = self.run_and_retrieve_thread()
            file = retrieve_from_file_or_text(self.client,thread)
            return file

    def upload_text_to_file(self,text):
        return self.filehandler.upload_text_to_file(self.client,text)

    def retrieve_output(self):
        file = retrieve_from_file_or_text(self.client, self.active_thread())
        if file:
            dprint(f"good file retrieved")
            return file
        return None

    def create_new_assistant(self, name, description, instructions):
        assistant = self.client.beta.assistants.create(
            name=name,
            description=description,
            model="gpt-4-turbo-preview",
            tools="code_interpreter",
            instructions=instructions
        )
        # Assume the assistant creation response includes the assistant ID and description
        self.agent_id = assistant.id
        self.description = assistant.description


    def append_input_files(self, input_files):
        if isinstance(input_files, str):
            if input_files not in self.input_files:
                self.input_files.append(input_files)
            elif isinstance(input_files, list):
                for input_file in input_files:
                    if input_file not in self.input_files:
                        self.input_files.append(input_file)

    def create_thread(self, prompt, input_files=None):

        # input files should be fileIDs already uploaded but will need adding to local list
        if input_files:
            self.append_input_files(input_files)
            # if isinstance(input_files, str):
            #     if input_files not in self.input_files:
            #         self.input_files.append(input_files)
            #     elif isinstance(input_files, list):
            #         for input_file in input_files:
            #             if input_file not in self.input_files:
            #                 self.input_files.append(input_file)

        # TODO safety check all input files already exist on the
        dprint(f"self.input_files = {self.input_files}")

        # now auto-generate the runtime prompt ready for uploading to thread

        self.generate_runtime_prompt()

        # Create the thread with the prompt and input file
        thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": f"Read the file {self.input_files} using code_interpreter. {self.prompt}",
                    "file_ids": self.input_files,
                }
            ]
        )
        self.threads.append(thread)
        return thread

    # Setter for agent_name
    def set_agent_name(self, new_name):
        self.agent_name = new_name

    def set_input_file_id(self, file_id):
        if file_id not in self.input_files:
            self.input_files.append(file_id)

    # Setter for role
    def set_role(self, new_role):
        self.role = new_role

    # Setter for json_schema
    def set_json_schema(self, new_json_schema):
        self.json_schema = new_json_schema

    # Setter for quality_criteria
    def set_quality_criteria(self, new_quality_criteria):
        self.quality_criteria = new_quality_criteria


