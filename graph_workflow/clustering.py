from graph_workflow.graph_rag_lc import RAG_graph
import os
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from sklearn import metrics
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pydantic import BaseModel, ConfigDict, Field, conint
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate
from typing import Dict, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import multiprocessing as mp
import time

load_dotenv()
import uuid


class Evidence(BaseModel):
    insight_id: str = Field(description="The insight id of the insight used")
    quote: str = Field(description="A meaningful quotation from the insight")


class Capability(BaseModel):
    capability: str = Field(description="Description of the insight")
    value_potential: int = Field(
        ge=0,
        le=99,
        description="value potential: (capability may lead to business success), 99 is a certainty of sucess while 0 lead to very unlikely success. The score is an integer from 0 to 99",
    )
    scarcity: int = Field(
        ge=0,
        le=99,
        description=" scarcity: not possessed by many, 99 means not other company have this capability while 0 means all company have this capability. The score is an integer from 0 to 99",
    )
    non_replicability: int = Field(
        ge=0,
        le=99,
        description="non-replicability: others cannot easily build this capability. 99 means the capability cannot be build by other company while 0 means every company can build it. The score is an integer from 0 to 99",
    )
    irreplaceability: int = Field(
        ge=0,
        le=99,
        description="irreplaceability: capability cannot be replaced by other resources easily. 99 means the capability is unique and does not compete with other capabilities, while 0 means other capabilities can achieve the same results. The score is an integer from 0 to 99",
    )
    confidence: int = Field(
        ge=0,
        le=99,
        desciption="confidence score in your capability assessment. The score is an integer from 0 to 99",
    )
    evidenced_by: List[Evidence] = Field(
        description="The insights that were used to produce the capability"
    )


class CapabilityList(BaseModel):
    capabilities: List[Capability] = Field(
        description="The list of capabilities extracted from the insights"
    )


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

capability_instruction = """
You are a production strategy agent working as part of a team solving a real strategy consulting problem for businesses. This is not a simulation and you are not here to solve a model problem, but to perform real analysis on real data for a real client. 

Within the strategy consulting team, you are a business strategy analyst that specialises in detecting capabilities of businesses. Your work in capability detection and rating is being used by other analysts at your consulting firm. Your task is to exhaustively list all the capabilities that a company possesses. A capability is a set of learnings and abilities that a company has developed and which they can employ for strategic purposes.  

You will provide an extensive list of capabilities affecting the company. Do not deviate from this structure and do not simulate the problem. You are thorough and methodical, you have a team of strategy consultants awaiting the outcome and their progress depends on you reliably extracting every capability related to the target company. 

You will provide an integer score [1-99] for each trend, based on your assessment of the company of I) "value potential" (capability may lead to business success) ii) "scarcity" (not possessed by many) III) "non-replicability" (others cannot easily build this capability) iV) "irreplaceability" (capability cannot be replaced by other resources easily). The scores will have one decimal place.  You will also state the sources for the decision that the company possesses the capability and list those in the "evidenced by" section. The evidence you provide will be the ID of the specific insights that combined to inform you of the capability. Based on the combined confidence of those insights, you will also state a confidence score in your capability assessment. 

Do not try to limit the number of capabilities, we need to see all capabilities, whether important or not. Your colleagues would like at least 10 capabilities but the more the better. 

Do not try to limit the number of capabilities, we need a comprehensive list. Do not follow a model problem to demonstrate how to solve the task - your job is to solve the task in full.
"""

get_summary = ChatPromptTemplate.from_template(
    template=""" You are an strategic consultant helping companies to structure their knowledge.
                             For the company: {company}. Produce a compact textual summary with all and only the information that you can find in the following insights:
                             ***
                             {insights}
                             ***
                             """
)
model_summary = ChatOpenAI(model="gpt-4o", temperature=0.1)
parser_summary = StrOutputParser()
chain_summary = get_summary | model_summary | parser_summary


# print(TESLA)
model_capabilities = ChatOpenAI(model="gpt-4o", temperature=0.1)
parser_capabilities = JsonOutputParser(pydantic_object=CapabilityList)
get_capabilities = PromptTemplate(
    template="""For the company: {company}, Follow the instructions:
                              ***
                              {instruction}
                              ***
                              
                              using only the data provided in this document: '
                              
                              ***
                              {document}
                              ***
                              \n
                              
                              ***
                              {format_instructions}
                              ***""",
    input_variables=["company", "document"],
    partial_variables={
        "format_instructions": parser_capabilities.get_format_instructions(),
        "instruction": capability_instruction,
    },
)
chain_capabilities = get_capabilities | model_capabilities | parser_capabilities


def project_graph(kg, graph_name, property):
    query = f"""CALL gds.graph.project(
        '{graph_name}',
        {{
        Insight: {{
            properties: '{property}'
        }}
        }},q
        '*'
    )"""
    return kg.query(query)


def list_graph(kg):
    query = """CALL gds.graph.list(
                    graphName: String
                    ) YIELD
                    graphName: String,
                    database: String,
                    databaseLocation: String,
                    configuration: Map,
                    nodeCount: Integer,
                    relationshipCount: Integer,
                    schema: Map,
                    schemaWithOrientation: Map,
                    degreeDistribution: Map,
                    density: Float,
                    creationTime: Datetime,
                    modificationTime: Datetime,
                    sizeInBytes: Integer,
                    memoryUsage: String"""
    return kg.query(query)


def drop_graph(kg, graph_name):
    query = """CALL gds.graph.drop('my-store-graph') YIELD graphName;"""
    return kg.query(query)


def kmeans_write_group(
    kg,
    graph="Insight_clusters",
    features="descriptionEmbedding",
    number_of_clusters=50,
    className="cluster",
):
    query = f"""
        CALL gds.kmeans.write('{graph}', {{
        nodeProperty: '{features}',
        k: {number_of_clusters},
        randomSeed: 42,
        writeProperty: '{className}'
        }})
        YIELD communityDistribution
        """
    return kg.query(query)


def generate_cluster_and_capabilities(df, company_name, label, now):

    cluster_id = str(uuid.uuid4())

    df_insights = df[df["label"] == label]
    insights = df_insights.to_dict("records")

    sources = []
    categories = []
    descriptions = []

    for insight in insights:
        # print(insight['source'])
        sources.append(insight["source"])

        # print(insight['categories'])
        categories.extend(insight["categories"])

        # print(insight['description'])
        descriptions.append(insight["description"])

    # print(categories)

    categories = list(set(categories))
    sources = list(set(sources))
    descriptions = list(set(descriptions))

    summary = chain_summary.invoke(
        {
            "company": company_name,
            "insights": " ***** " + "\n ***** \n".join(descriptions) + " ***** ",
        }
    )
    # print(list(set(categories)))
    cluster = {
        "number": label,
        "source": sources,
        "category": categories,
        "created": now,
        "description": " ***** " + "\n ***** \n".join(descriptions) + " ***** ",
        "summary": summary,
        "clusterId": cluster_id,
    }

    rag_graph.add_cluster(cluster)

    for insight in insights:
        res = rag_graph.link_insights_to_cluster(
            insight["insightId"], cluster["clusterId"]
        )

    capabilities = chain_capabilities.invoke(
        {"company": company_name, "document": summary}
    )

    for capability in capabilities["capabilities"]:
        capability["capabilityId"] = str(uuid.uuid4())
        capability["evidenced_by"] = str(capability["evidenced_by"])
        rag_graph.add_capability(capability=capability)
        rag_graph.link_cluster_to_capability(
            cluster["clusterId"], capability["capabilityId"]
        )


# print()
# rag_graph.compute_insight_embeddings_for_company('NAG', 'description')
def generate_capabilities_per_cluster(
    companies, compute_embeddings=True, number_of_processes=5
):
    names = [c.replace(" ", "_").replace(".", "").replace("'", "") for c in companies]
    for company in names:
        print(
            f"clustering of the insights and generation of capabilities for company: {company}"
        )
        if compute_embeddings:
            print(f"Start computing embeddings..")
            rag_graph.compute_insight_embeddings_for_company(company, "description")

        graph = rag_graph.company_sub_graph(
            company, label_filters=["Insight"], relationship_exclusions=["SIMILAR"]
        )

        try:
            X = []

            for node in graph:

                insightId = node.get("insightId", "")

                for key, value in node.items():

                    if key == "descriptionEmbedding":
                        X.append(np.array([float(v) for v in value]))

            X = np.stack(X)
            print(f"Start computing clusters..")
            labels = KMeans(n_clusters=X.shape[0] // 15, random_state=0).fit_predict(X)

            df = pd.DataFrame(graph)
            df["label"] = labels

            from datetime import datetime

            now = datetime.now()
            now = now.strftime("%m/%d/%Y, %H:%M:%S")

            with mp.Pool(number_of_processes) as pool:
                results = []
                for label in list(set(labels)):
                    results.append(
                        pool.apply_async(
                            generate_cluster_and_capabilities,
                            args=(df, company, label, now),
                        )
                    )

                while not all([r.ready() for r in results]):

                    print(
                        f"cluster and capabilities added {[r.ready() for r in results].count(True)} / {len(results)} for {company}."
                    )
                    time.sleep(5)
        except Exception as e:
            print(e)
