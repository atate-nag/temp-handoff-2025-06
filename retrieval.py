import os
from dotenv import load_dotenv
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
from core_components.src.RAG.rag import RAG
from core_components.src.DocumentLoader.document_retriever_sharepoint import (
    SharePointRetriever,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
import json
import sys
import tempfile
import tika
from tika import parser
from langchain.docstore.document import Document
from core_components.src.agents.openAI import load_agents, query_assistant, client
import shutil
from run_assistant_thread import parallel_file_process, overseer_manage_assistant, run_performance_retrieval_evaluation
import concurrent.futures

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

def performance_analysis(client,insight_files, queries):
        performance_file = overseer_manage_assistant(
            client, run_performance_retrieval_evaluation, insight_files, queries
        )
        return performance_file

def evaluate_query_retrieval(folder, queries):
    insight_files=[]
    insight_files.append(parallel_file_process(client, folder))
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_perfs = executor.submit(performance_analysis, client, insight_files, queries)
    perfs_file = future_perfs.result()
    return perfs_file
        
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
    files = find_and_download_files(
        "Shared Documents/Research/Incubation/Socrates/Documents/test_retrieval/"
    )


    queries = ["What are the relevant markets, for a company specialized in HPC, optimisation and numerical algorithms? What can you tell me about the major industrial markets"]
    for query in queries:
        result_steps, result_response, result_thread = query_assistant(
            client, queries_agent["id"], query
        )
        messages = client.beta.threads.messages.list(thread_id=result_thread.id)
        increased_queries = [query]
        for message in messages:
            if message.role == "assistant":
                increased_queries.extend(message.content[0].text.value.split("\n"))

        
            
    print(f"Researches: {increased_queries}")
    folder ="Files-MARKET-retrieved"
    print(f"Queries: {queries}")
    retrieved_docs = retrieve_docs(
        files, increased_queries
    )
    files_to_remove = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.isfile(os.path.join(folder, f))
            ]
    for f in files_to_remove:
        os.remove(f)
        
        
    for file in retrieved_docs[:6]:
        print(os.path.join(folder, file.split("/")[-1]))
        shutil.copyfile(file, os.path.join(folder, file.split("/")[-1]))
        # os.rename(file,os.path.join(name,file.split("/")[-1]))
    res = evaluate_query_retrieval('Files-Market-retrieved', queries)
    print(res)
    res_content = client.files.retrieve_content(res)
    print(res_content)
    json_retrieval = json.loads(res_content)
    print(json_retrieval)