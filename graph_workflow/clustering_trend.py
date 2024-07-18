from core_components.RAG.graph import RAG_graph
import os
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
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

load_dotenv()
import uuid
import copy


def dict_to_plain_text(data, indent_level=0):
    """
    Transform an unstructured dictionary into plain text to make it easy for LLM to read.

    Parameters:
        data (dict): The dictionary to transform.
        indent_level (int): The current indentation level for nested dictionaries and lists.

    Returns:
        str: A string representing the dictionary in plain text.
    """
    plain_text = ""
    indent = "    " * indent_level  # 4 spaces per indent level

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                plain_text += f"{indent}{key}:\n"
                plain_text += dict_to_plain_text(value, indent_level + 1)
            elif isinstance(value, list):
                plain_text += f"{indent}{key}:\n"
                plain_text += dict_to_plain_text(value, indent_level + 1)
            else:
                plain_text += f"{indent}{key}: {value}\n"
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) or isinstance(item, list):
                plain_text += dict_to_plain_text(item, indent_level + 1)
            else:
                plain_text += f"{indent}- {item}\n"
    else:
        plain_text += f"{indent}{data}\n"

    return plain_text


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
rag_graph_cluster = RAG_graph(
    "bolt://localhost:7687",
    user,
    password,
    "clustering",
    OPENAI_API_KEY,
    OPENAI_EMBEDDINGS_URL,
)
rag_graph_ict = RAG_graph(
    "bolt://localhost:7687",
    user,
    password,
    "ict",
    OPENAI_API_KEY,
    OPENAI_EMBEDDINGS_URL,
)

# rag_graph.kg.query("match (t:Trend)-[]-(cl:Cluster)  detach delete cl")

get_summary = ChatPromptTemplate.from_template(
    template=""" You are an strategic consultant helping companies to structure their knowledge.
Produce a compact textual summary with all and only the information that you can find in the following trends:
***
{trends}
***
"""
)
model_summary = ChatOpenAI(model="gpt-4o", temperature=0.1)
parser_summary = StrOutputParser()
chain_summary = get_summary | model_summary | parser_summary

rag_graph.compute_embeddings("Trend", "Description")

query = """
MATCH (excluded:Cluster)
WITH collect(excluded) as excluded
MATCH (r:Trend)
WHERE  r.gics_code IS NOT NULL and NONE(i in excluded WHERE (r)-[]->(i))
RETURN r as trends
"""

# trends = rag_graph.kg.query(
#     "match (n:Trend) where n.gics_code IS NOT NULL return n as trends"
# )
trends = rag_graph.kg.query(query)
trends = [trend["trends"] for trend in trends]
trends_ = trends
trends = []
for t in trends_:
    t["EvidencedBy"] = eval(t["EvidencedBy"])
    t["AffectedAreas"] = eval(t["AffectedAreas"])
for trend in trends_:
    # print(trend)
    print([aa["IndustryName"] for aa in trend["AffectedAreas"]])
    # if len([aa for aa in trend['AffectedAreas'] if aa['IndustryName'] == 'IndustryName'])>0:

    trends.append(trend)
for t in trends:
    t["EvidencedBy"] = str(t["EvidencedBy"])
    t["AffectedAreas"] = str(t["AffectedAreas"])

X = []
print(len(trends_))
print(len(trends))
for trend in trends:

    for key, value in trend.items():

        if key == "DescriptionEmbedding":

            X.append(np.array([float(v) for v in value]))

X = np.stack(X)
print(X.shape[0] // 15)

labels = KMeans(n_clusters=X.shape[0] // 15, random_state=0).fit_predict(X)


# df = pd.DataFrame({i:node for i,node in enumerate(TESLA)}.items())
trends_ = copy.deepcopy(trends)
for trend in trends_:
    trend.pop("DescriptionEmbedding", None)
# print(trends_)
df = pd.DataFrame(trends_)
df["label"] = labels
# print(df)


from datetime import datetime

now = datetime.now()
now = now.strftime("%m/%d/%Y, %H:%M:%S")

for label in list(set(labels)):
    cluster_id = str(uuid.uuid4())

    df_trends = df[df["label"] == label]
    print(df_trends.shape)
    trends = df_trends.to_dict("records")
    # print(trends)
    for t in trends:
        t["EvidencedBy"] = eval(t["EvidencedBy"])
        t["AffectedAreas"] = eval(t["AffectedAreas"])
    sources = []
    titles = []
    AffectedAreas = []
    gics_codes = []
    gics_names = []

    print("gathering data")
    for trend in trends:
        # print(insight['source'])
        sources.append(trend["source"])
        gics_codes.append(trend["gics_code"])
        gics_names.append(trend["gics_name"])
        # print(insight['categories'])
        titles.append(trend["title"])

        # print(insight['description'])
        AffectedAreas.extend(trend["AffectedAreas"])

    # print(categories)

    titles = list(set(titles))
    # print(titles)
    sources = list(set(sources))
    gics_codes = list(set(gics_codes))
    gics_names = list(set(gics_names))
    # AffectedAreas = list(set(AffectedAreas))
    AffectedAreas = list(set([str(aa) for aa in AffectedAreas]))
    AffectedAreas = eval(str(AffectedAreas))
    # print(AffectedAreas)
    print("trends to summarize")
    trend_to_summarize = [
        {"title": trend["title"], "description": trend["Description"]}
        for trend in trends
    ]

    summary = chain_summary.invoke(
        {
            "trends": " ***** "
            + "\n ***** \n".join(dict_to_plain_text(trend_to_summarize))
            + " ***** "
        }
    )
    # print(summary)
    # print(list(set(categories)))
    print("cluster to add")
    cluster = {
        "number": label,
        "source": sources,
        "titles": titles,
        "gics_codes": gics_codes,
        "gics_names": gics_names,
        "created": now,
        "AffectedAreas": AffectedAreas,
        # 'description': ' ***** ' +'\n ***** \n'.join(summary) + ' ***** ',
        "summary": summary,
        "type": "trend",
        "clusterId": cluster_id,
    }

    # print(cluster)
    # assert 1==2
    print("adding cluster")
    rag_graph.add_cluster(cluster)

    # print(f'\nLabel: {label}\n')
    # print(df[df['label'] == label])
    print("linking trends to cluster")
    for trend in trends:
        # print(trend['trendId'])
        # assert 1==2
        res = rag_graph.link_trend_to_cluster(trend["trendId"], cluster["clusterId"])
