import concurrent.futures
from socrates_main import execute_workflow
from fastapi import FastAPI
import datetime
import multiprocessing as mp
import threading
import time
from typing import Dict, Any

app = FastAPI()
running_data = {}

# with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
#         future = executor.submit(execute_workflow, workflow_config)
#         while not future.done():
#             if time.time() - start > timeout:
#                 raise Exception("timeout", f"function: {fn.__name__} failed")
#             time.sleep(0.2)
#     future.result()


def update_status(running_data=running_data):
    for run_id, data in running_data.items():
        if not running_data[run_id]["status"] == "done":
            if data["process"].ready():
                running_data[run_id]["status"] = "done"
                running_data[run_id]["result"] = data["process"].get()


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


@app.post("/run")
async def create_run(workflow_config: Dict[Any, Any]):
    print(workflow_config)
    run_id = str(datetime.datetime.now())
    print("Starting run", run_id)

    with mp.Pool(processes=1) as pool:

        p = pool.apply_async(execute_workflow, args=(workflow_config,))

    # with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    #     future = executor.submit(execute_workflow, workflow_config)
    running_data[run_id] = {"status": "running", "process": p}
    print("Run Started", run_id)
    return run_id


@app.get("/")
async def root():
    return {"message": "Hello World"}
