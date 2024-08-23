import json
import datetime
import datetime
import shutil

import os


def list_files_in_folder(folder_path):
    try:
        files = os.listdir(folder_path)
    except FileNotFoundError:
        print(f"The folder {folder_path} does not exist.")
    except PermissionError:
        print(f"Permission denied to access the folder {folder_path}.")
    return files


def update_mdata(data, metadata):
    keys = data.keys()

    for key, value in metadata.items():

        # print(f'\n\data keys: {data.keys()}\n\n')
        if key.endswith("used"):

            if value in data:

                data[value] += 1
            else:

                data[value] = 1
        elif key not in keys:
            data[key] = value
        elif key.endswith("count"):
            data[key] += value
        elif key.endswith("detail"):
            detail_data = eval(value)
            data[key] = str(update_mdata(eval(data[key]).copy(), detail_data))
    return data


def delete_folder(folder_path):
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
            print(f"Folder {folder_path} has been deleted.")
        else:
            print(f"The folder {folder_path} does not exist.")
    except PermissionError:
        print(f"Permission denied to delete the folder {folder_path}.")
    except Exception as e:
        print(f"An error occurred: {e}")


def delete_file(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File {file_path} has been deleted.")
        else:
            print(f"The file {file_path} does not exist.")
    except PermissionError:
        print(f"Permission denied to delete the file {file_path}.")
    except Exception as e:
        print(f"An error occurred: {e}")


def create_tree_structure(base_path, tree_structure):
    for key, value in tree_structure.items():
        current_path = os.path.join(base_path, key)
        os.makedirs(current_path, exist_ok=True)
        if isinstance(value, dict):
            create_tree_structure(current_path, value)


class Data_store:
    def __init__(self):
        self.datasets = {}
        if not os.path.exists("data_store"):
            self.init("data_store")

    def read_data(self, path):

        files = list_files_in_folder(path)
        print("files: ")
        print(files)
        print("reading data")
        data_list = []
        for file in files:
            filepath = path + "/" + file
            print(f"Reading data from {filepath}")
            with open(filepath) as f:
                dict_data = json.load(f)

            print(f"dict_data: {dict_data}")
            if "id" in dict_data:
                if dict_data["id"] not in self.datasets:
                    data = dict_data["data"]
                    data_list.append(data)
                    data["timestamp"] = str(datetime.datetime.now())
                    self.datasets[dict_data["id"]] = [data]
                else:
                    data = dict_data["data"]
                    data_list.append(data)
                    data["timestamp"] = str(datetime.datetime.now())
                    self.datasets[dict_data["id"]].append(data)
            if "type" in dict_data:
                print(f"updating metadata: {dict_data['type']}")
                self.update_metadata(dict_data["type"], dict_data.copy())
            delete_file(filepath)
        return data_list

    def update_metadata(self, data_type, data):
        print(f"updating metadata: {data_type} with data: {data}")
        if not os.path.exists("data_store/metadata/" + data_type + ".json"):
            with open("data_store/metadata/" + data_type + ".json", "w") as f:
                print(f"writing metadata: {data}")
                metadata = [update_mdata({}, data.copy())]
                json.dump(metadata, f)
                # metadata = data
        else:
            with open("data_store/metadata/" + data_type + ".json", "r") as f:
                try:
                    metadata = json.load(f)
                except json.JSONDecodeError:
                    metadata = []
                    raise Exception("Cannot load metadata")
            print(f"loaded metadata: {metadata}")
            print(f"data: {data}")

            if len([mdata for mdata in metadata if mdata["id"] == data["id"]]) > 0:
                metadata = [
                    (
                        update_mdata(mdata.copy(), data.copy())
                        if mdata["id"] == data["id"]
                        else mdata
                    )
                    for mdata in metadata
                ]
            else:
                metadata.append(update_mdata({}, data.copy()))

                # else:
                #     self.datasets[key].append(value)

            print(f"\n\nWRITING metadata: {metadata}\n\n")
            with open("data_store/metadata/" + data_type + ".json", "w") as f:
                json.dump(metadata, f)

        data = []
        labels = [key for key in metadata[0].keys()]
        # for key, value in metadata.items():
        #     labels.append(key)
        #     data.append(value)
        return metadata, labels

    def load_index(self):
        return list(self.datasets.keys())

    def clear_data(self, folder):
        delete_folder(folder)

    def init(self, folder):
        create_tree_structure(
            "./", {folder: {"data": {}, "metadata": {}, "input": {}, "tmp": {}}}
        )

    def write_index(self, path):
        with open(path, "w") as f:
            json.dump(self.datasets, f)

    def load(self, data_type):
        with open("data_store/metadata/" + data_type + ".json", "r") as f:
            metadata = json.load(f)
        print(f"loading metadata: {metadata}")
        # data = [{key: str(value) for key, value in metadata.items()}]

        # labels = [{"name": i, "id": i} for i in metadata.keys()]
        print(f"metadata: {metadata}")
        metadata = [
            {key: str(value) for key, value in mdata.items()} for mdata in metadata
        ]
        labels = [{"name": i, "id": i} for i in metadata[0].keys()]
        print(f"\nLABELS: {labels}")
        return metadata, labels

    # def get_lonlatalt(self, time):

    #     data = self.read_data("data_store/input")
    #     output = {"Longitude": [], "Latitude": [], "Altitude": []}
    #     for point in data:
    #         output["Longitude"].append(point["longitude"])
    #         output["Latitude"].append(point["latitude"])
    #         output["Altitude"].append(point["altitude"])
    #     return output["Longitude"], output["Latitude"], output["Altitude"]
