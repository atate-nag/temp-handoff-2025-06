from pydantic import ValidationError
from validations import (WorkFlowContextModel, AgentConfigs, AgentContextModel,
                         AgentThreadModel)
from import_files import InputFilesModel, AsstFilesModel
from data_validation import UnvalidatedData, ValidatedData
from debug import dprint
from collections import defaultdict
from openai_asst import AgentThread
from agent_state_machine_config import AgentStateMachineConfig
from pubsub import pub
import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError

class Agent:
    states = ['Zero', 'Waiting', 'Initialised', 'Loaded', 'Running', 'Retrieved', 'Completed']

    def __init__(self, **kwargs):
        # set all class variables to None until validated
        # self.unvalidated_data = UnvalidatedData()
        self.validated = ValidatedData(self)
        self.unvalidated_data = UnvalidatedData()
        # passed data is unvalidated so stored only as "user_data" until validation
        # defaultdict will add optional arguments to None so they can still be queried without key error
        self.user_data = defaultdict(lambda: None, **kwargs)
        self.last_validated_output = None
        self.agent_type = None
        """
            Each state transition will follow this path:
            before_validation  ->   validation ->  after_validation - > transition 
            (set up                 (True or       ( cleanup          (Opt: trigger
            validation)             False   )      State Data)         next state)
        """
        self.state_machine = AgentStateMachineConfig().setup(self)
        dprint(f"State machine = {self.state_machine}")
        self.permissions = AgentStateMachineConfig().permissions

    def initialise(self, qm_id=None):
        self.user_data['qm_id'] = qm_id
        self.initial_trigger(self.unvalidated_data)

    def load(self, initial_run, agent_output=None, qm_instructions=None,agent_requirements=None):
        self.user_data['initial_run'] = initial_run
        if agent_output:
            self.user_data['agent_output'] = agent_output
        if qm_instructions:
            self.user_data['qm_instructions'] = qm_instructions
        if agent_requirements:
            self.user_data['agent_requirements'] = agent_requirements
        self.load_trigger(self.unvalidated_data)

    def receive_input(self, agent_output=None, qm_instructions=None, agent_requirements=None):
        # assumption is that this is a QM itself
        # so the inputs are
        if agent_output:
            self.user_data['agent_output'] = agent_output
        if qm_instructions:
            self.user_data['qm_instructions'] = qm_instructions
        if agent_requirements:
            self.user_data['agent_requirements'] = agent_requirements

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

    def before_zero_to_initialised(self,unvalidated_data):
        """ Prepare data specifically for the 'Zero2Initialised' state transition. """
        dprint(f"Generating state data for state {self.state}")
        self.unvalidated_data.set_data_for_state('Zero', **self.user_data)

    def zero_to_initialised_validation(self,unvalidated_data):
        """ Validate data when transitioning from 'Zero' to 'Initialised'. """
        dprint("Running validations for state transition from Zero to Initialised")
        try:
            unvalidated_data = self.unvalidated_data.get_data_for_state('Zero')
            validated_workflow_context = WorkFlowContextModel(**unvalidated_data)
            agent_configs_valid = AgentConfigs.get_agent_details(validated_workflow_context.agent_type)
            qm_id = validated_workflow_context.qm_id

            agent_context_valid = AgentContextModel(**agent_configs_valid, qm_id=qm_id)
            self.validated.set_data('workflow_context', validated_workflow_context)
            self.validated.set_data('agent_config', agent_configs_valid)
            self.validated.set_data('agent_context', agent_context_valid)
            self.validated.set_data('qm_id', qm_id)
            self.agent_type = validated_workflow_context.agent_type

            input_files_valid = None
            if self.user_data['input_files'] is not None:
                dprint(f"Validating input files which are {self.user_data['input_files']}")
                input_files_valid = InputFilesModel(
                    client=self.validated.workflow_context.client,
                    agent_id=self.validated.agent_context.agent_id,
                    input_files=self.user_data['input_files'])
            self.validated.set_data('input_files', input_files_valid)

            agent_thread = AgentThread(
                client=self.validated.workflow_context.client,
                agent_id=self.validated.agent_context.agent_id,
                initial_prompt=self.validated.agent_context.prompt,
                file_handler=self.validated.workflow_context.file_handler)
            self.validated.set_data('agent_thread', agent_thread)
            return True
        except Exception as e:
            dprint(f"Validation error during Zero to Initialised transition: {e}")
            return False

    def after_validation_zero_to_initialised(self,unvalidated_data):
        """ Execute AFTER validation of zero2initial state transition"""
        dprint(f"Running transition before state {self.state} to next state")
        client = self.validated.workflow_context.client
        agent_id = self.validated.agent_context.agent_id
        self.delete_existing_assistant_files(client, agent_id)

    """ Initialised State to Loaded State Transition """

    def before_initialised_to_loaded(self, unvalidated_data):
        """ Prepare data specifically for the 'Initialised2Loaded' state transition. """
        dprint(f"Generating state data for state {self.state}")
        client = self.validated.workflow_context.client
        agent_id = self.validated.agent_context.agent_id
        file_handler = self.validated.workflow_context.file_handler
        uploaded_assistant_files = []

        if self.user_data.get('input_files'):
            for file in self.user_data['input_files']:
                asst_file = file_handler.create_asst_file_from_local(client, agent_id, file)
                uploaded_assistant_files.append(asst_file)

        agent_response_file = agent_output_file = agent_structured_output = None
        if self.user_data.get('agent_output'):
            output = self.user_data['agent_output']
            agent_response_file = output['response_file']
            agent_output_file = output['output_file']
            agent_structured_output = output['structured_output']

        self.unvalidated_data.set_data_for_state(
            'Initialised',
            agent_output_file=agent_output_file,
            agent_response_file=agent_response_file,
            agent_structured_output=agent_structured_output,
            asst_input_files=uploaded_assistant_files,
        )

    def initialised_to_loaded_validation(self, unvalidated_data):
        """ Validate data when transitioning from 'Initialised' to 'Loaded'. """
        dprint("Running validations for state transition from Initialised to Loaded")
        try:
            unvalidated_data = self.unvalidated_data.get_data_for_state('Initialised')
            dprint("Retrieved unvalidated data for 'Initialised' state.")

            input_files_valid = None
            dprint("Initialized input_files_valid to None.")

            asst_input_files = None
            dprint("Initialized asst_input_files to None.")

            if unvalidated_data['asst_input_files']:
                asst_files_valid = AsstFilesModel(
                    client=self.validated.workflow_context.client,
                    agent_id=self.validated.agent_context.agent_id,
                    input_files=unvalidated_data['asst_input_files'])
                dprint("Assistant files model created.")

                asst_input_files = unvalidated_data['asst_input_files']
                dprint("Assigned assistant files to asst_input_files.")

            self.validated.set_data('asst_input_files', asst_input_files)
            dprint("Assistant input files data set in validated data store.")

            agent_thread = self.validated.agent_thread
            dprint("Retrieved agent thread from validated data.")

            agent_output_file = agent_response_file = agent_structured_output = agent_schema_errors = agent_requirements = None
            dprint("Initialized multiple variables to None for further validation.")

            if self.user_data['agent_requirements']:
                agent_requirements = self.user_data['agent_requirements']
                dprint("Agent requirements retrieved from user data.")

            self.validated.set_data('agent_requirements', agent_requirements)
            dprint("Agent requirements set in validated data.")

            if self.user_data['agent_output']:
                agent_response_file = unvalidated_data['agent_response_file']
                dprint("Agent response file retrieved from unvalidated data.")

                agent_output_file = unvalidated_data['agent_output_file']
                dprint("Agent output file retrieved from unvalidated data.")

                agent_structured_output = unvalidated_data['agent_structured_output']
                dprint(f"Agent structured output retrieved from unvalidated data.{agent_structured_output}")
                dprint(f"schema to check against is {self.validated.agent_requirements}")
                # TODO schema not working for writer agents
                # if self.agent_type is not "competitive_analysis_report_agent":
                #     agent_schema_errors = self.validate_schema(agent_structured_output, self.validated.agent_requirements)
                #     dprint(f"agent_schema_errors are {agent_schema_errors}")

            self.validated.set_data('agent_output_file', agent_output_file)
            dprint("Agent output file set in validated data.")

            self.validated.set_data('agent_response_file', agent_response_file)
            dprint("Agent response file set in validated data.")

            self.validated.set_data('agent_structured_output', agent_structured_output)
            dprint("Agent structured output set in validated data.")

            self.validated.set_data('agent_schema_errors', agent_schema_errors)
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

    def before_loaded_to_running(self,unvalidated_data):
        """ Actions to prepare for the 'Loaded2Running' state transition. """
        dprint("Preparing for the Loaded state.")
        pass

    def loaded_to_running_validation(self, unvalidated_data):
        """ Validate data when transitioning from 'Loaded' to 'Running'. """
        dprint("Running validations for state transition from Loaded to Running")
        try:
            # Insert specific validation logic for data pertinent to this transition
            # Validate and create a RunObjModel instance
            prompt = agent_requirements = None
            # TODO - should qm_instructions and agent_output be
            #  validated in Initialised state since part of load()?
            if self.user_data['qm_instructions']:
                # we need to give feedback to the agent from the QM
                prompt = self.user_data['qm_instructions']
                dprint(f"Due to QM feedback, using the prompt {prompt}")
            if self.user_data['agent_output']:
                # we need to tell the QM that the agent followed instructions
                # and that there is a new output file
                if self.user_data['initial_run']:
                    prompt = self.validated.agent_context.prompt
                else:
                    prompt = self.validated.agent_context.instructions

            run_object = self.validated.agent_thread.new_runobj(
                parent=self.validated.agent_thread,
                retrieval_limit=20,
                input_files=self.validated.asst_input_files,
                agent_response=self.validated.agent_response_file,
                agent_output=self.validated.agent_output_file,
                agent_requirements=self.validated.agent_requirements,
                output_schema=self.validated.agent_context.output_schema,
                agent_schema_errors=self.validated.agent_schema_errors,
                prompt=prompt
            )

            self.validated.set_data('run_object', run_object)
            return True
        except Exception as e:
            dprint(f"Validation error during Loaded to Running transition: {e}")
            return False

    """ Running State to Retrieved State Transitions """

    def before_running_to_retrieved(self,unvalidated_data):
        """ Actions to prepare for the 'Running2Retreived' state transition. """
        dprint("Preparing for the Running state")
        self.validated.agent_thread.retrieve(qm_id=self.validated.qm_id)

    def running_to_retrieved_validation(self, unvalidated_data):
        """ Validate data when transitioning from 'Running' to 'Retrieved'. """
        dprint("Running validations for state transition from Running to Retrieved")
        try:
            unvalidated_data = self.unvalidated_data.get_data_for_state('Running')
            # Insert specific validation logic for data pertinent to this transition
            # did the run produce the right outputs and response?
            raw_output_dict = self.validated.agent_thread.get_output()
            dprint(f"raw output from agent = {raw_output_dict}")
            # if not, it will get reissued
            # TODO validate output_dict
            # TODO Much of the following is not validation logic - move to after

            if raw_output_dict:
                output_dict = self.normalize_agent_output(raw_output_dict)
                self.validated.set_data('retrieve_output', output_dict)
                dprint("Good JSON output - validating state")
                return True
            else:
                instructions = ("No valid structured JSON was detected in your response or "
                                "in an output file that you have indicated was present. Please "
                                "regenerate your response and try again.")
                # reissue logic will go here
                dprint(f"Agent did not produce output and will be informed: {instructions}")
                # TODO cannot act on agent_thread state
                self.validated.agent_thread.add_message(instructions)
                self.validated.set_data('retrieve_output', None)
                # need to delete some files here in case we get into a long loop
                #  of uploading new files
                #  TODO reissue should not create new files?
                self.delete_oldest_assistant_files(
                    self.validated.workflow_context.client,
                    self.validated.agent_context.agent_id)
                # need to remove the instructions so that they don't
                # just repeat
                self.user_data['qm_instructions'] = None
                self.reissue()
            return True
        except Exception as e:
            dprint(f"Validation error during Running to Retrieved transition: {e}")
            return False

    def after_validation_running_to_retrieved(self, unvalidated_data):
        """ Execute AFTER validation but before state transition"""
        current_state = self.state
        client = self.validated.workflow_context.client
        agent_id = self.validated.agent_context.agent_id
        self.delete_oldest_assistant_files(client, agent_id)
        return

    # def before_validation(self, unvalidated_data):
    #     """ Execute Before validation and transition """
    #     dprint(f"Generating state data for state {self.state}")
    #     current_state = self.state
    #     if current_state == 'Zero':
    #         self.unvalidated_data.set_data_for_state(current_state, **self.user_data)
    #     elif current_state == 'Initialised':
    #         # TODO must not reload data when reinitialising
    #         # possibly needs to be split into two states, input files are
    #         #  a one-time upload wheras the others are not
    #         client = self.validated.workflow_context.client
    #         agent_id = self.validated.agent_context.agent_id
    #         file_handler = self.validated.workflow_context.file_handler
    #         uploaded_assistant_files = []
    #         if self.user_data['input_files']:
    #             for file in self.user_data['input_files']:
    #                 asst_file = file_handler.create_asst_file_from_local(
    #                     client,
    #                     agent_id,
    #                     file)
    #                 uploaded_assistant_files.append(asst_file)
    #         agent_response_file = agent_output_file = agent_structured_output = agent_schema_error = None
    #         if self.user_data['agent_output']:
    #             output = self.user_data['agent_output']
    #             agent_response_file = output['response_file']
    #             agent_output_file = output['output_file']
    #             agent_structured_output = output['structured_output']
    #         self.unvalidated_data.set_data_for_state(
    #             'Initialised',
    #             agent_output_file=agent_output_file,
    #             agent_response_file=agent_response_file,
    #             agent_structured_output=agent_structured_output,
    #             asst_input_files=uploaded_assistant_files,
    #         )
    #     elif current_state == 'Loaded':
    #         dprint("Loaded state")
    #     elif current_state == 'Running':
    #         dprint("In Running state, waiting for thread")

    #     return

        # Validation functions specific to state transitions

    # def validation(self, unvalidated_data):
    #     """ the validation phase of the transition. The state transition will
    #     only happen if the validation returns True"""
    #     dprint(f"Running validations for state {self.state}")
    #     current_state = self.state
    #     unvalidated_data = self.unvalidated_data.get_data_for_state(current_state)
    #     dprint(f"validation data for {self.state} = {unvalidated_data}")
    #     if current_state == 'Zero':
    #         try:
    #             # Validate initial data
    #             validated_workflow_context = WorkFlowContextModel(**unvalidated_data)
    #             agent_configs_valid = AgentConfigs.get_agent_details(validated_workflow_context.agent_type)
    #             qm_id = validated_workflow_context.qm_id
    #
    #             agent_context_valid = AgentContextModel(**agent_configs_valid, qm_id=qm_id)
    #             self.validated.set_data('workflow_context', validated_workflow_context)
    #             self.validated.set_data('agent_config', agent_configs_valid)
    #             self.agent_type = validated_workflow_context.agent_type
    #             self.validated.set_data('agent_context', agent_context_valid)
    #             # TODO add model for qm_id
    #             self.validated.set_data('qm_id', qm_id)
    #             input_files_valid = None
    #             self.validated.set_data('agent_id', self.validated.agent_context.agent_id)
    #             if self.user_data['input_files']:
    #                 input_files_valid = InputFilesModel(
    #                     client=self.validated.workflow_context.client,
    #                     agent_id=self.validated.agent_context.agent_id,
    #                     input_files=self.user_data['input_files'])
    #             self.validated.set_data('input_files', input_files_valid)
    #             agent_thread = AgentThread(
    #                 client=self.validated.workflow_context.client,
    #                 agent_id=self.validated.agent_context.agent_id,
    #                 initial_prompt=self.validated.agent_context.prompt,
    #                 file_handler=self.validated.workflow_context.file_handler)
    #             agent_thread_valid = AgentThreadModel(agent_thread=agent_thread)
    #             self.validated.set_data('agent_thread', agent_thread)
    #             return True
    #         except ValidationError as e:
    #             dprint("Validation error:", e.json())
    #         except ValueError as e:
    #             dprint(f"Value error: {e}")
    #         except Exception as e:
    #             dprint(f"Unexpected error while validating ZeroState data: {e}")
    #     elif current_state == "Initialised":
    #         input_files_valid = None
    #         try:
    #             print("Transition successful, context and files validated")
    #             asst_input_files = None
    #             if unvalidated_data['asst_input_files']:
    #                 asst_files_valid = AsstFilesModel(
    #                     client=self.validated.workflow_context.client,
    #                     agent_id=self.validated.agent_context.agent_id,
    #                     input_files=unvalidated_data['asst_input_files'])
    #                 asst_input_files = unvalidated_data['asst_input_files']
    #             self.validated.set_data('asst_input_files', asst_input_files)
    #             agent_thread = self.validated.agent_thread
    #             agent_output_file = agent_response_file = agent_structured_output = agent_schema_errors = agent_requirements = None
    #             if self.user_data['agent_requirements']:
    #                 # TODO need to validate agent_requirements
    #                 agent_requirements = self.user_data['agent_requirements']
    #             self.validated.set_data('agent_requirements', agent_requirements)
    #
    #             if self.user_data['agent_output']:
    #                 agent_response_file = unvalidated_data['agent_response_file']
    #                 # TODO validate output, response, schema
    #                 agent_output_file = unvalidated_data['agent_output_file']
    #                 agent_structured_output = unvalidated_data['agent_structured_output']
    #                 agent_schema_errors = self.validate_schema(agent_structured_output, self.validated.agent_requirements)
    #                 dprint(f"agent_schema_errors are {agent_schema_errors}")
    #             self.validated.set_data('agent_output_file', agent_output_file)
    #             self.validated.set_data('agent_response_file', agent_response_file)
    #             self.validated.set_data('agent_structured_output', agent_structured_output)
    #             self.validated.set_data('agent_schema_errors', agent_schema_errors)
    #             return True
    #         except ValidationError as e:
    #             print(f"Validation failed: {e}")
    #             return False
    #     elif current_state == 'Loaded':
    #         # Validate and create a RunObjModel instance
    #         prompt = agent_requirements = None
    #         # TODO - should qm_instructions and agent_output be
    #         #  validated in Initialised state since part of load()?
    #         if self.user_data['qm_instructions']:
    #             # we need to give feedback to the agent from the QM
    #             prompt = self.user_data['qm_instructions']
    #             dprint(f"Due to QM feedback, using the prompt {prompt}")
    #         if self.user_data['agent_output']:
    #             # we need to tell the QM that the agent followed instructions
    #             # and that there is a new output file
    #             if self.user_data['initial_run']:
    #                 prompt = self.validated.agent_context.prompt
    #             else:
    #                 prompt = self.validated.agent_context.instructions
    #         run_object = self.validated.agent_thread.new_runobj(
    #             parent=self.validated.agent_thread,
    #             retrieval_limit=20,
    #             input_files=self.validated.asst_input_files,
    #             agent_response=self.validated.agent_response_file,
    #             agent_output=self.validated.agent_output_file,
    #             agent_requirements=self.validated.agent_requirements,
    #             output_schema=self.validated.agent_context.output_schema,
    #             agent_schema_errors=self.validated.agent_schema_errors,
    #             prompt=prompt
    #         )
    #         self.validated.set_data('run_object', run_object)
    #         return True
    #     elif current_state == 'Running':
    #         # did the run produce the right outputs and response?
    #         dprint(f"Validating the run in state {current_state}")
    #         # checks 1) is there a valid response and output file?
    #         raw_output_dict = self.validated.agent_thread.get_output()
    #
    #         dprint(f"raw output from agent = {raw_output_dict}")
    #         # if not, it will get reissued
    #         # TODO validate output_dict
    #         # Much of the following is not validation logic - move to after
    #         if raw_output_dict:
    #             output_dict = self.normalize_agent_output(raw_output_dict)
    #             self.validated.set_data('retrieve_output', output_dict)
    #             dprint("Good JSON output - validating state")
    #             return True
    #         else:
    #             instructions = ("No valid structured JSON was detected in your response or "
    #                             "in an output file that you have indicated was present. Please "
    #                             "regenerate your response and try again.")
    #             # reissue logic will go here
    #             dprint(f"Agent did not produce output and will be informed: {instructions}")
    #             # TODO cannot act on agent_thread state
    #             self.validated.agent_thread.add_message(instructions)
    #             self.validated.set_data('retrieve_output', None)
    #             # need to delete some files here in case we get into a long loop
    #             #  of uploading new files
    #             #  TODO reissue should not create new files?
    #             self.delete_oldest_assistant_files(
    #                 self.validated.workflow_context.client,
    #                 self.validated.agent_context.agent_id)
    #             self.reissue()

    def validate_schema(self, data, schema):
        # Store validation issues
        issues = []
        if data is None or schema is None:
            return issues
        # Validate schema
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            issues.append(f"Schema validation error: {e.message}")

        # Check for duplicate names
        seen_names = {}
        for index, item in enumerate(data):
            competitor_name = item['competitor']['name']
            if competitor_name in seen_names:
                issues.append(
                    f"Duplicate competitor name found at index {index} and {seen_names[competitor_name]}: '{competitor_name}'")
            else:
                seen_names[competitor_name] = index

        return issues

    def delete_existing_assistant_files(self, client, agent_id):
        """ Manage existing assistant files in OpenAI """
        asst_files = client.beta.assistants.files.list(
            assistant_id=agent_id,
        )
        dprint(f"Assistant files: {asst_files}")
        for asst_file in asst_files.data:
            try:
                client.beta.assistants.files.delete(
                    assistant_id=agent_id,
                    file_id=asst_file.id
                )
                dprint(f"Deleted Assistant file")
            except Exception as e:
                dprint(f"Error deleting Assistant file {e}")

    def delete_oldest_assistant_files(self, client, agent_id, max_files=6):
        """Manage existing assistant files by keeping only the latest 'max_files'."""
        dprint("delete_oldest_assistant_files")
        try:
            # Retrieve list of assistant files
            asst_files = client.beta.assistants.files.list(
                assistant_id=agent_id,
            )
            dprint(f"Total assistant files: {len(asst_files.data)} on {agent_id}")
            # Check if the number of files exceeds the maximum allowed
            if len(asst_files.data) > max_files:
                sorted_files = sorted(asst_files.data, key=lambda x: x.created_at)
                files_to_delete = sorted_files[:len(asst_files.data) - max_files]

                # Delete the oldest files
                for asst_file in files_to_delete:
                    client.beta.assistants.files.delete(
                        assistant_id=agent_id,
                        file_id=asst_file.id
                    )
                    dprint(f"Deleted Assistant file-id: {asst_file.id}")
        except Exception as e:
            dprint(f"Error managing Assistant files: {e}")

    def normalize_agent_output(self, output):
        # Check and convert 'completed' from string 'true'/'false' to Boolean True/False
        # TODO needs other normalisations - these are specific
        #  to QM issues
        if 'completed' in output:
            completed_value = output['completed']
            if isinstance(completed_value, str):
                completed_value = completed_value.lower()
                if completed_value == 'true':
                    output['completed'] = True
                elif completed_value == 'false':
                    output['completed'] = False
                else:
                    raise ValueError("Unexpected value for 'completed': must be 'true' or 'false'")
            elif not isinstance(completed_value, bool):
                raise ValueError("Unexpected type for 'completed': must be a boolean or string representing a boolean")

        # Normalize other fields as needed
        return output
