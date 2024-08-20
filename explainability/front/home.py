import streamlit as st
import time
import json
import requests
import pandas as pd
import os

workflows = {
    "cleanUp": {},
    "fill_graph": {"companies": "List"},
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
        "company_name": "Str",
        "problemFile": "Str",
        "force_recreate": "Bool",
    },
    "clusterTrends": {"compute_embeddings": "Bool", "number_of_processes": "Int"},
    "runStrategy": {"companyName": "Str", "problemsFile": "Str"},
    "runFrameworks": {"companyName": "Str", "problemsFile": "Str"},
    "runScenarios": {"companyName": "Str", "problemsFile": "Str"},
}


def file_selector(folder_path="."):
    filenames = os.listdir(folder_path)
    selected_filename = st.selectbox("Select a file", filenames)
    return os.path.join(folder_path, selected_filename)


url = "http://127.0.0.1:8000/run"


st.set_page_config(
    page_title="Socrates",
    page_icon="👋",
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
print(workflow)
print(workflows[workflow])
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
            f"Enter {key}", value="Tesla\nApple\nWalmart" if key == "companies" else ""
        ).split("\n")
    elif value == "Bool":
        current_workflow["parameters"][key] = st.checkbox(f"Delete existing insights")
    elif value == "Int":
        current_workflow["parameters"][key] = st.number_input(f"Enter {key}", value=1)
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
    print("\n")
    print(st.session_state["running"])
    if st.session_state["running"]:
        st.session_state["running"] = False
    else:
        p = requests.post(url, json=st.session_state["workflow_config"].copy())
        st.session_state["workflow_config"] = {}
        print(p.text)
        st.session_state["running"] = True
    print(st.session_state["running"])


# st.button('Clear name', on_click=start_socrates, args=[''])
st.button(
    "Start Socrates!" if not st.session_state["running"] else "Stop Socrates",
    on_click=start_socrates,
    args=["Streamlit"],
)

st.write(f"Running: {st.session_state['running']}")


def get_status():
    url = "http://127.0.0.1:8000/get_all_status"
    x = requests.get(url)
    print(x.text)
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
