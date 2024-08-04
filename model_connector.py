from abc import ABC, abstractmethod
from openai import OpenAI
from debug import dprint
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

class ModelConnectorFactory:
    @staticmethod
    def create_connector(config, filehandler):
        model_type = config['model_type']
        if model_type == 'openai_assistants':
            return OpenAIAssistantsConnector(config, filehandler)
        else:
            raise "model not yet supported"