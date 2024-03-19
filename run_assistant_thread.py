import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from core_components.src.agents.openAI import load_agents

from dochandler import Rdoc
from datetime import datetime
from dochandler import Rdoc

condense_agent = "asst_AzJOCJFl1D8BKF4oNrge9XF8"
condense_description = "Condensing Assistant for Json"

insight_agent = "asst_iYvVBX1aaxu3KBgSEvIAZFEb"
insight_description = "Structured Extraction Agent"

trends_agent = "asst_ripeR7nhZq822ek0PwDM31Fs"
trends_description = "Trends Agent"

capabilities_agent = "asst_NoLfJg1BUS4yNuZhurDAedXO"
capabilities_description = "Capabilities Agent"

challenges_agent = "asst_vlOVosMTXgg8qOf8FReoeNjg"
challenges_description = "Challenges Agent"

actions_agent = "asst_ACUyLQAjjCii40BRs9sBPout"
actions_description = "Actions Agent"

recommender_agent = "asst_Fh2bYH5IaS0qJKrMlNO3DZLJ"
recommender_description = "Recommender Agent"

assistants = load_agents("openAI_agents.yml")


def success_criteria_met(client, thread):
    print(f"Success Criteria: Checking thread {thread.id}")
    file_direct = retrieve_file_annotation(client, thread)
    if file_direct:
        print(f"Success Criteria:got a direct file {file_direct}")
        return file_direct
    else:
        file_from_response = return_json_and_file(client, thread)
        print(f"Success Criteria: found a file response at {file_from_response}")
        if file_from_response:
            return file_from_response
    return None


def overseer_manage_assistant(
    client, write_intermediate, prefix, index, assistant_function, *args, max_retries=3
):

    print(f"Attempt 1 for {assistant_function.__name__}")
    run_steps, retrieve_response, thread, agent = assistant_function(client, *args)

    for retry in range(max_retries):
        print(f"Retry {retry} for {assistant_function.__name__}")
        # run_steps, retrieve_response, thread = assistant_function(client, *args)

        # Check if success criteria are met
        file = success_criteria_met(client, thread)
        if file:
            print(f"good file from retrieval on attempt: {retry }")

            if write_intermediate:
                json_content = download_file_by_id(client, file)
                with open(
                    f"./Intermediates/insight_{prefix}_{index}.json",
                    "w",
                    encoding="utf-8",
                ) as json_file:
                    json_file.write(json_content)

            return file
        # If not successful, reply to the thread and insist on the file
        print(
            "Success criteria not met. Requesting refinement or a different approach."
        )
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content="Please ensure a file-ID is produced for the JSON file that contains your completed task.",
        )
        description = f"retry run due to lack of output file"
        print(f"retry number { retry } for {assistant_function.__name__}")
        run_steps, retrieve_response = run_thread(client, agent, thread, 3, description)
        # TODO: add some logic that will do a QA on the content before deciding to proceed or not
        # Logic to wait or handle the thread's response can be added here
    print(
        f"{assistant_function.__name__} did not meet success criteria after {max_retries} attempts."
    )
    return None


def retrieve_run(client, thread_id, run_id, max_retries, description):
    retries = 0
    while retries < max_retries:
        try:
            retrieve = client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run_id
            )
            print(f" Assistant {description} status: {retrieve.status}")
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
    print(f"Run {run_id} did not complete after {max_retries} retries.")
    return None  # Return None if all retries fail


def run_assistant(client, assistant, prompt, file_ids, description):
    print(f" running assistant with files {file_ids}")
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": f"Read the files {file_ids} using code_interpreter. {prompt}",
                "file_ids": file_ids,
            }
        ]
    )
    run_steps, retrieve = run_thread(client, assistant, thread, 3, description)
    return run_steps, retrieve, thread


def run_thread(client, assistant, thread, max_retries, description):
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant,
        model="gpt-4-turbo-preview",
        tools=[{"type": "code_interpreter"}],
    )
    # TODO: add explicit timeout not just retries
    start_time = time.time()
    retrieve = retrieve_run(client, thread.id, run.id, max_retries, description)
    end_time = time.time()
    print(f"Response received in {end_time - start_time} seconds")
    run_steps = client.beta.threads.runs.steps.list(thread_id=thread.id, run_id=run.id)
    return run_steps, retrieve


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


def parallel_file_process(client, file_dir, company_data, prefix, write_intermediates):
    files = [
        f for f in os.listdir(file_dir) if os.path.isfile(os.path.join(file_dir, f))
    ]
    index = 0
    # # parallel loop - submit the process_file function on as many threads as there are files
    return_files = []
    # TODO: change the number of files per worker (single file per worker currently)
    print(
        f"In parallel file processor with file_name = {file_dir} and company_data = {company_data}"
    )
    with ThreadPoolExecutor(max_workers=len(files)) as executor:
        future_to_file = {
            executor.submit(
                process_file,
                client,
                file_name,
                index + i,
                file_dir,
                company_data,
                prefix,
                write_intermediates,
            ): file_name
            for i, file_name in enumerate(files)
        }
        for future in as_completed(future_to_file):
            file_name = future_to_file[future]
            try:
                result = future.result()
                if result is not None:
                    return_files.append(result)
            except Exception as exc:
                print(f"Generated an exception: {exc}")
    return return_files


# TODO move file handling into appropriate module
def import_data_files_and_upload(client, data_dir, document_type="data"):
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
        print(f"format is {format}")
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

        print(
            f"wrote file ./Intermediates/structured_data_{i}.json and uploaded to {json_openai_response.id}"
        )
        responses.append(json_openai_response.id)
        docs.append(doc)
    return responses, docs


def process_file(
    client, file_name, index, insight_dir, company_data, prefix, write_intermediate
):

    # step 1 : extract the filename and create dochandler class

    file_path = os.path.join(insight_dir, file_name)  # Full path to the file
    _, file_extension = os.path.splitext(file_name)  # Extract file extension
    format = file_extension.lstrip(".")  # Remove the leading '.' from the extension
    print(f"format is for {file_name} is {format} and prefix is {prefix}")
    doc = Rdoc.create(file_path, format, "insight")

    # step 2 : convert to structured format (json)

    json_doc = doc.build_structured_data()
    # print(json_doc)

    # step 3 : condense to remove excess data (needs a written file creation)

    with open(
        f"./Intermediates/structured_{prefix}_{index}.json", "w", encoding="utf-8"
    ) as json_file:
        json_file.write(json_doc)
    with open(
        f"./Intermediates/structured_{prefix}_{index}.json", "rb"
    ) as json_openai_file:
        json_openai_response = client.files.create(
            file=json_openai_file, purpose="assistants"
        )

    condense_file = overseer_manage_assistant(
        client,
        write_intermediate,
        prefix,
        index,
        run_condense_analysis,
        json_openai_response,
    )

    if condense_file:
        insight_file = overseer_manage_assistant(
            client,
            write_intermediate,
            prefix,
            index,
            run_insight_analysis,
            condense_file,
            company_data,
            file_name,
        )
        print(
            f"Process file: completed the condense file operations and returned {insight_file}"
        )

        return insight_file
    else:
        return None


def download_content_and_write(client, agent_file, local_filename):
    json_content = download_file_by_id(client, agent_file)
    with open(
        f"./Intermediates/{local_filename}.json", "w", encoding="utf-8"
    ) as json_file:
        json_file.write(json_content)
    return json_file


def run_insight_analysis(client, condense_file, data_files_id, source_file):
    today_date = datetime.today().date()
    insight_prompt = (
        f"Generate the insights that relate to the company NAG Or Numerical Algorithms Group "
        f"with basic information contained in the files {data_files_id} and potential insights "
        f"in {condense_file}. Today's date is {today_date} and the source file is called {source_file}."
    )
    insight_steps, insight_response, insight_thread = run_assistant(
        client,
        insight_agent,
        insight_prompt,
        file_ids=[*data_files_id, condense_file],
        description=insight_description,
    )
    return insight_steps, insight_response, insight_thread, insight_agent


def run_condense_analysis(client, raw_file):
    condense_prompt = f"Condense the json file {raw_file.id}"

    condense_steps, condense_response, condense_thread = run_assistant(
        client,
        condense_agent,
        condense_prompt,
        file_ids=[raw_file.id],
        description=condense_description,
    )
    return condense_steps, condense_response, condense_thread, condense_agent


def run_performance_retrieval_evaluation(client, insight_file, queries):
    performance_prompt = f"Evaluate the how relevant are the insight files {insight_file} regarding the queries: {queries}"
    performance_steps, performance_response, performance_thread = run_assistant(
        client,
        assistants["OpenAI"]["retrieval_performance_evaluator"]["id"],
        performance_prompt,
        file_ids=insight_file,
        description="performance_description",
    )
    return performance_steps, performance_response, performance_thread


def run_trends_analysis(client, insight_files, data_files_id):
    trends_prompt = (
        f"Generate the trends that are affecting NAG Or Numerical Algorithms Group with basic information "
        f"contained in the file {data_files_id} and collected insights in {insight_files}"
    )

    trends_steps, trends_response, trends_thread = run_assistant(
        client,
        trends_agent,
        trends_prompt,
        file_ids= data_files_id + insight_files,
        description=trends_description,
    )
    return (
        trends_steps,
        trends_response,
        trends_thread,
        trends_agent,
    )  # Modified to return necessary info


def run_capabilities_analysis(client, insight_file):
    capabilities_prompt = (
        f"Evaluate the capabilities of the company described in the file {insight_file}"
    )
    capabilities_steps, capabilities_response, capabilities_thread = run_assistant(
        client,
        capabilities_agent,
        capabilities_prompt,
        file_ids=[insight_file],
        description=capabilities_description,
    )
    return (
        capabilities_steps,
        capabilities_response,
        capabilities_thread,
        capabilities_agent,
    )


def run_recommender_analysis(client, insight_file):
    recommender_prompt = (
        f"Make the neccesary recommendations for the insights in {insight_file}"
    )
    recommender_steps, recommender_response, recommender_thread = run_assistant(
        client,
        recommender_agent,
        recommender_prompt,
        file_ids=[insight_file],
        description=recommender_description,
    )
    return (
        recommender_steps,
        recommender_response,
        recommender_thread,
        recommender_agent,
    )


def run_capabilities_analysis(client, insight_files, data_files_id):
    capabilities_prompt = (
        f"Generate the capabilities possessed by NAG Or Numerical Algorithms Group with basic information "
        f"contained in the file {data_files_id} and collected insights in {insight_files}"
    )
    capabilities_steps, capabilities_response, capabilities_thread = run_assistant(
        client,
        capabilities_agent,
        capabilities_prompt,
        file_ids=data_files_id + insight_files,
        description=capabilities_description,
    )
    return capabilities_steps, capabilities_response, capabilities_thread, capabilities_agent


def run_challenges_analysis(client, trends_file, capabilities_file):
    challenges_prompt = (
        f"Generate the challenges that NAG Or Numerical Algorithms Group faces, using the files {trends_file} "
        f"and {capabilities_file}"
    )
    challenges_steps, challenges_response, challenges_thread = run_assistant(
        client,
        challenges_agent,
        challenges_prompt,
        file_ids=[trends_file, capabilities_file],
        description=challenges_description,
    )
    return challenges_steps, challenges_response, challenges_thread, challenges_agent


def run_actions(client, challenge, trends_file, capabilities_file):
    actions_prompt = (
        f"Your consultant colleagues have decided that the top strategic challenge facing the company "
        f"NAG Or Numerical Algorithms Group is: {challenge['challenge']}. This was based on an analysis of"
        f"the trends affecting NAG (you can read them in file {trends_file}) and NAG's capabilities (you"
        f"can read them in the file {capabilities_file}. Make sure you write the response to JSON in a "
        f"file and you provide the file location"
    )
    actions_steps, actions_response, actions_thread = run_assistant(
        client,
        actions_agent,
        actions_prompt,
        file_ids=[trends_file, capabilities_file],
        description=actions_description,
    )
    return actions_steps, actions_response, actions_thread, actions_agent
