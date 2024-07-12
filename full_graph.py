from graph_rag_lc import RAG_graph
from dotenv import load_dotenv

load_dotenv()
from utility import dict_to_plain_text
import os
from chains import evaluate_trend_cluster
import json


uri = os.getenv("NEO4J_URL")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
OPENAI_EMBEDDINGS_URL = os.getenv("OPENAI_EMBEDDINGS_URL")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

rag_graph = RAG_graph(
    "bolt://localhost:7687",
    user,
    password,
    database,
    OPENAI_API_KEY,
    OPENAI_EMBEDDINGS_URL,
)


def remove_attribute(subgraph, attribute):
    for key, value in subgraph.items():
        if key == attribute:
            subgraph.pop(key)
        if isinstance(value, dict):
            remove_attribute(value, attribute)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    remove_attribute(item, attribute)
    return subgraph


def remove_attribute_containing(subgraph, attribute):
    if isinstance(subgraph, list):
        for item in subgraph:
            remove_attribute_containing(item, attribute)
    elif isinstance(subgraph, dict):
        for key, value in subgraph.copy().items():
            if attribute in key:
                subgraph.pop(key)
            if isinstance(value, dict):
                remove_attribute(value, attribute)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        remove_attribute(item, attribute)
    else:
        raise ValueError("subgraph must be a list or a dict")
    return subgraph


def dump_company_graph_to_plain_txt(company_name):
    subgraph = rag_graph.company_sub_graph(
        company_name,
        label_filters=["Insight", "Capability"],
        relationship_exclusions=["SIMILAR"],
    )

    remove_attribute_containing(subgraph, "embedding")
    remove_attribute_containing(subgraph, "Embedding")

    return dict_to_plain_text(subgraph)


def filter_trends(subgraph, problem_statement):
    number_of_trends = len(subgraph)
    trends_assesment = {
        "number_of_validated_trends": 0,
        "number_of_trends": number_of_trends,
        "trends": [],
        "problem_statement": problem_statement,
    }
    trends_output = {"trends": []}
    for trends in subgraph:
        trend = trends["trends"]
        evaluation = evaluate_trend_cluster.invoke(
            {
                "trend_summary": dict_to_plain_text(trend),
                "problem_statement": problem_statement,
            }
        )
        if evaluation["Validated"]:
            trends_assesment["number_of_validated_trends"] += 1
            trends_output["trends"].append(evaluation["Statements"])
        evaluation["Explanation"]
        trends_assesment["trends"].append(
            {
                "trend": trend["summary"],
                "validation": evaluation["Validated"],
                "explanation": evaluation["Explanation"],
                "statements": evaluation["Statements"],
            }
        )
    # Convert trends_assesment to JSON
    trends_assesment_json = json.dumps(trends_assesment)
    with open("trends_assesment.json", "w") as f:
        f.write(trends_assesment_json)

    # Print the JSON
    # print(trends_assesment_json)

    # for trend in trends['trends']:
    #     if trend['name'] in problem_statement:
    #         return trends
    return trends_output


def get_trends_from_gics_code(gics_code, problem_statement):
    condition = " OR ".join([f"'{code}' in c.gics_codes" for code in gics_code])
    subgraph = rag_graph.kg.query(
        "match (c:Cluster) where {} return distinct c as trends".format(condition)
    )
    remove_attribute_containing(subgraph, "embedding")
    remove_attribute_containing(subgraph, "Embedding")
    # print(len(subgraph))
    subgraph = filter_trends(subgraph, problem_statement)
    # return dict_to_plain_text('')
    return subgraph
