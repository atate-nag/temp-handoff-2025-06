from abc import ABC, abstractmethod
from openai import OpenAI
from debug import dprint
from datetime import datetime, timedelta
from agent_configs import AgentConfigs
import os
import uuid
import sys

class ModelConnector(ABC):
    def __init__(self, config, filehandler):
        self.config = config
        self.client = self.initialize_client()
        self.last_timestamp = 0
        self.filehandler = filehandler
        self.model = config.get("model")
        self.tools = []
        self.initial_message = {}
        self.conversation_histories = {}
        self.file_contents = {}
        self.messages_per_thread = {}
        self.last_response = {}

    @abstractmethod
    def initialize_client(self):
        pass

    @abstractmethod
    def generate_response(self, prompt):
        pass

    @abstractmethod
    def retrieve(self, agent_id, thread, run):
        pass

    @abstractmethod
    def clean_up(self):
        pass


class OpenAIChatConnector(ModelConnector):
    def initialize_client(self):
        client = OpenAI()
        return client

    def retrieve(self, agent_id, thread_id, run_id):
        messages = self.initial_message[agent_id] + self.messages_per_thread[thread_id]
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        self.messages_per_thread[thread_id].append({"role": "assistant", "content": completion.choices[0].message.content})
        self.last_response[thread_id] = completion.choices[0].message.content
        return completion

    def agent_clone(self, agent, parent=None):
        source_assistant_id = agent
        client = self.client
        # Retrieve the list of assistants
        my_assistants = client.beta.assistants.list(order="desc", limit=100).data
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

        agent_data = {
            "name": "Cloned Chat Agent",
            "description": source_assistant.description,
            "model": self.model,
            "instructions": source_assistant.instructions,
            "tools": [{"type": "code_interpreter"}],
            "temperature": source_assistant.temperature,
            "top_p": source_assistant.top_p,
        }
        # instead of making a new assistant, we will store the assistant data in agent config
        # self.initial_message[parent.id] = [{"role": "system", "content": source_assistant.instructions}]
        # o1-preview doesn't allow system messages so instead insert instructions into a user message

        self.initial_message[parent.id] = [{"role": "user" , "content" : source_assistant.instructions}]

        # # now add the file content
        # file_contents = self.file_contents.get(parent.id, {})
        # dprint("file_content is ",file_contents)
        #
        # if file_contents:
        #     combined_content = ''
        #     for uid, content in file_contents.items():
        #         # Optionally, summarize or truncate content
        #         combined_content += f"Content of file (UID: {uid}):\n{content}\n\n"
        #     self.initial_message[parent.id].append({
        #         "role": "user",
        #         "content": f"Here's information extracted from my files:\n{combined_content}"
        #     })
        # # Add the conversation history to the messages
        # # Store the messages object for the thread
        # # instead of returning an agent_id we return parent with is Agent ID to denote Chat API
        # dprint(f"the initial message is {self.initial_message[parent.id]}")
        # sys.exit()
        return parent

    def clean_up(self):
        pass

    def generate_response(self, prompt):
        pass

    def upload_locals(self, agent_id, file_paths):
        # Initialize dictionaries if they don't exist
        if not hasattr(self, 'file_contents'):
            self.file_contents = {}
        if not hasattr(self, 'file_uids'):
            self.file_uids = {}
        if agent_id not in self.file_contents:
            self.file_contents[agent_id] = {}
        if agent_id not in self.file_uids:
            self.file_uids[agent_id] = {}

        # Read and store the content of each file with a generated UID

        uploaded = []
        combined_content = ''
        for file_path in file_paths:
            try:
                with open(file_path, 'r') as file:
                    content = file.read()
                    # Generate a unique identifier for the file
                    file_uid = str(uuid.uuid4())
                    self.file_contents[agent_id][file_uid] = content
                    # # Optionally, store the original file name for reference
                    self.file_uids[agent_id][file_uid] = file_path
                    uploaded.append(file_uid)
                    # now add the file content
                    file_contents = self.file_contents.get(agent_id, {})
                    if file_contents:
                        for uid, content in file_contents.items():
                            # Optionally, summarize or truncate content
                            combined_content += f"Content of file (UID: {uid}):\n{content}\n\n"
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        self.initial_message[agent_id].append({
            "role": "user",
            "content": f"Here's information extracted from my files:\n{combined_content}"
        })

        return uploaded

    def upload_file_ids(self, agent_id, file_ids):
        # Since Chat Completions does not upload, this just returns the list of stored files
        return self.file_uids[agent_id]

    def add_message(self, thread, agent_id, instructions):
        """
        Add a message to the conversation history for the given thread
        and store the messages object for later use.
        """
        thread_id = thread.id
        # Build the messages object to be used later
        # Store the messages object for the thread
        dprint("thread id is " + thread_id)
        if thread_id not in self.messages_per_thread:
            self.messages_per_thread[thread_id] = []

        self.messages_per_thread[thread_id].append({
            "role": "user",
            "content": instructions,
        })

        dprint("messages per thread is " + str(self.messages_per_thread[thread_id]))
        return

    def create_run(self, thread, assistant_id):
        # completions does not have a concept of run_create
        # so we just return thread_id, this may not suffice
        return thread

    def agent_retrieve(self, agent, thread):
        """
        returns all the relevant output from an agent run
        including response text and separated json output
        For Chat API
        """

        latest_response = self.last_response[thread.id]
        inline_json = self.filehandler.extract_json_from_response_text(latest_response)
        agent_output = {
            "output_file": None,
            "response_text": self.messages_per_thread[thread.id],
            "response_file": None,
            "inline_dict": inline_json,
        }
        return agent_output

    def write_output_to_local(self, tag, output):
        response = output.get("response_text")
        inline = output.get("inline_dict")
        # content = output.get("response_text")
        response_file = self.filehandler.write_local_dict(tag, response)
        tag += "_inline"
        inline_file = self.filehandler.write_local_dict(tag, inline)
        return response_file, inline_file

    # def write_report(self, tag, output):
    #     response = output.get("response_text")
    #     inline = output.get("inline_dict")
    #     text = inline['content']
    #     # content = output.get("response_text")
    #     response_file = self.filehandler.write_local_dict(tag, response)
    #     tag += "_inline"
    #     inline_file = self.filehandler.write_local_dict(tag, inline)
    #     return response_file, inline_file

    def download_and_write_local(self, tag, file):
        content = self.client.files.content(file)
        dprint(f"content is {content}")
        local = self.filehandler.write_local_bin_to_json(tag, content)
        dprint(f"local is {local}")
        return local

class OpenAIAssistantsConnector(ModelConnector):
    def initialize_client(self):
        client = OpenAI(default_headers={"OpenAI-Beta": "assistants=v2"})
        return client

    def retrieve(self, thread_id, run_id):
        # assistant API can allow status retrieval
        retrieve = self.client.beta.threads.runs.retrieve(
            thread_id=thread_id, run_id=run_id
        )
        if retrieve.status == "completed":
            dprint(f"Run {run_id} completed successfully.")
            return True
        elif retrieve.status in ["failed", "incomplete", "expired"]:
            dprint(f"Run {run_id} failed with status: {retrieve.status}")
            return None

    def create_run(self, thread, agent_id):
        model_run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=agent_id,
                model=self.model,
                tools=[{"type": "code_interpreter"}])
        return model_run

    def agent_clone(self, agent):
        source_assistant_id = agent
        client = self.client
        # Retrieve the list of assistants
        # TODO replace with connector.clone
        my_assistants = client.beta.assistants.list(order="desc", limit=100).data
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
            # TODO abstract model choice
            "model": self.model,
            "instructions": source_assistant.instructions,
            "tools": [{"type": "code_interpreter"}],
            "temperature": source_assistant.temperature,
            "top_p": source_assistant.top_p,
        }
        new_assistant = client.beta.assistants.create(**assistant_data)
        return new_assistant

    def upload_file_ids(self, agent_id, file_ids):
        # modifies the assistant by uploading files
        my_updated_assistant = self.client.beta.assistants.update(
            agent_id,
            tool_resources={"code_interpreter": {"file_ids": file_ids}},
        )
        return my_updated_assistant.id

    def upload_locals(self, agent_id, file_paths):
        uploaded_files = []
        for file in file_paths:
            u_file = self.client.files.create(
                file=open(file, "rb"), purpose="assistants"
            )
            uploaded_files.append(u_file.id)
        return uploaded_files

    def clean_up(self):
        self.delete_assistants_clones()
        self.delete_files_less_than_1_hour()

    def generate_response(self, prompt):
        pass

    def agent_retrieve(self, agent, thread):
        """
        returns all the relevant output from an agent run
        including output file and response text
        """
        new_messages = self.get_new_messages(thread)
        file_id = self.retrieve_file_annotation(new_messages)
        latest_response = self.get_response(new_messages)
        uploaded_response = self.upload_text_to_file(latest_response)
        inline_json = self.filehandler.extract_json_from_response_text(latest_response)
        agent_output = {
            "output_file": file_id,
            "response_file": uploaded_response,
            "response_text" : None,
            "inline_dict": inline_json,
        }
        return agent_output

    def retrieve_direct_agent_content(self, agent_id, response, output_file):
        """
        Retrieves the content from a file, annotations or set of messages.
        """
        # TODO make this more intelligent - get the best JSON from either
        if output_file:
            json_data = self.filehandler.retrieve_file_content_dict(
                agent_id, output_file
            )
            if json_data:
                return json_data
        json_data = self.filehandler.extract_json_from_response_text(response)
        if json_data:
            return json_data

    def add_message(self, thread, instructions):
        """
        add a message {prompt} to the thread
        """
        self.client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=instructions
        )

    def retrieve_file_annotation(self, messages):
        """
        Retrieves the file-id from "annotations" which is where the agents should store it
        TODO only search in the later messages (like in agent.get_new_messages)
        """
        # messages = self.client.beta.threads.messages.list(thread_id=thread.id).data
        for message in messages:
            if message.role == "assistant" and message.content[0].type == "text":
                annotations = message.content[0].text.annotations
                for index, annotation in enumerate(annotations):
                    dprint(f"annotation.file_path = {annotation.file_path}")
                    if annotation.file_path.file_id:
                        file = annotation.file_path.file_id
                        return file
        dprint("No annotations for a file were found")
        return None

    def download_file(self, file):
        return self.client.files.content(file)

    def download_and_write_local(self, tag, file):
        content = self.client.files.content(file)
        dprint(f"content is {content}")
        local = self.filehandler.write_local_bin_to_json(tag, content)
        dprint(f"local is {local}")
        return local

    def retrieve_file_content(self, file):
        dprint(f"in retrieve_file_content  with file {file}")
        content = self.client.files.content(file)
        return content

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
        return new_messages

    def upload_text_to_file(self, text):
        with open(f"./Intermediates/response.json", "w", encoding="utf-8") as file:
            file.write(text)
        with open(f"./Intermediates/response.json", "rb") as openai_file:
            openai_response = self.client.files.create(
                file=openai_file, purpose="assistants"
            )
        dprint(
            f"wrote file ./Intermediates/response.json and uploaded to {openai_response.id}"
        )
        return openai_response.id

    def get_response(self, new_messages):
        response = ""
        for message in new_messages:
            if message.role == "assistant" and message.content[0].type == "text":
                response += message.content[0].text.value
        # Update the last timestamp
        if new_messages:
            self.last_timestamp = new_messages[-1].created_at
        return response

    def delete_oldest_assistant_files(self, agent_id, max_files=6):
        client = self.client
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

    def delete_files_older_than_x_days(self, days_old=30):
        client = self.client
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

    def delete_files_less_than_1_hour(self):
        # Calculate the cutoff date
        client = self.client
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

    def delete_not_known_assistants(self):
        client = self.client
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

    def delete_assistants_clones(self):
        client = self.client
        tag = "Cloned"
        try:
            # List all files
            assistants = client.beta.assistants.list(limit=100)
            dprint(f"Number of assistants is {len(assistants.data)}")
            for ass in assistants.data:
                if ass.name == "Cloned Agent":
                    dprint(f"Assistant with name {ass.name}")
                    client.beta.assistants.delete(assistant_id=ass.id)
                    print(f"Deleted ass: {ass.id}, created at {ass.created_at}")
            print("Deletion process completed.")
        except Exception as e:
            print(f"An error occurred: {e}")
        assistants = client.beta.assistants.list(limit=100)
        dprint(f"Number of assistants is now {len(assistants.data)}")

    def delete_all_uploaded_files(self):
        # Calculate the cutoff date
        client = self.client
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

    def delete_existing_assistant_files(self, agent_id):
        client = self.client
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

    def delete_assistants_less_than_x_days(self, days_old=10):
        client = self.client
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


class ModelConnectorFactory:
    @staticmethod
    def create_connector(config, filehandler):
        model_type = config["model_type"]
        if model_type == "openai_assistants":
            return OpenAIAssistantsConnector(config, filehandler)
        elif model_type == "openai_chat":
            return OpenAIChatConnector(config,filehandler)
        else:
            raise "model not yet supported"
