import json
import os
import openai
import re
from dochandler import Rdoc
from debug import dprint


# TODO precent wasteful uploads by corelating local and remote file IDs

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
        ass_file = self.create_asst_file_from_local(client, assistant, local_json)
        return ass_file

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
        return openai_file.id

    def upload_dir(self, path_to_dir, company_name, doctype):
        files = [
            f for f in os.listdir(path_to_dir) if os.path.isfile(os.path.join(path_to_dir, f))
        ]
        dprint(f"FH: files are {files}")
        uploaded_files = []
        for i, file_name in enumerate(files):
            dprint(f"FH: i,file_name = {i},{file_name}")
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
        file_path = f"./Intermediates/local_{tag}_for_agent_upload.txt"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "wb") as file:
            file.write(text.encode('utf-8'))
        return file_path


    @staticmethod
    def write_local_json(tag, data):
        file_path = f"./Intermediates/local_{tag}_for_agent_upload.json"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "w") as file:
            json.dump(data, file)
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
        dprint("uploaded file", uploaded_file)
        try:
            asst_file = client.beta.assistants.files.create(
                assistant_id=assistant,
                file_id=uploaded_file
            )
            dprint("assistant file", asst_file)
            return asst_file.id
        except Exception as e:
            dprint(f"Failed to create assistant file due to {e}")
            return None

    def create_asst_file_from_id(self, client, assistant, file):

        dprint("pre-uploaded file: ", file)
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
            dprint(f"format is {format}")
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

    def retrieve_and_create_asst_file(self, client, assistant, thread, tag=None):
        file_id = retrieve_file_annotation(client, thread)
        if file_id:
            asst_file = self.create_asst_file_from_id(client, assistant, file_id)
            dprint(f"returned from annotations {file_id}")
            return asst_file
        json_data = self.extract_json_from_response(client, thread)
        if json_data:
            asst_file = self.json_to_asst_file(client, json_data, tag, assistant)
            if asst_file:
                dprint(f"created asst file {asst_file}")
                return asst_file
        dprint(f"No annotations or json content were found, returning None")
        return None

    def extract_json_from_response(self, client, thread):
        # Sometimes naughty little AIs still send via response, so must extract it via regular expressions
        messages = client.beta.threads.messages.list(thread_id=thread.id).data
        for message in messages:
            if message.role == "assistant":  # Identify the assistant's message
                for content in message.content:
                    if content.type == "text":
                        match = re.search(r"\{.*\}", content.text.value, re.DOTALL)
                        if match:
                            json_string = match.group()
                            # Remove or replace invalid control characters
                            cleaned_json_string = re.sub(
                                r"[\x00-\x1f\x7f]", "", json_string
                            )
                            cleaned_json_string = re.sub(
                                r":\s*([0-9]+),([0-9]+)", r': "\1,\2"', cleaned_json_string
                            )
                            cleaned_json_string = re.sub(
                                r'\b(False|True)\b', lambda match: match.group(0).lower(), cleaned_json_string)
                            try:
                                full_info = json.loads(cleaned_json_string)
                                dprint(
                                    f"JSON found in the message, returning it"
                                )
                                return full_info
                            except json.JSONDecodeError as e:
                                dprint(f"Failed to decode JSON: {e}")
                                dprint(f"Faulty JSON string: {repr(cleaned_json_string)}")

                        else:
                            dprint("No JSON found in the message, returning None")
                            return None
        # Extremely naughty AI did not produce anything! Hopefully next round will be better
        dprint("No JSON content was found")
        return None

def retrieve_from_id_or_path(client, thread, file_str):
    # the problem is that the file is either in
    file_direct = retrieve_file_annotation(client, thread)
    if file_direct == file_str:
        return file_direct
    file_from_path = retrieve_file_path(thread)
    return None


def retrieve_file_annotation(client, thread):
    # Retrieve file from "annotations" which is where it (mostly) resides
    messages = client.beta.threads.messages.list(thread_id=thread.id).data
    for message in messages:
        dprint(message)
        if message.role == "assistant" and message.content[0].type == "text":
            annotations = message.content[0].text.annotations
            dprint(annotations)
            for index, annotation in enumerate(annotations):
                dprint(annotation)
                dprint(f"annotation.file_path = {annotation.file_path}")
                if annotation.file_path.file_id:
                    file = annotation.file_path.file_id
                    return file
    dprint("No annotations for a file were found")
    return None


def retrieve_file_path(client, thread):
    # Retrieve file from "annotations" but when it is a path
    messages = client.beta.threads.messages.list(thread_id=thread.id).data
    for message in messages:
        dprint(message)
        if message.role == "assistant" and message.content[0].type == "text":
            annotations = message.content[0].text.annotations
            dprint(annotations)
            for index, annotation in enumerate(annotations):
                dprint(annotation)
                dprint(f"annotation.file_path = {annotation.file_path}")
                if annotation.file_path.file_id:
                    dprint(annotation.file_path)
                    file = annotation.file_path.file_id
                    return file
    dprint("No annotations for a file were found")
    return None

def download_file_by_id(client, file_id):
    content = client.files.retrieve_content(file_id)
    return content

def download_content_and_write(client, agent_file, local_filename):
    json_content = download_file_by_id(client, agent_file)
    with open(
            f"./Intermediates/{local_filename}.json", "w", encoding="utf-8"
    ) as json_file:
        json_file.write(json_content)
    return json_file
