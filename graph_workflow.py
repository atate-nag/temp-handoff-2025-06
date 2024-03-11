from neo4j import GraphDatabase
from dochandler import Rdoc
import os
import openai
from dotenv import load_dotenv
from run_assistant_thread import parallel_file_process, import_data_files_and_upload
from graph import CompanyGraph, InsightGraph, map_json_to_company_schema
from insight_node import InsightManager
from dochandler import import_data_files
import json

# setup openaAI

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# setup neo4j database

uri = "bolt://localhost:7687"
user = "neo4j"
password = "naginnov"

def get_step_function(step_name):
    """
    Returns the function mapped to the specified workflow step without executing it.
    """
    step_map = {
        "createCompanies": create_companies,
        "updateCompanyData": update_company_data,
        "deleteInsights":delete_insights,
    }
    return step_map.get(step_name, None)  # Return None if not found
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



# Following are the workflow functionality functions
def create_companies(company_name):
    global company_graph
    print(f"Creating company {company_name}")
    company_graph.create_company_only(company_name)

def update_company_data(dataDir, companyName):
    company_data_dir = os.path.join(dataDir, companyName)
    print(f"Dir for company is {company_data_dir}")
    if os.path.exists(company_data_dir):
        print(f"Importing data for {companyName} at {company_data_dir}...")
        remote_openai_company_data, company_data_doc = import_data_files_and_upload(client,
                                                            company_data_dir, "data")
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

def extract_insights(source_dir):
    print("Extracting insights...")
    return

def update_insights():
    print("Updating insights...")
    return

def delete_insights(companyName):
    print("Deleting insights...")
    company_graph.delete_company_insights(companyName)
    company_graph.delete_orphan_insights()
    return

# Load the workflow configuration
with open('workflow_config.json', 'r') as file:
    config = json.load(file)

workflow_config = config['workflow']
global company_graph
company_graph = CompanyGraph(uri, user, password)

# Collect and print enabled workflow steps
enabled_steps = [step for step, details in workflow_config.items() if details['enabled']]
print("Enabled workflow steps:")
for step in enabled_steps:
    print(f"- {step}")

execute_workflow()