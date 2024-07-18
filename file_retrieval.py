
# TODO this file is defunct, combined with filehandler
def retrieve_from_file_or_text(client,thread):
    file_direct = retrieve_file_annotation(client, thread)
    if file_direct:
        return file_direct
    else:
        file_from_response = return_json_and_file(client, thread)
        if file_from_response:
            return file_from_response
    return None

def retrieve_from_id_or_path(client,thread, file_str):
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
        if message.role == "assistant" and message.content[0].type == "text":
            annotations = message.content[0].text.annotations
            for index, annotation in enumerate(annotations):
                if annotation.file_path.file_id:
                    file = annotation.file_path.file_id
                    return file
    print("No annotations for a file were found")
    return None

def retrieve_file_path(client, thread):
    # Retrieve file from "annotations" but when it is a path
    messages = client.beta.threads.messages.list(thread_id=thread.id).data
    for message in messages:
        if message.role == "assistant" and message.content[0].type == "text":
            annotations = message.content[0].text.annotations
            for index, annotation in enumerate(annotations):
                if annotation.file_path.file_id:
                    print(annotation.file_path)
                    file = annotation.file_path.file_id
                    return file
    print("No annotations for a file were found")
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
                            print(
                                f"JSON found in the message, written to file with ID: {file.id}"
                            )
                            return file.id
                        except json.JSONDecodeError as e:
                            print(f"Failed to decode JSON: {e}")
                            print(f"Faulty JSON string: {repr(cleaned_json_string)}")
                    else:
                        print("No JSON found in the message, returning None")
                        return None
    # Extremely naughty AI did not produce anything! Hopefuly next round will be better
    # TODO need to parse the run_steps and see what happened, respond accordingly
    print("No JSON content was found")
    return None


def download_content_and_write(client, agent_file, local_filename):
    json_content = download_file_by_id(client, agent_file)
    with open(
        f"./Intermediates/{local_filename}.json", "w", encoding="utf-8"
    ) as json_file:
        json_file.write(json_content)
    return json_file