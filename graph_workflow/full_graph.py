from graph_workflow.graph_rag_lc import RAG_graph
from utility import dict_to_plain_text, invoke, logger

import os
from chains import (
    evaluate_trend_cluster,
    evaluate_capability_cluster,
    evaluate_insight_cluster,
)
import json
import multiprocessing as mp
import time
import uuid

try:
    logger.debug(f"{mp.get_start_method()} ---- {__name__}")
    mp.set_start_method("spawn")
except Exception as e:
    logger.error(__name__ + " - " + str(e))

uri = os.getenv("NEO4J_URL")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
OPENAI_EMBEDDINGS_URL = os.getenv("OPENAI_EMBEDDINGS_URL")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

rag_graph = RAG_graph(
    uri,
    user,
    password,
    database,
    OPENAI_API_KEY,
    OPENAI_EMBEDDINGS_URL,
)


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


def format_insight_and_capability(
    cluster, problem_statement, company_name, klist=["statement", "source", "quote"]
):
    outputs = {"insights": [], "capabilities": []}
    query = "match (i:Insight)-[]-(c:Cluster {{ clusterId: '{clusterId}' }}) return i as insight".format(
        clusterId=cluster["clusterId"]
    )
    insights = rag_graph.kg.query(query)
    for insight in insights:
        insight = insight["insight"]
        remove_attribute_containing(insight, "Embedding")
    # insights_and_capabilities_assesment["number_of_insights"] += len(insights)
    # print(insights[0]['insight'].keys())

    query = "match (i:Capability)-[]-(c:Cluster {{ clusterId: '{clusterId}' }}) return i as capability".format(
        clusterId=cluster["clusterId"]
    )
    capabilities = rag_graph.kg.query(query)
    for capability in capabilities:
        capability = capability["capability"]
        remove_attribute_containing(capability, "Embedding")

    evaluation_insights = invoke(
        evaluate_insight_cluster,
        {
            "insights_summary": dict_to_plain_text(insights),
            "problem_statement": problem_statement,
            "company": company_name,
        },
    )
    # evaluation_insights = evaluate_insight_cluster.invoke(
    #     {
    #         "insights_summary": dict_to_plain_text(insights),
    #         "problem_statement": problem_statement,
    #         "company": company_name,
    #     }
    # )

    if evaluation_insights["Validated"]:
        statements = [
            {k: v for k, v in statement.items() if k in klist}
            for statement in evaluation_insights["Statements"]
            if statement["relevant"]
        ]

        outputs["insights"].extend(statements)

    evaluation_capabilities = invoke(
        evaluate_capability_cluster,
        {
            "capabilities_summary": dict_to_plain_text(capabilities),
            "problem_statement": problem_statement,
            "company": company_name,
        },
    )
    # evaluation_capabilities = evaluate_capability_cluster.invoke(
    #     {
    #         "capabilities_summary": dict_to_plain_text(capabilities),
    #         "problem_statement": problem_statement,
    #         "company": company_name,
    #     }
    # )
    if evaluation_capabilities["Validated"]:
        statements = [
            {k: v for k, v in statement.items() if k in klist}
            for statement in evaluation_capabilities["Statements"]
            if statement["relevant"]
        ]
        outputs["capabilities"].extend(statements)
    return outputs


def filter_insights_and_capabilities(subgraph, problem_statement, company_name):
    insights_and_capabilities_output = {"insights": [], "capabilities": []}
    klist = ["statement", "source", "quote"]
    with mp.Pool(5) as p:
        results = [
            p.apply_async(
                format_insight_and_capability,
                (insight_or_capability, problem_statement, company_name),
            )
            for insight_or_capability in subgraph
        ]
        while not all([r.ready() for r in results]):
            print(
                f"insights_and_capabilities {[r.ready() for r in results].count(True)} / {len(results)} filtered."
            )
            time.sleep(5)
        results = [r.get() for r in results if r.get() != []]

        insights_and_capabilities_output["insights"].extend(
            [
                [
                    {k: v for k, v in statement.items() if k in klist}
                    for statement in result["insights"]
                ]
                for result in results
            ]
        )
        insights_and_capabilities_output["capabilities"].extend(
            [
                [
                    {k: v for k, v in statement.items() if k in klist}
                    for statement in result["capabilities"]
                ]
                for result in results
            ]
        )
    return insights_and_capabilities_output


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


def dump_company_graph_to_plain_txt(company_name, problem_statement):
    subgraph = rag_graph.company_sub_graph(
        company_name,
        label_filters=["Cluster"],
        relationship_exclusions=["SIMILAR"],
    )

    remove_attribute_containing(subgraph, "embedding")
    remove_attribute_containing(subgraph, "Embedding")

    subgraph = filter_insights_and_capabilities(
        subgraph, problem_statement, company_name
    )

    return dict_to_plain_text(subgraph)


def dump_company_graph_to_json(company_name, problem_statement):
    subgraph = rag_graph.company_sub_graph(
        company_name,
        label_filters=["Cluster"],
        relationship_exclusions=["SIMILAR"],
    )

    remove_attribute_containing(subgraph, "embedding")
    remove_attribute_containing(subgraph, "Embedding")

    subgraph = filter_insights_and_capabilities(
        subgraph, problem_statement, company_name
    )

    return subgraph


def format_trend(trends, problem_statement):
    trend = trends["trends"]
    evaluation = invoke(
        evaluate_trend_cluster,
        {
            "trend_summary": dict_to_plain_text(trend),
            "problem_statement": problem_statement,
        },
    )
    statements = [
        statement for statement in evaluation["Statements"] if statement["relevant"]
    ]
    return statements if evaluation["Validated"] else []


def filter_trends(subgraph, problem_statement):
    trends_output = {"trends": []}

    klist = ["statement", "source", "quote", "relevant"]
    with mp.Pool(5) as p:
        results = [
            p.apply_async(format_trend, (trends, problem_statement))
            for trends in subgraph
        ]
        while not all([r.ready() for r in results]):
            print(
                f"trends {[r.ready() for r in results].count(True)} / {len(results)} filtered."
            )
            time.sleep(5)
        results = [r.get() for r in results if r.get() != []]
        print(results)
        trends_output["trends"].extend(
            [
                [
                    {k: v for k, v in statement.items() if k in klist}
                    for statement in result
                    if statement["relevant"]
                ]
                for result in results
            ]
        )

    return trends_output


def get_trends_from_gics_code(gics_code, problem_statement):
    condition = " OR ".join([f"'{code}' in c.gics_codes" for code in gics_code])
    # print(condition)
    subgraph = rag_graph.kg.query(
        "match (c:Cluster) where {} return distinct c as trends".format(condition)
    )
    # print(subgraph)
    remove_attribute_containing(subgraph, "embedding")
    remove_attribute_containing(subgraph, "Embedding")
    # print(len(subgraph))
    subgraph = filter_trends(subgraph, problem_statement)
    # return dict_to_plain_text('')
    return subgraph


def save_curated_trend_data(company_name, gics_code, problem_statement, trend_data):
    query = """
    MATCH (c:Company {name: '%s'})
    MERGE (ctd:CuratedTrendData {gics_code: '%s', problem_statement: '%s'})
    SET ctd.trend_data = '%s', ctd.last_updated = datetime()
    MERGE (c)-[:HAS_CURATED_TREND]->(ctd)
    """ % (
        company_name,
        gics_code,
        problem_statement,
        json.dumps(trend_data).replace("'", "\\'"),
    )
    rag_graph.kg.query(query)


def get_curated_trend_data(company_name, gics_code, problem_statement):
    query = """
    MATCH (c:Company {name: '%s'})-[:HAS_CURATED_TREND]->(ctd:CuratedTrendData)
    WHERE ctd.gics_code = '%s' AND ctd.problem_statement = '%s'
    RETURN ctd.trend_data AS trend_data, ctd.last_updated AS last_updated
    """ % (
        company_name,
        gics_code,
        problem_statement,
    )
    result = rag_graph.kg.query(query)
    if result:
        return json.loads(result[0]["trend_data"])
    return None


def save_condensed_trend_data(company_name, problem_statement, trend_data):
    for trend in trend_data:
        query = """
        MATCH (c:Company {name: '%s'})
        MERGE (ctd:CondensedTrendData {problem_statement: '%s', idCondesedTrendData: '%s'})
        SET ctd.trend_data = '%s', ctd.last_updated = datetime()
        MERGE (c)-[:HAS_CONDENSED_TREND]->(ctd)
        """ % (
            company_name,
            problem_statement,
            str(uuid.uuid4()),
            # trend.replace("'", "\\'").replace('"', '\\"'),
            json.dumps(trend).replace("'", "\\'"),
        )
        rag_graph.kg.query(query)


def get_condensed_trend_data(company_name, problem_statement):
    query = """
    MATCH (c:Company {name: '%s'})-[:HAS_CONDENSED_TREND]->(ctd:CondensedTrendData)
    WHERE ctd.problem_statement = '%s'
    RETURN ctd.trend_data AS trend_data, ctd.last_updated AS last_updated
    """ % (
        company_name,
        problem_statement,
    )
    results = rag_graph.kg.query(query)
    if results:
        return [result["trend_data"] for result in results]
    return None


def save_condensed_company_data(company_name, problem_statement, company_data):
    for data in company_data:
        query = """
        MATCH (c:Company {name: '%s'})
        MERGE (ctd:CondensedCompanyData {problem_statement: '%s', idCondesedCompanyData: '%s'})
        SET ctd.company_data = '%s', ctd.last_updated = datetime()
        MERGE (c)-[:HAS_CONDENSED_COMPANY]->(ctd)
        """ % (
            company_name,
            json.dumps(problem_statement).replace("'", "\\'"),
            str(uuid.uuid4()),
            json.dumps(data).replace("'", "\\'"),
        )
        rag_graph.kg.query(query)
    print(query)


def get_condensed_company_data(company_name, problem_statement):
    query = """
    MATCH (c:Company {name: '%s'})-[:HAS_CONDENSED_COMPANY]->(ctd:CondensedCompanyData)
    WHERE ctd.problem_statement = '%s'
    RETURN ctd.company_data AS company_data
    """ % (
        company_name,
        json.dumps(problem_statement).replace("'", "\\'"),
    )
    results = rag_graph.kg.query(query)
    print(query)
    print("results: ")
    print(str(results)[:100])
    print("****")
    if results:
        return [result["company_data"] for result in results]
    return None


def get_tesla_capabilities():
    query = """
    MATCH (company:Company {name: 'Tesla'})-[]->(capability:Capability)
    RETURN capability AS Capability
    """
    results = rag_graph.kg.query(query)
    return results


# from capabilities import plot_capabilities
# # Example usage of the new function
# tesla_capabilities = get_tesla_capabilities()
# print("Tesla Capabilities:")
# caps = []
# for capability in tesla_capabilities:
#     print(capability["Capability"])
#     caps.append(capability["Capability"])
#
# print("done")
# plot = plot_capabilities(caps)
# plot.show()
# print("shown fig")
