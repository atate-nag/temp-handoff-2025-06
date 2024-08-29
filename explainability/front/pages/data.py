import streamlit as st
import requests
import json
import time
import logging
import datetime
from logging import config

if "socrates_front" not in logging.root.manager.loggerDict.keys():
    config.fileConfig(
        "../../config/logging_config_front.ini",
        defaults={"date": datetime.datetime.now().strftime("%m-%d-%Y")},
        disable_existing_loggers=True,
    )


logger = logging.getLogger("socrates_front")

st.set_page_config(
    page_title="Data",
    page_icon="🔥",
    layout="wide",
)

if "files" not in st.session_state:
    st.session_state["files"] = {
        "Intermediates": [],
        "Strategic Reports": [],
        "files": [],
    }

if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = []


def update_files():
    url = "http://127.0.0.1:8000/list_files"
    for folder, files in st.session_state["files"].items():
        if folder == "files":
            continue
        x = requests.get(url, params={"folder": folder})

        for file in json.loads(x.text):
            if file not in st.session_state["files"]["files"]:
                files.append(file)
                st.session_state["files"]["files"].append(file)
                get_file(folder + "/" + file)


def get_file(file_path):
    url = "http://127.0.0.1:8000/get_file"
    file = requests.get(url, params={"file_path": file_path})
    with open(f"Outputs/{file_path.split('/')[-1]}", "wb") as f:
        f.write(file.content)


import os


# def file_selector(folder_path="."):
#     companies = os.listdir(folder_path)
#     selected_company = st.selectbox("Select a Company", companies)
#     if selected_company:
#         sources = os.listdir(os.path.join(folder_path, selected_company))
#         selected_source = st.selectbox(
#             "Select a Source", sources
#         )
#         if selected_source:
#             st.write("Selected source:", selected_source)
#             uploaded_files = st.file_uploader("Select files to import", accept_multiple=True)
#             if uploaded_files:
#                 for uploaded_file in uploaded_files:
#                     pass
# return os.path.join(folder_path, selected_filename)


def get_companies():
    url = "http://127.0.0.1:8000/get_companies"
    r = requests.get(url)
    return json.loads(r.text)


def get_sources(company):
    url = "http://127.0.0.1:8000/get_sources"
    r = requests.get(url, params={"company": company})
    return json.loads(r.text)


def add_source(company, source):
    url = "http://127.0.0.1:8000/add_source"
    r = requests.post(url, params={"company": company, "source": source})
    logger.info(r.text)


def add_company(company):
    url = "http://127.0.0.1:8000/create_company"
    r = requests.post(url, params={"company": company})
    logger.info(r.text)


def get_source_files(company, source):
    url = "http://127.0.0.1:8000/get_source_files"
    r = requests.get(url, params={"company": company, "source": source})
    return json.loads(r.text)


def upload_company_file(company, source, file):
    url = "http://127.0.0.1:8000/upload_company_file"
    file = {"file": (file.name, file.read())}
    r = requests.post(url, params={"company": company, "source": source}, files=file)
    logger.info(r.text)


col1, col2 = st.columns([2.0, 4.0], gap="large")
with col1:
    with st.container(border=True):
        col_name, col_button = st.columns([1, 1], vertical_alignment="center")
        with col_name:
            new_company_name = st.text_input("New Company Name")
        with col_button:
            st.button("Add Company", on_click=add_company, args=[new_company_name])
    with st.container(border=True):
        folder_path = "."
        companies = get_companies()
        selected_company = st.selectbox("Select a Company", companies)
        if selected_company:
            # folder_path = folder_path + "/" + selected_company
            folder_path = os.path.join(folder_path, selected_company)
            sources = get_sources(selected_company)
            logger.info(f"Sources: {sources}")
            selected_source = st.selectbox("Select a Source", sources)
            if selected_source:
                st.write("Selected source:", selected_source)
                uploaded_files = st.file_uploader(
                    "Select files to import", accept_multiple_files=True
                )
                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        upload_company_file(
                            selected_company, selected_source, uploaded_file
                        )
                st.write("Available Files:")
                st.write(get_source_files(selected_company, selected_source))
            with st.container(border=True):
                col_value, col_button = st.columns([1, 1], vertical_alignment="center")
                with col_value:
                    new_source_name = st.text_input("New Source Name")
                with col_button:
                    st.button(
                        "Add Source",
                        on_click=add_source,
                        args=[selected_company, new_source_name],
                    )
    uploaded_file = st.file_uploader(
        "Select problem statement file to import", accept_multiple_files=False
    )
    if uploaded_file:
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
    # with open(uploaded_file.name, "wb") as f:
    #     f.write(bytes_data)

    # uploaded_files = st.file_uploader(
    #     "Select perigon files to import", accept_multiple_files=True
    # )
    # for uploaded_file in uploaded_files:
    #     bytes_data = uploaded_file.read()
    #     st.write("filename:", uploaded_file.name)
    #     st.write(bytes_data)
    #     with open(uploaded_file.name, "wb") as f:
    #         f.write(bytes_data)

    # uploaded_files = st.file_uploader(
    #     "Select reportLinker files to import", accept_multiple_files=True
    # )
    # for uploaded_file in uploaded_files:
    #     bytes_data = uploaded_file.read()
    #     st.write("filename:", uploaded_file.name)
    #     st.write(bytes_data)
    #     with open(uploaded_file.name, "wb") as f:
    #         f.write(bytes_data)

    # uploaded_files = st.file_uploader(
    #     "Select wikipedia files to import", accept_multiple_files=True
    # )
    # for uploaded_file in uploaded_files:
    #     bytes_data = uploaded_file.read()
    #     st.write("filename:", uploaded_file.name)
    #     st.write(bytes_data)
    #     with open(uploaded_file.name, "wb") as f:
    #         f.write(bytes_data)

    # uploaded_files = st.file_uploader(
    #     "Select data files to import", accept_multiple_files=True
    # )
    # for uploaded_file in uploaded_files:
    #     bytes_data = uploaded_file.read()
    #     st.write("filename:", uploaded_file.name)
    #     st.write(bytes_data)
    #     with open(uploaded_file.name, "wb") as f:
    #         f.write(bytes_data)


def delete_file(file_path):
    os.remove(file_path)
    url = "http://127.0.0.1:8000/delete_file"
    filename = file_path.split("/")[-1]
    for folder, files in st.session_state["files"].items():
        if folder != "files":
            if filename in files:
                x = requests.post(url, params={"file_path": folder + "/" + filename})
    logger.info(x.text)


with col2:
    buttons = {}

    while True:
        time.sleep(2)
        update_files()
        for file in os.listdir("Outputs"):
            if file != "__init__.py" and file != "__pycache__":
                if file not in buttons.copy():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="center")

                        with c1:
                            st.write(file)
                        with c2:
                            with open("Outputs/" + file) as f:
                                buttons[file] = {
                                    "download_button": st.download_button(
                                        f"Download", f, file_name=file
                                    )
                                }
                        with c3:
                            buttons[file]["delete_button"] = st.button(
                                f"Delete",
                                on_click=delete_file,
                                args=["Outputs/" + file],
                                key=file,
                            )

        for button in buttons.keys():
            if not os.path.exists("Outputs/" + button):
                logger.info("Removing button")
                buttons.pop(button)
            # with open("Outputs/"+file) as f:
            #     st.download_button(f"Download {file}", f, key=file)
