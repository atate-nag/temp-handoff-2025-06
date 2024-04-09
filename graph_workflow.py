
import os
import openai
from dotenv import load_dotenv
from agent import Agent
from datetime import datetime
from multiprocessing import Process, Queue
from debug import dprint
from graph import CompanyGraph, InsightGraph, map_json_to_company_schema
from filehandler import FileHandler
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

# global company_graph, insight_graph, file_handler

file_handler = FileHandler(client)
company_graph = CompanyGraph(uri, user, password)
insight_graph = InsightGraph(uri, user, password)

def execute_workflow():
    dprint("Enabled workflow steps:")
    for step, details in workflow_config.items():
        if details.get("enabled", False):
            func = get_step_function(step)
            if func:
                # Unpack all parameters dynamically for the function
                parameters = details.get("parameters", {})
                dprint(f"- Executing {step} with parameters: {parameters}...")
                func(**parameters)  # Use ** to unpack and pass named parameters
            else:
                dprint(f"No function defined for {step}.")
    dprint("Finished workflow steps.")


def main():
    enabled_steps = [
        step for step, details in workflow_config.items() if details["enabled"]
    ]
    dprint("Enabled workflow steps:")
    for step in enabled_steps:
        dprint(f"- {step}")
    execute_workflow()
    company_graph.close()
    insight_graph.close()


def get_step_function(step_name):
    """
    Returns the function mapped to the specified workflow step without executing it.
    """
    step_map = {

        "createCompanies": create_companies,

        # graph manipulation and display routines

        "updateCompanyData": update_company_data,
        "displayInsights" : display_insights,
        "deleteCompany" : delete_company,
        "dumpCompanyGraph" : dump_company_graph,
        "deleteCapabilities" : delete_capabilities,
        "displayCapabilities" : display_capabilities,
        "cleanInsights" : clean_insights,
        "deleteInsights": delete_insights,

        # custom agent implementations

        "extractInsights": extract_insights,

        # generic Agent implementations

        "evaluateCapabilities": generic_agent_run,
        "recommendInsightPruning" : generic_agent_run,
        "buildCompetitiveEnvironment" : generic_agent_run,
    }
    return step_map.get(step_name, None)  # Return None if not found


"""Following are the workflow functionality functions - they are 1:1 mappings between
 functions mentioned in the file wofkflow_config.json
 Note: camelCase naming denotes parameters directly inherited from the json config file"""


def create_companies(companyName):
    dprint(f"Creating company {companyName}")
    company_graph.create_company_only(companyName)


def create_company_with_data(companyName, data):
    company_node_data = map_json_to_company_schema(json.loads(data))
    company_graph.add_company_info(companyName, company_node_data)


def update_company_data(dataDir, companyName):
    company_data_dir = os.path.join(dataDir, companyName)
    dprint(f"Dir for company is {company_data_dir}")
    if os.path.exists(company_data_dir):
        dprint(f"Importing data for {companyName} at {company_data_dir}...")
        remote_openai_company_data, company_data_doc = file_handler.import_data_files_and_upload(
            client, company_data_dir, "data"
        )
        dprint(f"Uploaded file for {companyName} at {company_data_dir} ")
        json_company_data = company_data_doc.build_structured_data()
        dprint(f"Company data = {json_company_data}")
        company_node_data = map_json_to_company_schema(json.loads(json_company_data))
        dprint(f"Data imported for {companyName}: {company_node_data}")
        company_graph.add_company_info(companyName, company_node_data)
        dprint(f"Graph updated with data for {companyName}.")
    else:
        dprint(f"No data directory found for {companyName}.")
    return


def display_insights(companyName, relevanceFrom):
    dprint(
        f"display insights, Company: {companyName}, relevanceFrom={relevanceFrom} and type is {type(relevanceFrom)}"
    )
    insights = insight_graph.get_company_insights_above_relevance(
        companyName, relevanceFrom
    )
    dprint(f"insights to display : {insights}")
    for insight in insights:
        dprint(insight)
    return


def delete_insights(companyName):
    dprint("Deleting insights...")
    company_graph.delete_company_insights(companyName)
    # TODO not the right place to delete orphans
    company_graph.delete_orphan_insights()
    return


def delete_capabilities(companyName):
    dprint("Deleting capabilities...")
    company_graph.delete_company_capabilities(companyName)
    return


def prune_capabilities(companyName):
    dprint("Cleaning capabilities...")
    # remove capabilities that are not evidenced by insights
    company_graph.prune_company_capabilities(companyName)
    return


def dump_company_graph(companyName):
    dprint(company_graph.dump_company_graph_to_json(companyName))
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


def condense_and_extract(file_id, companyName, json_graph_str, filename, output_queue):
    cond_prompt = f"Condense the file {file_id}"
    dprint(cond_prompt)
    cond_agent = Agent(client, file_handler, "condense_agent")
    dprint(cond_agent.agent_id, cond_agent.description)
    cond_agent.setup_run(file_id, qm=False)  # not clear we can QM the condense process
    cond_agent_output = cond_agent.run_agent()
    # dprint(f"condensed agent output = {cond_agent_output}")
    # setup and execute the insight agent with QM in place
    insight_prompt = (f"Extract the insights about the company {companyName} with info={json_graph_str} "
                      f"from the file {cond_agent_output}. You will need to know the name of the original sourcedocument"
                      f" is '{filename}' and today's date is {datetime.today().date()} (these will be recorded in the "
                      f"output data)")
    dprint(f"Extract_Insights: insight_prompt = {insight_prompt}")
    # TODO Agent instance needs updating
    insight_agent = Agent(client, file_handler, "insight_agent", prompt=insight_prompt)
    dprint(insight_agent.agent_id, insight_agent.description)
    insight_agent.setup_run(cond_agent_output, qm=True)  # not clear we can QM the condense process
    insight_agent_output = insight_agent.run_agent()
    output_queue.put(insight_agent_output)
    return insight_agent_output


def extract_insights(sourceDir, companyName, debug, updateGraph):
    # task 1: load company data from graph or from a debug file (if debug == True)
    llm_company_data_graph = company_graph.get_company_info(companyName)
    json_graph_str = json.dumps(llm_company_data_graph)
    if debug:
        dprint(f"Debug of insights not currently supported")
        return None
    company_insight_dir = os.path.join(sourceDir, companyName)
    # step 1 : generate a structured extraction of the document
    dprint(f"Company insight Dir is {company_insight_dir}")
    input_files = file_handler.upload_dir(company_insight_dir, companyName, "insight")
    dprint(f"input_files is {input_files}")
    # Now call the condense agent to get rid of all the junk in the file
    # this is where the parallelism should be
    processes = []
    output_queue = Queue()
    for file_id, filename in input_files:
        dprint(f"starting process when file_id is {file_id}")
        p = Process(target=condense_and_extract, args=(file_id, companyName, json_graph_str, filename, output_queue))
        dprint(f"p = {p}")
        processes.append(p)
        p.start()
    for p in processes:
        p.join()
    company_insights = []
    while not output_queue.empty():
        result = output_queue.get()
        company_insights.append(result)
    dprint(f"company insights are {company_insights}")
    for id in company_insights:
        dprint(f"company insight is {id}")
        # TODO don't need this json.loads anymore
        insight_content = json.loads(client.files.retrieve_content(id))
        dprint(f"Main: Company insights extracted: content = {insight_content}")
        if updateGraph:
            insight_graph.add_insight(insight_content, companyName)
    return


def generic_agent_run(agentType, companyName, updateGraph, debugRun):
    # TODO needs a generic intermediates write adding
    # TODO can be made more generic by defining the graph input -> agent function -> graph output
    if debugRun:
        # TODO debugRun needs to be incremental not wholesale
        dictionary_return = file_handler.local_json_read(f"debug_{agentType}_{companyName}.json")
    else:
        # get the graph data to send to agent
        json_graph = company_graph.dump_company_insight_graph_to_json(companyName)
        # dprint(json_graph)
        filename_prefix = f"{agentType}_graph_{companyName}"
        agent_graph_file = file_handler.direct_upload_json(json_graph, filename_prefix, purpose="assistants")
        dprint(f"agent graph file: {agent_graph_file}")
        # create appropriate agent type
        dprint(f"creating an agent of type {agentType}")
        agent = Agent(client, file_handler, agentType)
        dprint(agent.agent_id, agent.description)
        # setup the agent run with QM enabled
        run = agent.setup_run(agent_graph_file, qm=True)
        dictionary_return = agent.run_agent()
        dprint(f"Agent file has returned {dictionary_return}")
    # now call a generic graph updater also
    if updateGraph:
        company_graph.generic_update_graph(companyName, dictionary_return, agentType)
    for item in dictionary_return:
        dprint(item)


if __name__ == '__main__':
    main()