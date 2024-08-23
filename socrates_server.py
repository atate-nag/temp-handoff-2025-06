import concurrent.futures
from socrates_main import execute_workflow
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi import File, UploadFile
from graph_workflow.graph_rag_lc import RAG_graph
import datetime
import multiprocessing as mp
import threading
import time
import copy
import json
import os
from typing import Dict, Any

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

mp.set_start_method("spawn")

app = FastAPI()
running_data = {}

# with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
#         future = executor.submit(execute_workflow, workflow_config)
#         while not future.done():
#             if time.time() - start > timeout:
#                 raise Exception("timeout", f"function: {fn.__name__} failed")
#             time.sleep(0.2)
#     future.result()


def update_companies():
    company_names = rag_graph.kg.query(
        "match (n:Company) return DISTINCT n.name as name"
    )
    company_names = [company["name"] for company in company_names]
    for company in company_names:
        if not os.path.exists(f"data/{company}"):
            os.mkdir(f"data/{company}")
            print(f"Created company {company}")


@app.post("/create_company")
def create_company(company):
    try:
        rag_graph.add_company(company)
        update_companies()
        return {"message": f"Successfully created company {company}"}
    except Exception as e:
        return {"message": f"Error: {e}"}


@app.get("/get_companies")
def get_companies():
    update_companies()
    company_names = rag_graph.kg.query(
        "match (n:Company) return DISTINCT n.name as name"
    )
    company_names = [company["name"] for company in company_names]
    return company_names


@app.get("/get_sources")
def get_sources(company):
    try:
        return [source for source in os.listdir(f"data/{company}")]
    except Exception as e:
        return {"message": f"Error: {e}"}


@app.post("/add_source")
def add_source(company, source):
    try:
        os.mkdir(f"data/{company}/{source}")
        return {"message": f"Successfully added source {source} to company {company}"}
    except Exception as e:
        return {"message": f"Error: {e}"}


@app.post("/upload_company_file")
def upload_company_file(company, source, file: UploadFile = File(...)):
    try:
        print(f"File name: {file.filename}")
        contents = file.file.read()
        with open(f"data/{company}/{source}/{file.filename}", "wb") as f:
            f.write(contents)
    except Exception:
        return {"message": "There was an error uploading the file"}
    finally:
        file.file.close()

    return {"message": f"Successfully uploaded {file.filename}"}


@app.get("/get_source_files")
def get_source_files(company, source):
    return [file for file in os.listdir(f"data/{company}/{source}")]


@app.get("/get_file")
def get_file(file_path):
    print(f"File Path: {file_path}")
    return FileResponse(path=file_path, filename=file_path.split("/")[-1])


@app.get("/list_files")
def list_files(folder):
    if folder == "Intermediates" or folder == "Strategic Reports":
        return [file for file in os.listdir(folder)]


@app.post("/delete_file")
def delete_file(file_path):
    print(f"File Path: {file_path}")
    if os.path.exists(file_path):
        print("File exists")
        if file_path.split("/")[0] in ["Intermediates", "Strategic Reports"]:
            # return {"message": "Cannot delete this file"}
            os.remove(file_path)
            return {"message": "File deleted successfully"}


@app.post("/set_problem_statement")
def set_problem_statement(file: UploadFile = File(...)):
    try:
        print(f"File name: {file.filename}")
        contents = file.file.read()
        with open(file.filename, "wb") as f:
            f.write(contents)
    except Exception:
        return {"message": "There was an error uploading the file"}
    finally:
        file.file.close()

    return {"message": f"Successfully uploaded {file.filename}"}


def update_status(running_data=running_data):
    # PROCESS

    for run_id, data in running_data.items():
        if not running_data[run_id]["status"] == "done":
            if "process" in data:
                if data["process"].is_alive():
                    pass
                else:
                    running_data[run_id]["status"] = "done"
                    running_data[run_id]["result"] = data["process"].exitcode
                    print(
                        f"Process {run_id} is done with exitcode {data['process'].exitcode}"
                    )
            else:
                running_data[run_id]["status"] = "done"
                running_data[run_id]["result"] = "No process found"
                print(f"Process {run_id} is done with no process found")

    # POOL

    # print("Updating status")
    # for run_id, data in running_data.items():
    #     if not running_data[run_id]["status"] == "done":
    #         print("Checking status")
    #         if "process" in data:
    #             print("Updating if ready")
    #             print(f"Is process ready: {data['process'].ready()}")
    #             print(f"Is process ready: {data['process'].get()}")
    #             if data["process"].ready():
    #                 print("Updating...")
    #                 running_data[run_id]["status"] = "done"
    #                 running_data[run_id]["result"] = data["process"].get()


# t = threading.Thread(target=update_status).start()


@app.get("/get_status")
async def get_status(run_id):
    update_status()
    print(f"running_data: {running_data}")
    print(run_id)
    return {
        "message": "",
        "run_data": (
            running_data[run_id]["result"]
            if running_data[run_id]["status"] == "done"
            else None
        ),
        "status": running_data[run_id]["status"],
    }


@app.get("/get_all_status")
async def get_status():
    update_status()
    print(f"running_data: {running_data}")
    status = {}

    for runid, data in running_data.items():
        status[runid] = {
            "status": data["status"],
            "results": data["result"] if "result" in data else None,
        }

    print(f"status: {status}")
    return {"message": "", "run_data": status}


@app.post("/run")
async def create_run(workflow_config: Dict[Any, Any]):
    print(workflow_config)
    run_id = str(datetime.datetime.now())
    print("Starting run", run_id)

    p = mp.Process(target=execute_workflow, args=(workflow_config,))
    p.start()
    # with mp.Pool(processes=5) as pool:

    #     p = pool.apply_async(execute_workflow, args=(workflow_config,))

    # with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    #     future = executor.submit(execute_workflow, workflow_config)
    running_data[run_id] = {"status": "running", "process": p}
    print("Run Started", run_id)
    return run_id


@app.get("/")
async def root():
    return {"message": "Hello World"}
