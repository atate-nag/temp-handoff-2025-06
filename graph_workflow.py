from neo4j import GraphDatabase
from dochandler import Rdoc
import os
import openai
from dotenv import load_dotenv
from agent import Agent
from datetime import datetime
from multiprocessing import Process, Queue

# overseer_manage_assistant,
# run_capabilities_analysis,
# run_recommender_analysis,
# run_competition_analysis,
# overseer_manage_agent,

from run_assistant_thread import (
    parallel_file_process,
    import_data_files_and_upload,
)
from graph import CompanyGraph, InsightGraph, map_json_to_company_schema
from filehandler import FileHandler
from dochandler import import_data_files
import json
import sys

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# setup neo4j database

uri = "bolt://localhost:7687"
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
# Load the workflow configuration
with open("workflow_config.json", "r") as file:
    config = json.load(file)
workflow_config = config["workflow"]

global company_graph, insight_graph, file_handler

file_handler = FileHandler(client)

# It is a design decision to have separate handlers for different parts of
# the graph, but could be replaced with a single graph handler if the graph remains
# simple. Let's observe how much complexity is required.

company_graph = CompanyGraph(uri, user, password)
insight_graph = InsightGraph(uri, user, password)

def execute_workflow():
    print("Enabled workflow steps:")
    for step, details in workflow_config.items():
        if details.get("enabled", False):
            func = get_step_function(step)
            if func:
                # Unpack all parameters dynamically for the function
                parameters = details.get("parameters", {})
                print(f"- Executing {step} with parameters: {parameters}...")
                func(**parameters)  # Use ** to unpack and pass named parameters
            else:
                print(f"No function defined for {step}.")
    print("Finished workflow steps.")


def main():
    # # setup openaAI
    #
    # load_dotenv()
    # client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    #
    # # setup neo4j database
    #
    # uri = "bolt://localhost:7687"
    # user = os.getenv("NEO4J_USER")
    # password = os.getenv("NEO4J_PASSWORD")
    # # Load the workflow configuration
    # with open("workflow_config.json", "r") as file:
    #     config = json.load(file)
    #
    # workflow_config = config["workflow"]
    #
    # global company_graph, insight_graph, file_handler

    # initialise the openAI file handler class

    # file_handler = FileHandler(client)
    #
    # # It is a design decision to have separate handlers for different parts of
    # # the graph, but could be replaced with a single graph handler if the graph remains
    # # simple. Let's observe how much complexity is required.
    #
    # company_graph = CompanyGraph(uri, user, password)
    # insight_graph = InsightGraph(uri, user, password)

    # generate the openAI files that are needed for this workflow
    # Collect and print enabled workflow steps
    enabled_steps = [
        step for step, details in workflow_config.items() if details["enabled"]
    ]
    print("Enabled workflow steps:")
    for step in enabled_steps:
        print(f"- {step}")

    execute_workflow()
    company_graph.close()
    insight_graph.close()


def get_step_function(step_name):
    """
    Returns the function mapped to the specified workflow step without executing it.
    """
    step_map = {
        "createCompanies": create_companies,
        "updateCompanyData": update_company_data,
        "deleteInsights": delete_insights,
        "extractInsights": extract_insights,
        "displayInsights" : display_insights,
        "deleteCompany" : delete_company,
        "dumpCompanyGraph" : dump_company_graph,
        "evaluateCapabilities" : evaluate_capabilities,
        "deleteCapabilities" : delete_capabilities,
        "displayCapabilities" : display_capabilities,
        "cleanInsights" : clean_insights,
        "pruneInsights" : prune_insights,
        "buildCompetitiveEnvironment" : build_competitive_environment,
    }
    return step_map.get(step_name, None)  # Return None if not found

# Following are the workflow functionality functions - they are 1:1 mappings between
# functions mentioned in the file wofkflow_config.json
# note - camelCase naming denotes parameters directly inherited from the json config file

def create_companies(companyName):
    global company_graph
    print(f"Creating company {companyName}")
    company_graph.create_company_only(companyName)


def update_company_data(dataDir, companyName):
    company_data_dir = os.path.join(dataDir, companyName)
    print(f"Dir for company is {company_data_dir}")
    if os.path.exists(company_data_dir):
        print(f"Importing data for {companyName} at {company_data_dir}...")
        remote_openai_company_data, company_data_doc = import_data_files_and_upload(
            client, company_data_dir, "data"
        )
        print(f"Uploaded file for {companyName} at {company_data_dir} ")
        json_company_data = company_data_doc.build_structured_data()
        print(f"Company data = {json_company_data}")
        company_node_data = map_json_to_company_schema(json.loads(json_company_data))
        print(f"Data imported for {companyName}: {company_node_data}")
        company_graph.add_company_info(companyName, company_node_data)
        print(f"Graph updated with data for {companyName}.")
    else:
        print(f"No data directory found for {companyName}.")

    return

def display_insights(companyName, relevanceFrom):
    print(
        f"display insights, Company: {companyName}, relevanceFrom={relevanceFrom} and type is {type(relevanceFrom)}"
    )
    insights = insight_graph.get_company_insights_above_relevance(
        companyName, relevanceFrom
    )
    print(f"insights to display : {insights}")
    for insight in insights:
        print(insight)
    return


def delete_insights(companyName):
    print("Deleting insights...")
    company_graph.delete_company_insights(companyName)
    # TODO not the right place to delete orphans
    company_graph.delete_orphan_insights()
    return


def delete_capabilities(companyName):
    print("Deleting capabilities...")
    company_graph.delete_company_capabilities(companyName)
    return


def prune_capabilities(companyName):
    print("Cleaning capabilities...")
    # remove capabilities that are not evidenced by insights
    company_graph.prune_company_capabilities(companyName)
    return


def dump_company_graph(companyName):
    print(company_graph.dump_company_graph_to_json(companyName))
    return


def delete_company(companyName):
    # will delete a company and all the insights both associated with it and orphaned
    # TODO make this less dangerous
    company_graph.delete_company_insights(companyName)
    company_graph.delete_company(companyName)
    company_graph.delete_orphan_insights()
    return


def display_capabilities(companyName):
    company_graph.display_company_capabilities(companyName)
    return


def clean_insights(companyName):
    insight_graph.remove_non_integer_ids()
    return


def prune_insights(companyName):
    # first get the insight graph state
    json_graph = company_graph.dump_company_insight_graph_to_json(companyName)
    print(json_graph)
    filename_prefix = f"company_and_insight_graph_{companyName}"
    file = file_handler.direct_upload(
        json_graph, filename_prefix, companyName, purpose="assistants"
    )
    print(f"Newly uploaded file ID for '{companyName}': {file}")
    # now call the recommender agent and it give a set of recommendations and justifications
    recommended_insights_file = overseer_manage_assistant(
        client, None, "recommender", 0, run_recommender_analysis, file
    )
    # download the file and dump
    print(recommended_insights_file)
    str_recommender_content = client.files.retrieve_content(recommended_insights_file)
    recommender_content = json.loads(
        client.files.retrieve_content(recommended_insights_file)
    )
    with open(
        f"./Intermediates/insight_recommendations.json",
        "w",
        encoding="utf-8",
    ) as json_file:
        json_file.write(str_recommender_content)
    # now add the capabilities to the graph
    company_graph.prune_insights_from_recommendation(companyName, recommender_content)
    return


def condense_and_extract(file_id, companyName, json_graph_str, filename, output_queue):
    cond_prompt = f"Condense the file {file_id}"
    print(cond_prompt)
    cond_agent = Agent(client, file_handler, "condense_agent", prompt=cond_prompt)
    print(cond_agent.agent_id, cond_agent.description)
    cond_agent.setup_run(file_id, qm=False)  # not clear we can QM the condense process
    cond_agent_output = cond_agent.run_agent()
    print(f"condensed agent output = {cond_agent_output}")
    # setup and execute the insight agent with QM in place
    insight_prompt = (f"Extract the insights about the company {companyName} with info={json_graph_str} "
                      f"from the file {cond_agent_output}. You will need to know the name of the original sourcedocument"
                      f" is '{filename}' and today's date is {datetime.today().date()} (these will be recorded in the "
                      f"output data)")
    print(f"Extract_Insights: insight_prompt = {insight_prompt}")
    insight_agent = Agent(client, file_handler, "insight_agent", prompt=insight_prompt)
    print(insight_agent.agent_id, insight_agent.description)
    insight_agent.setup_run(cond_agent_output, qm=True)  # not clear we can QM the condense process
    insight_agent_output = insight_agent.run_agent()
    output_queue.put(insight_agent_output)
    return insight_agent_output

def extract_insights(sourceDir, companyName, debug, updateGraph):
    # task 1: load company data from graph or from a debug file (if debug == True)
    llm_company_data_graph = company_graph.get_company_info(companyName)
    json_graph_str = json.dumps(llm_company_data_graph)
    if debug:
        print(f"Debug of insights not currently supported")
        return None
    company_insight_dir = os.path.join(sourceDir, companyName)
    # step 1 : generate a structured extraction of the document
    print(f"Company insight Dir is {company_insight_dir}")
    input_files = file_handler.upload_dir(company_insight_dir, companyName, "insight")
    print(f"input_files is {input_files}")
    # Now call the condense agent to get rid of all the junk in the file
    # this is where the parallelism should be
    processes = []
    output_queue = Queue()

    for file_id, filename in input_files:
        print(f"starting process when file_id is {file_id}")
        p = Process(target=condense_and_extract, args=(file_id, companyName, json_graph_str, filename, output_queue))
        print(f"p = {p}")
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    company_insights = []
    while not output_queue.empty():
        result = output_queue.get()
        company_insights.append(result)

    print(f"company insights are {company_insights}")
    for id in company_insights:
        print(f"company insight is {id}")
        insight_content = json.loads(client.files.retrieve_content(id))
        print(f"Main: Company insights extracted: content = {insight_content}")
        if updateGraph:
            insight_graph.add_insight(insight_content, companyName)
    return


def evaluate_capabilities(companyName, debug, updateGraph):
    # dump the graph in a form suitable to send on to the AI agents
    json_graph = company_graph.dump_company_insight_graph_to_json(companyName)
    print(json_graph)
    if debug:
        # read the relevant files from debug directory instead of generating more capabilities
        capabilities_file = f"debug_capabilities_{companyName}.json"
        with open(capabilities_file, "rb") as local_file:
            capabilities_content = json.loads(local_file.read())
    else:
        # upload the graph date to openAI and get file-ID
        filename_prefix = f"company_and_insight_graph_{companyName}"
        # file = file_handler.serialize_and_upload(json_graph, filename_prefix, companyName, purpose="assistants")
        file = file_handler.direct_upload(
            json_graph, filename_prefix, companyName, purpose="assistants"
        )
        print(f"Newly uploaded file ID for '{companyName}': {file}")
        # now call the capabilities agent and it will define a set of core capabilities
        capabilities_file = overseer_manage_assistant(
            client, None, "capabilities", 0, run_capabilities_analysis, file
        )
        # download the file and dump
        print(capabilities_file)
        capabilities_content = json.loads(
            client.files.retrieve_content(capabilities_file)
        )
    # now add the capabilities to the graph
    if updateGraph:
        company_graph.add_capability_and_evidence(companyName, capabilities_content)
    return


def build_competitive_environment(companyName, updateGraph):
    # first get the insight graph state
    json_graph = company_graph.dump_company_insight_graph_to_json(companyName)
    print(json_graph)
    filename_prefix = f"company_and_insight_graph_{companyName}"
    file = file_handler.direct_upload(json_graph, filename_prefix, companyName, purpose="assistants")
    print(f"Newly uploaded file ID for '{companyName}': {file}")
    # set up the agent
    prompt = f"Define the competitive environment based on the file {file}"
    agent = Agent(client, file_handler, "competition_agent", prompt=prompt)
    print(agent.agent_id, agent.description)
    run = agent.setup_run(file, qm=True)  # prepare for a run with QM enabled
    # how much basic information do we have on each competitor? Dump the competition graph
    competition_file = agent.run_agent()
    print(competition_file)
    str_competition_file = client.files.retrieve_content(competition_file)
    competition_content = json.loads(str_competition_file)
    print(str_competition_file)
    # if UpdateGraph for every company in the competitors, we should create a new Company node

    # display competitor graph
    return


if __name__ == '__main__':
    main()