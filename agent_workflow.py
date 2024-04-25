from transitions import Machine
import logging
from pydantic import ValidationError
from state_transitions import (ZerotoInitialTransition, InitialtoLoadedTransition,
                               LoadedtoRunningTransition, RunningtoReturnedTransition, ReturnedtoCompleteTransition)
from validations import (WorkFlowContextModel, AgentConfigs, AgentContextModel, InputFilesModel,
                         AsstFilesModel, AgentThreadModel,
                         InitialtoLoadedValidation, LoadedtoRunningValidation, RunningtoReturnedValidation,
                         ReturnedtoCompleteValidation)
from import_files import InputFilesModel, AsstFilesModel

from data_validation import UnvalidatedData, ValidatedData
from debug import dprint
from collections import defaultdict
from openai_asst import AgentThread
from agent_state_machine_config import AgentStateMachineConfig
import time
from pubsub import pub

class Agent:
    states = ['Zero', 'Waiting', 'Initialised', 'Loaded', 'Running', 'Retrieved', 'Completed']

    def __init__(self, **kwargs):
        # set all class variables to None until validated
        self.unvalidated_data = UnvalidatedData()
        # passed data is unvalidated so stored only as "user_data" until validation
        # defaultdict will add optional arguments to None so they can still be queried without key error
        self.user_data = defaultdict(lambda: None, **kwargs)

        # self.qm_agent = self.thread = self.agent_details = self.input_files = None
        # self.agent_id = self.prompt = self.description = self.output_schema = self.context = None

        self.validated = ValidatedData(self)  # container for validated data

        """
            Generation  ->  Validation ->  Transition ->  Trigger 
            (set up         (True or       (Modify        (Opt: trigger
            validation)      False   )     State Data)    next state)
        """

        self.state_machine = AgentStateMachineConfig().setup(self)
        dprint(f"State machine = {self.state_machine}")
        self.permissions = AgentStateMachineConfig().permissions
        receive_input = None
        # TODO - the subscription should only happen when agentType is
        # validated

    def initialise(self):
        self.initial_trigger(self.unvalidated_data)

    def load(self, agent_output=None):
        if agent_output:
            self.user_data['agent_output'] = agent_output
        self.load_trigger(self.unvalidated_data)

    def wait(self):
        self.wait_trigger(self.unvalidated_data)

    def run(self):
        self.run_trigger(self.unvalidated_data)

    def retrieve(self):
        self.retrieve_trigger(self.unvalidated_data)

    def receive_input(self, input):
        # Process the input and possibly generate new output
        self.process_input(input)
        pub.sendMessage(f'{self.agent_type}_output', sender=self.agent_type, output="Processed")

    def before_validation(self, unvalidated_data):
        """ Execute Before validation and transition """
        dprint(f"Generating state data for state {self.state}")
        current_state = self.state
        if current_state == 'Zero':
            self.unvalidated_data.set_data_for_state(current_state, **self.user_data)
            client = self.user_data['client']
            agent_id = self.user_data['agent_id']
            file_handler = self.user_data['file_handler']
            # self.unvalidated_data.set_data_for_state(
            #     'Initialised')
        elif current_state == 'Initialised':
            # Handle both direct user inputs and outputs from other agents
            # Determine input sources: direct user files or outputs from other agents
            client = self.validated.workflow_context.client
            agent_id = self.validated.agent_context.id
            file_handler = self.validated.workflow_context.file_handler
            uploaded_assistant_files = []
            if self.user_data['input_files']:
                for file in self.user_data['input_files']:
                    asst_file = file_handler.create_asst_file_from_local(
                        client,
                        agent_id,
                        file)
                    uploaded_assistant_files.append(asst_file)
            self.unvalidated_data.set_data_for_state(
                'Initialised',
                asst_input_files=uploaded_assistant_files)
            if self.user_data['agent_output']:
                output = self.user_data['agent_output']
                response = output['agent_response']
                output_file = output['output_file']
                structured_output = output['structured_output']
                asst_output_file = file_handler.create_asst_file_from_local(
                    client,
                    agent_id,
                    output)
                asst_response_file = file_handler.txt_to_asst_file(client, response, "response_", agent_id)

                self.unvalidated_data.set_data_for_state('Initialised',agent_output_file=asst_output_file)
                self.unvalidated_data.set_data_for_state('Initialised',agent_output_file=asst_response_file)
                self.unvalidated_data.set_data_for_state('Initialised',structured_output=structured_output)

        elif current_state == 'Loaded':
            dprint("Loaded state")
           # agent_thread = self.validated.agent_thread
        elif current_state == 'Running':
            dprint("In Running state, waiting for thread")
            #
            self.validated.agent_thread.retrieve(
                debug=False
            )


        return

    def validation(self, unvalidated_data):
        """ the validation phase of the transition. The state transition will
        only happen if the validation returns True"""
        dprint(f"Running validations for state {self.state}")
        current_state = self.state
        unvalidated_data = self.unvalidated_data.get_data_for_state(current_state)
        dprint(f"validation data for {self.state} = {unvalidated_data}")
        if current_state == 'Zero':
            try:
                # Validate initial data
                dprint(f"Doing Validations for Zero state with {unvalidated_data}")
                validated_workflow_context = WorkFlowContextModel(**unvalidated_data)
                dprint("Validated Workflow context")
                agent_configs_valid = AgentConfigs.get_agent_details(validated_workflow_context.agent_type)
                dprint("Validated AgentConfigs details")
                agent_context_valid = AgentContextModel(**agent_configs_valid)
                dprint("Validated AgentContextModel")
                self.validated.set_data('workflow_context', validated_workflow_context)
                self.validated.set_data('agent_config', agent_configs_valid)
                self.validated.set_data('agent_context', agent_context_valid)
                dprint("Set Validated data")
                input_files_valid = None
                if self.user_data['input_files']:
                    input_files_valid = InputFilesModel(
                        client=self.validated.workflow_context.client,
                        agent_id=self.validated.agent_context.id,
                        input_files=self.user_data['input_files'])
                dprint("Validated input files")
                self.validated.set_data('input_files', input_files_valid)
                agent_thread = AgentThread(
                    self.validated.workflow_context.client,
                    self.validated.agent_context.id,
                    self.validated.agent_context.prompt,
                    self.validated.workflow_context.file_handler)
                dprint(f"New agent_thread = {agent_thread} ")
                agent_thread_valid = AgentThreadModel(agent_thread=agent_thread)
                self.validated.set_data('agent_thread', agent_thread)
                return True
            except ValidationError as e:
                dprint("Validation error:", e.json())
            except ValueError as e:
                dprint(f"Value error: {e}")
            except Exception as e:
                dprint(f"Unexpected error while validating ZeroState data: {e}")
        elif current_state == "Initialised":
            input_files_valid = None
            try:
                print("Transition successful, context and files validated")
                asst_input_files = None
                if unvalidated_data['asst_input_files']:
                    dprint(f"Transition contains Asst files, validating...")
                    asst_files_valid = AsstFilesModel(
                        client=self.validated.workflow_context.client,
                        agent_id=self.validated.agent_context.id,
                        input_files=unvalidated_data['asst_input_files'])
                    dprint(f"Validation successful, asst_files{asst_files_valid}")
                    asst_input_files = unvalidated_data['asst_input_files']
                self.validated.set_data('asst_input_files', asst_input_files)
                agent_thread = self.validated.agent_thread
                agent_output = agent_response = structured_output = None
                if self.user_data['agent_output']:
                    agent_response = unvalidated_data['agent_response']
                    # TODO validate output, response
                    agent_output = unvalidated_data['output_file']
                    structured_output = unvalidated_data['structured_output']
                    dprint("Validation successful, agent_output")
                self.validated.set_data('agent_output', agent_output)
                self.validated.set_data('agent_response', agent_response)
                self.validated.set_data('structured_output', structured_output)

                return True
            except ValidationError as e:
                print(f"Validation failed: {e}")
                return False
        elif current_state == 'Loaded':
            # Validate and create a RunObjModel instance
            response = None
            if self.validated.agent_output:
                response = self.validated.agent_output['response']
            run_object = self.validated.agent_thread.new_runobj(
                parent=self.validated.agent_thread,
                input_files=self.validated.asst_input_files,
                retrieval_limit=20,
                agent_response=response,
                requirements=self.validated.agent_context.requirements,
                output_schema=self.validated.agent_context.output_schema
            )
            self.validated.set_data('run_object',run_object)
            return True
        elif current_state == 'Running':
            # did the run produce the right outputs and response?
            dprint(f"Validating the run in state {current_state}")
            # checks 1) is there a valid response and output file?
            output_dict = self.validated.agent_thread.get_output()
            # if not, it will get reissued
            # TODO validate output_dict
            self.validated.set_data('output_dict', output_dict)
            if output_dict['structured_output']:
               dprint("Good JSON output - validating state")
               return True
            else:
                instructions = ("No valid structured JSON was detected in your response or"
                                "in an output file that you have indicated was present. Please"
                                "regenerate your response and try again.")
                # reissue logic will go here
                dprint("Reissuing with an updated message")
                dprint(f"Agent did not complete and will be informed: {instructions}")
                # TODO cannot act on agent_thread state
                self.validated.agent_thread.add_message(instructions)
                self.trigger('run_trigger')

    def after_validation(self, unvalidated_data):
        """ Execute AFTER validation but before state transition"""
        dprint(f"Running transition before state {self.state} to next state")
        current_state = self.state
        unvalidated_data = self.unvalidated_data.get_data_for_state(current_state)
        dprint(f"transition data for {self.state} = {unvalidated_data}")
        client = self.validated.workflow_context.client
        agent_id = self.validated.agent_context.id
        file_handler = self.validated.workflow_context.file_handler
        if current_state == 'Zero':
            dprint("After Validation of Zero")
            pub.subscribe(self.receive_input, f'{self.validated.workflow_context.agent_type}_input')
            # Process existing assistant files (if any)
            self.delete_existing_assistant_files(client, agent_id, file_handler)
        if current_state == "Initialised":
            # pub.sendMessage(f'{self.validated.workflow_context.agent_type}_output', sender=self.validated.workflow_context.agent_type, output="Initialised")
            dprint(f"Initialised: Loading state Loaded")
        if current_state == 'Loaded':
            dprint(f"Exiting Loaded state 'Running'")
        elif current_state == 'Running':
            dprint(f"State '{current_state}' and output is {self.validated.output_dict}")
            pub.sendMessage(f"{self.validated.workflow_context.agent_type}.output", output=self.validated.output_dict)
        elif current_state == 'Retrieved':
            dprint(f"State '{current_state}'")
        else:
            dprint(f"Completed state: {current_state}")
            return

    def determine_input_sources(self):
        """ Decide whether to use user_data or outputs from previous agents
            Multiple situations
            1) Initial run and has inputs
            2) Initial run with inputs from another agent (e.g. QM)
            3) Repeated run - incorporated user feedback
        """
        if self.validated.agent_thread is None:
            # this means has not yet been through an execution
            if self.user_data['input_files'] is None:
                # For QM agents, inputs are typically outputs from other agents
                dprint("No user inputs")
            else:
                # For other agents, use provided input_files if available
                dprint(f"User inputs")
            return self.user_data.get('input_files', [])
        else:
            # this is the state that the
            dprint("User XXX inputs")

    def handle_input(self, agent_output_object):
        """Triggered when AI output is published"""
        dprint(f"Received output from another agent {agent_output_object}")
        dprint(f"Can now invoke recieving agent into")
        return agent_output_object

    def delete_existing_assistant_files(self, client, agent_id, file_handler):
        """ Manage existing assistant files in OpenAI """
        asst_files = client.beta.assistants.files.list(
            assistant_id=agent_id,
        )
        dprint(f"Assistant files: {asst_files}")
        for asst_file in asst_files.data:
            dprint(f"Assistant file: {asst_file}")
            try:
                dprint(f"Attempting to delete Assistant file-id: {asst_file.id}")
                client.beta.assistants.files.delete(
                    assistant_id=agent_id,
                    file_id=asst_file.id
                )
                dprint(f"Deleted Assistant file")
            except Exception as e:
                dprint(f"Error deleting Assistant file {e}")



    def upload_and_prepare_files(self, client, agent_id, file_handler, input_sources):
        """ Upload files to assistant and prepare them for processing """
        uploaded_files = []
        for file in input_sources:
            uploaded_file = file_handler.create_asst_file_from_local(client, agent_id, file)
            uploaded_files.append(uploaded_file)
        return uploaded_files

    def create_agent_thread(self, client, agent_id, file_handler):
        """ Create an AgentThread instance """
        agent_thread = AgentThread(client, agent_id, self.validated.agent_context.prompt, file_handler)
        return agent_thread

    def after_transition(self, unvalidated_data):
        """ Execute AFTER  transition"""
        pass


    def to_error(self):
        logging.error("An error occurred during the state transitions.")
        self.state_machine.set_state('error')

    def set_validated_data(self, key, value):
        if key in self.permissions.get(self.state, []):
            self.validated[key] = value
        else:
            raise PermissionError(f"Setting {key} is not allowed in the {self.state} state.")
