import time
from graph_workflow.graph_rag_lc import RAG_graph
import os
from dotenv import load_dotenv

from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from typing import List
from langchain_openai import ChatOpenAI
from utility import dict_to_plain_text, invoke, logger
import multiprocessing
from multiprocessing import Pool

load_dotenv()
import uuid
import json

try:
    logger.debug(f"{mp.get_start_method()} ---- {__name__}")
    multiprocessing.set_start_method("spawn")
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

import datetime

d = datetime.datetime.now()
d = d.strftime("%m/%d/%Y %H:%M:%S")

rag_graph_cluster = RAG_graph(
    uri,
    user,
    password,
    database,
    OPENAI_API_KEY,
    OPENAI_EMBEDDINGS_URL,
)


industry_document = [
    {
        "SectorID": 10,
        "SectorName": "Energy",
        "IndustryGroups": [
            {
                "IndustryGroupID": 1010,
                "IndustryGroupName": "Energy",
                "Industries": [
                    {
                        "IndustryID": 101010,
                        "IndustryName": "Energy Equipment & Services",
                    },
                    {
                        "IndustryID": 101020,
                        "IndustryName": "Oil, Gas & Consumable Fuels",
                    },
                ],
            }
        ],
    },
    {
        "SectorID": 15,
        "SectorName": "Materials",
        "IndustryGroups": [
            {
                "IndustryGroupID": 1510,
                "IndustryGroupName": "Materials",
                "Industries": [
                    {"IndustryID": 151010, "IndustryName": "Chemicals"},
                    {"IndustryID": 151020, "IndustryName": "Construction Materials"},
                    {"IndustryID": 151030, "IndustryName": "Containers & Packaging"},
                    {"IndustryID": 151040, "IndustryName": "Metals & Mining"},
                    {"IndustryID": 151050, "IndustryName": "Paper & Forest Products"},
                ],
            }
        ],
    },
    {
        "SectorID": 20,
        "SectorName": "Industrials",
        "IndustryGroups": [
            {
                "IndustryGroupID": 2010,
                "IndustryGroupName": "Capital Goods",
                "Industries": [
                    {"IndustryID": 201010, "IndustryName": "Aerospace & Defense"},
                    {"IndustryID": 201020, "IndustryName": "Building Products"},
                    {
                        "IndustryID": 201030,
                        "IndustryName": "Construction & Engineering",
                    },
                    {"IndustryID": 201040, "IndustryName": "Electrical Equipment"},
                    {"IndustryID": 201050, "IndustryName": "Industrial Conglomerates"},
                    {"IndustryID": 201060, "IndustryName": "Machinery"},
                    {
                        "IndustryID": 201070,
                        "IndustryName": "Trading Companies & Distributors",
                    },
                ],
            },
            {
                "IndustryGroupID": 2020,
                "IndustryGroupName": "Commercial & Professional Services",
                "Industries": [
                    {
                        "IndustryID": 202010,
                        "IndustryName": "Commercial Services & Supplies",
                    },
                    {"IndustryID": 202020, "IndustryName": "Professional Services"},
                ],
            },
            {
                "IndustryGroupID": 2030,
                "IndustryGroupName": "Transportation",
                "Industries": [
                    {"IndustryID": 203010, "IndustryName": "Air Freight & Logistics"},
                    {"IndustryID": 203020, "IndustryName": "Passenger Airlines"},
                    {"IndustryID": 203030, "IndustryName": "Marine Transportation"},
                    {"IndustryID": 203040, "IndustryName": "Ground Transportation"},
                    {
                        "IndustryID": 203050,
                        "IndustryName": "Transportation Infrastructure",
                    },
                ],
            },
        ],
    },
    {
        "SectorID": 25,
        "SectorName": "Consumer Discretionary",
        "IndustryGroups": [
            {
                "IndustryGroupID": 2510,
                "IndustryGroupName": "Automobiles & Components",
                "Industries": [
                    {"IndustryID": 251010, "IndustryName": "Automobile Components"},
                    {"IndustryID": 251020, "IndustryName": "Automobiles"},
                ],
            },
            {
                "IndustryGroupID": 2520,
                "IndustryGroupName": "Consumer Durables & Apparel",
                "Industries": [
                    {"IndustryID": 252010, "IndustryName": "Household Durables"},
                    {"IndustryID": 252020, "IndustryName": "Leisure Products"},
                    {
                        "IndustryID": 252030,
                        "IndustryName": "Textiles, Apparel & Luxury Goods",
                    },
                ],
            },
            {
                "IndustryGroupID": 2530,
                "IndustryGroupName": "Consumer Services",
                "Industries": [
                    {
                        "IndustryID": 253010,
                        "IndustryName": "Hotels, Restaurants & Leisure",
                    },
                    {
                        "IndustryID": 253020,
                        "IndustryName": "Diversified Consumer Services",
                    },
                ],
            },
            {
                "IndustryGroupID": 2550,
                "IndustryGroupName": "Consumer Discretionary Distribution & Retail",
                "Industries": [
                    {"IndustryID": 255010, "IndustryName": "Distributors"},
                    {
                        "IndustryID": 255020,
                        "IndustryName": "Internet & Direct Marketing Retail",
                    },
                    {"IndustryID": 255030, "IndustryName": "Broadline Retail"},
                    {"IndustryID": 255040, "IndustryName": "Specialty Retail"},
                ],
            },
        ],
    },
    {
        "SectorID": 30,
        "SectorName": "Consumer Staples",
        "IndustryGroups": [
            {
                "IndustryGroupID": 3010,
                "IndustryGroupName": "Consumer Staples Distribution & Retail",
                "Industries": [
                    {
                        "IndustryID": 301010,
                        "IndustryName": "Consumer Staples Distribution & Retail",
                    }
                ],
            },
            {
                "IndustryGroupID": 3020,
                "IndustryGroupName": "Food, Beverage & Tobacco",
                "Industries": [
                    {"IndustryID": 302010, "IndustryName": "Beverages"},
                    {"IndustryID": 302020, "IndustryName": "Food Products"},
                    {"IndustryID": 302030, "IndustryName": "Tobacco"},
                ],
            },
            {
                "IndustryGroupID": 3030,
                "IndustryGroupName": "Household & Personal Products",
                "Industries": [
                    {"IndustryID": 303010, "IndustryName": "Household Products"},
                    {"IndustryID": 303020, "IndustryName": "Personal Care Products"},
                ],
            },
        ],
    },
    {
        "SectorID": 35,
        "SectorName": "Health Care",
        "IndustryGroups": [
            {
                "IndustryGroupID": 3510,
                "IndustryGroupName": "Health Care Equipment & Services",
                "Industries": [
                    {
                        "IndustryID": 351010,
                        "IndustryName": "Health Care Equipment & Supplies",
                    },
                    {
                        "IndustryID": 351020,
                        "IndustryName": "Health Care Providers & Services",
                    },
                    {"IndustryID": 351030, "IndustryName": "Health Care Technology"},
                ],
            },
            {
                "IndustryGroupID": 3520,
                "IndustryGroupName": "Pharmaceuticals, Biotechnology & Life Sciences",
                "Industries": [
                    {"IndustryID": 352010, "IndustryName": "Biotechnology"},
                    {"IndustryID": 352020, "IndustryName": "Pharmaceuticals"},
                    {
                        "IndustryID": 352030,
                        "IndustryName": "Life Sciences Tools & Services",
                    },
                ],
            },
        ],
    },
    {
        "SectorID": 40,
        "SectorName": "Financials",
        "IndustryGroups": [
            {
                "IndustryGroupID": 4010,
                "IndustryGroupName": "Banks",
                "Industries": [
                    {"IndustryID": 401010, "IndustryName": "Banks"},
                    {
                        "IndustryID": 401020,
                        "IndustryName": "Thrifts & Mortgage Finance",
                    },
                ],
            },
            {
                "IndustryGroupID": 4020,
                "IndustryGroupName": "Financial Services",
                "Industries": [
                    {"IndustryID": 402010, "IndustryName": "Financial Services"},
                    {"IndustryID": 402020, "IndustryName": "Consumer Finance"},
                    {"IndustryID": 402030, "IndustryName": "Capital Markets"},
                    {
                        "IndustryID": 402040,
                        "IndustryName": "Mortgage Real Estate Investment Trusts (REITs)",
                    },
                ],
            },
            {
                "IndustryGroupID": 4030,
                "IndustryGroupName": "Insurance",
                "Industries": [{"IndustryID": 403010, "IndustryName": "Insurance"}],
            },
        ],
    },
    {
        "SectorID": 45,
        "SectorName": "Information Technology",
        "IndustryGroups": [
            {
                "IndustryGroupID": 4510,
                "IndustryGroupName": "Software & Services",
                "Industries": [
                    {"IndustryID": 451020, "IndustryName": "IT Services"},
                    {"IndustryID": 451030, "IndustryName": "Software"},
                ],
            },
            {
                "IndustryGroupID": 4520,
                "IndustryGroupName": "Technology Hardware & Equipment",
                "Industries": [
                    {"IndustryID": 452010, "IndustryName": "Communications Equipment"},
                    {
                        "IndustryID": 452020,
                        "IndustryName": "Technology Hardware, Storage & Peripherals",
                    },
                    {
                        "IndustryID": 452030,
                        "IndustryName": "Electronic Equipment, Instruments & Components",
                    },
                ],
            },
            {
                "IndustryGroupID": 4530,
                "IndustryGroupName": "Semiconductors & Semiconductor Equipment",
                "Industries": [
                    {
                        "IndustryID": 453010,
                        "IndustryName": "Semiconductors & Semiconductor Equipment",
                    }
                ],
            },
        ],
    },
    {
        "SectorID": 50,
        "SectorName": "Communication Services",
        "IndustryGroups": [
            {
                "IndustryGroupID": 5010,
                "IndustryGroupName": "Telecommunication Services",
                "Industries": [
                    {
                        "IndustryID": 501010,
                        "IndustryName": "Diversified Telecommunication Services",
                    },
                    {
                        "IndustryID": 501020,
                        "IndustryName": "Wireless Telecommunication Services",
                    },
                ],
            },
            {
                "IndustryGroupID": 5020,
                "IndustryGroupName": "Media & Entertainment",
                "Industries": [
                    {"IndustryID": 502010, "IndustryName": "Media"},
                    {"IndustryID": 502020, "IndustryName": "Entertainment"},
                    {
                        "IndustryID": 502030,
                        "IndustryName": "Interactive Media & Services",
                    },
                ],
            },
        ],
    },
    {
        "SectorID": 55,
        "SectorName": "Utilities",
        "IndustryGroups": [
            {
                "IndustryGroupID": 5510,
                "IndustryGroupName": "Utilities",
                "Industries": [
                    {"IndustryID": 551010, "IndustryName": "Electric Utilities"},
                    {"IndustryID": 551020, "IndustryName": "Gas Utilities"},
                    {"IndustryID": 551030, "IndustryName": "Multi-Utilities"},
                    {"IndustryID": 551040, "IndustryName": "Water Utilities"},
                    {
                        "IndustryID": 551050,
                        "IndustryName": "Independent Power and Renewable Electricity Producers",
                    },
                ],
            }
        ],
    },
    {
        "SectorID": 60,
        "SectorName": "Real Estate",
        "IndustryGroups": [
            {
                "IndustryGroupID": 6010,
                "IndustryGroupName": "Equity Real Estate Investment Trusts (REITs)",
                "Industries": [
                    {"IndustryID": 601010, "IndustryName": "Diversified REITs"},
                    {"IndustryID": 601025, "IndustryName": "Industrial REITs"},
                    {"IndustryID": 601030, "IndustryName": "Hotel & Resort REITs"},
                    {"IndustryID": 601040, "IndustryName": "Office REITs"},
                    {"IndustryID": 601050, "IndustryName": "Health Care REITs"},
                    {"IndustryID": 601060, "IndustryName": "Residential REITs"},
                    {"IndustryID": 601070, "IndustryName": "Retail REITs"},
                    {"IndustryID": 601080, "IndustryName": "Specialized REITs"},
                ],
            },
            {
                "IndustryGroupID": 6020,
                "IndustryGroupName": "Real Estate Management & Development",
                "Industries": [
                    {
                        "IndustryID": 602010,
                        "IndustryName": "Real Estate Management & Development",
                    }
                ],
            },
        ],
    },
]


class Affected_Area(BaseModel):
    SectorName: str = Field(description="The name of the sector impacted")
    IndustryGroupName: str = Field(
        description="The name of the group of industry impacted"
    )
    IndustryName: str = Field(description="The name of the industry impacted")


class Evidence(BaseModel):
    DocumentName: str = Field(description="The name of the document.")
    Quote: str = Field(
        description="The document quote used for the analysis. The quote must be found in the data document"
    )


class Trend(BaseModel):
    TrendID: str = Field(description="The ID of the trend")
    Title: str = Field(description="The title of the trend")
    Summary: str = Field(description="A summary of the trend")
    Description: str = Field(description="A description of the trend")
    SourceAnalysis: str = Field(
        description="Explain how the source support the trend and how strong the evidence is."
    )
    AffectedAreas: List[Affected_Area] = Field(
        description="The list of the areas impacted by the trend"
    )
    EvidencedBy: List[Evidence] = Field(description="List of evidences")


class Trends_list(BaseModel):
    Trends: List[Trend] = Field(description="List of trends")


trend_detection = """
You are providing support for a production workflow in a strategy consultancy. This is not a simulation, you must perform real analysis on real data that will be used by your colleagues to provide services for clients. 

The file has a high chance of containing insights about trends. Your role is to notice trends that are affecting industries, markets or societies. A trend is a significant, noticeable change in  the environment of industries, markets, sectors and affecting organisations operating in those industries, markets, sectors. 
The trend is something that those organisations need to be aware of in order to develop meaningful strategies for maximum impact. When a trend possibly affects organizations then that will be recorded in the AffectedAreas field. 
You must extract the trend from a text that argues an idea; it cannot be extracted from a title or a table content or a text without context, as arguments or examples should illustrate the trend. If you conduct a quantitative analysis, you must provide concrete arguments from the text, such as the increase rate of other valuable numbers.
You will summarise the trend and record the names of the sectors, industries or industry groups that are affected by the trend that you have detected. The other input file contains the definitions of industries, sectors and industry groups that you should refer to when you state that they will be affected by a trend. 
Remember, the document you're reading is just a portion of a larger document. Do not make assumptions based solely on this section, especially if you're reading a table of contents.

The evidenced by field is where you will state which quote and which document the trend was noticed. 

The output trends should only come from the data document provided. You have to able to relate the trend to a quote from in the data document. 
Ensure the quote is in the data document.
If you do not find trends in the document do not output anything in the trend list.
You must be methodical and thorough. A team of consultants is dependent on your work and their project will be impacted if you fail to do this properly. 
"""
model_trends = ChatOpenAI(model="gpt-4o", temperature=0.1)
parser_trends = JsonOutputParser(pydantic_object=Trends_list)
get_trends = PromptTemplate(
    template="""Follow the instructions:
                              ***
                              {instruction}
                              ***
                              
                              Based on the industry details from this document:
                              ***
                              {industry_document}
                              ***
                              
                              using only the data provided in this data document: 
                              ***
                              {trend_document}
                              ***
                              \n
                              
                              ***
                              {format_instructions}
                              ***""",
    input_variables=["industry_document", "trend_document"],
    partial_variables={
        "format_instructions": parser_trends.get_format_instructions(),
        "instruction": trend_detection,
    },
)


chain_trends = get_trends | model_trends | parser_trends
# folders = ["45. Information Technology", "00. NAG Activities"]
folders = [
    "00. NAG Activities",
    "10. Energy",
    "15. Materials",
    "20. Industrials",
    "25. Consumer Discretionary",
    "30. Consumer Staples",
    "35. Healthcare",
    "40. Financials",
    "45. Information Technology",
    "50. Communication Services",
    "60. Real Estate",
]


def trend_extraction(chunk, gics_code, gics_name):
    # trends = chain_trends.invoke(
    #     {
    #         "industry_document": dict_to_plain_text(industry_document),
    #         "trend_document": chunk["text"] + "\nSource: " + chunk["source"],
    #     }
    # )
    trends = invoke(
        chain_trends,
        {
            "industry_document": dict_to_plain_text(industry_document),
            "trend_document": chunk["text"] + "\nSource: " + chunk["source"],
        },
    )
    # print(trends)
    for trend in trends["Trends"]:
        try:
            trend_id = str(uuid.uuid4())
            trend = {
                "trendId": trend_id,
                "title": trend["Title"],
                "Summary": trend["Summary"],
                "Description": trend["Description"],
                "AffectedAreas": str(
                    trend.get("AffectedAreas", trend.get("Affectedareas", ""))
                ),
                "EvidencedBy": str(
                    trend.get("EvidencedBy", trend.get("Evidencedby", ""))
                ),
                "SourceAnalysis": str(trend.get("SourceAnalysis", "")),
                "gics_code": gics_code,
                "gics_name": gics_name,
                "source": chunk["source"],
                "created": datetime.datetime.today().strftime("%Y-%m-%d"),
            }
            rag_graph_cluster.add_trend(trend)
            rag_graph_cluster.link_chunk_to_trend(chunk["chunkId"], trend_id)
        except Exception as e:
            print(e)


def generate_trends(folders=folders, number_of_processes=5):
    for folder in folders:  # [ f.path for f in os.scandir('.') if f.is_dir() ]:
        print(folder)
        folder = "graph_workflow/trends/" + folder
        folder_name = folder.split("/")[-1]
        gics_code = folder_name.split(".")[0]
        gics_name = folder_name.split(".")[1][1:]
        print(f"folder_name: {folder_name}")
        print(f"gics_code: {gics_code}")
        print(f"gics_name: {gics_name}")

        category = folder_name
        docs_id = []
        for file in [
            fi.path
            for fi in os.scandir(folder)
            if fi.is_file() and fi.path.split("/")[-1][0] != "."
        ]:
            try:
                file_name = file.split("/")[-1]
                # print()
                print(f"file_name: {file_name}")
                try:
                    query = (
                        'match (n:Document) where n.name = "' + file_name + '" return n'
                    )

                    # print(query)
                    doc = rag_graph_cluster.kg.query(
                        'match (n:Document) where n.name = "' + file_name + '" return n'
                    )
                except Exception as e:
                    print(e)
                print(len(doc))
                if len(doc) > 0:
                    print("Document already exists")
                    continue

                doc = rag_graph_cluster.add_document_and_chunks(
                    file, file_name, file_name, file_name, d
                )
                docs_id.append(doc["docId"])
            except Exception as e:
                print(e)
        query = (
            "match (n:Chunk)-[r]-(m) where m.docId in ['"
            + "', '".join(docs_id)
            + "'] return n as chunk"
        )

        chunks = rag_graph_cluster.kg.query(query)

        with Pool(processes=number_of_processes) as pool:
            results = []
            for chunk in chunks:
                chunk = chunk["chunk"]
                # print(chunk)
                if len(chunk["text"]) > 100:
                    results.append(
                        pool.apply_async(
                            trend_extraction, args=(chunk, gics_code, gics_name)
                        )
                    )

            print("Waiting for processes to finish...")
            while not all([r.ready() for r in results]):
                print(
                    f"trends added for chunk {[r.ready() for r in results].count(True)} / {len(results)}."
                )
                time.sleep(5)
