import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
from agent_workflow_manager import AgentManager
from graph_workflow.full_graph import (
    dump_company_graph_to_plain_txt,
    dump_company_graph_to_json,
    get_trends_from_gics_code,
    save_curated_trend_data,
    get_curated_trend_data,
    save_condensed_trend_data,
    get_condensed_trend_data,
    save_condensed_company_data,
    get_condensed_company_data,
)
from filehandler import FileHandler
from graph_workflow.build_graph import fill_graph
from graph_workflow.extract_insights import get_insights
from graph_workflow.trends.trends_analyser import generate_trends
from graph_workflow.trends.clustering_trend import cluster_trends
from graph_workflow.clustering import generate_capabilities_per_cluster
from chains import (
    chain_scenario,
    chain_framework,
    chain_report,
    summary_chain,
    generate_report_plan,
)
from report_agent import Agent as ReportAgent
from report_agent import get_subsections, find_and_fill
import json, re
from model_connector import ModelConnectorFactory
import datetime

from utility import (
    dict_to_plain_text,
    json_to_markdown,
    dict_to_markdown,
    retry,
    condense,
    invoke,
    report_to_markdown,
)

from config.conf import setup_config, read_config
import logging
import logging.config

#from decomp_task.execute import run_decomp

d = datetime.datetime.now()
d = d.strftime("%m-%d-%Y %H:%M:%S")


if "socrates_main" not in logging.root.manager.loggerDict.keys():
    logging.config.fileConfig(
        "config/logging_config_socrates.ini",
        defaults={"date": datetime.datetime.now()},
        disable_existing_loggers=True,
    )


logger = logging.getLogger("socrates_main")

logger.info("Started")
# Example usage
model_config = {
    "model_type": "openai_chat",
    "api_key": os.getenv("OPENAI_API_KEY"),
    "model": "o1-preview",
    #'model': 'gpt-3.5-turbo',
}
file_handler = FileHandler()

connector = ModelConnectorFactory.create_connector(model_config, file_handler)
client = connector.client

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
    60: "Real Estate",
}

# This is the local file handler. remote files are dealt with in ModelConnector


def execute_workflow(workflow_config=workflow_config):
    """Executes the workflow steps based on the configuration."""
    logger.debug(f"workflow config is {workflow_config}")
    logger.debug("Enabled workflow steps:")
    for step_name, details in workflow_config.items():
        logger.info(f"- {step_name}")
        logger.info(f"details: {details}")
        step = details.get("step", step_name)
        logger.info(f"step: {step}")
        if details.get("enabled", False):
            func = get_step_function(step)
            run_id = step_name + "_" + str(datetime.datetime.now())
            setup_config(**{"run_id": run_id})

            if func:
                # Unpack all parameters dynamically for the function
                parameters = details.get("parameters", {})
                logger.debug(
                    f"- Executing {step_name} with parameters: {parameters}..."
                )
                func(**parameters)  # Use ** to unpack and pass named parameters
            else:
                logger.debug(f"No function defined for {step}.")
    logger.debug("Finished workflow steps.")


def main():
    enabled_steps = [
        step for step, details in workflow_config.items() if details["enabled"]
    ]
    logger.debug("Enabled workflow steps:")
    for step in enabled_steps:
        logger.debug(f"- {step}")
    execute_workflow()


def get_step_function(step_name):
    """
    Returns the function mapped to the specified workflow step without executing it.
    """
    step_map = {
        # administrative routines
        "cleanUp": clean_up,
        # graph manipulation and display routines
        "fillGraph": fill_graph,
        "getInsights": get_insights,
        "condenseTrends": condense_trends,
        "condenseCompanyData": condense_company_data,
        "getCapabilities": generate_capabilities_per_cluster,
        "getTrends": generate_trends,
        "clusterTrends": cluster_trends,
        "runStrategy": run_strategy,
        "runFrameworks": run_frameworks,
        "runScenarios": run_scenarios,
        "runReport": run_report,
        #"runReport2": run_decomp,
    }
    return step_map.get(step_name, None)
    #    Note: camelCase naming denotes parameters directly inherited from the json config file


def get_capabilities(companyName, problemsFile):
    """
    Generates the capabilities for a given company.
    """
    company_name = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(company_name, problemsFile)
    problem_file_path = file_handler.write_local_json(
        f"problem_{company_name}", json.dumps(problem_data)
    )
    company_full_data = get_company_data(companyName, problem_data)
    capabilities = generate_capabilities_per_cluster(
        [company_name], compute_embeddings=True, number_of_processes=5
    )
    logger.debug("capabilities:", capabilities)
    return capabilities


def condense_trends(company_name, problemsFile):
    gics_code, _ = get_gics_code_and_name(company_name)
    trends = get_curated_trend_data(company_name, gics_code, problemsFile)
    problem = get_problem(company_name, problemsFile)
    context = problem
    subject = f"""
The trends impacting {company_name}
    """
    if not trends:
        trends = get_trends_from_gics_code(gics_code, problem)
        trends = trends["trends"]
        save_curated_trend_data(company_name, gics_code, problem, trends)
    condensed_trends = condense(
        trends,
        "statement",
        context,
        subject,
        number_of_clusters=10,
        number_of_processes=5,
    )

    save_condensed_trend_data(company_name, problem, condensed_trends)


def condense_company_data(company_name, problem):
    # problem = get_problem(company_name, problemsFile)
    logger.info("company_name", company_name)
    logger.info("problem", problem)
    company_data = dump_company_graph_to_json(company_name, problem)

    # the full capabilities
    logger.info("company_data", company_data)
    context = problem
    subject = f"""
The insights and capabilities of {company_name}
    """
    company_data_full = [x for x in company_data["insights"]]
    company_data_full.extend([x for x in company_data["capabilities"]])
    condensed_company_data = condense(
        company_data_full,
        "statement",
        context,
        subject,
        number_of_clusters=50,
        number_of_processes=5,
    )
    logger.info("Saving condensed company data")
    save_condensed_company_data(company_name, problem, condensed_company_data)


def get_problem(company_name, problemsFile):
    """
    Retrieves the problem statement for a given company from a JSON file.
    """
    with open(problemsFile, "r") as file:
        problem_statements = json.load(file)
        # Retrieve the problem statement for the given company name
        statement = ""
    if company_name in problem_statements:
        statement = problem_statements[company_name]
        return statement.replace("'", "\\'")
    else:
        logger.debug(
            f"Problem statement not found for the specified company {company_name}."
        )
        raise Exception(
            f"Problem statement not found for the specified company {company_name}."
        )


def get_trends(company_name, problemFile, force_recreate=False):
    """
    Retrieves the trends for a given company.
    Will load from archive if available, otherwise will generate new trends unless force_recreate is set to True.
    Will store to archive after generation.
    """
    problem = get_problem(company_name, problemFile)
    gics_code, gics_name = get_gics_code_and_name(company_name)
    logger.debug(f"gics_code: {gics_code}")
    condense_trend_data = get_condensed_trend_data(company_name, problem)
    curated_trend_data = get_curated_trend_data(company_name, gics_code, problem)

    trend_data = None  # Initialize trend_data

    if condense_trend_data and not force_recreate:
        logger.debug(f"Loaded condensed trends from archive")
        trend_data = condense_trend_data
    elif curated_trend_data and not force_recreate:
        logger.debug(f"Loaded trends from archive")
        trend_data = condense_trends(company_name, problemFile)
    else:
        curated_trend_data = get_trends_from_gics_code(gics_code, problem)
        logger.debug(f"Generated trends")
        save_curated_trend_data(company_name, gics_code, problem, curated_trend_data)
        trend_data = condense_trends(company_name, problemFile)
        logger.debug(f"Saved trends to archive")

    # implement validation and checking of trends

    return trend_data


def get_company_data(companyName, problem_statement):
    """
    Retrieves the full data for a given company
    """
    logger.debug(" calling get_company_data with companyName: ", companyName)
    condensed_company_data = get_condensed_company_data(companyName, problem_statement)
    if condensed_company_data:
        logger.debug(f"Loaded condensed company data from archive")
        company_full_data = condensed_company_data
    else:
        condense_company_data(companyName, problem_statement)
        logger.info("Getting condensed company data")
        company_full_data = get_condensed_company_data(companyName, problem_statement)
    # implement validation and checking of trends
    return company_full_data


def clean_up():
    connector.clean_up()


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
    filename = re.sub(
        r"[^a-z0-9 ]", "", normalized_name
    )  # Remove anything not a letter, number, or space
    filename = filename.replace(" ", "_")  # Replace spaces with underscores

    # Add the .json extension
    filename += ".json"
    return filename


def get_gics_code_and_name(company_name):
    company_to_gics = {
        "Tesla": [25],
        "McKesson": [35],
        "Elevance_Health": [35],
        "Costco_Wholesale": [30],
        "Marathon_Petroleum": [10],
        "Exxon_Mobil": [10],
        "Valero_Energy": [10],
        "Chevron": [10],
        "Alphabet": [50],
        "CVS_Health": [35],
        "Walmart": [30],
        "Cardinal_Health": [35],
        "Berkshire_Hathaway": [40],
        "JPMorgan_Chase": [40],
        "AmerisourceBergen": [35],
        "ConocoPhillips": [10],
        "AT&T": [50],
        "Amazon": [25],
        "Kroger": [30],
        "UnitedHealth_Group": [35],
        "Apple": [45],
        "Phillips_66": [10],
        "Ford Motor": [25],
        "Home Depot": [25],
        "General Motors": [25],
        "Centene": [35],
        "Verizon Communications": [35],
        "Walgreens Boots Alliance": [30],
        "Fannie Mae": [40],
        "Comcast": [50],
        "Meta Platforms": [50],
        "Bank of America": [40],
        "Target": [30],
        "Dell Technologies": [45],
        "Archer Daniels Midland": [30],
        "Citigroup": [40],
        "United Parcel Service": [20],
        "Pfizer": [35],
        "Lowe's": [20],
        "Johnson & Johnson": [35],
        "FedEx": [20],
        "Humana": [35],
        "Energy Transfer": [10],
        "State Farm Insurance": [40],
        "Freddie Mac": [40],
        "PepsiCo": [30],
        "Wells Fargo": [40],
        "Walt Disney": [50],
        "Procter & Gamble": [30],
        "General Electric": [20],
        "Albertsons": [30],
        "MetLife": [40],
        "Goldman Sachs Group": [40],
        "Sysco": [30],
        "Raytheon Technologies": [20],
        "Boeing": [20],
        "StoneX Group": [40],
        "Lockheed Martin": [20],
        "Morgan Stanley": [40],
        "Intel": [45],
        "HP": [45],
        "nag": [45],
        "TD Synnex": [45],
        "International Business Machines": [45],
        "HCA Healthcare": [35],
        "Prudential Financial": [40],
        "Caterpillar": [20],
        "Merck": [35],
        "World Fuel Services": [10],
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
        60: "Real Estate",
    }
    logger.info(f"company_name: {company_name}")
    gics_code = company_to_gics.get(company_name, None)
    logger.info(f"gics_code: {gics_code}")
    gics_name = [gics_mapping.get(g_code, "") if g_code else "" for g_code in gics_code]
    return gics_code, gics_name
def get_file_paths(company_name, problemsFile):
    """
    Give a single company, extracts the problem, company and trend data
    and generates files suitable for agent processing
    """
    conf = read_config()
    run_id = "_" + conf.get("run_id")

    company_name = company_name.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(company_name, problemsFile)
    problem_file_path = file_handler.write_local_json(
        f"problem_{company_name}" + run_id, json.dumps(problem_data)
    )
    trends = get_trends(company_name, problemsFile, force_recreate=False)
    company_full_data = get_company_data(company_name, problem_data)

    trends_file_path = file_handler.write_local_json(
        f"company_trends_{company_name}" + run_id, json.dumps(trends)
    )

    company_file_path = file_handler.write_local_json(
        f"company_data_{company_name}" + run_id, json.dumps(company_full_data)
    )
    return problem_file_path, trends_file_path, company_file_path


def run_scenarios(companyName, problemsFile):
    """
    Runs the stand-alone scenarios analysis for a single company
    """
    company_name = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        company_name, problemsFile
    )
    scenarios_return_file = generate_scenarios(
        company_name, problem_file_path, trends_file_path, company_file_path
    )

    # Add validation and quality checks of scenarios outputs
    logger.debug(
        f"The final scenarios output is available in file {scenarios_return_file}"
    )


def generate_scenarios(
    company_name, problem_file_path, trends_file_path, company_file_path
):
    conf = read_config()
    run_id = "_" + conf.get("run_id")
    """
    Executes the scenarios agent  for a single company
    """
    agent_configs = [{"agent_type": "full_graph_connector_scenario_agent"}]
    scenarios_manager = AgentManager(
        connector,
        file_handler,
        agent_configs,
        [problem_file_path, trends_file_path, company_file_path],
        use_qm_agents=True,
    )
    scenarios_manager.run_workflow()
    scenarios_return_data = scenarios_manager.return_dict()
    scenarios_local_response, scenarios_local_output = connector.write_output_to_local(
        f"scenarios_output_{company_name}", scenarios_return_data
    )
    return scenarios_local_response, scenarios_local_output


def run_frameworks(companyName, problemsFile):
    """
    Runs a stand-alone frameworks agent for a single company
    """
    company_name = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        company_name, problemsFile
    )
    frameworks_file = generate_frameworks(
        company_name, problem_file_path, trends_file_path, company_file_path
    )
    logger.debug(f"the frameworks output file is {frameworks_file}")
    # Add validation and quality checks of frameworks outputs


def generate_frameworks(
    company_name, problem_file_path, trends_file_path, company_file_path
):
    """
    Executes the frameworks agent  for a single company
    """

    conf = read_config()
    run_id = "_" + conf.get("run_id")

    agent_configs = [{"agent_type": "full_graph_frameworks_agent"}]
    for path in [problem_file_path, trends_file_path, company_file_path]:
        logger.info(f"Path: {path}")
    frameworks_manager = AgentManager(
        connector,
        file_handler,
        agent_configs,
        [problem_file_path, trends_file_path, company_file_path],
        use_qm_agents=True,
    )
    frameworks_manager.run_workflow()
    frameworks_return_data = frameworks_manager.return_dict()
    frameworks_response, frameworks_local_output = connector.write_output_to_local(
        f"frameworks_output_{company_name}", frameworks_return_data
    )
    # frameworks_output = frameworks_dictionary_return.get("output_file")
    # logger.debug(f"the frameworks output file is {frameworks_output}")
    # frameworks_return_local_file = connector.download_and_write_local(
    #     f"frameworks_output_{company_name}" + run_id, frameworks_output
    # )
    return frameworks_local_output


def run_report(companyName, problemsFile):
    """
    Runs a stand-alone report generation for a single company
    """

    conf = read_config()
    run_id = "_" + conf.get("run_id")

    company_name = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        company_name, problemsFile
    )

    scenarios_response_file = (
        f"./Intermediates/local_scenarios_response_{company_name}.json"
    )
    scenarios_return_file = (
        f"./Intermediates/local_scenarios_return_{company_name}.json"
    )
    frameworks_file_path = f"./Intermediates/local_frameworks_file_{company_name}.json"

    reporting_return_file = generate_report(
        company_name,
        scenarios_response_file,
        scenarios_return_file,
        frameworks_file_path,
        trends_file_path,
    )
    if reporting_return_file:
        report_content = connector.download_and_write_local(
            f"strategic_report_{company_name}" + run_id, reporting_return_file
        )
        logger.debug(
            f"completed report generation for {company_name} at file {reporting_return_file}"
        )
    else:
        logger.debug(f"Error: Report generation for {company_name} failed")


def generate_report(
    company_name,
    scenarios_response_file,
    scenarios_return_file,
    frameworks_file_path,
    trends_file_path,
):
    """
    Executes the report generation for a single company
    """
    conf = read_config()
    run_id = "_" + conf.get("run_id")
    logger.info(f"agent_type: full_graph_reporting_agent")
    agent_configs = [{"agent_type": "full_graph_reporting_agent"}]
    reporting_manager = AgentManager(
        connector,
        file_handler,
        agent_configs,
        [
            scenarios_response_file,
            scenarios_return_file,
            frameworks_file_path,
            trends_file_path,
        ],
        use_qm_agents=True,
    )
    reporting_manager.run_workflow()
    reporting_return = reporting_manager.return_dict()
    reporting_output_file = reporting_return["output_file"]
    reporting_output_local_file = connector.download_and_write_local(
        f"strategic_report_{company_name}" + run_id, reporting_output_file
    )
    return reporting_output_local_file


@retry(number_of_retry=1)  # Retry the function once in case of failure
def run_strategy(companyName, problemsFile):
    """
    Executes the strategic analysis process for a given company.
    (this is the full workload automation)
    """
    company_name = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    # Get the files and paths for the necessary files related to the company and problem
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        company_name, problemsFile
    )
    # Generate scenarios using the scenarios agent
    scenarios_response, scenarios_return_file = generate_scenarios(
        companyName, problem_file_path, trends_file_path, company_file_path
    )

    scenarios_response_file = file_handler.write_local_json(
        f"scenarios_{company_name}", json.dumps(scenarios_response)
    )
    logger.info(f"scenarios_response_file: {scenarios_response_file}")

    # logger.info(connector.retrieve_file_content(scenarios_response_file))
    # assert scenarios_response_file.startswith("./Intermediates")

    # logger.info(f"scenarios_return_file: {scenarios_return_file}")
    # assert scenarios_return_file.startswith("./Intermediates")
    # Generate frameworks using the frameworks agent
    frameworks_file_path = generate_frameworks(
        company_name, problem_file_path, trends_file_path, company_file_path
    )

    # logger.info(f"frameworks_file_path: {frameworks_file_path}")
    # assert frameworks_file_path.startswith("./Intermediates")
    # Generate a strategic report using the reporting agent
    logger.info(f"scenarios_response_file: {scenarios_response_file}")
    logger.info(f"scenarios_return_file: {scenarios_return_file}")
    logger.info(f"frameworks_file_path: {frameworks_file_path}")
    reporting_return_file = generate_report(
        company_name,
        scenarios_response_file,
        scenarios_return_file,
        frameworks_file_path,
        trends_file_path,
    )

    logger.info(f"reporting_return_file: {reporting_return_file}")
    # assert reporting_return_file.startswith("./Intermediates")
    # report_content = connector.download_and_write_local(f"_strategic_report_{company_name}", reporting_return_file)
    logger.debug(
        f"completed strategic analysis for {company_name} at file {reporting_return_file}"
    )
    # with open(report_path, "w") as file:
    #     file.write(json.dumps(reporting_return))
    # # Convert the report to markdown format
    # markdown = dict_to_markdown(reporting_return)
    # markdown = "# " + companyName + " Strategic Report\n\n" + markdown
    # # Write the markdown report to a file
    # with open(f"./Strategic Reports/{companyName}_strategic_report.md", "w") as file:
    #     file.write(markdown)

if __name__ == "__main__":
    main()
