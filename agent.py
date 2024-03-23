
import json
import time
from file_retrieval import retrieve_from_file_or_text
from quality_manager import QualityManager
class Agent:
    def __init__(self, client, agent_key=None, prompt=None, description=None, name=None, instructions=None):
        self.config = self.load_config("known_agents.json")
        self.known_agents = self.config['known_agents']
        self.client = client
        self.qm = None
        self.max_retries = 3
        if agent_key and agent_key in self.known_agents:
            self.agent_id = self.known_agents[agent_key]['id']
            self.description = self.known_agents[agent_key]['description']
            if self.known_agents[agent_key]['output_schema']:
                self.output_schema = self.known_agents[agent_key]['output_schema']
        else:
            self.create_new_assistant(client)
        self.prompt = prompt  # does an agent instance need more than one promot?
        self.threads = []
        self.thread_details = {}  # notused yet: A dictionary to map threads to their details
        self.input_files = []
    @staticmethod
    def load_config(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)

    def get_thread_details(self, thread_id):
        # Retrieve details for a specific thread by ID
        return self.thread_details.get(thread_id)

    def active_thread(self):
        return self.threads[-1]
    def set_input_files(self, input_files):
        for file in input_files:
            self.input_files.append(file)
    def setup_run(self, input_files, qm=True, max_retries=3):
        self.max_retries = max_retries
        if input_files:
            thread = self.create_thread(self.prompt, input_files)
        else:
            thread = self.create_thread( self.prompt)
        # build a QM instance
        self.threads.append(thread)
        if qm:
            self.qm = QualityManager( self, Agent(self.client, "qm_agent") )
            print("Agent: setup_run created a QM instance")
        return

    def run_agent(self):
        # 1) run the agent
        retrieve = self.run_and_retrieve_thread()
        # 2) run the QM if enabled
        print("Agent: QM is enabled")
        if self.qm:
            agent_file = self.qm.assess_run_quality(self.active_thread())
            return agent_file
        else:
            # TODO implement the nonQM version
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
        print("Retrieve time: " + str(end_time - start_time))
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
                print(f" Assistant {self.description} status: {retrieve.status}")
                if retrieve.status == "completed":
                    return retrieve
                elif retrieve.status == "failed" or retrieve.status == "expired":
                    print(f"Run {run_id} failed.")
                    return None
                time.sleep(5)
            except Exception as e:
                print(f"Error retrieving run {run_id} for thread {thread_id}: {e}")
                retries += 1
                time.sleep(5)  # Wait before retrying
        print(f"Run {run_id} did not complete after {self.max_retries} retries.")
        return None

    def retrieve_file_content(self, file):
        content = json.loads(self.client.files.retrieve_content(file))
        return content
    def get_messages(self, thread):
        messages = self.client.beta.threads.messages.list(thread_id=thread.id).data
        response = ""
        for message in messages:
            if message.role == "assistant" and message.content[0].type == "text":
                print(message.content[0])
                print(message.content[0].text.value)
                response += message.content[0].text.value
        return response

    def add_message(self, thread_id, prompt):
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt,
        )

    def retrieve_output_or_reissue(self, thread):
        client = self.client
        file = retrieve_from_file_or_text(self.client,thread)
        if file:
            print(f"good QM file retrieved")
            return file
        else:
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content="Please write your required output to an external JSON file for processing by the agent team"
            )
            response = self.run_and_retrieve_thread()
            file = retrieve_from_file_or_text(self.client,thread)
            return file

    def upload_text_to_file(self,text):
        with open(
                f"./Intermediates/response.json", "w", encoding="utf-8"
        ) as file:
            file.write(text)
        with open(
                f"./Intermediates/response.json", "rb"
        ) as openai_file:
            openai_response = self.client.files.create(
                file=openai_file, purpose="assistants"
            )
        print(
            f"wrote file ./Intermediates/response.json and uploaded to {openai_response.id}"
        )
        return openai_response

    def retrieve_output(self):
        file = retrieve_from_file_or_text(self.client, self.active_thread())
        if file:
            print(f"good QM file retrieved")
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

    def create_thread(self, prompt, input_files=None):
        if input_files:
            if isinstance(input_files, str):
                if input_files not in self.input_files:
                    self.input_files.append(input_files)
                elif isinstance(input_files, list):
                    for input_file in input_files:
                        if input_file not in self.input_files:
                            self.input_files.append(input_file)

        print(f"file_ids = {self.input_files}")
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
        # Keep track of the thread along with its associated prompt and input file
        self.threads.append(thread)
        self.thread_details[thread.id] = {
            "prompt": prompt,
            "input_file_id": self.input_files,
            "thread": thread  # Store the whole thread object for easy access
        }
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


