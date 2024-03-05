import os
import openai
from dotenv import load_dotenv
from run_assistant_thread import (run_trends_analysis, run_challenges_analysis, run_capabilities_analysis,
                                  run_actions, overseer_manage_assistant, import_data_files, parallel_file_process)
from concurrent.futures import ThreadPoolExecutor, as_completed
from challenges import find_top_right_challenge
from langchain_openai import OpenAIEmbeddings
from powerpoint import create_powerpoint
import concurrent.futures

from langchain.text_splitter import RecursiveCharacterTextSplitter
import json
import sys
import shutil
load_dotenv()
# from core_components.src.RAG.rag import RAG
from core_components.src.DocumentLoader.document_retriever_sharepoint import (
    SharePointRetriever,
)
from core_components.src.agents.openAI import load_agents, query_assistant, client
from retrieval import retrieve_docs, find_and_download_files


# print(os.getenv("OPENAI_API_KEY"))
agents = load_agents("openAI_agents.yml")
queries_agent = agents["OpenAI"]["queries_agent"]
files = find_and_download_files(
    "Shared Documents/Research/Incubation/Socrates/Documents/test_retrieval/"
)
researches = [
        [
            "NAG",
            "Numerical Algorithms Group",
            "NAG provides industry-leading numerical software and technical services to banking and finance, energy, engineering, and market research, as well as academic and government institutions.",
            "leadership",
            "Services",
        ]
    ]

queries = [
        "Can you tell me more about NAG (Numerical Algorithm Group) insights, perspective, risks, opportunities, and challenges?",
        "What are the relevant markets, for a company specialized in HPC, optimisation and numerical algorithms? What can you tell me about the major industrial markets",
    ]
print(files)
for query in queries:
        result_steps, result_response, result_thread = query_assistant(
            client, queries_agent["id"], query
        )
        messages = client.beta.threads.messages.list(thread_id=result_thread.id)
        increased_queries = [query]
        for message in messages:
            if message.role == "assistant":
                increased_queries.extend(message.content[0].text.value.split("\n"))

        
        researches.append(increased_queries)
        
print(f"Researches: {researches}")
for queries, folder in zip(researches,["Files-DATA-retrieved", "Files-INSIGHT-retrieved", "Files-MARKET-retrieved"]):
    print(f"Queries: {queries}")
    retrieved_docs = retrieve_docs(
        files, queries
    )
    files_to_remove = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.isfile(os.path.join(folder, f))
            ]
    for f in files_to_remove:
        os.remove(f)
    for file in retrieved_docs:
        print(os.path.join(folder, file.split("/")[-1]))
        shutil.copyfile(file, os.path.join(folder, file.split("/")[-1]))
        # os.rename(file,os.path.join(name,file.split("/")[-1]))

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

index = 0
company_insight_dir = "Files-COMPANY"  # Directory containing the insight files (insights need to be extracted)
market_insight_dir = "Files-MARKET"
data_dir = "Files-DATA"  # Directory containing background data files (Data will be used directly)

# company_insight_dir = "Files-INSIGHT"  # Directory containing the insight files (insights need to be extracted)
# market_insight_dir = "Files-Market"
# data_dir = "Files-DATA"

# debug run is for the latter stages so that you can read files and not prduce them again
DEBUG_RUN = None
# some intermediates files are created neccesarily, but this forces all to be created
PRODUCE_INTERMEDIATES = True

if not DEBUG_RUN:
    # read contents of the Files-COMPANY directory
    # step 1: Extract the data files without loss of information
    company_data = import_data_files(client, data_dir )
    print(f"Main: Company data imported: file_id={company_data.id}")

    # step 2: Run through the insight files on the company, extract and collect in company_insights
    company_insights = parallel_file_process(client, company_insight_dir, company_data,
                                                  "company",PRODUCE_INTERMEDIATES)
    print(f"Main: Company insights extracted: file_ids ={company_insights}")
    # for company_insight_file in company_insights:
    #     print(company_insight_file)

    # step 3 : run through the insight files on the markets and extract into insights_environment

    market_insights = parallel_file_process(client, market_insight_dir, company_data,
                                                 "market", PRODUCE_INTERMEDIATES)
    print(f"Main: Market insights extracted: file_ids ={market_insights}")

    # for market_insight_file in market_insights:
    #     print(market_insight_file)

    # step 4 & 5 : generate trends and capabilities affecting the company, create trend radar

    ## ( have to define those in funnctions so that the parallel executor can parallelise over them)
    # TODO: hide this in the run_assistant_thread module (or its replacement)
    def trend_analysis(client, market_insights,PRODUCE_INTERMEDIATES):
        trends_file = overseer_manage_assistant(client, PRODUCE_INTERMEDIATES, "trends",
            0, run_trends_analysis, market_insights, company_data)
        return trends_file
    def capabilities_analysis(client, company_insights,PRODUCE_INTERMEDIATES):
        capabilities_file = overseer_manage_assistant(client, PRODUCE_INTERMEDIATES, "capabilities",
            0, run_capabilities_analysis,  company_insights, company_data)
        return capabilities_file

    ## parallel execution of the future and capabilities assistants

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_trends = executor.submit(trend_analysis,client, market_insights,PRODUCE_INTERMEDIATES)
        future_capabilities = executor.submit(capabilities_analysis,client, company_insights,PRODUCE_INTERMEDIATES)

    ## wait for prallel execution to end

    trends_file = future_trends.result()
    capabilities_file = future_capabilities.result()

    ## pull content from trends and capabilities files

    capabilities_content = client.files.retrieve_content(capabilities_file)
    json_capabilities = json.loads(capabilities_content)

    trends_content = client.files.retrieve_content(trends_file)
    json_trends = json.loads(trends_content)

    # step 4 : generate challenges affecting the company

    challenges_file = overseer_manage_assistant(client, PRODUCE_INTERMEDIATES, "challenges",
            0, run_challenges_analysis, trends_file, capabilities_file)
    challenges_content = client.files.retrieve_content(challenges_file)
    json_challenges = json.loads(challenges_content)

    top_challenge = find_top_right_challenge(json_challenges)
    print(f"top challenge is {top_challenge}")

    # step 5 : generate an action plan based on the challenges

    actions_file = overseer_manage_assistant(client, PRODUCE_INTERMEDIATES, "actions", 0,
        run_actions, top_challenge, trends_file, capabilities_file)

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
