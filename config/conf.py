import json


def setup_config(**kwargs):
    with open("config/conf.json", "w") as configfile:
        json.dump(kwargs, configfile)


def read_config():
    with open("config/conf.json", "r") as configfile:
        conf = json.load(configfile)
    return conf
