import time  # to simulate a real time data, time loop

import numpy as np  # np mean, np random
import pandas as pd  # read csv, df manipulation
import plotly.express as px  # interactive charts
import streamlit as st  # 🎈 data web app development
from data_store import Data_store
import logging
import datetime
import os
import json
from streamlit.components.v1 import html

if "socrates_front" not in logging.root.manager.loggerDict.keys():
    logging.config.fileConfig(
        "../../config/logging_config_front.ini",
        defaults={"date": datetime.datetime.now().strftime("%m-%d-%Y")},
        disable_existing_loggers=True,
    )


logger = logging.getLogger("socrates_front")

st.set_page_config(
    page_title="Real-Time Data Science Dashboard",
    page_icon="📖",
    layout="wide",
)


data_store = Data_store()
# read csv from a github repo
if "log_files" not in st.session_state:
    logs = os.listdir("../../logs/")
    logs = [log for log in logs if log.endswith(".log")]
    st.session_state["log_files"] = logs

if "selected_log" not in st.session_state:
    st.session_state["selected_log"] = ""


if "data_file" not in st.session_state:
    st.session_state["data_file"] = None

selected_log = st.selectbox("Select the log file", st.session_state["log_files"])

if selected_log != st.session_state["selected_log"]:
    st.session_state["selected_log"] = selected_log
    with open(f"../../logs/{selected_log}", "r") as f:
        st.session_state["data_file"] = f.readlines()

if st.session_state["data_file"]:
    # x = st.slider("Select the number of lines to display", 1, len(st.session_state["data_file"])-30 if len(st.session_state["data_file"]) > 30 else 2, 1)
    # st.code('\n'.join(st.session_state["data_file"][x:x+30]))
    # html('<br>'.join(st.session_state["data_file"]), height=300, scrolling=True)
    with st.container(height=300, border=True):
        st.code("".join(st.session_state["data_file"]))


# read csv from a UR
def load_logs():
    data_store.read_data("data_store/input")
    # logger.info("Loading LLM CALLS")
    try:
        data_table, labels = data_store.load("llm_call")
        # logger.info(f"Data Table: {data_table}")
    except Exception as e:
        logger.info(f"Error: {e}")
        data_table = []
        labels = []
    return pd.DataFrame.from_dict(data_table)


df = load_logs()

# dashboard title
st.title("Real-Time / Live Data Science Dashboard")

# top-level filters
job_filter = st.selectbox("Select the run", pd.unique(df["id"]))

# creating a single-element container
placeholder = st.empty()


# near real-time / live feed simulation

while True:

    with placeholder.container():

        df = load_logs()
        st.dataframe(df)
        # st.dataframe(df)
        time.sleep(15)
