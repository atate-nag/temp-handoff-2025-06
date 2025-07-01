
The following files are hot files for the Socrates project, specifically for Sprint 7. These files are crucial for the functionality and integration of various agents within the Socrates framework:

* [socrates_main.py](/-/raw/responses/socrates_main.py)
* [schemas.py](/-/raw/responses/schemas.py)
* [agent_and_assessor.py](/-/raw/responses/agent_and_assessor.py)
* [pipeline/builders.py](/-/raw/responses/pipeline/builders.py)
* [local_agents/forces_agent.py](/-/raw/responses/local_agents/forces_agent.py)
* [local_agents/background_agent.py](/-/raw/responses/local_agents/background_agent.py)
* [local_agents/company_profile_agent.py](/-/raw/responses/local_agents/company_profile_agent.py)
* [local_agents/financial_screen_agent.py](/-/raw/responses/local_agents/financial_screen_agent.py)
* [local_agents/five_forces_assessor_agent.py](/-/raw/responses/local_agents/five_forces_assessor_agent.py)
* [local_agents/framework_selector_agent.py](/-/raw/responses/local_agents/framework_selector_agent.py)
* [local_agents/generic_assessor_agent.py](/-/raw/responses/local_agents/generic_assessor_agent.py)
* [local_agents/initial_crux_agent.py](/-/raw/responses/local_agents/initial_crux_agent.py)
* [local_agents/framework_selector_agent.py](/-/raw/responses/local_agents/framework_selector_agent.py)
* [local_agents/initial_crux_agent.py](/-/raw/responses/local_agents/initial_crux_agent.py)
* [local_agents/pest_agent.py](/-/raw/responses/local_agents/pest_agent.py)
* [local_agents/report_assessor_agent.py](/-/raw/responses/local_agents/report_assessor_agent.py)
* [local_agents/report_composer_agent.py](/-/raw/responses/local_agents/report_composer_agent.py)
* [local_agents/trend_radar_agent.py](/-/raw/responses/local_agents/trend_radar_agent.py)
* [local_agents/VRIO_agent.py](/-/raw/responses/local_agents/VRIO_agent.py)
* [local_agents/VRIO_agent.py](/-/raw/responses/local_agents/VRIO_agent.py)
* [tests/conftest.py](/-/raw/responses/tests/conftest.py)
* [tests/test_forces_schema.py](/-/raw/responses/tests/test_forces_schema.py)
* [tests/test_initial_crux.py](/-/raw/responses/tests/test_initial_crux.py)
* [tests/test_pest_schema.py](/-/raw/responses/tests/test_pest_schema.py)
* [tests/test_pipeline_integration.py](/-/raw/responses/tests/test_pipeline_integration.py)
* [tests/test_trend_radar_schema.py](/-/raw/responses/tests/test_trend_radar_schema.py)

You can mostly ignore the other files in this repo. 

Sprint 7 :
Of particular interest is making sure that the five forces data is successfully populated into the report.
Passing Dicts between agents is not useful and has resulted in way too many bandaid utilities and cleanups. The approach taken is to use Artifact and ArtifactCollection classes to  keep track of the agent outputs, and pass those natively into the report generation. Currently, only 5-forces, PEST and trend_radar builders generate artefacts, and hence the need for an interim solution in the main program, which will be removed when all agents support this approach. However, the driving deficiency at the moment is making sure that the 5-forces data is successfully propagated and handled through to the final report. 