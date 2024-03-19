import json
import os
import openai


class FileHandler:
    def __init__(self, client, base_path="./Intermediates/"):
        self.client = client
        self.base_path = base_path
        self.file_ids = {}  # Changed to a dictionary to store files by a unique key

    def serialize_and_upload(self, data, filename_prefix, handle, purpose="assistants"):
        local_file_path = f"{self.base_path}{filename_prefix}.json"

        # Check if file already exists locally and has been uploaded
        if handle in self.file_ids:
            print(
                f"File for handle '{handle}' already uploaded with ID: {self.file_ids[handle]}"
            )
            return self.file_ids[handle]

        # Serialize data to JSON and write to local file
        with open(local_file_path, "w", encoding="utf-8") as json_file:
            json.dump(data, json_file)

        # Upload to OpenAI
        with open(local_file_path, "rb") as json_local_file:
            openai_response = self.client.files.create(
                file=json_local_file, purpose=purpose
            )
            print(f"Wrote file {local_file_path} and uploaded to {openai_response.id}")

        # Store the file ID with its handle for later use
        self.file_ids[handle] = openai_response.id
        return openai_response

    def direct_upload(self, data, filename_prefix, handle, purpose="assistants"):

        # data is already in json format, so don't serialise again (this leads to problems)

        local_file_path = f"{self.base_path}{filename_prefix}.json"

        # Check if file already exists locally and has been uploaded
        if handle in self.file_ids:
            print(
                f"File for handle '{handle}' already uploaded with ID: {self.file_ids[handle]}"
            )
            return self.file_ids[handle]

        # write to local file
        with open(local_file_path, "w", encoding="utf-8") as json_file:
            json_file.write(data)

        # Upload to OpenAI
        with open(local_file_path, "rb") as json_local_file:
            openai_response = self.client.files.create(
                file=json_local_file, purpose=purpose
            )
            print(f"Wrote file {local_file_path} and uploaded to {openai_response.id}")

        # Store the file ID with its handle for later use
        self.file_ids[handle] = openai_response.id
        return openai_response.id

    def check_and_retrieve_file(self, handle):
        # Check if file has been uploaded and retrieve its ID
        if handle in self.file_ids:
            return self.file_ids[handle]
        else:
            print(f"No file found for handle '{handle}'. Generating and uploading...")
            # Logic to generate and upload the file if it doesn't exist
            # This might involve calling another method to get the data for this handle
            # and then calling serialize_and_upload
            return None  # Placeholder for actual upload logic

    def get_file_id(self, handle):
        # Retrieve the OpenAI file ID for a given handle
        return self.file_ids.get(handle)
