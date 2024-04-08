
import json
import time
import sys

#from filehandler import retrieve_from_file_or_text
from quality_manager import QualityManager
from debug import dprint
class Agent:
    def __init__(self, client, filehandler, agent_key=None, requirements=None):
        self.config = self.load_config("known_agents.json")
        self.known_agents = self.config['known_agents']
        self.client = client
        self.qm = None
        self.qm_agent = None
        self.max_retries = 4
        self.filehandler = filehandler
        self.last_timestamp = 0
        if agent_key and agent_key in self.known_agents:
            self.agent_id = self.known_agents[agent_key]['id']
            self.description = self.known_agents[agent_key]['description']
            if self.known_agents[agent_key]['prompt']:
                self.prompt = self.known_agents[agent_key]['prompt']
            if self.known_agents[agent_key]['output_schema']:
                self.output_schema = self.known_agents[agent_key]['output_schema']
        else:
            # TODO when creating a nont-know assistant
            self.create_new_assistant(client)
        self.threads = []
        self.thread_details = {}  # notused yet: A dictionary to map threads to their details
        self.input_files = []
        self.requirements = requirements
        self.output_files = []
        self.response_file = ""
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

    def list_asst_files(self):
        asst_files = self.client.beta.assistants.files.list(
            assistant_id=self.agent_id
        )
        return asst_files

    def check_asst_files(self,file):
        asst_files = self.list_asst_files()
        dprint(f"Assistant files for agent {self.agent_id} ", asst_files)
        for asst_file in asst_files.data:
            if file == asst_file.id:
                dprint(f"Agent has {file} in file_ids already")
            return True
        dprint(f"Agent does not have {file} accessible in file_ids")
        return False

    def generate_runtime_prompt(self):
        placeholder_values = {
            "INPUT_FILES": self.input_files,
            "AGENT_RESPONSE": self.response_file,
            "AGENT_OUTPUT" : self.latest_output_file(),
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

    def latest_output_file(self):
        if self.output_files:
            return self.output_files[-1]
        else:
            return None

    def setup_run(self, input_files=None, qm=False, max_retries=4):
        self.max_retries = max_retries
        dprint(f"input files: {input_files}")
        thread = self.create_thread(self.prompt, input_files)
        dprint(f"Running agent with prompt {self.prompt}")
        dprint(f"Thread input files: {self.input_files}")
        # build a QM instance
        self.threads.append(thread)
        if qm:
            self.qm_agent = Agent(self.client, self.filehandler, "qm_agent", requirements=self.output_schema)
            self.qm = QualityManager(self, self.qm_agent)
            # remove any assistant files already on the Agent. These are uploaded during execution and will
            # persist between runs
            self.qm_agent.delete_asst_files()
        return

    def setup_qm_run(self, agent_response_file, agent_output_file, max_retries=4):
        self.max_retries = max_retries
        dprint(f"Agent response file {agent_response_file} and output file {agent_output_file}")
        thread = self.create_qm_thread(agent_response_file, agent_output_file)
        # build a QM instance
        self.threads.append(thread)
        dprint(f"setup_run created a QM instance with run_agent:{self.qm_agent} ")

    def run_agent(self):
        # 1) run the agent and make both response and output available to other agents
        retrieve = self.run_and_retrieve_thread()
        output = self.retrieve_output()
        # TODO some duplication of effort - retrieve_and_create_asst_file is extracting a response
        asst_file = self.filehandler.retrieve_and_create_asst_file(
            self.client,
            self.agent_id,
            self.active_thread(),
            "agent_retrieval_for_asst_file",
        )
        if asst_file:
            self.output_files.append(asst_file)
            dprint(f"Output file = {output} now in self.output_files and returned as {self.latest_output_file()}")
        response = self.get_new_messages(self.active_thread())
        # append the output file list and replace the response file
        if response:
            self.response_file = response
            dprint(f"Response file = {response} now in self.response_file and returned as {self.response_file}")
        # 2) optionally run the QM if enabled
        agent_output_file = asst_file
        if self.qm:
            agent_output_file = self.qm.assess_run_quality(self.active_thread())
            if agent_output_file:
                return agent_output_file
        else:
            dprint("QM is not enabled")
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
            dprint(f"Message: {message}")
            if message.role == "assistant" and message.content[0].type == "text":
                dprint(message.content[0])
                dprint(message.content[0].text.value)
                response += message.content[0].text.value
        return response

    def get_new_messages(self, thread):
        # Fetch all messages from the thread
        messages = self.client.beta.threads.messages.list(thread_id=thread.id).data
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

    def add_message(self, thread_id, prompt, input_files=None):
        dprint(f"Adding message [{prompt}] to thread {thread_id}")
        if input_files:
            dprint(f"Adding input file(s): input_files")
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

    def qm_add_message(self, prompt, response, output ):
        dprint(f"Adding message {prompt} to thread {self.active_thread()}")
        dprint(f"Adding input file(s): input_files")
        file_ids = []
        if response:
            file_ids.append(response)
        if output:
            file_ids.append(output)
        self.client.beta.threads.messages.create(
            thread_id=self.active_thread().id,
            role="user",
            content=prompt,
            file_ids=file_ids
        )

    def retrieve_output_or_reissue(self, thread):
        client = self.client
        dprint(f" thread {thread}")
        afile = self.filehandler.retrieve_and_create_asst_file(self.client, self.agent_id, thread)
        dprint(f"file is {afile}")
        if afile:
            dprint(f"good file retrieved")
            return afile
        else:
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content="Please generate JSON data for processing by the agent team"
            )
            dprint("updated message to ask for output")
            response = self.run_and_retrieve_thread()
            afile = self.filehandler.retrieve_and_create_asst_file(self.client, self.agent_id, thread)
            return afile

    def upload_text_to_file(self, tag, text):
        local_file_path = self.filehandler.write_local_file(tag, text)
        dprint(local_file_path)
        agent_file = self.filehandler.create_asst_file_from_local(
            self.client, self.agent_id, local_file_path)
        self.append_input_files(agent_file)
        dprint(f"uploading ")
        # return self.filehandler.upload_text_to_file(self.client,text)
        return agent_file

    def create_asst_file_from_id(self, file):
        # file should be an already-uploaded file-ID that
        # just needs to be added to the assistant
        agent_file = self.filehandler.create_asst_file_from_id(
            self.client, self.agent_id, file)
        return agent_file

    def delete_asst_files(self):
        asst_files = self.list_asst_files()
        dprint(f"assistant files: {asst_files}")
        for asst_file in asst_files:
            dprint(f"Assistant file-id: {asst_file.id} ")
            try:
                self.client.beta.assistants.files.delete(
                    assistant_id=self.agent_id,
                    file_id=asst_file.id
                )
            except Exception as e:
                dprint(f"Assistant error deleting file-id: {asst_file}")

    def retrieve_output(self):
        afile = self.filehandler.retrieve_and_create_asst_file(self.client, self.agent_id, self.active_thread())
        if afile:
            dprint(f"good file retrieved")
            return afile
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
                if input_file not in self.input_files and input_file:
                    self.input_files.append(input_file)

    def create_qm_thread(self, agent_response, agent_output):
        if agent_response:
            self.append_input_files(agent_response)
            self.response_file = agent_response
        if agent_output:
            self.append_input_files(agent_output)

        dprint(f"input_files are now {self.input_files}")

        # now auto-generate the runtime prompt ready for uploading to thread
        self.generate_runtime_prompt()

        # Create the thread with the prompt and input file
        thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": self.prompt,
                    "file_ids": self.input_files,
                }
            ]
        )
        self.threads.append(thread)
        return thread

    def create_thread(self, prompt, input_files=None):
        # input files should be fileIDs already uploaded but will need adding to local list
        if input_files:
            dprint(f"Input files detected : {input_files}")
            self.append_input_files(input_files)

        # TODO safety check all input files already exist on the
        dprint(f"self.input_files = {self.input_files}")

        # now auto-generate the runtime prompt ready for uploading to thread

        self.generate_runtime_prompt()

        # Create the thread with the prompt and input file
        thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": f"Read the file(s) {self.input_files}. {self.prompt}",
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


