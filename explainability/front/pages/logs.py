import time  # to simulate a real time data, time loop

import numpy as np  # np mean, np random
import pandas as pd  # read csv, df manipulation
import plotly.express as px  # interactive charts
import streamlit as st  # 🎈 data web app development
from data_store import Data_store

st.set_page_config(
    page_title="Real-Time Data Science Dashboard",
    page_icon="📖",
    layout="wide",
)

data_store = Data_store()
# read csv from a github repo


# read csv from a UR
def load_logs():
    data_store.read_data("data_store/input")
    # print("Loading LLM CALLS")
    try:
        data_table, labels = data_store.load("llm_call")
        # print(f"Data Table: {data_table}")
    except Exception as e:
        print(f"Error: {e}")
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
