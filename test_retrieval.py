import os
import pytest
from retrieval import retrieve_docs
from dotenv import load_dotenv
load_dotenv()
from core_components.src.tests.test_retrieval import unit_test_retrieval
from core_components.src.tests.test_utils import precision, recall



@pytest.fixture
def files(tmpdir):
    # Create a temporary input folder for testing
    folder = tmpdir.mkdir("input")
    # Create some test files in the input folder
    file1 = folder.join("file1.txt")
    file1.write("Test file 1")
    file2 = folder.join("file2.txt")
    file2.write("Test file 2")
    return [str(file1), str(file2)]


@pytest.fixture
def queries():
    # Create a temporary output folder for testing
    return ["query1", "query2"]

@pytest.fixture
def expected_output():
    # Create a temporary output folder for testing
    output = []
    return output


def test_retrieve_docs(files, queries, expected_output):
    # Call the retrieve_docs function with the test input and output folders
    retrieved_output = retrieve_docs(files, queries)

    unit_test_retrieval(
        retrieved_output,
        expected_output,
        metrics_and_thresholds=[(precision, 0.7), (recall, 0.7)],
    )
