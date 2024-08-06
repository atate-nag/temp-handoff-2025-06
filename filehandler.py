import json
import os
import openai
import re
from dochandler import Rdoc
from debug import dprint
from utility import dict_to_plain_text
import time


class FileHandler:
    def __init__(self, base_path="./Intermediates/"):
        self.base_path = base_path
        # self.uploaded_file_ids = {}  # Changed to a dictionary to store files by a unique key


    @staticmethod
    def extract_context(json_string, pos, context_len=100):
        """
        Extracts and returns the context around a given position in the JSON string for better error debugging.
        """
        start = max(0, pos - context_len)
        end = min(len(json_string), pos + context_len)
        return json_string[start:end]

    def split_json_objects(self, json_string):
        """
        Split a string containing multiple JSON objects into a list of JSON objects.
        This function will handle and skip over malformed JSON segments.
        """
        decoder = json.JSONDecoder()
        pos = 0
        length = len(json_string)
        json_objects = []

        while pos < length:
            try:
                match = decoder.raw_decode(json_string, pos)
                json_objects.append(match[0])
                pos = match[1]
                # Skip any whitespace between JSON objects
                while pos < length and json_string[pos].isspace():
                    pos += 1
            except json.JSONDecodeError as e:
                # Print error and skip to the next possible JSON object
                context = FileHandler.extract_context(json_string, pos)
                print(f"Skipping malformed JSON segment at position {pos}: {e}")
                print(f"Context: {context}")

                # Attempt more aggressive repair
                start_pos = pos
                while pos < length and json_string[pos] not in "{[":
                    pos += 1
                # Capture the malformed segment
                malformed_segment = json_string[start_pos:pos]
                print(f"Malformed segment: {malformed_segment}")

                # Try to skip over the malformed segment
                pos += 1

        return json_objects

    @staticmethod
    def clean_structured_data(data):
        """
        Cleans structured data to fix common issues before converting to JSON.
        """
        if isinstance(data, list):
            return [FileHandler.clean_structured_data(item) for item in data]
        elif isinstance(data, dict):
            cleaned_data = {}
            for key, value in data.items():
                cleaned_key = (
                    FileHandler.clean_json_string(key) if isinstance(key, str) else key
                )
                cleaned_value = FileHandler.clean_structured_data(value)
                cleaned_data[cleaned_key] = cleaned_value
            return cleaned_data
        elif isinstance(data, str):
            return FileHandler.clean_json_string(data)
        else:
            return data

    def process_and_save_json_files(self, path_to_dir):
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
            if os.path.isfile(file_path) and not file_name.lower().endswith(".json"):
                _, file_extension = os.path.splitext(
                    file_name
                )  # Extract file extension
                file_format = file_extension.lstrip(
                    "."
                )  # Remove the leading '.' from the extension
                doc = Rdoc.create(file_path, file_format, "insight")

                # Step 2: Convert to structured format (json)
                structured_data = doc.build_structured_data()
                print(
                    f"Original structured data snippet: {json.dumps(structured_data)[:1000]}"
                )  # Debugging

                # Verify and clean the structured data
                if isinstance(structured_data, str):
                    try:
                        structured_data = json.loads(structured_data)
                    except json.JSONDecodeError as e:
                        print(f"Initial structured data is not valid JSON: {e}")

                cleaned_structured_data = self.clean_structured_data(structured_data)
                print(
                    f"Cleaned structured data snippet: {json.dumps(cleaned_structured_data)[:1000]}"
                )  # Debugging

                # Convert structured data to a JSON string
                json_string = json.dumps(cleaned_structured_data, indent=4)
                print(f"JSON string snippet: {json_string[:1000]}")  # Debugging

                # Clean and repair the JSON string
                cleaned_json_string = self.clean_json_string(json_string)
                print(
                    f"Cleaned JSON string snippet: {cleaned_json_string[:1000]}"
                )  # Debugging

                try:
                    full_info = json.loads(cleaned_json_string)
                except json.JSONDecodeError as e:
                    if "Extra data" in str(e) or "Expecting value" in str(e):
                        # Handle multiple JSON objects case
                        full_info = list(self.split_json_objects(cleaned_json_string))
                        print("Handled multiple JSON objects.")
                    else:
                        # Attempt to repair JSON if it's not just multiple JSON objects
                        repaired_json = self.attempt_to_repair_json(cleaned_json_string)
                        try:
                            full_info = json.loads(repaired_json)
                        except json.JSONDecodeError as e:
                            print(f"Failed to repair JSON: {e}")
                            continue
                # Create the JSON file path and save the JSON data
                json_file_path = os.path.splitext(file_path)[0] + ".json"
                with open(json_file_path, "w", encoding="utf-8") as json_file:
                    json.dump(full_info, json_file, indent=4)
                json_files.append(json_file_path)

        return json_files

    @staticmethod
    def write_local_file(tag, text):
        file_path = f"./Intermediates/upload{tag}.json"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "w") as file:
            file.write(text.encode("utf-8"))
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

    @staticmethod
    def write_local_txt(tag, data):
        # TODO - pass dictionary data not a string?
        # sdata is already a serialised json string
        file_path = f"./Intermediates/local_{tag}.txt"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "w") as file:
            file.write(data)
        return file_path

    @staticmethod
    def write_local_dict(tag, data):
        # data is now a dictionary
        file_path = f"./Intermediates/local_{tag}.json"
        # Open the file in write mode
        with open(file_path, "w") as file:
            json.dump(data, file)
        return file_path

    def local_json_read(self, local_filename):
        # reads local json file and returns dictionary
        with open(f"{local_filename}", "r", encoding="utf-8") as json_file:
            json_content = json_file.read()
        # TODO store local files in class
        return json.loads(json_content)

    @staticmethod
    def clean_json_string(s):
        """
        Cleans a JSON string in common ways that JSON is often invalid.
        """
        # Fix unquoted keys (assumes keys are valid Python identifiers)
        s = re.sub(r'([{,]\s*)([a-zA-Z_]\w*)(\s*:)', r'\1"\2"\3', s)

        # Fix booleans
        s = re.sub(r'\b(True|False|null)\b', lambda m: m.group(0).lower(), s)

        # Fix escaping issues
        s = s.replace("\\'", "'")  # Single quotes should not be escaped in JSON
        s = s.replace("\\\\", "\\")  # Unescape escaped backslashes
        s = s.replace("\\/", "/")  # Unescape escaped slashes

        # Remove stray backslashes not followed by a valid escape sequence
        s = re.sub(r'\\([^"\\/bfnrtu])', r'\1', s)

        # Fix issues with trailing backslashes
        s = re.sub(r'\\$', '', s)

        # Remove newlines within strings (only the escaped newlines)
        s = re.sub(r'\\n', ' ', s)
        s = re.sub(r'\\r', ' ', s)

        # Remove trailing commas in objects and arrays
        s = re.sub(r',\s*}', '}', s)
        s = re.sub(r',\s*]', ']', s)

        return s.strip()

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
                                dprint(f"JSON found in the message, returning it")
                                return full_info
                            except json.JSONDecodeError as e:
                                dprint(f"Failed to decode JSON: {e}")
                                dprint(
                                    f"Faulty JSON string: {repr(cleaned_json_string)}"
                                )
                                repaired_json = (
                                    "["
                                    + re.sub(
                                        r"\}\s*,\s*\{",
                                        "}, {",
                                        cleaned_json_string.strip(),
                                    )
                                    + "]"
                                )
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

    def extract_json_from_response_text(self, response):
        """
        Get JSON data directly from provided agent response text and return as a dictionary or list.
        Specifically looks for JSON containing "completed" key, and optionally "agent instructions" key.
        """
        # Adjusting regex to capture JSON data enclosed within markdown code blocks
        # and be resilient to the absence of newlines
        json_pattern = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
        matches = json_pattern.findall(response)

        for json_string in matches:
            cleaned_json_string = self.clean_json_string(json_string)
            try:
                json_data = json.loads(cleaned_json_string)
                if isinstance(json_data, dict) and "completed" in json_data:
                    dprint("Specific JSON found in the message, returning it")
                    return json_data
            except json.JSONDecodeError as e:
                dprint(f"Failed to decode JSON: {e}")
                dprint(f"Faulty JSON string: {repr(cleaned_json_string)}")
                repaired_json = self.attempt_to_repair_json(cleaned_json_string)
                try:
                    json_data = json.loads(repaired_json)
                    if isinstance(json_data, dict) and "completed" in json_data:
                        dprint("Repaired JSON loaded successfully")
                        return json_data
                except json.JSONDecodeError as e:
                    dprint(f"Failed to decode JSON after repair: {e}")
                    dprint(f"Faulty JSON string: {repr(repaired_json)}")

        dprint("No specific JSON content found in the message")
        return None

    def attempt_to_repair_json(self, json_string):
        """
        Attempt to repair a JSON string that could not be decoded.
        This might involve fixing common JSON formatting issues.
        """
        try:
            # Try to load with trailing commas removed
            json_data = json.loads(json_string)
            return json.dumps(json_data)  # Serialize back to string to clean it
        except json.JSONDecodeError:
            pass
        repaired_json_string = self.clean_json_string(json_string)
        return repaired_json_string
