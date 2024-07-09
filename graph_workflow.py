import os
from openai import OpenAI
from dotenv import load_dotenv
from multiprocessing import Process, Queue, Semaphore
from agent_workflow_manager import AgentManager
from debug import dprint
from graph import CompanyGraph, InsightGraph, map_json_to_company_schema
from full_graph import dump_company_graph_to_plain_txt, get_trends_from_gics_code
from filehandler import FileHandler
import json, re
from openai_asst import (delete_assistants_clones, delete_all_uploaded_files, delete_not_known_assistants,
                         delete_files_less_than_1_hour)
# from doc_converter import StrategicReportGenerator
import sys
import concurrent.futures

load_dotenv()
#client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), default_headers={"OpenAI-Beta": "assistants=v2"})
client = OpenAI(default_headers={"OpenAI-Beta": "assistants=v2"})
# setup neo4j database

uri = os.getenv("NEO4J_URL")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE")

# Load the workflow configuration
with open("workflow.json", "r") as file:
    config = json.load(file)
workflow_config = config["workflow"]

gics_mapping = {
    10: "Energy",
    15: "Materials",
    20: "Industrials",
    25: "Consumer Discretionary",
    30: "Consumer Staples",
    35: "Health Care",
    40: "Financials",
    45: "Information Technology",
    50: "Communication Services",
    55: "Utilities",
    60: "Real Estate"
}

file_handler = FileHandler(client)
company_graph = CompanyGraph(uri, user, password, database_name=database)
insight_graph = InsightGraph(uri, user, password, database_name=database)

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

        # administrative routines
        "cleanUp": clean_up,
        "createCompanies": create_companies,

        # graph manipulation and display routines
        "updateCompanyData": update_company_data,
        "displayInsights": display_insights,
        "deleteCompany": delete_company,
        "dumpCompanyGraph": dump_company_graph,
        "deleteCapabilities": delete_capabilities,
        "displayCapabilities": display_capabilities,
        "cleanInsights": clean_insights,
        "deleteInsights": delete_insights,

        # custom agent implementations
        "extractInsights": extract_insights,
        "detectTrends": detect_trends,

        # generic Agent implementations
        "evaluateCapabilities": generic_agent_run,
        "recommendInsightPruning": generic_agent_run,
        "buildCompetitiveEnvironment": generic_agent_run,

        # temporary
        "runStrategy": run_strategy,
        "runStrategyforAll": run_strategy_for_all,

        # general tasks
        "runTask": run_task,

    }
    return step_map.get(step_name, None)  # Return None if not found

    #    Following are the workflow functionality functions - they are 1:1 mappings between
    #    functions mentioned in the file wofkflow_config.json
    #    Note: camelCase naming denotes parameters directly inherited from the json config file

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

def clean_up():
    # Aggressive Cleanup of assistants and files
    # except for those and all files
    deleted = delete_assistants_clones(client)
    deleted = deleted_files = None
    # deleted = delete_not_known_assistants(client)
    deleted_files = delete_files_less_than_1_hour(client)
    # deleted_files = delete_all_uploaded_files(client)
    dprint(f"Deleted {deleted} assistants and {deleted_files} files")

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

def condense_and_extract(json_input_file, file_path, output_queue, agentType, index, semaphore):
    try:
        cond_prompt = f"Condense the file {file_path}"
        agent_configs = [{'agent_type': "condense_agent"}]
        agent_manager = AgentManager(client, file_handler, agent_configs, [file_path])
        agent_manager.run_workflow()
        agent_dictionary_return = agent_manager.return_dict()
        condense_file = file_handler.write_local_json(f"input_condense_process{index}", json.dumps(agent_dictionary_return))
        agent_configs = [{'agent_type': agentType}]
        agent_manager = AgentManager(client, file_handler, agent_configs, [json_input_file, condense_file])
        agent_manager.run_workflow()
        agent_dictionary_return = agent_manager.return_dict()
        output_queue.put(agent_dictionary_return)
    finally:
        semaphore.release()

""" custom workflow executions """

def extract_insights(sourceDir, companyName, debug, updateGraph, agentType):
    llm_company_data_graph = company_graph.get_company_info(companyName)
    json_graph_str = json.dumps(llm_company_data_graph)
    dprint(f"company graph is {json_graph_str}")
    company_insight_dir = os.path.join(sourceDir, companyName)
    dprint(f"Company insight Dir is {company_insight_dir}")
    processes = []
    output_queue = Queue()
    file_paths = file_handler.process_and_save_json_files(company_insight_dir)
    dprint(f"file paths are {file_paths}")
    index = 1
    max_processes = 12  # Setting the limit to the number of cores
    pool_semaphore = Semaphore(max_processes)  # Create a semaphore object
    for data_file_path in file_paths:
        dprint(f"starting process when file_id is {data_file_path}")
        json_graph_file = file_handler.write_local_json(f"input_graph_process{index}", json_graph_str)
        pool_semaphore.acquire()  # Acquire a semaphore slot before starting a new process
        p = Process(target=condense_and_extract, args= (json_graph_file, data_file_path, output_queue, agentType, index, pool_semaphore))
        dprint(f"p = {p}")
        processes.append(p)
        p.start()
        index += 1
    for p in processes:
        p.join()
    company_insights_list = []
    while not output_queue.empty():
        result = output_queue.get()
        company_insights_list.append(result)
    dprint(f"company insights are {company_insights_list} ")
    dprint(f"{len(company_insights_list)} processes returned output {len(file_paths)} expected")
    for company_insights in company_insights_list:
        if updateGraph:
            insight_graph.add_insight(company_insights, companyName)
    return

def delete_trend(trend_name):
    delete_criteria = {'Title': trend_name}
    company_graph.delete_trends(delete_criteria)


def detect_trends(sourceDir, industries, debug, updateGraph, agentType):
    # Trend categories, including PESTLE and GICS
    # trend_categories = ['Political', 'Economic', 'Society', 'Technology', 'Legal', 'Environment']
    trend_categories = ['Technology', 'Legal', 'Environment']
    trend_categories = []
    # GICS mapping as a dictionary
    gics_mapping = {
        # 10: "Energy",
        # 15: "Materials",
        # 20: "Industrials",
        25: "Consumer Discretionary",
        # 30: "Consumer Staples",
        # 35: "Health Care",
        # 40: "Financials",
        # 45: "Information Technology",
        # 50: "Communication Services",
        # 55: "Utilities",
        # 60: "Real Estate"
    }

    trend_categories.extend([f"{gics_id}. {gics_name}" for gics_id, gics_name in gics_mapping.items()])
    processes = []
    output_queue = Queue()
    max_processes = 24  # Setting the limit to 2x the number of cores
    pool_semaphore = Semaphore(max_processes)  # Create a semaphore object

    # Iterate through each trend category to find and process files in each subdirectory
    for category in trend_categories:
        processes = []
        output_queue = Queue()
        category_dir = os.path.join(sourceDir, category)  # Use subdirectory for each category

        if not os.path.exists(category_dir):
            os.makedirs(category_dir)
            print(f"Directory {category_dir} created.")

        file_paths = file_handler.process_and_save_json_files(category_dir)
        print(f"File paths in {category_dir} are {file_paths}")
        index = 1

        for data_file_path in file_paths:
            print(f"Starting process for file {data_file_path} in category {category}")
            pool_semaphore.acquire()  # Acquire a semaphore slot before starting a new process
            p = Process(target=condense_and_extract,
                        args=(industries, data_file_path, output_queue, agentType, index, pool_semaphore))
            processes.append(p)
            p.start()
            index += 1

        # Wait for all processes to complete
        for p in processes:
            p.join()

        # Collect results from the output queue
        trends_list = []
        while not output_queue.empty():
            result = output_queue.get()
            trends_list.append(result)

        print(f"All trends: {trends_list}")
        for trend_dict in trends_list:
            for trend in trend_dict['Trends']:
                company_graph.add_trend(trend,category)

    return trends_list


def create_json_filename(company_name):
    """
    Generates a JSON filename from a company name by normalizing it and adding the appropriate file extension.

    Args:
    company_name (str): The name of the company.

    Returns:
    str: A filename based on the company name, suitable for saving as a JSON file.
    """
    # Normalize the string: convert to lowercase
    normalized_name = company_name.lower()

    # Remove special characters and replace spaces with underscores
    filename = re.sub(r'[^a-z0-9 ]', '', normalized_name)  # Remove anything not a letter, number, or space
    filename = filename.replace(' ', '_')  # Replace spaces with underscores

    # Add the .json extension
    filename += '.json'

    return filename

def get_gics_code_and_name(company_name):
    company_to_gics = {
        "Tesla": 25,
        "McKesson": 35,
        "Elevance_Health": 35,
        "Costco_Wholesale": 30,
        "Marathon_Petroleum": 10,
        "Exxon_Mobil": 10,
        "Valero_Energy": 10,
        "Chevron": 10,
        "Alphabet": 50,
        "CVS_Health": 35,
        "Walmart": 30,
        "Cardinal_Health": 35,
        "Berkshire_Hathaway": 40,
        "JPMorgan_Chase": 40,
        "AmerisourceBergen": 35,
        "ConocoPhillips": 10,
        "AT&T": 50,
        "Amazon": 25,
        "Kroger": 30,
        "UnitedHealth_Group": 35,
        "Apple": 45
    }
    gics_mapping = {
        10: "Energy",
        15: "Materials",
        20: "Industrials",
        25: "Consumer Discretionary",
        30: "Consumer Staples",
        35: "Health Care",
        40: "Financials",
        45: "Information Technology",
        50: "Communication Services",
        55: "Utilities",
        60: "Real Estate"
    }
    gics_code = company_to_gics.get(company_name, None)
    gics_name = gics_mapping.get(gics_code, "") if gics_code else ""
    return gics_code, gics_name
def run_strategy_for_all(problemsFile):
    # companies = [
    #     'Tesla', 'McKesson', 'Elevance_Health', 'Costco_Wholesale', 'Marathon_Petroleum',
    #     'Exxon_Mobil', 'Valero_Energy', 'Chevron', 'Alphabet', 'CVS_Health', 'Walmart',
    #     'Cardinal_Health', 'Berkshire_Hathaway', 'JPMorgan_Chase', 'AmerisourceBergen',
    #     'ConocoPhillips', 'AT&T', 'Amazon', 'Kroger', 'UnitedHealth_Group', 'Apple'
    # ]

    companies = ['Berkshire_Hathaway']

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {executor.submit(run_strategy, company, False, problemsFile): company for company in companies}
        for future in concurrent.futures.as_completed(futures):
            company = futures[future]
            try:
                future.result()
                dprint(f"Strategy for {company} completed successfully.")
            except Exception as e:
                dprint(f"Strategy for {company} generated an exception: {e}")


def run_strategy(companyName, debug, problemsFile):
    dprint(f"debug is {debug}")
    if debug:
        dprint(f"debug is not true but not false?")
        # company_file_path = f"./Intermediates/local_company_data_{companyName}.json"
        # problem_file_path = f"./Intermediates/local_problem_{companyName}.json"
        # trends_file_path = f"./Intermediates/local_trends.json"
        # scenarios_return_file = f"./Intermediates/local_scenarios_return_{companyName}.json"
        # scenarios_response_file = f"./Intermediates/local_scenarios_response_{companyName}.json"
        # frameworks_file_path =f"./Intermediates/local_frameworks_file_{companyName}.json"
    else:
        with open(problemsFile, 'r') as file:
            problem_statements = json.load(file)
            # Retrieve the problem statement for the given company name
            statement = ""
        if companyName in problem_statements:
            statement = problem_statements[companyName]
            dprint(f"statement: {statement}")
        else:
            dprint(f"Problem statement not found for the specified company {companyName}.")

        problem_data = { "problem_statement": statement }
        dprint(f"problem_data: {problem_data}")
        problem_file_path = file_handler.write_local_json(f"problem_{companyName}",json.dumps(problem_data))
        dprint(f"problem_file_path: {problem_file_path}")
        gics_code, gics_name = get_gics_code_and_name(companyName)
        # dprint("gics_code: ", gics_code)
        # trends_file_path = f"./Intermediates/local_trends.json"
        # company_full_data = company_graph.dump_company_graph_to_json(companyName)
        company_full_data = dump_company_graph_to_plain_txt(companyName)
        trends = get_trends_from_gics_code(['00','45'])
        trends_file_path = file_handler.write_local_txt(f"company_trends_{companyName}",trends)
        dprint(f"company_full_data: {company_full_data}")
        # company_file_path = file_handler.write_local_json(f"company_data_{companyName}",company_full_data)
        company_file_path = file_handler.write_local_txt(f"company_data_{companyName}",company_full_data)

        agent_configs = [{'agent_type': "full_graph_scenario_agent"}]
        for path in [problem_file_path, trends_file_path, company_file_path]:
            print(f"Path: {path}")
        scenarios_manager = AgentManager(client, file_handler, agent_configs,
                                     [ problem_file_path, trends_file_path, company_file_path],use_qm_agents=True)
        scenarios_manager.run_workflow()
        scenarios_return = scenarios_manager.return_dict()
        scenarios_response = scenarios_manager.return_response
        scenarios_return_file = file_handler.write_local_json(f"scenarios_return_{companyName}",json.dumps(scenarios_return))
        response_dict = { "response_text" : scenarios_response}
        scenarios_response_file = file_handler.write_local_json(f"scenarios_response_{companyName}",json.dumps(response_dict))

        # company_file_path = f"./Intermediates/local_company_data_{companyName}.json"
        agent_configs = [{'agent_type': "full_graph_frameworks_agent"}]
        for path in [problem_file_path, trends_file_path, company_file_path]:
            print(f"Path: {path}")
        frameworks_manager = AgentManager(client, file_handler, agent_configs,
                                     [problem_file_path, trends_file_path, company_file_path],
                                          use_qm_agents=True)
   
        frameworks_manager.run_workflow()
        frameworks_dictionary_return = frameworks_manager.return_dict()
        frameworks_file_path = file_handler.write_local_json(f"frameworks_file_{companyName}",json.dumps(frameworks_dictionary_return))

    print(f"agent_type: reporting_agent")
    agent_configs = [{'agent_type': "reporting_agent"}]
    for path in [scenarios_response_file, scenarios_return_file,frameworks_file_path, trends_file_path]:
        print(f"Path: {path}")
    reporting_manager = AgentManager(client, file_handler, agent_configs,
                                     [scenarios_response_file, scenarios_return_file,frameworks_file_path, trends_file_path], use_qm_agents=True)
    reporting_manager.run_workflow()
    reporting_return = reporting_manager.return_dict()

    reporting_response = reporting_manager.return_response

    dprint(f"reporting_return: {json.dumps(reporting_return)}")

    report_path = f"./Strategic Reports/{companyName}_strategic_report.json"
    # Open the file in binary mode for writing; encode the text to bytes
    with open(report_path, "w") as file:
        file.write(json.dumps(reporting_return))

    template_path = './Strategic Reports/'
    reports_path = './Strategic Reports/'
    template_name = 'report_template.docx'
    # generator = StrategicReportGenerator(template_path, reports_path, template_name)
    # generator.generate_report(companyName)

def print_formatted_text(data):
    # Define the sections and titles for clarity
    sections = {
        'Background': "Background",
        'ProblemContext': "Problem in More Context",
        'CompanyAnalysis': "Analysis of the Question Given Company Information",
        'FrameworkApplication': "Application of Strategic Frameworks",
        'ScenarioAnalysis': "Scenario Analysis and Utility Scores",
        'ActionPlan': "Action Plan Development",
        'RiskMitigation': "Risk Mitigation",
        'Conclusions': "Conclusions and Summary"
    }

    # Loop through each section and print with headers
    for key, title in sections.items():
        print(f"{title}:\n{'=' * len(title)}\n{data[key]}\n")

def run_task(companyName, debug, problemsFile):
    if debug:
        pass
    else:
        with open(problemsFile, 'r') as file:
            problem_statements = json.load(file)
            # Retrieve the problem statement for the given company name
            statement = ""
        if companyName in problem_statements:
            statement = problem_statements[companyName]
            dprint(f"statement: {statement}")
        else:
            dprint(f"Problem statement not found for the specified company {companyName}.")
        problem_data = {"problem_statement": statement}
        dprint(f"problem_data: {problem_data}")
        problem_file_path = file_handler.write_local_json(f"problem_{companyName}", json.dumps(problem_data))
        dprint(f"problem_file_path: {problem_file_path}")
        gics_code, gics_name = get_gics_code_and_name(companyName)
        dprint("gics_code: ", gics_code)
        trends_file_path = f"./Intermediates/local_trends.json"
        company_full_data = company_graph.dump_company_graph_to_json(companyName)
        company_file_path = file_handler.write_local_json(f"company_data_{companyName}", company_full_data)
        exemplar_path = f"/Users/adrian/Documents/Strategic Reports/pick/Marathon_petroleum_strategic_report.docx"
        agent_configs = [{'agent_type': "strategic_problem_agent"}]
        agent_manager = AgentManager(client, file_handler, agent_configs,
                                     [problem_file_path, trends_file_path, company_file_path],
                                     use_qm_agents=True,
                                     qm_inputs=[exemplar_path],
                                     )
        agent_manager.run_workflow()
        agent_dictionary_return = agent_manager.return_dict()
        dprint(f"Agent file has returned {agent_dictionary_return}")
        dprint(f"agent_dict={agent_dictionary_return}")

def generic_agent_run(agentType, reportType, companyName, updateGraph, debugRun):
    # TODO needs a generic intermediates write adding
    # TODO can be made more generic by defining the graph input -> agent function -> graph output
    if debugRun:
        # TODO debugRun needs to be incremental not wholesale
        agent_dictionary_return = file_handler.local_json_read(f"debug_{agentType}_{companyName}.json")
    else:
        # get the graph data to send to agent
        json_graph = company_graph.dump_company_insight_graph_to_json(companyName)
        file_path = file_handler.write_local_json("graph_upload_",json_graph)
        agent_configs = [{'agent_type': agentType}]
        agent_manager = AgentManager(client, file_handler, agent_configs, [file_path])
        agent_manager.run_workflow()
        agent_dictionary_return = agent_manager.return_dict()
        dprint(f"Agent file has returned {agent_dictionary_return}")
        dprint(f"agent_dict={agent_dictionary_return}")
    if updateGraph:
        company_graph.generic_update_graph(companyName, agent_dictionary_return, agentType)
    for item in agent_dictionary_return:
        dprint(item)


if __name__ == '__main__':
    main()
