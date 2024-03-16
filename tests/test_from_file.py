import os

import dotenv
import pytest

# from retrieval import retrieve_docs, find_and_download_files
# from dotenv import load_dotenv
# load_dotenv()
# from core_components.src.tests.test_retrieval import unit_test_retrieval
from core_components.src.tests.test_utils import (
    dict_eval,
    load_tests_from_file,
    precision,
    recall,
)

dotenv.load_dotenv()
# from core_components.src.agents.openAI import load_agents, query_assistant, client
# from deepeval import
# from run_assistant_thread import run_performance_retrieval_evaluation
# from retrieval import evaluate_query_retrieval


# @pytest.fixture
# def tests_dict_():
#     print(load_tests_from_file('tests.yml'))
#     return load_tests_from_file('tests.yml')


# @pytest.mark.parametrize("test_dict_", load_tests_from_file('tests.yml'))
def test_from_file():
    tests_dict_ = load_tests_from_file("tests.yml")
    print(tests_dict_)
    # print(tests_dict_)
    dict_eval(tests_dict_, expected_output="")


def test_from_file2():
    tests_dict_ = load_tests_from_file("tests2.yml")
    print(tests_dict_)
    # print(tests_dict_)
    dict_eval(tests_dict_, expected_output="")


def test_from_file3():
    tests_dict_ = load_tests_from_file("tests3.yml")
    print(tests_dict_)
    # print(tests_dict_)
    dict_eval(tests_dict_, expected_output="")
