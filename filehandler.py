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

    def direct_upload(self, data, filename_prefix, purpose="assistants"):
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
            uploaded_files.append((self.direct_upload(json_doc, f"{company_name}_insight_doc",
                                                      purpose="assistants"), file_name))
        return uploaded_files

    def upload_text_to_file(self, client, text):
        with open(
                f"./Intermediates/response.json", "w", encoding="utf-8"
        ) as file:
            file.write(text)
        with open(
                f"./Intermediates/response.json", "rb"
        ) as openai_file:
            openai_response = client.files.create(
                file=openai_file, purpose="assistants"
            )
        dprint(
            f"wrote file ./Intermediates/response.json and uploaded to {openai_response.id}"
        )
        return openai_response.id

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

def retrieve_from_file_or_text(client, thread):
    file_direct = retrieve_file_annotation(client, thread)
    dprint(f"returned from annotations {file_direct}")
    if file_direct:
        return file_direct
    else:
        file_from_response = return_json_and_file(client, thread)
        if file_from_response:
            return file_from_response
    dprint(f"No annotations or json content were found, returning None")
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


def return_json_and_file(client, thread):
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
                            with open(
                                    f"json_file.json", "w", encoding="utf-8"
                            ) as json_file:
                                json_file.write(cleaned_json_string)
                            with open(f"json_file.json", "rb") as json_file:
                                file = client.files.create(
                                    file=json_file, purpose="assistants"
                                )
                            dprint(
                                f"JSON found in the message, written to file with ID: {file.id}"
                            )
                            return file.id
                        except json.JSONDecodeError as e:
                            dprint(f"Failed to decode JSON: {e}")
                            dprint(f"Faulty JSON string: {repr(cleaned_json_string)}")

                    else:
                        dprint("No JSON found in the message, returning None")
                        return None
    # Extremely naughty AI did not produce anything! Hopefully next round will be better
    dprint("No JSON content was found")
    return None


def download_content_and_write(client, agent_file, local_filename):
    json_content = download_file_by_id(client, agent_file)
    with open(
            f"./Intermediates/{local_filename}.json", "w", encoding="utf-8"
    ) as json_file:
        json_file.write(json_content)
    return json_file
