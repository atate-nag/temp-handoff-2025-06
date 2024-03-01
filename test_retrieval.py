import os
import pytest
from retrieval import retrieve_docs, find_and_download_files
from dotenv import load_dotenv
load_dotenv()
from core_components.src.tests.test_retrieval import unit_test_retrieval
from core_components.src.tests.test_utils import precision, recall
from core_components.src.agents.openAI import load_agents, query_assistant, client


@pytest.fixture
def files():
    files = find_and_download_files('Shared Documents/Research/Incubation/Socrates/Documents/test_retrieval/')
    return files


@pytest.fixture
def queries_insight():
    agents = load_agents("openAI_agents.yml")
    queries_agent = agents["OpenAI"]["queries_agent"]
    query ="Can you tell me more about NAG (Numerical Algorithm Group) insights, perspective, risks, opportunities, and challenges?"
    result_steps, result_response, result_thread = query_assistant(
        client, queries_agent["id"], query
    )
    messages = client.beta.threads.messages.list(thread_id=result_thread.id)
    increased_queries = [query]
    for message in messages:
        if message.role == "assistant":
            increased_queries.extend(message.content[0].text.value.split("\n"))
    return increased_queries

@pytest.fixture
def queries_market():
    agents = load_agents("openAI_agents.yml")
    queries_agent = agents["OpenAI"]["queries_agent"]
    query ="What are the relevant markets, for a company specialized in HPC, optimisation and numerical algorithms? What can you tell me about the major industrial markets"
    result_steps, result_response, result_thread = query_assistant(
        client, queries_agent["id"], query
    )
    messages = client.beta.threads.messages.list(thread_id=result_thread.id)
    increased_queries = [query]
    for message in messages:
        if message.role == "assistant":
            increased_queries.extend(message.content[0].text.value.split("\n"))
    return increased_queries


@pytest.fixture
def expected_output_insight():
    # Create a temporary output folder for testing
    output = os.listdir('Files-INSIGHT')
    return [f.split('/')[-1] for f in output]

@pytest.fixture
def expected_output_market():
    # Create a temporary output folder for testing
    output = os.listdir('Files-Market')
    return [f.split('/')[-1] for f in output]


def test_retrieve_docs_insight_recall(files, queries_insight, expected_output_insight):
    # Call the retrieve_docs function with the test input and output folders
    retrieved_output = retrieve_docs(files, queries_insight)
    retrieved_output = [f.split('/')[-1] for f in retrieved_output]
    unit_test_retrieval(
        retrieved_output,
        expected_output_insight,
        metrics_and_thresholds=[(recall, 0.5)],
    )

def test_retrieve_docs_insight_precision(files, queries_insight, expected_output_insight):
    # Call the retrieve_docs function with the test input and output folders
    retrieved_output = retrieve_docs(files, queries_insight)
    retrieved_output = [f.split('/')[-1] for f in retrieved_output]
    unit_test_retrieval(
        retrieved_output,
        expected_output_insight,
        metrics_and_thresholds=[(precision, 0.5)],
    )
    
def test_retrieve_docs_market_recall(files, queries_market, expected_output_market):
    # Call the retrieve_docs function with the test input and output folders
    retrieved_output = retrieve_docs(files, queries_market)
    retrieved_output = [f.split('/')[-1] for f in retrieved_output]
    unit_test_retrieval(
        retrieved_output,
        expected_output_market,
        metrics_and_thresholds=[(recall, 0.5)],
    )

def test_retrieve_docs_market_precision(files, queries_market, expected_output_market):
    # Call the retrieve_docs function with the test input and output folders
    retrieved_output = retrieve_docs(files, queries_market)
    retrieved_output = [f.split('/')[-1] for f in retrieved_output]
    unit_test_retrieval(
        retrieved_output,
        expected_output_market,
        metrics_and_thresholds=[(precision, 0.5)],
    )
