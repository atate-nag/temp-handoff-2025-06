# tests/test_main.py

import pytest
from unittest.mock import mock_open, patch, MagicMock
from socrates_main import get_gics_code_and_name, create_json_filename, get_problem, get_trends
import json
def test_get_gics_code_and_name():
    company_name = "Tesla"
    gics_code, gics_name = get_gics_code_and_name(company_name)
    assert gics_code == [25]
    assert gics_name == ["Consumer Discretionary"]

def test_create_json_filename():
    company_name = "Tesla Inc."
    filename = create_json_filename(company_name)
    assert filename == "tesla_inc.json"

def test_get_problem(monkeypatch):
    # Mock the problem statements
    problem_statements = {
        "Tesla": "Scaling production efficiently amidst growing competition in the electric vehicle market is Tesla’s challenge. Optimizing production capacity, reducing costs, and maintaining innovation leadership are key. The company’s strategic focus centers on automation, battery technology, and global expansion. By fine-tuning its supply chain, investing in Gigafactories, and expanding charging infrastructure, Tesla can meet surging demand. The question: How can Tesla balance rapid growth with quality control and sustainable practices, ensuring its electric vehicles remain at the forefront of the automotive industry?",
    }
    # Mock the dprint function
    def mock_dprint(msg):
        pass

    # Apply the mock for dprint
    monkeypatch.setattr("socrates_main.dprint", mock_dprint)

    # Mock the open function to return the problem statements
    m = mock_open(read_data=json.dumps(problem_statements))

    with patch("builtins.open", m):
        # Test case: Company exists in the problem statements
        company_name = "Tesla"
        problemsFile = "problem_statements.json"
        statement = get_problem(company_name, problemsFile)
        assert statement == problem_statements[company_name]

        # Test case: Company does not exist in the problem statements
        company_name = "Unknown"
        with pytest.raises(Exception) as excinfo:
            get_problem(company_name, problemsFile)
        assert "Problem statement not found for the specified company" in str(excinfo.value)


def test_get_trends(monkeypatch):
    # Mock the GICS code and name
    def mock_get_gics_code_and_name(company_name):
        return [25], ["Consumer Discretionary"]

    # Mock the dprint function
    def mock_dprint(msg):
        pass

    # Mock the curated trend data
    def mock_get_curated_trend_data(company_name, gics_code, problem):
        if company_name == "Tesla" and not force_recreate:
            return {"trend": "archived trend data"}
        return None

    # Mock the trends from GICS code
    def mock_get_trends_from_gics_code(gics_code, problem):
        return {"trend": "new trend data"}

    # Mock the save curated trend data
    mock_save_curated_trend_data = MagicMock()

    # Apply the mocks
    monkeypatch.setattr("socrates_main.get_gics_code_and_name", mock_get_gics_code_and_name)
    monkeypatch.setattr("socrates_main.dprint", mock_dprint)
    monkeypatch.setattr("socrates_main.get_curated_trend_data", mock_get_curated_trend_data)
    monkeypatch.setattr("socrates_main.get_trends_from_gics_code", mock_get_trends_from_gics_code)
    monkeypatch.setattr("socrates_main.save_curated_trend_data", mock_save_curated_trend_data)

    # Test case: Load trends from archive
    company_name = "Tesla"
    problem = "sample problem"
    force_recreate = False
    trend_data = get_trends(company_name, problem, force_recreate)
    assert trend_data == {"trend": "archived trend data"}

    # Test case: Generate new trends and save to archive
    company_name = "Tesla"
    problem = "sample problem"
    force_recreate = True
    trend_data = get_trends(company_name, problem, force_recreate)
    assert trend_data == {"trend": "new trend data"}
    mock_save_curated_trend_data.assert_called_with(company_name, [25], "sample problem", {"trend": "new trend data"})

# def test_execute_workflow(monkeypatch):
#     def mock_dprint(msg):
#         pass
#
#     monkeypatch.setattr("main_program.dprint", mock_dprint)
#
#     # Assuming workflow_config has some steps enabled
#     for step in workflow_config:
#         workflow_config[step]["enabled"] = True
#
#     execute_workflow()
#
#     # Add appropriate assertions based on the expected outcome
#     assert True