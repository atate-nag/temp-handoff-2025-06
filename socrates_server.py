import concurrent.futures
from socrates_main import execute_workflow
from fastapi import FastAPI
from fastapi.responses import FileResponse

import datetime
import multiprocessing as mp
import threading
import time
import copy
import json
import os
from typing import Dict, Any

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


@app.get("/get_file")
def get_file(file_path):
    return FileResponse(path=file_path, filename=file_path.split["/"][-1])


@app.get("/list_files")
def list_files(folder):
    if folder == "Intermediates" or folder == "Strategic Reports":
        return [file for file in os.listdir(folder)]


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
