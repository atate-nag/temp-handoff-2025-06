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
from agent import Agent


# def overseer_manage_assistant(
#     client, write_intermediate, prefix, index, assistant_function, *args, max_retries=3
# ):
#     print(f"Attempt 1 for {assistant_function.__name__}")
#     run_steps, retrieve_response, thread, agent = assistant_function(client, *args)
#     file = quality_manager(client, thread, agent)
#     return file
#
# def overseer_manage_agent(client, assistant_function, *args):
#     thread, response, agent = assistant_function(client, *args)
#     # basically all the assistant_functions are the same minus the prompting
#     output_file = quality_manager(client, thread, agent)
#     return output_file

# def quality_manager(client, thread, agent):
#     ''' quality manager is going to assess the quality of agent output by
#         1) checking if some additional user response is needed and performing it
#         2) Checking if the agent solved a simulation/proxy/
#         2) checking if the desired outputs were produced, requesting them if not
#         3) checking that desired outputs are in the format needed
#         4) checking that desired outputs are sufficiently numerous
#         5) checking that desired outputs are sufficiently detailed '''
#     # 1 - checking if some additional user response is needed
#     tries = 0
#     while True:
#         if tries == 3:
#             print(f"QM did not manage to get a good result after {tries} attempts")
#             return None
#         response = agent.get_messages(client, thread)
#         openai_response = upload_text_to_file(client, response)
#         qm_prompt = f"Check the agent completed the task in the given response file {openai_response.id}"
#         qm_agent = Agent(client, "qm_agent")
#         qm_thread = qm_agent.create_thread(client, qm_prompt, openai_response.id)
#         qm_response = qm_agent.run_and_retrieve_thread(client, qm_thread, 3)
#         qm_file = qm_agent.retrieve_output_or_reissue(client, qm_thread)
#         qm_content_dict = json.loads(client.files.retrieve_content(qm_file))
#
#         if qm_content_dict["completed"]:
#             agent_output_file = agent.retrieve_output(client, qm_thread)
#             print(f"QM: returning file {agent_output_file}")
#             return agent_output_file
#
#         # QM said task did not complete, need to go back to the agent
#         prompt = qm_content_dict["agent instructions"]
#         print(f"QM: agent did not complete and will be informed {prompt}")
#         agent.add_message(client, thread.id, prompt)
#         print(f"QM: going back to {agent} ")
#         response = agent.run_and_retrieve_thread(client, thread, 3)
#         file = agent.retrieve_output(client, thread)
#         if file:
#             return file
#         tries += 1

# def retrieve_run(client, thread_id, run_id, max_retries, description):
#     retries = 0
#     while retries < max_retries:
#         try:
#             retrieve = client.beta.threads.runs.retrieve(
#                 thread_id=thread_id, run_id=run_id
#             )
#             print(f" Assistant {description} status: {retrieve.status}")
#             if retrieve.status == "completed":
#                 return retrieve
#             elif retrieve.status == "failed" or retrieve.status == "expired":
#                 print(f"Run {run_id} failed.")
#                 return None
#             time.sleep(5)
#         except Exception as e:
#             print(f"Error retrieving run {run_id} for thread {thread_id}: {e}")
#             retries += 1
#             time.sleep(5)  # Wait before retrying
#     print(f"Run {run_id} did not complete after {max_retries} retries.")
#     return None  # Return None if all retries fail
#
# def run_assistant(client, assistant, prompt, file_ids, description):
#     print(f"Running {assistant} accessing stored files {file_ids}")
#     thread = client.beta.threads.create(
#         messages=[
#             {
#                 "role": "user",
#                 "content": f"Read the files {file_ids} using code_interpreter. {prompt}",
#                 "file_ids": file_ids,
#             }
#         ]
#     )
#     run_steps, retrieve = run_thread(client, assistant, thread, 3, description)
#     return run_steps, retrieve, thread
#
# def run_thread(client, assistant, thread, max_retries, description):
#     run = client.beta.threads.runs.create(
#         thread_id=thread.id,
#         assistant_id=assistant,
#         model="gpt-4-turbo-preview",
#         tools=[{"type": "code_interpreter"}],
#     )
#     # TODO: add explicit timeout not just retries
#     start_time = time.time()
#     retrieve = retrieve_run(client, thread.id, run.id, max_retries, description)
#     end_time = time.time()
#     print(f"Response received in {end_time - start_time} seconds")
#     run_steps = client.beta.threads.runs.steps.list(thread_id=thread.id, run_id=run.id)
#     return run_steps, retrieve

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

# def run_insight_analysis(client, condense_file, data_file, source_file):
#     today_date = datetime.today().date()
#     prompt = (
#         f"Generate the insights that relate to the company NAG Or Numerical Algorithms Group "
#         f"with basic information contained in the files {data_file.id} and potential insights "
#         f"in {condense_file}. Today's date is {today_date} and the source file is called {source_file}."
#     )
#     agent = Agent(client, agent_key="insight_agent")
#     print(agent.agent_id, agent.description)
#     thread = agent.create_thread(client, prompt,[data_file.id, condense_file])
#     retrieval = agent.run_and_retrieve_thread(client, thread, max_retries=3)
#     return thread, retrieval, agent

# def run_condense_analysis(client, raw_file):
#     agent = Agent(client, agent_key="condense_agent")
#     print(agent.agent_id, agent.description)
#     prompt = f"Condense the json file {raw_file.id}"
#     thread = agent.create_thread(client, prompt, raw_file)
#     retrieval = agent.run_and_retrieve_thread(client, thread, max_retries=3)
#     return thread, retrieval, agent
#
# def run_performance_retrieval_evaluation(client, insight_file, queries):
#     performance_prompt = f"Evaluate the how relevant are the insight files {insight_file} regarding the queries: {queries}"
#     performance_steps, performance_response, performance_thread = run_assistant(
#         client,
#         assistants["OpenAI"]["retrieval_performance_evaluator"]["id"],
#         performance_prompt,
#         file_ids=insight_file,
#         description="performance_description",
#     )
#     return performance_steps, performance_response, performance_thread
#
# def run_trends_analysis(client, insight_files, data_files_id):
#     trends_prompt = (
#         f"Generate the trends that are affecting NAG Or Numerical Algorithms Group with basic information "
#         f"contained in the file {data_files_id} and collected insights in {insight_files}"
#     )
#
#     trends_steps, trends_response, trends_thread = run_assistant(
#         client,
#         trends_agent,
#         trends_prompt,
#         file_ids= data_files_id + insight_files,
#         description=trends_description,
#     )
#     return (
#         trends_steps,
#         trends_response,
#         trends_thread,
#         trends_agent,
#     )  # Modified to return necessary info
#
#
# def run_recommender_analysis(client, insight_file):
#     recommender_prompt = (
#         f"Make the neccesary recommendations for the insights in {insight_file}"
#     )
#     recommender_steps, recommender_response, recommender_thread = run_assistant(
#         client,
#         recommender_agent,
#         recommender_prompt,
#         file_ids=[insight_file],
#         description=recommender_description,
#     )
#     return (
#         recommender_steps,
#         recommender_response,
#         recommender_thread,
#         recommender_agent,
#     )
#
#
# def run_capabilities_analysis(client, file):
#     capabilities_prompt = (
#         f"Generate the capabilities relevant to the company and insights in the file {file}"
#     )
#     capabilities_steps, capabilities_response, capabilities_thread = run_assistant(
#         client,
#         capabilities_agent,
#         capabilities_prompt,
#         file_ids=[file],
#         description=capabilities_description,
#     )
#     return capabilities_steps, capabilities_response, capabilities_thread, capabilities_agent
#
#
# def run_challenges_analysis(client, trends_file, capabilities_file):
#     challenges_prompt = (
#         f"Generate the challenges that NAG Or Numerical Algorithms Group faces, using the files {trends_file} "
#         f"and {capabilities_file}"
#     )
#     challenges_steps, challenges_response, challenges_thread = run_assistant(
#         client,
#         challenges_agent,
#         challenges_prompt,
#         file_ids=[trends_file, capabilities_file],
#         description=challenges_description,
#     )
#     return challenges_steps, challenges_response, challenges_thread, challenges_agent

# def run_competition_analysis(client, insight_file):
#     agent_comp = Agent(client, agent_key="competition_agent")
#     print(agent_comp.agent_id, agent_comp.description)
#     prompt = f"Define the competitive environment based on the file {insight_file}"
#     competition_prompt = f"Define the competitive environment based on the file {insight_file}"
#     thread = agent_comp.create_thread(prompt, input_files=insight_file)
#     retrieval = agent_comp.run_and_retrieve_thread()
#     return thread, retrieval, agent_comp




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
