from pydantic import ValidationError
from validations import WorkFlowContextModel, AgentConfigs, AgentContextModel
from import_files import InputFilesModel, AsstFilesModel
from data_validation import UnvalidatedData, ValidatedData
from debug import dprint
from collections import defaultdict
from openai_asst import (
    AgentThread,
    clone_assistant,
    delete_existing_assistant_files,
    delete_oldest_assistant_files,
)
from agent_state_machine_config import AgentStateMachineConfig
from jsonschema import validate
from jsonschema.exceptions import ValidationError


class Agent:
    states = [
        "Zero",
        "Waiting",
        "Initialised",
        "Loaded",
        "Running",
        "Retrieved",
        "Completed",
    ]

    def __init__(self, **kwargs):
        self.validated = ValidatedData(self)
        self.unvalidated_data = UnvalidatedData()
        # passed data is unvalidated so stored only as "user_data" until validation
        self.user_data = defaultdict(
            lambda: None, **kwargs
        )  # defaultdict will set optional arguments to None
        self.last_validated_output = None
        self.agent_type = None
        self.run_limit = 10  #  TODO should be a workflow parameter
        """
            Each state transition will follow this path:
            before_validation  ->   validation ->  after_validation - > transition 
            (set up                 (True or       ( cleanup           (Opt: trigger
            validation)             False   )      State Data)         next state)
        """
        self.state_machine = AgentStateMachineConfig().setup(self)
        dprint(f"State machine = {self.state_machine}")
        self.permissions = AgentStateMachineConfig().permissions
        self.agent_response = None
        self.connector = None

    def initialise(self, qm_id=None):
        self.user_data["qm_id"] = qm_id
        self.connector = self.user_data["connector"]
        self.initial_trigger(self.unvalidated_data)

    # def load(
    #     self,
    #     initial_run,
    #     agent_output=None,
    #     qm_instructions=None,
    #     agent_requirements=None,
    # ):
    #     self.user_data["initial_run"] = initial_run

    def load(
        self,
        initial_run,
        agent_output=None,
        qm_instructions=None,
        agent_requirements=None,
    ):
        self.user_data["initial_run"] = initial_run
        # TODO the following assignments may be outmoded due to receive_input
        if agent_output:
            self.user_data["agent_output"] = agent_output
        if qm_instructions:
            self.user_data["qm_instructions"] = qm_instructions
        if agent_requirements:
            self.user_data["agent_requirements"] = agent_requirements
        self.load_trigger(self.unvalidated_data)

    def clean_output_file(self):
        self.user_data["agent_output"] = None

    def receive_input(
        self, agent_output=None, qm_instructions=None, agent_requirements=None
    ):
        if agent_output:
            self.user_data["agent_output"] = agent_output
            self.user_data["agent_output"] = agent_output
            # print("receive input: set agent output to ",agent_output)
        if qm_instructions:
            self.user_data["qm_instructions"] = qm_instructions
            self.user_data["qm_instructions"] = qm_instructions
            print("receive input: set qm_instructions to ", qm_instructions)

        if agent_requirements:
            self.user_data["agent_requirements"] = agent_requirements

    def reissue(self):
        self.reissue_trigger(self.unvalidated_data)

    def run(self):
        self.run_trigger(self.unvalidated_data)
        return self.validated.retrieve_output

    def retrieve(self):
        self.retrieve_trigger(self.unvalidated_data)
        return self.validated.retrieve_output

    def requirements(self):
        return self.validated.agent_context.output_schema

    """ Class methods """

    def get_id(self):
        return self.validated.agent_context.agent_id

    def get_qm_id(self):
        return self.validated_workflow_context.qm_id

    """ State Transition and Validation Methods """

    """ Zero State to Initialised State Transition """

    def before_zero_to_initialised(self, unvalidated_data):
        """Prepare data specifically for the 'Zero2Initialised' state transition."""
        dprint(f"Generating state data for state {self.state}")
        self.unvalidated_data.set_data_for_state("Zero", **self.user_data)

    def zero_to_initialised_validation(self, unvalidated_data):
        """Validate data when transitioning from 'Zero' to 'Initialised'."""
        dprint("Running validations for state transition from Zero to Initialised")
        try:
            unvalidated_data = self.unvalidated_data.get_data_for_state("Zero")
            validated_workflow_context = WorkFlowContextModel(**unvalidated_data)
            agent_configs_valid = AgentConfigs.get_agent_details(
                validated_workflow_context.agent_type
            )
            # here if the agent is condigured to generate a new assistant instead of an existing, then it will
            # need to do so and genearate the agent_id

            qm_id = validated_workflow_context.qm_id

            agent_context_valid = AgentContextModel(**agent_configs_valid, qm_id=qm_id)
            self.validated.set_data("workflow_context", validated_workflow_context)
            self.validated.set_data("agent_config", agent_configs_valid)
            self.validated.set_data("agent_context", agent_context_valid)

            # TODO replace this with connector.clone.agent

            my_assistant = clone_assistant(
                self.validated.workflow_context.connector.client,
                self.validated.agent_context.agent_id,
            )

            if my_assistant:
                self.validated.agent_context.agent_id = my_assistant.id
            else:
                dprint("Agent clone was not created - Aborting")
                raise Exception("Agent clone was not created")
            self.validated.set_data("qm_id", qm_id)
            self.agent_type = validated_workflow_context.agent_type

            input_files_valid = None
            if self.user_data["input_files"] is not None:
                dprint(
                    f"Validating input files which are {self.user_data['input_files']}"
                )
                # TODO replace with connector or client from connector
                input_files_valid = InputFilesModel(
                    client=self.validated.workflow_context.connector.client,
                    agent_id=self.validated.agent_context.agent_id,
                    input_files=self.user_data["input_files"],
                )
            self.validated.set_data("input_files", input_files_valid)

            # TODO replace with connector or client from connector

            agent_thread = AgentThread(
                connector=self.validated.workflow_context.connector,
                agent_id=self.validated.agent_context.agent_id,
                initial_prompt=self.validated.agent_context.prompt,
                file_handler=self.validated.workflow_context.file_handler,
            )
            self.validated.set_data("agent_thread", agent_thread)
            return True
        except Exception as e:
            dprint(f"Validation error during Zero to Initialised transition: {e}")
            return False

    def after_validation_zero_to_initialised(self, unvalidated_data):
        """Execute AFTER validation of zero2initial state transition"""
        dprint(f"Running transition before state {self.state} to next state")
        # TODO replace with connector or client from connector
        client = self.validated.workflow_context.connector.client
        agent_id = self.validated.agent_context.agent_id
        # delete_existing_assistant_files(client, agent_id)

    """ Initialised State to Loaded State Transition """

    def before_initialised_to_loaded(self, unvalidated_data):
        """Prepare data specifically for the 'Initialised2Loaded' state transition."""
        dprint(f"Generating state data for state {self.state}")
        # TODO replace with connector or client from connector

        client = self.validated.workflow_context.connector.client
        agent_id = self.validated.agent_context.agent_id
        file_handler = self.validated.workflow_context.file_handler
        uploaded_assistant_files = []
        if self.user_data.get("input_files") and self.user_data["initial_run"]:
            file_list = self.user_data.get("input_files")
            uploaded_assistant_files = self.connector.upload_locals(agent_id, file_list)
            dprint(f"Uploaded from locals are {uploaded_assistant_files}")

        agent_response_file = agent_output_file = agent_inline_dict = None
        if self.user_data.get("agent_output"):
            output = self.user_data["agent_output"]
            agent_response_file = output["response_file"]
            agent_output_file = output["output_file"]
            agent_inline_dict = output["inline_dict"]
        print("doing the agent output stuff")
        if self.user_data.get("agent_output"):
            output = self.user_data["agent_output"]
            agent_response_file = output["response_file"]
            agent_output_file = output["output_file"]
            agent_inline_dict = output["inline_dict"]

        self.unvalidated_data.set_data_for_state(
            "Initialised",
            agent_output_file=agent_output_file,
            agent_response_file=agent_response_file,
            agent_inline_dict=agent_inline_dict,
            asst_input_files=uploaded_assistant_files,
            input_files=self.user_data.get("input_files"),
        )

    def initialised_to_loaded_validation(self, unvalidated_data):
        """Validate data when transitioning from 'Initialised' to 'Loaded'."""
        dprint("Running validations for state transition from Initialised to Loaded")
        try:
            unvalidated_data = self.unvalidated_data.get_data_for_state("Initialised")
            dprint("Retrieved unvalidated data for 'Initialised' state.")

            input_files_valid = None
            dprint("Initialized input_files_valid to None.")

            asst_input_files = None
            dprint("Initialized asst_input_files to None.")

            if unvalidated_data["asst_input_files"] and self.user_data["initial_run"]:
                asst_files_valid = AsstFilesModel(
                    # TODO replace with connector or client from connector
                    client=self.validated.workflow_context.connector.client,
                    agent_id=self.validated.agent_context.agent_id,
                    input_files=unvalidated_data["asst_input_files"],
                )
                dprint("Assistant files model created.")

                asst_input_files = unvalidated_data["asst_input_files"]
                dprint("Assigned assistant files to asst_input_files.")
            else:
                asst_input_files = None

            self.validated.set_data("asst_input_files", asst_input_files)
            dprint("Assistant input files data set in validated data store.")

            agent_thread = self.validated.agent_thread
            dprint("Retrieved agent thread from validated data.")

            agent_output_file = agent_response_file = agent_inline_dict = (
                agent_schema_errors
            ) = agent_requirements = None
            dprint("Initialized multiple variables to None for further validation.")

            if self.user_data["agent_requirements"]:
                agent_requirements = self.user_data["agent_requirements"]
                dprint("Agent requirements retrieved from user data.")

            self.validated.set_data("agent_requirements", agent_requirements)
            dprint("Agent requirements set in validated data.")

            if self.user_data["agent_output"]:
                agent_response_file = unvalidated_data["agent_response_file"]
                dprint("Agent response file retrieved from unvalidated data.")

                agent_output_file = unvalidated_data["agent_output_file"]
                dprint("Agent output file retrieved from unvalidated data.")

                agent_inline_dict = unvalidated_data["agent_inline_dict"]
                # dprint(f"Agent structured output retrieved from unvalidated data.{agent_inline_dict}")
                dprint(
                    f" Checking against schema"
                )
                # TODO schema not working for writer agents
                agent_schema_errors = self.validate_schema(
                    agent_inline_dict, self.validated.agent_requirements
                )
                dprint(f"agent_schema_errors are {agent_schema_errors}")

            self.validated.set_data("file_paths", unvalidated_data["input_files"])

            self.validated.set_data("agent_output_file", agent_output_file)
            dprint("Agent output file set in validated data.")

            self.validated.set_data("agent_response_file", agent_response_file)
            dprint("Agent response file set in validated data.")

            self.validated.set_data("agent_inline_dict", agent_inline_dict)
            dprint("Agent structured output set in validated data.")

            self.validated.set_data("agent_schema_errors", agent_schema_errors)
            dprint("Agent schema errors set in validated data.")

            return True
        except ValidationError as e:
            print(f"Validation failed: {e}")
            dprint(f"Validation exception caught: {e}")
            return False
        except Exception as e:
            dprint(f"Validation error during Initialised to Loaded transition: {e}")
            return False

    """ Loaded State to Running State Transition """

    def before_loaded_to_running(self, unvalidated_data):
        """Actions to prepare for the 'Loaded2Running' state transition."""
        dprint("Preparing for the Loaded state.")
        pass

    def loaded_to_running_validation(self, unvalidated_data):
        """Validate data when transitioning from 'Loaded' to 'Running'."""
        dprint("Running validations for state transition from Loaded to Running")
        try:
            # Insert specific validation logic for data pertinent to this transition
            # Validate and create a RunObjModel instance
            prompt = agent_requirements = None
            if (self.user_data):
                dprint("user data is provided")
            if (
                self.user_data
                and "qm_instructions" in self.user_data
                and self.user_data["qm_instructions"]
            ):
                # we need to give feedback to the agent from the QM
                prompt = self.user_data["qm_instructions"]
                dprint(f"Due to QM feedback, using the prompt {prompt}")
            dprint("Validating agent output")
            if (
                self.user_data
                and "agent_output" in self.user_data
                and self.user_data["agent_output"]
            ):
                # we need to tell the QM that the agent followed instructions
                # and that there is a new output file
                if "initial_run" in self.user_data and self.user_data["initial_run"]:
                    prompt = self.validated.agent_context.prompt
                else:
                    prompt = self.validated.agent_context.instructions

            # delete some old assistant files to make room

            # delete_oldest_assistant_files(
            #     self.validated.workflow_context.client,
            #     self.validated.agent_context.agent_id)

            # check if we have hit the limit of how many runs to make
            dprint("checking limit is not hit")

            if self.validated.agent_thread.runs_made() >= self.run_limit:
                dprint("Hit the limit, aborting")
                raise Exception
            # generate a new run object for this specific run
            dprint("generating run object")

            run_object = self.validated.agent_thread.new_runobj(
                parent=self.validated.agent_thread,
                retrieval_limit=20,
                input_files=self.validated.asst_input_files,
                agent_response=self.validated.agent_response_file,
                agent_output=self.validated.agent_output_file,
                agent_requirements=self.validated.agent_requirements,
                output_schema=self.validated.agent_context.output_schema,
                agent_schema_errors=self.validated.agent_schema_errors,
                prompt=prompt,
                # file_paths=self.validated.file_paths
            )
            # TODO temporary fix, please remove
            dprint("setting runobj")

            self.validated.set_data("run_object", run_object)
            return True
        except Exception as e:
            dprint(f"Validation error during Loaded to Running transition: {e}")
            return False

    """ Running State to Retrieved State Transitions """

    def before_running_to_retrieved(self, unvalidated_data):
        """Actions to prepare for the 'Running2Retreived' state transition."""
        dprint("Preparing for the Running state")
        self.validated.agent_thread.retrieve(qm_id=self.validated.qm_id)
        self.agent_response = self.validated.agent_thread.full_response

    def running_to_retrieved_validation(self, unvalidated_data):
        """Validate data when transitioning from 'Running' to 'Retrieved'."""
        dprint("Running validations for state transition from Running to Retrieved")
        try:
            unvalidated_data = self.unvalidated_data.get_data_for_state("Running")
            # Insert specific validation logic for data pertinent to this transition
            # did the run produce the right outputs and response?
            raw_output_dict = self.validated.agent_thread.get_output()

            # print(f"running_to_retrieved_validation: raw output from agent = {raw_output_dict}")

            # dprint(f"raw output from agent = {raw_output_dict}")
            # if not, it will get reissued
            # TODO validate output_dict
            # TODO Much of the following is not validation logic - move to after

            if raw_output_dict:
                output_dict = self.normalize_agent_output(raw_output_dict)
                self.validated.set_data("retrieve_output", output_dict)
                dprint("Good JSON output - validating state")
                print(
                    "running_to_retrieved_validation: Good JSON output - validating state"
                )

                return True
            else:
                instructions = (
                    "No valid structured JSON was detected in your response or "
                    "in an output file that you have indicated was present. Do not repeat the task, but please "
                    "print the output in JSON format and provide the file location"
                )
                # reissue logic will go here
                dprint(
                    f"Agent did not produce output and will be informed: {instructions}"
                )
                # TODO cannot act on agent_thread state
                # self.validated.agent_thread.add_message(instructions)
                self.validated.set_data("retrieve_output", None)
                # need to delete some files here in case we get into a long loop
                #  of uploading new files
                #  TODO reissue should not create new files?
                # delete_oldest_assistant_files(
                #     self.validated.workflow_context.client,
                #     self.validated.agent_context.agent_id)
                # need to remove the instructions so that they don't
                # just repeat
                self.user_data["qm_instructions"] = instructions
                self.reissue()
            return True
        except Exception as e:
            dprint(f"Validation error during Running to Retrieved transition: {e}")
            return False

    def before_reinitialise(self):
        # erase the old files that were used last time
        print("before reinitialise: resetting hte validated data")
        self.validated.set_data("asst_input_files", None)
        self.validated.set_data("file_paths", None)
        self.validated.set_data("agent_output_file", None)
        self.validated.set_data("agent_response_file", None)
        self.validated.set_data("agent_inline_dict", None)

    def after_validation_running_to_retrieved(self, unvalidated_data):
        """Execute AFTER validation but before state transition"""
        current_state = self.state
        # TODO replace with connector or client from connector

        client = self.validated.workflow_context.connector.client
        agent_id = self.validated.agent_context.agent_id
        # delete_oldest_assistant_files(client, agent_id)
        return

    def validate_schema(self, data, schema):
        issues = []
        if data is None or schema is None:
            return issues

        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            issues.append(f"Schema validation error: {e.message}")

        # TODO add some general code that prevents duplicates

        return issues

    def normalize_agent_output(self, output):
        # Check and convert 'completed' from string 'true'/'false' to Boolean True/False
        # TODO needs other normalisations - these are specific
        #  to QM issues
        if "completed" in output:
            completed_value = output["completed"]
            if isinstance(completed_value, str):
                completed_value = completed_value.lower()
                if completed_value == "true":
                    output["completed"] = True
                elif completed_value == "false":
                    output["completed"] = False
                else:
                    raise ValueError(
                        "Unexpected value for 'completed': must be 'true' or 'false'"
                    )
            elif not isinstance(completed_value, bool):
                raise ValueError(
                    "Unexpected type for 'completed': must be a boolean or string representing a boolean"
                )

        # Normalize other fields as needed
        return output

    def cleanup(self):
        # TODO remove from here, should not be cleanup in Agent?
        client = self.validated.workflow_context.connector.client
        agent_id = self.validated.agent_context.agent_id
        # # delete_oldest_assistant_files(client, agent_id)
        # dprint(f"Deleted old Assistant files on {agent_id}")
        # client.beta.assistants.delete(agent_id)
        # dprint(f"Deleted {agent_id}")
