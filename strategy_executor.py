import os
import openai
from dotenv import load_dotenv
from run_assistant_thread import (run_trends_analysis, run_challenges_analysis, run_capabilities_analysis,
                                  run_actions, overseer_manage_assistant, import_data_file, parallel_file_process)
from concurrent.futures import ThreadPoolExecutor, as_completed
from challenges import find_top_right_challenge
from powerpoint import create_powerpoint
import concurrent.futures
import json
import sys

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
company_insights = []
market_insights = []

index = 0
company_insight_dir = "Files-INSIGHT"  # Directory containing the insight files (insights need to be extracted)
market_insight_dir = "Files-MARKET"
data_dir = "Files-DATA"        # Directory containing background data files (Data will be used directly)

# debug run is for the latter stages so that you can read files and not prduce them again
DEBUG_RUN = None

if not DEBUG_RUN:
    # read contents of the Files-INSIGHT directory

    # step 1: Extract the data files without loss of information
    data_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    company_data = []  # company_data will be a list of json objects containing info about the company
    for data_file in data_files:
        company_data.append(import_data_file(data_dir,data_file))
    for company_datum in company_data:
        print(company_datum)

    # step 2: Run through the insight files on the company, extract and collect in company_insights

    company_insights.append(parallel_file_process(client, company_insight_dir ))
    for company_insight_file in company_insights:
        print(company_insight_file)

    # step 3 : run through the insight files on the markets and extract into insights_environment

    market_insights.append(parallel_file_process(client, market_insight_dir))
    for market_insight_file in market_insights:
        print(market_insight_file)

    # step 4 & 5 : generate trends and capabilities affecting the company, create trend radar

    ## ( have to define those in funnctions so that the parallel executor can parallelise over them)

    # TODO: hide this in the run_assistant_thread module (or its replacement)

    def trend_analysis(client, company_insights):
        trends_file = overseer_manage_assistant(client, run_trends_analysis, market_insights,
                                                company_data)
        return trends_file
    def capabilities_analysis(client, company_insights):
        capabilities_file = overseer_manage_assistant(client, run_capabilities_analysis,  company_insights,
                                                      company_data)
        return capabilities_file

    ## parallel execution of the future and capabilities assistants

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_trends = executor.submit(trend_analysis,client, company_insights)
        future_capabilities = executor.submit(capabilities_analysis,client, company_insights)

    ## wait for prallel execution to end

    trends_file = future_trends.result()
    capabilities_file = future_capabilities.result()

    ## pull content from trends and capabilities files

    capabilities_content = client.files.retrieve_content(capabilities_file)
    json_capabilities = json.loads(capabilities_content)

    trends_content = client.files.retrieve_content(trends_file)
    json_trends = json.loads(trends_content)

    # step 4 : generate challenges affecting the company

    challenges_file = overseer_manage_assistant(client, run_challenges_analysis, trends_file,
                                capabilities_file)
    challenges_content = client.files.retrieve_content(challenges_file)
    json_challenges = json.loads(challenges_content)

    top_challenge = find_top_right_challenge(json_challenges)
    print(top_challenge)

    # step 5 : generate an action plan based on the challenges

    actions_file = overseer_manage_assistant(client, run_actions, top_challenge, trends_file, capabilities_file)

    actions_content = client.files.retrieve_content(actions_file)
    json_actions = json.loads(actions_content)

    # step 6 : generate a powerpoint containing all the images
    # write the files so that we can debug from here if needed

    with open(f"json_trends.json", "w", encoding="utf-8") as json_file:
        json_trends = json.loads(trends_content)
    with open(f"json_capabilities.json", "w", encoding="utf-8") as json_file:
        json_file.write(capabilities_content)
    with open(f"json_challenges.json", "w", encoding="utf-8") as json_file:
        json_file.write(challenges_content)
    with open(f"json_actions.json", "w", encoding="utf-8") as json_file:
        json_file.write(actions_content)
else:
    with open("json_trends.json", "r", encoding="utf-8") as json_file:
            json_trends = json.load(json_file)
    with open(f"json_capabilities.json", "r", encoding="utf-8") as json_file:
        json_capabilities = json.load(json_file)
    with open(f"json_challenges.json", "r", encoding="utf-8") as json_file:
        json_challenges = json.load(json_file)
    with open(f"json_actions.json", "r", encoding="utf-8") as json_file:
        json_actions = json.load(json_file)

ppt = create_powerpoint(json_trends, json_capabilities, json_challenges, json_actions)
