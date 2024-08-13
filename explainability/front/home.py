import streamlit as st
import time
import json

workflows = {
    "cleanUp": {},
    "fill_graph": {"companies": "List"},
    "getInsights": {
        "companies": "List",
        "delete_existing_insights": "Bool",
        "number_of_processes": "Int",
    },
    "condenseTrends": {},
    "condenseCompanyData": {},
    "getCapabilities": {},
    "getTrends": {},
    "clusterTrends": {},
    "runStrategy": {},
    "runFrameworks": {},
    "runScenarios": {},
}

st.set_page_config(
    page_title="Socrates",
    page_icon="👋",
)

st.write("# Welcome to Socrates! 👋")

if "running" not in st.session_state:
    st.session_state["running"] = False

if "workflow_config" not in st.session_state:
    st.session_state["workflow_config"] = {}

st.markdown(
    """
    Socrates is an open-source app framework built specifically for
    generating strategic reports from your data. 
"""
)

st.write(json.dumps(st.session_state["workflow_config"], indent=4, sort_keys=True))

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
        current_workflow["parameters"][key] = st.text_area(f"Enter {key}").split("\n")
    elif value == "Bool":
        current_workflow["parameters"][key] = st.checkbox(f"Delete existing insights")
    elif value == "Int":
        current_workflow["parameters"][key] = st.number_input(f"Enter {key}")
# if workflows[workflow] == "List":
#     companies = st.text_area("Enter companies")
#     st.session_state['workflow_config'][workflow] = {"companies": companies}


def add_workflow(name):
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
        st.session_state["running"] = True
    print(st.session_state["running"])


# st.button('Clear name', on_click=start_socrates, args=[''])
st.button(
    "Start Socrates!" if not st.session_state["running"] else "Stop Socrates",
    on_click=start_socrates,
    args=["Streamlit"],
)

st.write(f"Running: {st.session_state['running']}")
