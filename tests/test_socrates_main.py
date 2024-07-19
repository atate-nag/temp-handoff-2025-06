# tests/test_main.py

import pytest
from socrates_main import get_gics_code_and_name, create_json_filename


def test_get_gics_code_and_name():
    company_name = "Tesla"
    gics_code, gics_name = get_gics_code_and_name(company_name)
    assert gics_code == [25]
    assert gics_name == ["Consumer Discretionary"]


def test_create_json_filename():
    company_name = "Tesla Inc."
    filename = create_json_filename(company_name)
    assert filename == "tesla_inc.json"


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
