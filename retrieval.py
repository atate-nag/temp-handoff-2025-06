import concurrent.futures
import json
import os
import shutil
import sys
import tempfile

import tika
from core_components.src.agents.openAI import client, load_agents, query_assistant
from core_components.src.DocumentLoader.document_retriever_sharepoint import (
    SharePointRetriever,
)
from core_components.src.RAG.rag import RAG
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# from run_assistant_thread import (
#     run_trends_analysis,
#     run_challenges_analysis,
#     run_capabilities_analysis,
#     run_actions,
#     overseer_manage_assistant,
#     import_data_file,
#     parallel_file_process,
# )
from langchain_openai import OpenAIEmbeddings
from tika import parser

from run_assistant_thread import (
    import_data_files_and_upload,
    overseer_manage_assistant,
    parallel_file_process,
    run_performance_retrieval_evaluation,
)

load_dotenv()
sharepoint_base_url = os.environ["sharepoint_base_url"]
sharepoint_user = os.environ["sharepoint_user"]
sharepoint_password = os.environ["sharepoint_password"]
sharePointRetriever = SharePointRetriever(
    sharepoint_base_url, sharepoint_user, sharepoint_password
)
vector_store_ = ["Chroma"]
embedding_function = OpenAIEmbeddings()
text_chunkers = [
    RecursiveCharacterTextSplitter(
        chunk_size=4000,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    ),
]
rag = RAG(vector_store_, embedding_function, text_chunkers)


def find_and_download_files(input_folder):
    files_ = list(
        sharePointRetriever.get_all_documents_from_folder(
            input_folder, extension=["pdf", "pptx", "docx"]
        )
    )

    files = []
    for file in files_:
        try:
            files.append(
                sharePointRetriever.download_file(
                    file, os.path.join(tempfile.mkdtemp(), os.path.basename(file))
                )
            )
            # print(f"\ndownloaded File: {files}")
        except Exception as e:
            print(e)
    return files


def retrieve_docs(files, queries, threshold=0.7):
    tika.initVM()
    docs = []
    for file in files:
        parsed = parser.from_file(file)
        doc = Document(
            page_content=parsed["content"], metadata={"source": file}
        )  # TODO metadata=parsed["metadata"])
        # print(parsed["metadata"])
        # print(doc.metadata)
        docs.append(doc)
    rag.add_documents(docs)

    # def query_assistant(client, assistant, prompt, file_ids=[], description=''):

    # researches = [["Numerical Algorithms Group or NAG", "NAG", "Numerical Algorithms Group"],
    #               ["NAG insights"],
    #               ["Markets",]]

    retrieved_docs = []
    for query in queries:
        retrieved_docs_per_query = []
        # print(f"\nquery: {query}")
        # print(f"\nresearch: {research}")
        print(f"\nquery: {query}\n")
        results = rag.similarity_search_with_relevance_scores(query=query)
        # print(f"\nthresholds: {thresholds}\n")
        for i, result in enumerate(results):
            # print(f"\n\nSimilarity Results: \n{result}\n\n")
            # print(f"vs: {len(result)}")
            retrieved_doc = []
            for content, _threshold in result:
                # print(f"content: {len(content.page_content)}\n")
                # print(f"_threshold: {_threshold}\n")
                # print(f"threshold: {threshold}\n")
                if _threshold > threshold:
                    # print(f"source: {content.metadata['source']}\n")
                    retrieved_doc.append(content.metadata["source"])
            retrieved_docs.extend(retrieved_doc)
            retrieved_docs_per_query.append((query, list(set(retrieved_doc))))
        # retrieved_docs_per_query = list(set(retrieved_docs_per_query))
        # print(f"\nretrieved_docs_per_query: {retrieved_docs_per_query}\n")
    retrieved_docs = list(set(retrieved_docs))
    print(f"\nretrieved_docs: {retrieved_docs}\n")
    return retrieved_docs


def performance_analysis(
    client,
    insight_files,
    queries,
    write_intermediate=False,
    prefix="retrieval",
    index="",
):
    performance_file = overseer_manage_assistant(
        client,
        write_intermediate,
        prefix,
        index,
        run_performance_retrieval_evaluation,
        insight_files,
        queries,
    )
    return performance_file


def evaluate_query_retrieval(
    folder, queries, company_data=None, prefix="retrieval", PRODUCE_INTERMEDIATES=False
):
    # insight_files=[]
    insight_files = parallel_file_process(
        client, folder, company_data, prefix, PRODUCE_INTERMEDIATES
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_perfs = [
            (
                executor.submit(performance_analysis, client, [insight_file], queries),
                filename,
            )
            for insight_file, filename in insight_files
        ]
    perfs_files = [
        (future_perf.result(), filename) for future_perf, filename in future_perfs
    ]
    return perfs_files


# pdf:docinfo:creator
# Content-Type

# {'pdf:unmappedUnicodeCharsPerPage': ['0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0'],
#  'pdf:PDFVersion': '1.3',
#  'pdf:docinfo:title': 'Numerical Libraries-5 Forces-June 2020 ',
#  'xmp:CreatorTool': 'Word',
#  'pdf:hasXFA': 'false',
#  'access_permission:modify_annotations': 'true',
#  'access_permission:can_print_degraded': 'true',
#  'X-TIKA:Parsed-By-Full-Set': ['org.apache.tika.parser.DefaultParser', 'org.apache.tika.parser.pdf.PDFParser'],
#  'X-TIKA:content_handler': 'ToTextContentHandler',
#  'dc:creator': 'Katherine Watson',
#  'pdf:num3DAnnotations': '0',
#  'dcterms:created': '2022-04-25T08:50:04Z',
#  'dcterms:modified': '2022-04-25T08:50:04Z',
#  'dc:format': 'application/pdf; version=1.3',
#  'pdf:docinfo:creator_tool': 'Word',
#  'pdf:overallPercentageUnmappedUnicodeChars': '0.0',
#  'access_permission:fill_in_form': 'true',
#  'pdf:docinfo:modified': '2022-04-25T08:50:04Z', 'pdf:hasCollection': 'false',
#  'pdf:encrypted': 'false', 'dc:title': 'Numerical Libraries-5 Forces-June 2020 ', 'pdf:containsNonEmbeddedFont': 'false',
#  'Content-Length': '1342160', 'pdf:hasMarkedContent': 'false', 'Content-Type': 'application/pdf', 'pdf:docinfo:creator': 'Katherine Watson',
#  'pdf:producer': 'macOS Version 12.3.1 (Build 21E258) Quartz PDFContext', 'pdf:totalUnmappedUnicodeChars': '0',
#  'access_permission:extract_for_accessibility': 'true', 'access_permission:assemble_document': 'true',
#  'xmpTPg:NPages': '42', 'resourceName': "b'Numerical Libraries-5 Forces-June 2020 .pdf'", 'pdf:hasXMP': 'false',
#  'pdf:charsPerPage': ['7950', '2059', '2854', '3647', '4895', '5781', '3904', '6374', '4969', '5696', '2556', '2585', '4392', '3343', '2772', '2403', '2529', '2384', '4291', '3417', '917', '3880', '3708', '2970', '5333', '2222', '4956', '5692', '4004', '3622', '2986', '3572', '3361', '2774', '4287', '1616', '1558', '3662', '2955', '2574', '1958', '2354'], 'access_permission:extract_content': 'true', 'access_permission:can_print': 'true',
#  'X-TIKA:Parsed-By': ['org.apache.tika.parser.DefaultParser', 'org.apache.tika.parser.pdf.PDFParser'],
#  'X-TIKA:parse_time_millis': '182', 'X-TIKA:embedded_depth': '0', 'access_permission:can_modify': 'true', 'pdf:docinfo:producer': 'macOS Version 12.3.1 (Build 21E258) Quartz PDFContext',
#  'pdf:docinfo:created': '2022-04-25T08:50:04Z', 'pdf:containsDamagedFont': 'false'}

if __name__ == "__main__":
    agents = load_agents("openAI_agents.yml")
    queries_agent = agents["OpenAI"]["queries_agent"]
    # files = find_and_download_files(
    #     "Shared Documents/Research/Incubation/Socrates/Documents/test_retrieval/"
    # )

    query = [
        "What are the relevant markets, for a company specialized in HPC, optimisation and numerical algorithms? What can you tell me about the major industrial markets"
    ]
    # for query in queries:
    #     result_steps, result_response, result_thread = query_assistant(
    #         client, queries_agent["id"], query
    #     )
    #     messages = client.beta.threads.messages.list(thread_id=result_thread.id)
    #     increased_queries = [query]
    #     for message in messages:
    #         if message.role == "assistant":
    #             increased_queries.extend(message.content[0].text.value.split("\n"))

    # print(f"Researches: {increased_queries}")
    increased_queries = [
        "What are the relevant markets, for a company specialized in HPC, optimisation and numerical algorithms? What can you tell me about the major industrial markets",
        "For a company specialized in High Performance Computing (HPC), optimization, and numerical algorithms, relevant markets include but aren't limited to:",
        "1. Financial services",
        "2. Energy and utilities",
        "3. Automotive industry",
        "4. Aerospace and defense",
        "5. Life sciences and health care",
        "6. Manufacturing",
        "7. Telecommunications",
        "8. Research and academia",
        "9. Oil and gas industry",
        "10. Electronics and semiconductors",
        "11. Weather forecasting",
        "12. Computational biology and chemistry",
        "13. Data analytics and big data",
        "14. Cloud computing services",
        "15. Government and public sector initiatives",
        "**Major Industrial Markets:**",
        "1. **Financial Services:**",
        "   - Utilize HPC for real-time trading algorithms, risk management, fraud detection, and quantitative modeling.",
        "2. **Energy and Utilities:**",
        "   - Used in simulations for oil and gas exploration, renewable energy sources optimization, and grid management.",
        "3. **Automotive Industry:**",
        "   - Applications in crash simulations, aerodynamic simulations, and optimization of designs for fuel efficiency.",
        "4. **Aerospace and Defense:**",
        "   - Utilized for flight simulations, satellite tracking, missile guidance systems, and stealth technology design.",
        "5. **Life Sciences and Health Care:**",
        "   - Critical for drug discovery, genomics and proteomics, personalized medicine, and medical imaging.",
        "6. **Manufacturing:**",
        "   - Helps in product design, process simulation, and optimization to reduce costs and improve quality.",
        "7. **Telecommunications:**",
        "   - Used for network design optimization, traffic management, and simulation of new technologies.",
        "8. **Research and Academia:**",
        "   - Fundamental tool for scientific research across physics, chemistry, climatology, and more.",
        "9. **Oil and Gas Industry:**",
        "   - Key for reservoir simulation, seismic imaging, and optimizing extraction processes.",
        "10. **Electronics and Semiconductors:**",
        "    - Supports design and simulation of electronic components, enhancing performance while reducing power consumption.",
        "11. **Weather Forecasting:**",
        "    - Enables more accurate and detailed climate and weather modeling.",
        "12. **Computational Biology and Chemistry:**",
        "    - Facilitates understanding of complex biological systems and chemical reactions.",
        "13. **Data Analytics and Big Data:**",
        "    - Power the processing and analysis of large data sets for insights and decision making.",
        "14. **Cloud Computing Services:**",
        "    - Offers scalable HPC resources on-demand, making it accessible to a wider range of businesses.",
        "15. **Government and Public Sector Initiatives:**",
        "    - Utilized for urban planning, national security, education, and healthcare initiatives.",
    ]

    folder = "Files-MARKET-retrieved"
    company_data = "Files-COMPANY-retrieved"
    company_data, _ = import_data_files_and_upload(client, "Files-COMPANY-retrieved")
    # print(f"Queries: {queries}")
    # retrieved_docs = retrieve_docs(
    #     files, increased_queries
    # )
    # files_to_remove = [
    #             os.path.join(folder, f)
    #             for f in os.listdir(folder)
    #             if os.path.isfile(os.path.join(folder, f))
    #         ]
    # for f in files_to_remove:
    #     os.remove(f)

    # for file in retrieved_docs[:6]:
    #     print(os.path.join(folder, file.split("/")[-1]))
    #     shutil.copyfile(file, os.path.join(folder, file.split("/")[-1]))
    #     # os.rename(file,os.path.join(name,file.split("/")[-1]))
    res = evaluate_query_retrieval(
        "Files-Market-retrieved", increased_queries, company_data=company_data
    )
    print(res)
    for f, file_name in res:
        res_content = client.files.retrieve_content(f)
        print(file_name)
        print(res_content)
        json_retrieval = json.loads(res_content)
