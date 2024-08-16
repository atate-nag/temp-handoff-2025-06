import streamlit as st

st.set_page_config(
    page_title="Data",
    page_icon="👋",
)

import os


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
