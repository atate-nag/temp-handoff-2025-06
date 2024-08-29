import os
import openai
from dotenv import load_dotenv
import time
import pandas as pd
from graph_workflow.graph_rag_lc import RAG_graph
import json
import uuid
import datetime
from graph_workflow.linkedin_agent import LinkedinAgent
import logging

if not logging.getLogger().hasHandlers():
    with open("config/logging_config.json") as json_file:
        logging.config.dictConfig(json.load(json_file))
logger = logging.getLogger("socrates_main")

# setup openaAI

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# setup neo4j database

uri = os.getenv("NEO4J_URL")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
OPENAI_EMBEDDINGS_URL = os.getenv("OPENAI_EMBEDDINGS_URL")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

d = datetime.datetime.now()
d = d.strftime("%m/%d/%Y %H:%M:%S")

ta = LinkedinAgent(period="1y")


def create_companies(companyName):
    logger.info(f"Creating company {companyName}")
    rag_graph.add_company(companyName)

    # (n, id, company['linkedin'],'linkedin',d)


def update_company_with_files(
    companyName,
    dataDir,
    fileType,
    source=None,
    source_location=None,
    creation_time=None,
):
    company_data_dir = os.path.join(dataDir, companyName)
    data_files = [
        os.path.join(company_data_dir, f)
        for f in os.listdir(company_data_dir)
        if os.path.isfile(os.path.join(company_data_dir, f))
    ]
    docs = []
    graph_files = rag_graph.kg.query(f"MATCH (n:Document) RETURN n")
    graph_files = [f["n"]["name"] for f in graph_files]
    # logger.info(graph_files)
    for data_file in data_files:
        logger.info(f"Adding data file {data_file} for {companyName}")
        if not data_file.split("/")[-1] in graph_files:
            logger.info("appending")
            docs.append(
                rag_graph.add_document_and_chunks(
                    data_file,
                    data_file.split("/")[-1],
                    data_file.split("/")[-1],
                    data_file.split("/")[-1],
                    d,
                )
            )
        else:
            logger.info("not appending")
            docs.append({"name": data_file.split("/")[-1]})

    rag_graph.add_class(
        {
            "classId": fileType,
            "name": fileType,
            "source": company_data_dir if source is None else source,
            "created": d if creation_time is None else creation_time,
            "text": fileType,
        }
    )
    rag_graph.link_company_to_class(companyName, fileType)

    for doc in docs:
        rag_graph.link_class_to_document(fileType, doc["name"])


mapping = {
    "Walmart": "Walmart",
    "Amazon": "Amazon_(company)",
    "Exxon Mobil": "Exxon_Mobil",
    "Apple": "Apple_Inc.",
    "UnitedHealth Group": "UnitedHealth_Group",
    "CVS Health": "CVS_Health",
    "Berkshire Hathaway": "Berkshire_Hathaway",
    "Alphabet": "Alphabet_Inc.",
    "McKesson": "McKesson",
    "Chevron": "Chevron_Corporation",
    "AmerisourceBergen": "AmerisourceBergen",
    "Costco Wholesale": "Costco",
    "Microsoft": "Microsoft",
    "Cardinal Health": "Cardinal_Health",
    "Cigna Group": "Cigna",
    "Marathon Petroleum": "Marathon_Petroleum",
    "Phillips 66": "Phillips_66",
    "Valero Energy": "Valero_Energy",
    "Ford Motor": "Ford_Motor",
    "Home Depot": "Home_Depot",
    "General Motors": "General_Motors",
    "Elevance Health": "Elevance_Health",
    "JPMorgan Chase": "JPMorgan_Chase",
    "Kroger": "Kroger",
    "Centene": "Centene",
    "Verizon Communications": "Verizon_Communications",
    "Walgreens Boots Alliance": "Walgreens_Boots_Alliance",
    "Fannie Mae": "Fannie_Mae",
    "Comcast": "Comcast",
    "AT&T": "AT&T",
    "Meta Platforms": "Meta_Platforms",
    "Bank of America": "Bank_of_America",
    "Target": "Target_Corporation",
    "Dell Technologies": "Dell_Technologies",
    "Archer Daniels Midland": "Archer_Daniels_Midland",
    "Citigroup": "Citigroup",
    "United Parcel Service": "United_Parcel_Service",
    "Pfizer": "Pfizer",
    "Lowe's": "Lowe's",
    "Johnson & Johnson": "Johnson_&_Johnson",
    "FedEx": "FedEx",
    "Humana": "Humana",
    "Energy Transfer": "Energy_Transfer_Partners",
    "State Farm Insurance": "State_Farm_Insurance",
    "Freddie Mac": "Freddie_Mac",
    "PepsiCo": "PepsiCo",
    "Wells Fargo": "Wells_Fargo",
    "Walt Disney": "The_Walt_Disney_Company",
    "ConocoPhillips": "ConocoPhillips",
    "Tesla": "Tesla,_Inc.",
}


rag_graph = RAG_graph(
    uri,
    user,
    password,
    database,
    OPENAI_API_KEY,
    OPENAI_EMBEDDINGS_URL,
)


d = datetime.datetime.now()
d = d.strftime("%m/%d/%Y %H:%M:%S")


def add_report_linker(companyName):
    pass


def add_linkedin(companyName):
    pass


def add_fortune(companyName):
    pass


def add_perigon(companyName):
    pass


def add_wikipedia(companyName):
    pass


def add_sources(companyName):
    folder_path = f"data/{companyName}"
    try:
        if os.path.exists(folder_path):
            for source in os.listdir(folder_path):
                docs = []
                for file in os.listdir(f"{folder_path}/{source}"):
                    logger.info(f"Adding {file} to {companyName}")
                    # self, document, title, source, source_location, creation_time
                    doc = rag_graph.kg.query(
                        'match (n:Document) where n.name = "' + file + '" return n'
                    )
                    if len(doc) > 0:
                        logger.info(f"Document {file} already exists")
                        continue

                    rag_graph.add_document_and_chunks(
                        f"{folder_path}/{source}/{file}",
                        file,
                        folder_path,
                        source,
                        d,
                    )

                    docs.append({"name": file})

                rag_graph.add_class(
                    {
                        "classId": source,
                        "name": source,
                        "source": source,
                        "created": d,
                        "text": source,
                    }
                )
                rag_graph.link_company_to_class(companyName, source)

                for doc in docs:
                    rag_graph.link_class_to_document(source, doc["name"])
    except Exception as e:
        logger.info(e)


def fill_graph(companies):
    logger.info("Filling graph")
    try:
        data = pd.read_csv("data/sources/fortune/fortune.csv")
        data["linkedin"] = data["linkedin2"]
        logger.info(data.columns)
        data = data.drop(columns=["linkedin2", "Unnamed: 0.1", "Unnamed: 0"])
    except Exception as e:
        logger.info(e)
    companies = [
        c.replace(" ", "_").replace(".", "").replace("'", "") for c in companies
    ]

    for company_name in companies:
        try:
            company = {
                "name": company_name,
                "linkedin": data[data["name"] == company_name]["linkedin"].values[0],
            }
        except Exception as e:
            logger.info(e)
            company = {
                "name": company_name,
                "linkedin": ta.get_linkedin_url_company(company_name),
            }

        name = company["name"]
        company["name"] = (
            company["name"].replace(" ", "_").replace(".", "").replace("'", "")
        )

        check = rag_graph.kg.query(
            f'MATCH (n:Company) WHERE n.name = "{company["name"]}" RETURN n LIMIT 10000;'
        )
        # logger.info(f"Check: {check}")
        if len(check) > 0:
            logger.info(f"Company {company['name']} already exists")
        else:
            create_companies(company["name"])

        ## Sources
        logger.info("SOURCES: ")

        add_sources(company["name"])

        ## ReportLinker
        logger.info("REPORTLINKER: ")
        check = rag_graph.kg.query(
            f'MATCH (n:Class) WHERE n.name =  "reportLinker_{company["name"]}" RETURN n LIMIT 1000;'
        )
        if len(check) > 0:
            logger.info(f"reportLinker {company['name']} already exists")
        else:
            try:
                # companyName, dataDir, fileType, title,source = None, source_location = None, creation_time = None
                update_company_with_files(
                    companyName=company["name"],
                    dataDir=f"data/sources/reportLinker/",
                    fileType=f"reportLinker_{company['name']}",
                    source="reportLinker",
                    source_location="reportLinker",
                    creation_time=d,
                )
                logger.info(f"Added {company['name']} for reportLinker")
            except Exception as e:
                logger.info(e)
                logger.info(f"Error with {company['name']} for reportLinker")

        ## LINKEDIN
        logger.info("LINKEDIN: ")
        check = rag_graph.kg.query(
            f'MATCH (n:Class) WHERE n.name =  "linkedin_{company["name"]}" RETURN n LIMIT 1000;'
        )
        # logger.info(f"Check: {check}")
        if len(check) > 0:
            logger.info(f"linkedin {company['name']} already exists")
        else:
            try:
                docs = []
                for n, t in ta.get_linkedin_feed(company["linkedin"]):
                    id = str(uuid.uuid4())
                    # add_document_and_chunks_from_text(self, document, title, source, source_location, creation_time)
                    docs.append(
                        rag_graph.add_document_and_chunks_from_text(
                            n, id, company["linkedin"], "linkedin", d
                        )
                    )

                rag_graph.add_class(
                    {
                        "classId": "linkedin_" + company["name"],
                        "name": "linkedin_" + company["name"],
                        "source": company["linkedin"],
                        "created": d,
                        "text": "linkedin",
                    }
                )

                rag_graph.link_company_to_class(
                    company["name"], "linkedin_" + company["name"]
                )

                for doc in docs:
                    rag_graph.link_class_to_document(
                        "linkedin_" + company["name"], doc["name"]
                    )
            except Exception as e:
                logger.info(e)
        ## LINKEDIN

        time.sleep(1.0)

        #     # logger.info(perigonAPI.get_companies_by_name('TotalEnergies'))
        #     logger.info(f"\nCompany: {company['name']}")
        #
        logger.info("FORTUNE: ")
        check = rag_graph.kg.query(
            f'MATCH (n:Class) WHERE n.name = "Fortune_{company["name"]}" RETURN n LIMIT 10000;'
        )
        # logger.info(f"Check: {check}")
        if len(check) > 0:
            logger.info(f"Fortune {company['name']} already exists")
        else:
            rag_graph.add_class(
                {
                    "classId": "Fortune_" + company["name"],
                    "name": "Fortune_" + company["name"],
                    "source": "Fortune",
                    "created": d,
                    "text": "Fortune",
                }
            )

            rag_graph.link_company_to_class(
                company["name"], "Fortune_" + company["name"]
            )
            # try:
            docs = []
            for key, value in company.items():
                if key == "name":
                    rag_graph.add_attribute(
                        "Fortune_" + company["name"],
                        str(key).replace(" ", "_").replace("'", "") + "_",
                        value,
                    )
                else:
                    rag_graph.add_attribute(
                        "Fortune_" + company["name"],
                        str(key).replace(" ", "_").replace("'", ""),
                        value,
                    )

                id = str(uuid.uuid4())
                value = str(value)

        check = rag_graph.kg.query(
            f'MATCH (n:Class) WHERE n.name = "perigon_page_1_{company["name"]}" RETURN n LIMIT 10000;'
        )
        logger.info("PERIGON: ")
        if len(check) > 0:
            logger.info(f"Perigon {company['name']} already exists")
        else:
            # try:
            # results = perigonAPI.get_company_by_name(company['name'])['results']
            logger.info("perigon/" + name + "_perigon.txt")

            try:
                with open("data/sources/perigon/" + name + "_perigon.txt", "r") as file:
                    # write to file
                    file_contents = file.read()
            except Exception as e:
                file_contents = []

            # logger.info(f"File content:\n{file_contents}")
            if len(file_contents) > 0:
                results = [
                    eval(r)
                    for r in file_contents.replace("}{", "}&&&{")
                    .replace("true", "True")
                    .replace("false", "False")
                    .replace("null", "None")
                    .split("&&&")
                ]
                # results = eval(results)
                # logger.info(f"Results: {results}")
                # assert False
            else:
                results = []
            i = 0
            for result in results:
                i += 1
                logger.info(i)
                class_name = "perigon_page_" + str(i) + "_" + company["name"]
                rag_graph.add_class(
                    {
                        "classId": class_name,
                        "name": class_name,
                        "source": "perigon",
                        "created": d,
                        "text": "perigon",
                    }
                )
                logger.info(class_name)
                rag_graph.link_company_to_class(company["name"], class_name)

                docs = []
                if isinstance(result, list):
                    pass
                else:
                    result = [result]
                # logger.info(result)
                for r in result:
                    for key, value in r.items():
                        id = str(uuid.uuid4())

                        value = str(value)
                        if len(str(value)) > 150:
                            doc = rag_graph.add_document_and_chunks_from_text(
                                key.replace("'", "") + ": " + value,
                                id,
                                "perigon",
                                "perigon",
                                d,
                            )
                            docs.append(doc)
                        else:
                            if key == "name":
                                rag_graph.add_attribute(
                                    "perigon_" + company["name"],
                                    key.replace(" ", "_").replace("'", "") + "_",
                                    value,
                                )
                            else:
                                rag_graph.add_attribute(
                                    "perigon_" + company["name"],
                                    key.replace(" ", "_").replace("'", ""),
                                    value,
                                )
                        logger.info(f"key: {key}")
                        logger.info(f"value: {value}")
                    for doc in docs:
                        rag_graph.link_class_to_document(class_name, doc["name"])
                        logger.info(f"node: {'perigon_'+company['name']}")
                        logger.info(f"with: {doc['name']}")

        check = rag_graph.kg.query(
            f'MATCH (n:Class) WHERE n.name = "wikipedia_{company["name"]}" RETURN n LIMIT 10000;'
        )

        logger.info("WIKIPEDIA: ")
        if len(check) > 0:
            logger.info(f"wikipedia {company['name']} already exists")
        else:
            rag_graph.add_class(
                {
                    "classId": "wikipedia_" + company["name"],
                    "name": "wikipedia_" + company["name"],
                    "source": "wikipedia",
                    "created": d,
                    "text": "wikipedia",
                }
            )

            rag_graph.link_company_to_class(
                company["name"], "wikipedia_" + company["name"]
            )
            try:
                with open(
                    f"data/sources/wikipedia/{mapping[name]}.json",
                    "r",
                    encoding="utf-8",
                ) as f:
                    # write to file
                    file_contents = f.read()

                    parsed_json = json.loads(file_contents)

                docs = []
                for key, value in parsed_json.items():
                    # rag_graph.add_attribute("perigon_"+company['name'],key.replace(' ', '_'),value)

                    id = str(uuid.uuid4())

                    value = str(value)
                    if len(str(value)) > 150:
                        doc = rag_graph.add_document_and_chunks_from_text(
                            key.replace("'", "") + ": " + value,
                            id,
                            "wikipedia",
                            "wikipedia",
                            d,
                        )
                        docs.append(doc)
                    else:
                        rag_graph.add_attribute(
                            "wikipedia_" + company["name"],
                            key.replace(" ", "_").replace("'", ""),
                            value,
                        )

                for doc in docs:
                    rag_graph.link_class_to_document(
                        "wikipedia_" + company["name"], doc["name"]
                    )

            except Exception as e:
                logger.info(e)
