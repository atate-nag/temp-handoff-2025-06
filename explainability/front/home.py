import logging
import streamlit as st
import time
import json
import requests
import pandas as pd
import os
import datetime
from streamlit.logger import get_logger


from logging.config import fileConfig

if "socrates_front" not in logging.root.manager.loggerDict.keys():
    fileConfig(
        "../../config/logging_config_front.ini",
        defaults={"date": str(datetime.datetime.now().strftime("%m-%d-%Y"))},
    )
logger = logging.getLogger("socrates_front")


# from streamlit.logger import get_logger

# class StreamlitLogHandler(logging.Handler):
#     def __init__(self, widget_update_func):
#         super().__init__()
#         self.widget_update_func = widget_update_func

#     def emit(self, record):
#         msg = self.format(record)
#         self.widget_update_func(msg)

if "logs" not in st.session_state:
    st.session_state["logs"] = []

# def update_logs(msg):
#     st.session_state["logs"].append(msg)
#     st.session_state["logs"] = st.session_state["logs"][-30:]

# logger = get_logger("socrates_server")
# handler = StreamlitLogHandler(update_logs)
# logger.addHandler(handler)

st.set_page_config(
    page_title="Socrates",
    page_icon="🔭",
    layout="wide",
)

st.write("# Welcome to Socrates! 👋")

if "running" not in st.session_state:
    st.session_state["running"] = False

if "workflow_config" not in st.session_state:
    st.session_state["workflow_config"] = {}

if "all_status" not in st.session_state:
    st.session_state["all_status"] = {}

st.markdown(
    """
    Socrates is an open-source app framework built specifically for
    generating strategic reports from your data. 
"""
)
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = []

col1, col2 = st.columns([1.0, 1.0], gap="large")
with col1:
    workflows = {
        "cleanUp": {},
        "fillGraph": {"companies": "List"},
        "getInsights": {
            "companies": "List",
            "delete_existing_insights": "Bool",
            "number_of_processes": "Int",
        },
        "condenseTrends": {"company_name": "Str", "problemsFile": "Str"},
        "condenseCompanyData": {"company_name": "Str", "problem": "Str"},
        "getCapabilities": {
            "companies": "List",
            "compute_embeddings": "Bool",
            "number_of_processes": "Int",
        },
        "getTrends": {
            "folders": "List",
            "number_of_processes": "Int",
        },
        "clusterTrends": {"compute_embeddings": "Bool", "number_of_processes": "Int"},
        "runStrategy": {"companyName": "Str", "problemsFile": "Str"},
        "runFrameworks": {"companyName": "Str", "problemsFile": "Str"},
        "runScenarios": {"companyName": "Str", "problemsFile": "Str"},
        "runReport2": {"company": "Str"},
    }

    def file_selector(folder_path="."):
        filenames = os.listdir(folder_path)
        selected_filename = st.selectbox("Select a file", filenames)
        return os.path.join(folder_path, selected_filename)

    url = "http://127.0.0.1:8000/run"

    st.write(json.dumps(st.session_state["workflow_config"], indent=4, sort_keys=True))

    uploaded_files = st.file_uploader(
        "Select workflow config json file to upload", accept_multiple_files=True
    )
    for uploaded_file in uploaded_files:
        bytes_data = uploaded_file.read()
        st.write("filename:", uploaded_file.name)
        st.write(bytes_data)
        with open(uploaded_file.name, "wb") as f:
            f.write(bytes_data)

    workflow = st.selectbox(label="Select a workflow", options=list(workflows.keys()))
    logger.info(workflow)
    logger.info(workflows[workflow])
    workflow_name = st.text_input(
        "Enter the name of the workflow 👇",
        # label_visibility="visible",
        # disabled=True,
        # placeholder=True,
    )
    current_workflow = {"step": workflow, "parameters": {}}
    for key, value in workflows[workflow].items():
        if value == "List":
            current_workflow["parameters"][key] = st.text_area(
                f"Enter {key}",
                value="Tesla\nApple\nWalmart" if key == "companies" else "",
            ).split("\n")
        elif value == "Bool":
            current_workflow["parameters"][key] = st.checkbox(key, value=True)
        elif value == "Int":
            current_workflow["parameters"][key] = st.number_input(
                f"Enter {key}", value=1
            )
        elif value == "Str":
            current_workflow["parameters"][key] = st.text_input(
                f"Enter {key}",
                value="./problem_statements.json" if key == "problemsFile" else "",
            )
    # if workflows[workflow] == "List":
    #     companies = st.text_area("Enter companies")
    #     st.session_state['workflow_config'][workflow] = {"companies": companies}

    def add_workflow(name):
        current_workflow["enabled"] = True
        st.session_state["workflow_config"][name] = current_workflow

    st.button(
        "Add workflow",
        on_click=add_workflow,
        args=[workflow_name if workflow_name else workflow],
    )

    def start_socrates(name):
        logger.info("\n")
        logger.info(st.session_state["running"])

        p = requests.post(url, json=st.session_state["workflow_config"].copy())
        st.session_state["workflow_config"] = {}
        logger.info(p.text)
        st.session_state["running"] = True

        # if st.session_state["running"]:
        #     st.session_state["running"] = False
        # else:
        #     p = requests.post(url, json=st.session_state["workflow_config"].copy())
        #     st.session_state["workflow_config"] = {}
        #     logger.info(p.text)
        #     st.session_state["running"] = True
        # logger.info(st.session_state["running"])

    # st.button('Clear name', on_click=start_socrates, args=[''])
    st.button(
        "Start Socrates!",
        on_click=start_socrates,
        args=["Streamlit"],
    )

    st.write(f"Running: {st.session_state['running']}")

    def get_status():
        url = "http://127.0.0.1:8000/get_all_status"
        x = requests.get(url)
        logger.info(x.text)
        st.session_state["all_status"] = json.loads(x.text)
        return x.text

    st.button(
        "Get runs status!",
        on_click=get_status,
    )

    # st.write(f"Status: {json.dumps(st.session_state['all_status'], indent=4, sort_keys=True)}")
    st.table(
        data=(
            pd.DataFrame.from_dict(
                st.session_state["all_status"]["run_data"], orient="index"
            )
            if "run_data" in st.session_state["all_status"]
            else pd.DataFrame()
        )
    )

    st.write("Logs:")

    # for log in st.session_state["logs"]:
    #     st.write(log)
    log_files = [
        folder
        for folder in os.listdir("../../logs")
        if os.path.isdir(os.path.join("../../logs", folder))
    ]
    st.selectbox("Select a file", options=log_files)


with col2:
    uploaded_file = st.file_uploader(
        "Select problem statement file to import", accept_multiple_files=False
    )
    logger.info(f"uploaded_file: {uploaded_file}")
    if uploaded_file and uploaded_file.name not in st.session_state["uploaded_files"]:
        bytes_data = uploaded_file.read()
        st.write("filename:", uploaded_file.name)

        url = "http://127.0.0.1:8000/set_problem_statement"
        file = {"file": (uploaded_file.name, bytes_data)}
        r = requests.post(url, files=file)
        if r.status_code == 200:
            st.write("File uploaded successfully")
            st.session_state["uploaded_files"].append(uploaded_file.name)
        logger.info(r.text)

    st.write("Uploaded files:")
    st.write(st.session_state["uploaded_files"])
