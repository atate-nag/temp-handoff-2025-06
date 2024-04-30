import json
import os
import openai
import re
from dochandler import Rdoc
from debug import dprint
import time

class FileHandler:
    def __init__(self, client, base_path="./Intermediates/"):
        self.client = client
        self.base_path = base_path
        # self.uploaded_file_ids = {}  # Changed to a dictionary to store files by a unique key

    def serialize_and_upload(self, data, filename_prefix, purpose="assistants"):
        local_file_path = f"{self.base_path}{filename_prefix}.json"
        with open(local_file_path, "w", encoding="utf-8") as json_file:
            json.dump(data, json_file)
        # Upload to OpenAI
        with open(local_file_path, "rb") as json_local_file:
            openai_response = self.client.files.create(
                file=json_local_file, purpose=purpose
            )
            dprint(f"Wrote file {local_file_path} and uploaded to {openai_response.id}")
        return openai_response

    def direct_upload_json(self, data, filename_prefix, purpose="assistants"):
        # Check if file already exists locally and has been uploaded
        #
        local_file_path = f"{self.base_path}{filename_prefix}.json"
        # write to local file
        with open(local_file_path, "w", encoding="utf-8") as json_file:
            json_file.write(data)
        # Upload to OpenAI
        with open(local_file_path, "rb") as json_local_file:
            openai_response = self.client.files.create(
                file=json_local_file, purpose=purpose
            )
            dprint(f"Wrote file {local_file_path} and uploaded to {openai_response.id}")
        return openai_response.id

    def json_to_asst_file(self, client, data, tag, assistant ):
        local_json = self.write_local_json(tag, data)
        # Upload to Assistant file
        asst_file = self.create_asst_file_from_local(client, assistant, local_json)
        return asst_file

    def txt_to_asst_file(self,client, text, tag, assistant):
        # Check if file already exists locally and has been uploaded
        # nuance - openAI needs an asssistant file if the agent is already active
        # local_file = self.write_local_file(tag, text)
        # asst_file = self.create_asst_file_from_local(client, assistant, local_file)
        # return asst_file
        with open(f"debug_{tag}.json", "w") as file:
            file.write(text)
        with open(f"debug_{tag}.json", "rb") as local_file:
            uploaded_file = client.files.create(
                file=local_file,
                purpose="assistants"
            )
            asst_file = client.beta.assistants.files.create(
                assistant_id=assistant,
                file_id=uploaded_file.id
            )
            return asst_file

    def direct_upload_txt(self, data, tag):
        # Check if file already exists locally and has been uploaded
        # nuance - openAI needs an asssistant file if the agent is already active
        local_file_path = f"./Intermediates/{tag}.txt"
        with open(
                f"./Intermediates/local_{tag}_for_agent_upload.txt", "w", encoding="utf-8"
        ) as file:
            # write to local file
            with open(local_file_path, "w", encoding="utf-8") as txt_file:
                txt_file.write(data)
        # Upload to OpenAI
        with open(local_file_path, "rb") as local_file:
            openai_file = self.client.files.create(
                file=local_file, purpose="assistants"
            )
            dprint(f"Wrote file {local_file_path} and uploaded to {openai_file}")
        return openai_file.id

    def direct_upload_file(self, file_path):
        with open(file_path, "rb") as file:
            openai_file = self.client.files.create(
                file=file,
                purpose="assistants"
            )
        dprint(f"Uploaded {file_path} to {openai_file}")

        # check that we can also download this file, if not why not?



        return openai_file.id

    def process_and_save_json_files(self,path_to_dir):
        """
        Converts all non-JSON files in the specified directory to structured JSON format and saves them as JSON files.

        Parameters:
            path_to_dir (str): The path to the directory containing the files to be processed.

        Returns:
            List[str]: A list of full paths to the created JSON files.
        """
        files = os.listdir(path_to_dir)
        json_files = []

        for file_name in files:
            file_path = os.path.join(path_to_dir, file_name)
            if os.path.isfile(file_path) and not file_name.lower().endswith('.json'):
                _, file_extension = os.path.splitext(file_name)  # Extract file extension
                file_format = file_extension.lstrip(".")  # Remove the leading '.' from the extension
                doc = Rdoc.create(file_path, file_format, "insight")
                # step 2 : convert to structured format (json)
                structured_data = doc.build_structured_data()
                # Create the JSON file path and save the JSON data
                json_file_path = os.path.splitext(file_path)[0] + '.json'
                with open(json_file_path, 'w') as json_file:
                    json.dump(structured_data, json_file)
                json_files.append(json_file_path)

        return json_files

    def upload_dir(self, path_to_dir, company_name, doctype):
        files = [
            f for f in os.listdir(path_to_dir) if os.path.isfile(os.path.join(path_to_dir, f))
        ]
        uploaded_files = []
        for i, file_name in enumerate(files):
            file_path = os.path.join(path_to_dir, file_name)  # Full path to the file
            _, file_extension = os.path.splitext(file_name)  # Extract file extension
            file_format = file_extension.lstrip(".")  # Remove the leading '.' from the extension
            doc = Rdoc.create(file_path, file_format, doctype)
            # step 2 : convert to structured format (json)
            json_doc = doc.build_structured_data()
            # TODO change to use asst_file
            uploaded_files.append((self.direct_upload_json(json_doc, f"{company_name}_insight_doc",
                                                      purpose="assistants"), file_name))
        return uploaded_files

    @staticmethod
    def write_local_file(tag, text):
        file_path = f"./Intermediates/upload{tag}.json"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "w") as file:
            file.write(text.encode('utf-8'))
        return file_path


    @staticmethod
    def write_local_json(tag, data):
        # TODO - pass dictionary data not a string?
        # sdata is already a serialised json string
        file_path = f"./Intermediates/local_{tag}.json"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "w") as file:
            file.write(data)
        return file_path

    def upload_text_to_file(self, client, text):
        with open(
                f"./Intermediates/response.json", "w", encoding="utf-8"
        ) as file:
            file.write(text)
        with open(
                f"./Intermediates/response.json", "rb"
        ) as openai_file:
            openai_response = client.files.create(
                file=openai_file,
                purpose="assistants"
            )
        dprint(
            f"wrote file ./Intermediates/response.json and uploaded to {openai_response.id}"
        )
        return openai_response.id

    def create_asst_file_from_local(self, client, assistant, file):
        # first upload the file
        uploaded_file = self.direct_upload_file(file)
        try:
            asst_file = client.beta.assistants.files.create(
                assistant_id=assistant,
                file_id=uploaded_file
            )
            return asst_file.id
        except Exception as e:
            dprint(f"Failed to create assistant file due to {e}")
            return None

    def create_asst_file_from_id(self, client, assistant, file):
        try:
            asst_file = client.beta.assistants.files.create(
                assistant_id=assistant,
                file_id=file
            )
            dprint("assistant file", asst_file)
            return asst_file.id
        except Exception as e:
            dprint(f"Failed to create assistant file due to {e}")
            return None

    def import_data_files_and_upload(self, client, data_dir, document_type="data"):
        # import all the files in the given directory and optionally write intermediates
        data_files = [
            f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))
        ]
        company_data = (
            []
        )  # company_data will be a list of json objects containing info about the company
        responses = []
        docs = []
        for i, file_name in enumerate(data_files):
            file_path = os.path.join(data_dir, file_name)  # Full path to the file
            _, file_extension = os.path.splitext(file_name)  # Extract file extension
            format = file_extension.lstrip(".")  # Remove the leading '.' from the extension
            doc = Rdoc.create(file_path, format, document_type)
            json_doc = doc.build_structured_data()
            with open(
                    f"./Intermediates/structured_data_{i}.json", "w", encoding="utf-8"
            ) as json_file:
                json_file.write(json_doc)
            with open(
                    f"./Intermediates/structured_data_{i}.json", "rb"
            ) as json_openai_file:
                json_openai_response = client.files.create(
                    file=json_openai_file, purpose="assistants"
                )

            dprint(
                f"wrote file ./Intermediates/structured_data_{i}.json and uploaded to {json_openai_response.id}"
            )
            responses.append(json_openai_response.id)
            docs.append(doc)
        return responses, docs

    def local_json_read(self, local_filename):
        # reads local json file and returns dictionary
        with open(
                f"{local_filename}", "r", encoding="utf-8"
        ) as json_file:
            json_content = json_file.read()
        # TODO store local files in class
        return json.loads(json_content)

    def retrieve_and_create_asst_file(self, client, assistant, thread, qm_id=None, tag=""):
        """
            From an assistant thread, extract the file id and store in
            an assistant-file for accessing by agent. Will need to create the output file
            on both the assistant-id and the qm_id
            If this comes out of an output file provided by an Agent, then don't create a
            new one. Just return the JSON.
        """
        file_id = retrieve_file_annotation(client, thread)
        if file_id:
            # This creating an assistant file not in the agent that has produced this but on the QM
            if qm_id is not None:
                asst_file_qm = self.create_asst_file_from_id(client, qm_id, file_id)
            asst_file = self.create_asst_file_from_id(client, assistant, file_id)
            return asst_file
        json_data = self.extract_json_from_response(client, thread)
        if json_data:
            # This creating an assistant file not in the agent that has produced this but on the QM
            if qm_id is not None:
                asst_file_qm = self.json_to_asst_file(client, json_data, tag, qm_id)
            asst_file = self.json_to_asst_file(client, json_data, tag, assistant)
            return asst_file
        return None

    def retrieve_output_file_id(self, client, assistant, thread, qm_id=None, tag=""):
        """
            From an assistant thread, extract the file id that it references, and store in
            (if necessary) copy it to the QM agent.
        """
        file_id = retrieve_file_annotation(client, thread)
        if file_id:
            # This creating an assistant file not in the agent that has produced this but on the QM
            if qm_id is not None:
                asst_file_qm = self.create_asst_file_from_id(client, qm_id, file_id)
            asst_file = self.create_asst_file_from_id(client, assistant, file_id)
            return file_id
        return None

    def retrieve_direct_agent_content(self, client, agent_id, response_str, output_file, tag=""):
        """
        Retrieves the content from a file, annotations or set of messages.
        """
        # TODO make this more intelligent - get the best JSON from either
        if output_file:
            json_data = self.retrieve_file_content_dict(client, agent_id, output_file)
            if json_data:
                return json_data
        json_data = self.extract_json_from_response_text(response_str)
        if json_data:
            return json_data
        # if nothing there, then extract contents of the output file
        # if output_file:
        #     json_data = self.retrieve_file_content_dict(client, agent_id, output_file)
        #     if json_data:
        #         return json_data
        dprint("No json data found in either response or latest output file, returning None")
        return None

    @staticmethod
    def clean_json_string(s):
        """
            Cleans a json string in common ways that JSON is often invalid
            TODO this needs extending to be exhaustive
        """
        # Fix unquoted keys
        s = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', s)
        # Fix booleans
        s = re.sub(r'\b(True|False)\b', lambda m: m.group(0).lower(), s)
        # Fix escaping issues
        s = re.sub(r"\\'", "'", s)  # Single quotes should not be escaped in JSON
        s = s.replace("\\\\", "\\")  # Unescape escaped backslashes
        s = s.replace("\\/", "/")  # Unescape escaped slashes
        return s

    def extract_json_from_response(self, client, thread):
        """
            Get JSON data directly from agent thread via messages
        """
        messages = client.beta.threads.messages.list(thread_id=thread.id).data
        for message in messages:
            if message.role == "assistant":  # Identify the assistant's message
                for content in message.content:
                    if content.type == "text":
                        match = re.search(r"\{.*\}", content.text.value, re.DOTALL)
                        if match:
                            json_string = match.group()
                            cleaned_json_string = self.clean_json_string(json_string)
                            try:
                                full_info = json.loads(cleaned_json_string)
                                dprint(
                                    f"JSON found in the message, returning it"
                                )
                                return full_info
                            except json.JSONDecodeError as e:
                                dprint(f"Failed to decode JSON: {e}")
                                dprint(f"Faulty JSON string: {repr(cleaned_json_string)}")
                                repaired_json = '[' + re.sub(r'\}\s*,\s*\{', '}, {', cleaned_json_string.strip()) + ']'
                                try:
                                    # Load the repaired JSON string
                                    full_info = json.loads(repaired_json)
                                    dprint("Repaired JSON loaded successfully")
                                    return full_info
                                except json.JSONDecodeError as e:
                                    print(f"Failed to decode JSON: {e}")
                                    print(f"Faulty JSON string: {repr(repaired_json)}")
                        else:
                            dprint("No JSON found in the message, returning None")
                            return None
        # Extremely naughty AI did not produce anything! Hopefully next round will be better
        dprint("No JSON content was found")
        return None
    def extract_json_from_response_asst_file(self, client, file_id, agent_id):
        str = self.retrieve_file_content_str(client, agent_id, file_id)

    def extract_json_from_response_text(self, response):
        """
            Get JSON data directly from provided agent response text and return as a dictionary or list
        """
        # Adjusting regex to capture JSON data enclosed within markdown code blocks
        # and be resilient to the absence of newlines
        match = re.search(r"```json\s*(.+?)\s*```", response, re.DOTALL)
        if match:
            json_string = match.group(1)
            cleaned_json_string = self.clean_json_string(json_string)
            try:
                full_info = json.loads(cleaned_json_string)
                dprint("JSON found in the message, returning it")
                return full_info
            except json.JSONDecodeError as e:
                dprint(f"Failed to decode JSON: {e}")
                dprint(f"Faulty JSON string: {repr(cleaned_json_string)}")
                repaired_json = self.attempt_to_repair_json(cleaned_json_string)
                try:
                    full_info = json.loads(repaired_json)
                    dprint("Repaired JSON loaded successfully")
                    return full_info
                except json.JSONDecodeError as e:
                    dprint(f"Failed to decode JSON after repair: {e}")
                    dprint(f"Faulty JSON string: {repr(repaired_json)}")
        else:
            dprint("No JSON found in the message, returning None")
            return None
        dprint("No JSON content was found")
        return None

    def attempt_to_repair_json(self, json_string):
        """
            Attempt to repair common issues in JSON strings that prevent parsing
        """
        # Example: Fixes for missing commas between objects, extra trailing commas, etc.
        repaired = re.sub(r'\}\s*,\s*\{', '}, {', json_string.strip().rstrip(','))
        return '[' + repaired + ']'

    def retrieve_file_content_str(self, client, agent_id, file):
        """
            given an asst-file-id, return the JSON file content
            TODO should be in filehandler?
        """
        asst_file = client.beta.assistants.files.retrieve(
            assistant_id=agent_id,
            file_id=file.id
        )
        content = client.files.retrieve_content(asst_file.id)
        return content

    def retrieve_file_content_dict(self, client, agent_id, file):
        """
            given an asst-file-id, return the JSON file content
            TODO should be in filehandler?
        """
        asst_file = client.beta.assistants.files.retrieve(
            assistant_id=agent_id,
            file_id=file
        )
        content = client.files.retrieve_content(asst_file.id)
        return json.loads(content)

    def list_asst_files(self, client, agent_id):
        asst_files = client.beta.assistants.files.list(
            assistant_id=agent_id,
            order="asc"
        )
        return asst_files
    def delete_asst_files(self, client, agent_id):
        """
        delete all assistant files on this assistant
        TODO: a bug means that this will always throw an error
        """
        asst_files = self.list_asst_files(client, agent_id)
        print(f"Assistant files: {asst_files}")
        for asst_file in asst_files:
            retries = 3
            while retries > 0:
                try:
                    print(f"Attempting to delete Assistant file-id: {asst_file.id}")
                    client.beta.assistants.files.delete(
                        assistant_id=agent_id,
                        file_id=asst_file.id
                    )
                    print(f"Successfully deleted Assistant file-id: {asst_file.id}")
                    break
                except openai.OpenAIError as e:
                    print(f"Error deleting file-id {asst_file.id}: {str(e)}")
                    if retries > 1:
                        print("Retrying...")
                        time.sleep(5)  # Wait a bit before retrying
                    else:
                        print("Final attempt failed.")
                retries -= 1
def retrieve_file_annotation(client, thread):
    """
    Retrieves the file-id from "annotations" which is where the agents should store it
    However, they  are not reliable hence this method cannot be relied upon to get a file
    TODO only search in the later messages (like in agent.get_new_messages)
    TODO some code redundancy between this and other uses of messages.list
    """
    messages = client.beta.threads.messages.list(thread_id=thread.id).data
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
