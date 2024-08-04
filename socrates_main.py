import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
from agent_workflow_manager import AgentManager
from debug import dprint
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
from agent_thread import (
    delete_assistants_clones,
    delete_all_uploaded_files,
    delete_not_known_assistants,
    delete_files_less_than_1_hour,
)

from model_connector import ModelConnectorFactory
from utility import (
    dict_to_plain_text,
    json_to_markdown,
    dict_to_markdown,
    retry,
    condense,
    invoke,
    report_to_markdown,
)

# Example usage
model_config = {
    'model_type': 'openai_assistants',
    'api_key': os.getenv("OPENAI_API_KEY"),
    'model': 'gpt-4o',
    'max_tokens': 150
}
file_handler = FileHandler()

connector = ModelConnectorFactory.create_connector( model_config, file_handler)
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

def execute_workflow():
    """Executes the workflow steps based on the configuration."""
    dprint(f"workflow config is {workflow_config}")
    dprint("Enabled workflow steps:")
    for step_name, details in workflow_config.items():
        step = details.get("step", step_name)
        if details.get("enabled", False):
            func = get_step_function(step)
            if func:
                # Unpack all parameters dynamically for the function
                parameters = details.get("parameters", {})
                dprint(f"- Executing {step_name} with parameters: {parameters}...")
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
        "getCapabilities": get_capabilities,
        "getTrends": generate_trends,
        "runData": run_data,
        "clusterTrends": cluster_trends,
        "runStrategy": run_strategy,
        "runFrameworks": run_frameworks,
        "runScenarios": run_scenarios,
        "runStrategyChains": run_strategy_chains,
        "runStrategyDynamicReport": run_strategy_report_agent,
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
        company_name, problem_data)
    dprint('capabilities:', capabilities)
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
    company_data = dump_company_graph_to_json(company_name, problem)

    # the full capabilities

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
    print("Saving condensed company data")
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
        dprint(f"Problem statement not found for the specified company {company_name}.")
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
    dprint(f"gics_code: {gics_code}")
    condense_trend_data = get_condensed_trend_data(company_name, problem)
    curated_trend_data = get_curated_trend_data(company_name, gics_code, problem)

    trend_data = None  # Initialize trend_data

    if condense_trend_data and not force_recreate:
        dprint(f"Loaded condensed trends from archive")
        trend_data = condense_trend_data
    elif curated_trend_data and not force_recreate:
        dprint(f"Loaded trends from archive")
        trend_data = condense_trends(company_name, problemFile)
    else:
        curated_trend_data = get_trends_from_gics_code(gics_code, problem)
        dprint(f"Generated trends")
        save_curated_trend_data(company_name, gics_code, problem, curated_trend_data)
        trend_data = condense_trends(company_name, problemFile)
        dprint(f"Saved trends to archive")

    # implement validation and checking of trends

    return trend_data


def get_company_data(companyName, problem_statement):
    """
    Retrieves the full data for a given company
    """
    dprint(" calling get_company_data with companyName: ", companyName)
    condensed_company_data = get_condensed_company_data(companyName, problem_statement)
    if condensed_company_data:
        dprint(f"Loaded condensed company data from archive")
        company_full_data = condensed_company_data
    else:
        condense_company_data(companyName, problem_statement)
        print("Getting condensed company data")
        company_full_data = get_condensed_company_data(companyName, problem_statement)
    # implement validation and checking of trends
    return company_full_data

def clean_up():
    # Aggressive Cleanup of assistants and files
    # except for those and all files
    deleted = delete_assistants_clones(client)
    deleted = deleted_files = None
    # deleted = delete_not_known_assistants(client)
    # deleted_files = delete_files_less_than_1_hour(client)
    # deleted_files = delete_all_uploaded_files(client)
    # dprint(f"Deleted {deleted} assistants and {deleted_files} files")


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
    print(f"company_name: {company_name}")
    gics_code = company_to_gics.get(company_name, None)
    print(f"gics_code: {gics_code}")
    gics_name = [gics_mapping.get(g_code, "") if g_code else "" for g_code in gics_code]
    return gics_code, gics_name


def get_file_paths(company_name, problemsFile):
    """
    Give a single company, extracts the problem, company and trend data
    and generates files suitable for agent processing
    """
    company_name = company_name.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(company_name, problemsFile)
    problem_file_path = file_handler.write_local_json(
        f"problem_{company_name}", json.dumps(problem_data)
    )
    trends = get_trends(company_name, problemsFile, force_recreate=False)
    company_full_data = get_company_data(company_name, problem_data)

    trends_file_path = file_handler.write_local_json(
        f"company_trends_{company_name}", json.dumps(trends)
    )

    company_file_path = file_handler.write_local_json(
        f"company_data_{company_name}", json.dumps(company_full_data)
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
    scenarios_return_file, scenarios_response_file = generate_scenarios(
        company_name, problem_file_path, trends_file_path, company_file_path
    )

    # Add validation and quality checks of scenarios outputs

    return scenarios_return_file, scenarios_response_file


def generate_scenarios(
    company_name, problem_file_path, trends_file_path, company_file_path
):
    """
    Executes the scenarios agent  for a single company
    """
    agent_configs = [{"agent_type": "full_graph_scenario_agent"}]
    scenarios_manager = AgentManager(
        connector,
        file_handler,
        agent_configs,
        [problem_file_path, trends_file_path, company_file_path],
        use_qm_agents=True,
    )
    scenarios_manager.run_workflow()
    scenarios_return_data = scenarios_manager.return_dict()
    scenarios_response = scenarios_manager.agent_response

    scenarios_output = scenarios_return_data.get("output_file")
    # scenarios_return_file = file_handler.write_local_json(
    #     f"scenarios_return_{company_name}", json.dumps(scenarios_return)
    # )
    # response_dict = {"response_text": scenarios_response}
    # scenarios_response_file = file_handler.write_local_json(
    #     f"scenarios_response_{company_name}", json.dumps(response_dict)
    # )
    # TODO no need to download and write  unless there is an intermediate file requested
    scenarios_response_file = file_handler.write_local_json(
        f"scenarios_{company_name}", json.dumps(scenarios_response)
    )
    scenarios_return_file = connector.download_and_write_local(f"_scenarios_output_{company_name}", scenarios_output )
    print(f"completed scenarios for {company_name}")
    return scenarios_response_file, scenarios_return_file


def run_frameworks(companyName, problemsFile):
    """
    Runs a stand-alone frameworks agent for a single company
    """
    company_name = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        company_name, problemsFile
    )
    frameworks_file_path = generate_frameworks(
        company_name, problem_file_path, trends_file_path, company_file_path
    )
    # Add validation and quality checks of frameworks outputs

    return frameworks_file_path


def generate_frameworks(
    company_name, problem_file_path, trends_file_path, company_file_path
):
    """
    Executes the frameworks agent  for a single company
    """
    agent_configs = [{"agent_type": "full_graph_frameworks_agent"}]
    for path in [problem_file_path, trends_file_path, company_file_path]:
        print(f"Path: {path}")
    frameworks_manager = AgentManager(
        connector,
        file_handler,
        agent_configs,
        [problem_file_path, trends_file_path, company_file_path],
        use_qm_agents=True,
    )
    frameworks_manager.run_workflow()
    frameworks_dictionary_return = frameworks_manager.return_dict()
    frameworks_file_path = file_handler.write_local_json(
        f"frameworks_file_{company_name}", json.dumps(frameworks_dictionary_return)
    )
    return frameworks_file_path


def run_report(company_name, problemsFile):
    """
    Runs a stand-alone report generation for a single company
    """
    company_name = company_name.replace(" ", "_").replace(".", "").replace("'", "")
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        company_name, problemsFile
    )

    # retrieve stored Scenarios

    # retrieve stored Frameworks

    # generate report


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
    print(f"agent_type: full_graph_reporting_agent")
    agent_configs = [{"agent_type": "reporting_agent_strong"}]
    for path in [
        scenarios_response_file,
        scenarios_return_file,
        frameworks_file_path,
        trends_file_path,
    ]:
        print(f"Path: {path}")
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
    reporting_response = reporting_manager.return_response
    return reporting_return, reporting_response


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
    scenarios_return_file, scenarios_response_file = generate_scenarios(
        companyName, problem_file_path, trends_file_path, company_file_path
    )
    # Generate frameworks using the frameworks agent
    frameworks_file_path = generate_frameworks(
        company_name, problem_file_path, trends_file_path, company_file_path
    )
    report_path = f"./Strategic Reports/{companyName}_strategic_report.json"
    # Generate a strategic report using the reporting agent
    reporting_return, reporting_response = generate_report(
        company_name,
        scenarios_response_file,
        scenarios_return_file,
        frameworks_file_path,
        trends_file_path,
    )
    with open(report_path, "w") as file:
        file.write(json.dumps(reporting_return))
    # Convert the report to markdown format
    markdown = dict_to_markdown(reporting_return)
    markdown = "# " + companyName + " Strategic Report\n\n" + markdown
    # Write the markdown report to a file
    with open(f"./Strategic Reports/{companyName}_strategic_report.md", "w") as file:
        file.write(markdown)
def run_data(companyName, problemsFile):
    companyName = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(companyName, problemsFile)

    # Get the files and paths for the necessary files related to the company and problem
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        companyName, problemsFile
    )

    with open(trends_file_path, "r") as file:
        trends_data = json.load(file)
    with open(company_file_path, "r") as file:
        company_data = json.load(file)



def run_strategy_chains(companyName, problemsFile):
    companyName = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(companyName, problemsFile)

    # Get the files and paths for the necessary files related to the company and problem
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        companyName, problemsFile
    )

    with open(trends_file_path, "r") as file:
        trends_data = json.load(file)
    with open(company_file_path, "r") as file:
        company_data = json.load(file)

    print("starting scenario chain")
    print(
        [
            len(x)
            for x in [
                dict_to_plain_text(problem_data),
                dict_to_plain_text(trends_data),
                dict_to_plain_text(company_data),
            ]
        ]
    )

    output_scenario = invoke(
        chain_scenario,
        {
            "problem_statement": dict_to_plain_text(problem_data),
            "trend_document": dict_to_plain_text(trends_data),
            "company_data": dict_to_plain_text(company_data),
            "company_name": "Tesla",
        },
    )

    print("starting framework chain")

    output_framework = invoke(
        chain_framework,
        {
            "problem_statement": dict_to_plain_text(problem_data),
            "trend_document": dict_to_plain_text(trends_data),
            "company_data": dict_to_plain_text(company_data),
            "company_name": "Tesla",
        },
    )
    with open("Intermediates/scenario_output.json", "w") as file:
        json.dump(output_scenario, file, indent=4)

    with open("Intermediates/framework_output.json", "w") as file:
        json.dump(output_framework, file, indent=4)

    print("starting report chain")
    print(
        [
            len(x)
            for x in [
                dict_to_plain_text(company_data),
                dict_to_plain_text(output_scenario),
                dict_to_plain_text(output_framework),
                dict_to_plain_text(trends_data),
            ]
        ]
    )
    output_report = invoke(
        chain_report,
        {
            "company_data": dict_to_plain_text(company_data),
            "scenario_analysis": dict_to_plain_text(output_scenario),
            "framework_analysis": dict_to_plain_text(output_framework),
            "trends": dict_to_plain_text(trends_data),
        },
    )

    print(output_report)
    # Define the output file path
    output_file = f"Strategic Reports/report_{companyName}.txt"

    # Write the report to the output file
    with open(output_file, "w") as file:
        file.write(output_report)


def run_strategy_report_agent(companyName, problemsFile):
    rp_ag = ReportAgent("reporter")
    rp_ag.set_tools([])
    rp_ag.build()
    companyName = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(companyName, problemsFile)

    # Get the files and paths for the necessary files related to the company and problem
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        companyName, problemsFile
    )

    with open(trends_file_path, "r") as file:
        trends_data = json.load(file)
    with open(company_file_path, "r") as file:
        company_data = json.load(file)

    summary_company = summary_chain.invoke(
        {
            "company": companyName,
            "problem_statement": problem_data,
            "data": dict_to_plain_text(company_data),
        }
    )
    summary_trends = summary_chain.invoke(
        {
            "company": companyName,
            "problem_statement": problem_data,
            "data": dict_to_plain_text(trends_data),
        }
    )

    # with open("company_summary.txt", "r") as file:
    #     summary_company = file.read()
    # with open("trends_summary.txt", "r") as file:
    #     summary_trends = file.read()

    # Write summaries to text files
    with open(f"Intermediates/{companyName}_company_summary.txt", "w") as file:
        file.write(summary_company)
    with open(f"Intermediates/{companyName}_trends_summary.txt", "w") as file:
        file.write(summary_trends)

    data_summary = (
        "Company data summary: "
        + summary_company
        + "\n"
        + "Trends data summary: "
        + summary_trends
    )
    print(
        {
            "data_summary": data_summary,
            "problem_statement": problem_data,
            "company": companyName,
        }
    )
    plan_data = {
        "data_summary": data_summary,
        "problem_statement": problem_data,
        "company": companyName,
    }
    # plan = evaluate_capability_cluster.invoke(plan_data)
    # print(plan)
    plan = generate_report_plan.invoke(plan_data)
    print(json.dumps(plan, indent=4))
    with open("plan.json", "w") as file:
        file.write(json.dumps(plan, indent=4))
    report = plan.copy()
    print(plan)
    for title, content in get_subsections(plan["plan"], "content_statement"):
        data_input = f"""
company data:
{company_data}

Trends:
{trends_data}
"""

        output = invoke(
            rp_ag.writing_chain,
            {
                "report_structure": dict_to_plain_text(plan),
                "data_input": data_input,
                "content_section": title + ": " + content + "\n\n" + problem_data,
            },
        )
        print("************")
        # print(output)
        print(output.keys())
        print(len(output["content"]))
        print(len(output["content_summary"]))
        print("************")
        print(title + ": " + content)
        # contentSection.model_validate(output)
        print("************")
        print("\n\n\n")
        # print(report)
        print("\n\n\n")
        find_and_fill(
            report,
            title,
            output["title"],
            output["content"],
            output["data_needed"],
            output["content_statements"],
        )
        # print(report)
        # assert 1 ==2
    with open(f"Strategic Reports/report_{companyName}.json", "w") as file:
        json.dump(report, file)

    print(report)
    markdown = report_to_markdown(report["plan"], "")

    with open(
        f"Strategic Reports/report_{companyName}_technical_assessment.md", "w"
    ) as file:
        file.write(markdown)


if __name__ == "__main__":
    main()
