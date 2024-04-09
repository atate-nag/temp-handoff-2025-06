
import json
import time
import sys
import openai

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
        self.input_response = None
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
        dprint("deleting all the existing assistant files")
        self.delete_asst_files()
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
            assistant_id=self.agent_id,
            order="asc"
        )
        return asst_files

    def len_asst_files(self):
        return len(self.list_asst_files())



    def check_asst_files(self,file):
        asst_files = self.list_asst_files().data
        dprint(f"Assistant files for agent {self.agent_id} ", asst_files)
        for asst_file in asst_files:
            dprint(f"asst_file = {asst_file}")
            if file == asst_file.id:
                dprint(f"Agent has {file} in file_ids")
                return True
            else:
                dprint(f"{file} != {asst_file.id}")
        dprint(f"Agent does not have {file} accessible in file_ids")
        return False

    def generate_runtime_prompt(self):
        placeholder_values = {
            "INPUT_FILES": self.input_files,
            "AGENT_RESPONSE": self.input_response,
            "AGENT_OUTPUT" : self.latest_input_file(),
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

    def latest_input_file(self):
        if self.input_files:
            return self.input_files[-1]
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
        return

    def setup_qm_run(self, agent_response_file, agent_output_file, max_retries=4):
        self.max_retries = max_retries
        dprint(f"Agent response file {agent_response_file} and output file {agent_output_file}")
        thread = self.create_qm_thread(agent_response_file, agent_output_file)
        # build a QM instance
        self.threads.append(thread)
        dprint(f"setup_run created a QM instance with run_agent:{self.qm_agent} ")

    def run_agent(self):
        '''run the agent and make both response and output available to other agents'''
        response_asst_file, asst_file_agent_output = self.run_and_retrieve_response_and_output()
        if self.qm:
            agent_output_file = self.qm.quality_manage_agent(self.active_thread())
            if agent_output_file:
                content_dict = self.retrieve_direct_agent_content(
                    f"agent_output_retrieval")
                return content_dict
        else:
            dprint("QM is not enabled (usually means it is a QM agent itself)")
            content_dict = self.retrieve_direct_agent_content(
                f"agent_output_retrieval")
            if content_dict:
                return content_dict
            else:
                # did not get output, so reissue
                prompt = "Please generate JSON data with your output"
                dprint(f"Agent did not complete and will be informed: {prompt}")
                self.add_message(self.active_thread(), prompt)
                asst_file_agent_output = self.run_and_retrieve_output_file()
                if asst_file_agent_output:
                    return asst_file_agent_output
                else:
                    dprint("Error - QM agent didn't generate its own output")
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

    def run_and_retrieve_output_file(self):
        retrieve = self.run_and_retrieve_thread()
        dprint(f"retrieve from Agent run = {retrieve}")
        asst_file_agent_output = self.filehandler.retrieve_and_create_asst_file(
            self.client,
            self.agent_id,
            self.active_thread(),
            "agent_retrieval_for_asst_file",
        )
        dprint(f"generated asst_file_agent_output = {asst_file_agent_output}")
        if asst_file_agent_output:
            self.output_files.append(asst_file_agent_output)
            dprint(
                f"Output file = {asst_file_agent_output} now in self.output_files and returned as "
                f"{self.latest_output_file()}")
            return asst_file_agent_output

    def run_and_retrieve_response_and_output(self):
        asst_file_output = self.run_and_retrieve_output_file()
        response = self.get_new_messages(self.active_thread())
        response_asst_file = self.filehandler.txt_to_asst_file(self.client, response, "latest_respose", self.agent_id)
        dprint(f"response from Agent = {response}")
        # append the output file list and replace the response file
        if response_asst_file:
            self.response_file = response_asst_file
            dprint(
                f"Response file = {response_asst_file} now in self.response_file and returned as {self.response_file}")
        return response_asst_file, asst_file_output

    def retrieve_run(self, run_id ):
        """
            from a run_id, retrieve a run and report status
        """
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
        """
            given an asst-file-id, return the file content
        """
        asst_file = self.client.beta.assistants.files.retrieve(
            assistant_id=self.agent_id,
            file_id=file
        )
        content = json.loads(self.client.files.retrieve_content(asst_file.id))
        return content

    def retrieve_direct_agent_content(self, tag=""):
        """
            given an asst-file-id, return the file content
        """
        return self.filehandler.retrieve_direct_agent_content( self.client, self.active_thread(), tag)


    def get_messages(self, thread):
        """
            extract and return all the messages on a thread
        """
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
        """
            just return the latest messages, i.e the last response
        """
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
        """
            add a message {prompt} to the thread
        """
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
        """
            add a message {prompt} to the thread
            TODO this may be defunct
        """
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

    # def retrieve_output_or_reissue(self, thread):
    #     client = self.client
    #     dprint(f" thread {thread}")
    #     afile = self.filehandler.retrieve_and_create_asst_file(self.client, self.agent_id, thread)
    #     dprint(f"file is {afile}")
    #     if afile:
    #         dprint(f"good file retrieved")
    #         return afile
    #     else:
    #         client.beta.threads.messages.create(
    #             thread_id=thread.id,
    #             role="user",
    #             content="Please generate JSON data for processing by the agent team"
    #         )
    #         dprint("updated message to ask for output")
    #         response = self.run_and_retrieve_thread()
    #         afile = self.filehandler.retrieve_and_create_asst_file(self.client, self.agent_id, thread)
    #         return afile

    # def upload_text_to_file(self, tag, text):
    #     local_file_path = self.filehandler.write_local_file(tag, text)
    #     dprint(local_file_path)
    #     agent_file = self.filehandler.create_asst_file_from_local(
    #         self.client, self.agent_id, local_file_path)
    #     self.append_input_files(agent_file)
    #     dprint(f"uploading ")
    #     # return self.filehandler.upload_text_to_file(self.client,text)
    #     return agent_file

    def create_asst_file_from_id(self, file):
        """
            when a file-id is already existing, attach it to an assistant
        """
        agent_file = self.filehandler.create_asst_file_from_id(
            self.client, self.agent_id, file)
        return agent_file

    def delete_asst_files(self):
        """
        delete all assistant files on this assistant
        TODO: a bug means that this will always throw an error
        """
        asst_files = self.list_asst_files()
        print(f"Assistant files: {asst_files}")
        for asst_file in asst_files:
            retries = 3
            while retries > 0:
                try:
                    print(f"Attempting to delete Assistant file-id: {asst_file.id}")
                    self.client.beta.assistants.files.delete(
                        assistant_id=self.agent_id,
                        file_id=asst_file.id
                    )
                    print(f"Successfully deleted Assistant file-id: {asst_file.id}")
                    break  # Exit the retry loop on success
                except openai.OpenAIError as e:
                    print(f"Error deleting file-id {asst_file.id}: {str(e)}")
                    if retries > 1:
                        print("Retrying...")
                        time.sleep(5)  # Wait a bit before retrying
                    else:
                        print("Final attempt failed.")
                retries -= 1

    # def retrieve_output(self):
    #     afile = self.filehandler.retrieve_and_create_asst_file(self.client, self.agent_id, self.active_thread())
    #     if afile:
    #         dprint(f"good file retrieved")
    #         return afile
    #     return None

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
        """
            Appends input_files to self.input_files
        """
        if isinstance(input_files, str):
            if input_files not in self.input_files:
                self.input_files.append(input_files)
        elif isinstance(input_files, list):
            for input_file in input_files:
                if input_file not in self.input_files and input_file:
                    self.input_files.append(input_file)

    def create_qm_thread(self, agent_response, agent_output):
        """
           adds a QM thread to the QM agent.
           TODO could be combined with the create_thread, it is just the inputs that differ really
        """
        if agent_response:
            self.append_input_files(self.create_asst_file_from_id(agent_output))
        if agent_output:
            self.input_response = self.create_asst_file_from_id(agent_response)
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
        """
            adds a new thread + message to an agent
        """
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
    # def set_agent_name(self, new_name):
    #     self.agent_name = new_name

    # def set_input_file_id(self, file_id):
    #     if file_id not in self.input_files:
    #         self.input_files.append(file_id)

    # Setter for role
    # def set_role(self, new_role):
    #     self.role = new_role

    # Setter for json_schema
    # def set_json_schema(self, new_json_schema):
    #     self.json_schema = new_json_schema

    # Setter for quality_criteria
    # def set_quality_criteria(self, new_quality_criteria):
    #     self.quality_criteria = new_quality_criteria


