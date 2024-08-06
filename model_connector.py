from abc import ABC, abstractmethod
from openai import OpenAI
from debug import dprint
from datetime import datetime, timedelta
from agent_configs import AgentConfigs
class ModelConnector(ABC):
    def __init__(self, config, filehandler):
        self.config = config
        self.client = self.initialize_client()
        self.last_timestamp = 0
        self.filehandler = filehandler

    @abstractmethod
    def initialize_client(self):
        pass

    @abstractmethod
    def generate_response(self, prompt):
        pass

    @abstractmethod
    def retrieve(self, thread, run):
        pass

    @abstractmethod
    def clean_up(self):
        pass

class OpenAIAssistantsConnector(ModelConnector):
    def initialize_client(self):
        client = OpenAI(default_headers={"OpenAI-Beta": "assistants=v2"})
        return client

    def retrieve(self, thread_id, run_id):
        retrieve = self.client.beta.threads.runs.retrieve(
            thread_id=thread_id, run_id=run_id
        )
        return retrieve

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
            "name": "Adrian Cloned Agent",
            "description": source_assistant.description,
            # TODO abstract model choice
            "model": "gpt-4o",  # 'gpt-3.5-turbo', #"gpt-4o",
            "instructions": source_assistant.instructions,
            "tools": [{"type": "code_interpreter"}],
            "temperature": source_assistant.temperature,
            "top_p": source_assistant.top_p,
        }
        new_assistant = client.beta.assistants.create(**assistant_data)
        return new_assistant

    def upload_file_ids(self,agent_id, file_ids):
        # modifies the assistant by uploading files
        my_updated_assistant = self.client.beta.assistants.update(
            agent_id,
            tool_resources={"code_interpreter": {"file_ids": file_ids}},
        )
        return my_updated_assistant.id

    def upload_locals(self, agent_id, file_paths ):
        uploaded_files = []
        for file in file_paths:
            u_file = self.client.files.create(
                file=open(file, "rb"),
                purpose="assistants"
            )
            uploaded_files.append(u_file.id)
        return uploaded_files

    def clean_up(self):
        self.delete_assistants_clones()
        self.delete_assistants_less_than_x_days()

    def generate_response(self, prompt):
        pass

    def agent_retrieve( self, agent, thread):
        """
        returns all the relevant output from an agent run
        including output file and response text
        """
        new_messages = self.get_new_messages(thread)
        file_id = self.retrieve_file_annotation(new_messages)
        latest_response = self.get_response(new_messages)
        uploaded_response = self.upload_text_to_file(latest_response)
        inline_json = self.filehandler.extract_json_from_response_text(latest_response)
        agent_output = {"output_file": file_id, "response_file" : uploaded_response, "inline_dict": inline_json }
        return agent_output

    def retrieve_direct_agent_content(
        self, agent_id, response, output_file
    ):
        """
        Retrieves the content from a file, annotations or set of messages.
        """
        # TODO make this more intelligent - get the best JSON from either
        dprint(f"output file is {output_file}")
        if output_file:
            json_data = self.filehandler.retrieve_file_content_dict(agent_id, output_file)
            if json_data:
                return json_data
        dprint(f"going to json extraction")
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

    def download_and_write_local(self, tag, file):
        content = self.client.files.content(file)
        local = self.filehandler.write_local_json(content, tag)
        return local

    def retrieve_file_content(self,client,
            agent_id, thread,
            target_id,
            file_path ):
        content = self.retrieve_output_file_id(client, agent_id, thread)
        return content

    def get_new_messages(self, thread):
        """
        just return the latest messages, i.e the last response
        """
        # Fetch all messages from the thread
        # TODO move into connector
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
                if ass.name == "Adrian Cloned Agent":
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
        model_type = config['model_type']
        if model_type == 'openai_assistants':
            return OpenAIAssistantsConnector(config, filehandler)
        else:
            raise "model not yet supported"