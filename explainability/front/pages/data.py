import streamlit as st
import requests
import json
import time

st.set_page_config(
    page_title="Data",
    page_icon="👋",
)

if "files" not in st.session_state:
    st.session_state["files"] = {"Intermediates": [], "Strategic Reports": []}


def update_files():
    print("Updating files")
    url = "http://127.0.0.1:8000/list_files"
    for folder, files in st.session_state["files"].items():
        x = requests.get(url, params={"folder": folder})
        print(x.text)
        for file in json.loads(x.text):
            if file not in files:
                files.append(file)
                get_file(file)
        print(files)


def get_file(file_path):
    print("Getting file")
    url = "http://127.0.0.1:8000/get_file"
    file = requests.get(url, params={"file_path": file_path})
    with open(f"Outputs/{file_path.split('/')[-1]}", "wb") as f:
        f.write(file.content)


import os

col1, col2 = st.columns(2, gap="large")
with col1:

    def file_selector(folder_path="."):
        filenames = os.listdir(folder_path)
        selected_filename = st.selectbox("Select a file", filenames)
        return os.path.join(folder_path, selected_filename)

    filename = file_selector()
    st.write("You selected `%s`" % filename)

    uploaded_files = st.file_uploader(
        "Select trend files to import", accept_multiple_files=True
    )
    for uploaded_file in uploaded_files:
        bytes_data = uploaded_file.read()
        st.write("filename:", uploaded_file.name)
        st.write(bytes_data)
        with open(uploaded_file.name, "wb") as f:
            f.write(bytes_data)

    uploaded_files = st.file_uploader(
        "Select perigon files to import", accept_multiple_files=True
    )
    for uploaded_file in uploaded_files:
        bytes_data = uploaded_file.read()
        st.write("filename:", uploaded_file.name)
        st.write(bytes_data)
        with open(uploaded_file.name, "wb") as f:
            f.write(bytes_data)

    uploaded_files = st.file_uploader(
        "Select reportLinker files to import", accept_multiple_files=True
    )
    for uploaded_file in uploaded_files:
        bytes_data = uploaded_file.read()
        st.write("filename:", uploaded_file.name)
        st.write(bytes_data)
        with open(uploaded_file.name, "wb") as f:
            f.write(bytes_data)

    uploaded_files = st.file_uploader(
        "Select wikipedia files to import", accept_multiple_files=True
    )
    for uploaded_file in uploaded_files:
        bytes_data = uploaded_file.read()
        st.write("filename:", uploaded_file.name)
        st.write(bytes_data)
        with open(uploaded_file.name, "wb") as f:
            f.write(bytes_data)

    uploaded_files = st.file_uploader(
        "Select data files to import", accept_multiple_files=True
    )
    for uploaded_file in uploaded_files:
        bytes_data = uploaded_file.read()
        st.write("filename:", uploaded_file.name)
        st.write(bytes_data)
        with open(uploaded_file.name, "wb") as f:
            f.write(bytes_data)


with col2:
    buttons = {}

    while True:
        time.sleep(5)
        update_files()
        for file in os.listdir("Outputs"):
            if file != "__init__.py" and file != "__pycache__":
                if file not in buttons.copy():
                    c1, c2, c3 = st.columns(3, vertical_alignment="center")
                    print("Adding button")
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
                            on_click=os.remove,
                            args=["Outputs/" + file],
                            key=file,
                        )

        for button in buttons.copy():
            if not os.path.exists("Outputs/" + button):
                print("Removing button")
                buttons.pop(button)
            # with open("Outputs/"+file) as f:
            #     st.download_button(f"Download {file}", f, key=file)
