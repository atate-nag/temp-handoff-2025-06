from transitions import Machine
import logging
from pydantic import ValidationError
from state_transitions import (ZerotoInitialTransition, InitialtoLoadedTransition,
                               LoadedtoRunningTransition, RunningtoReturnedTransition, ReturnedtoCompleteTransition)
from validations import (WorkFlowContextModel, AgentConfigs, AgentContextModel, InputFilesModel,
                         AsstFilesModel, AgentThreadModel,
                         InitialtoLoadedValidation, LoadedtoRunningValidation, RunningtoReturnedValidation,
                         ReturnedtoCompleteValidation)
from data_validation import UnvalidatedData, ValidatedData
from debug import dprint
from collections import defaultdict
from openai_asst import AgentThread
import time

class Agent:
    states = ['Zero', 'Initialised', 'Loaded', 'Running', 'Retrieved', 'Completed']

    def __init__(self, **kwargs):
        # set all class variables to None until validated
        self.unvalidated_data = UnvalidatedData()
        # passed data is unvalidated so stored only as "user_data" until validation
        # defaultdict will add optional arguments to None so they can still be queried without key error
        self.user_data = defaultdict(lambda: None, **kwargs)

        self.qm_agent = self.thread = self.agent_details = self.input_files = None
        self.agent_id = self.prompt = self.description = self.output_schema = self.context = None

        self.validated = ValidatedData(self)  # container for validated data
        self.permissions = {}

        """
            Generation  ->  Validation ->  Transition ->  Trigger 
            (set up         (True or       (Modify        (Opt: trigger
            validation)      False   )     State Data)    next state)
        """

        self.machine = Machine(model=self, states=Agent.states, initial='Zero')
        # ZeroState confgis
        self.permissions['Zero'] = ['workflow_context', 'agent_config', 'agent_context', 'input_files']
        self.machine.add_transition('initial_trigger',
                                    'Zero',
                                    'Initialised',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation')
        # Initialised State Configs
        self.permissions['Initialised'] = ['asst_input_files', 'agent_thread']
        self.machine.add_transition('load_trigger',
                                    'Initialised',
                                    'Loaded',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation'
                                    )
        # Loadedstate configs
        self.permissions['Loaded'] = ['run_object']
        self.machine.add_transition('run_trigger',
                                    'Loaded',
                                    'Running',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation')
        self.machine.add_transition('retrieve_trigger',
                                    'Running',
                                    'Retrieved',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation')
        self.permissions['Running'] = []
        self.machine.add_transition('complete', 'Returned', 'Completed',
                                    conditions=['validation'])
        self.permissions['Retrieved'] = []

    def initialise(self):
        self.initial_trigger(self.unvalidated_data)

    def load(self):
        self.load_trigger(self.unvalidated_data)

    def run(self):
        self.run_trigger(self.unvalidated_data)

    def retrieve(self):
        self.retrieve_trigger(self.unvalidated_data)

    def before_validation(self, unvalidated_data):
        """ Execute Before validation and transition """
        dprint(f"Generating state data for state {self.state}")
        current_state = self.state
        if current_state == 'Zero':
            self.unvalidated_data.set_data_for_state(current_state, **self.user_data)
        elif current_state == 'Initialised':
            uploaded_assistant_files = None
            file_handler = self.validated.workflow_context.file_handler
            client = self.validated.workflow_context.client
            agent_id = self.validated.agent_context.id
            if self.user_data['input_files']:
                uploaded_assistant_files = []
                for file in self.user_data['input_files']:
                    asst_file = file_handler.create_asst_file_from_local(
                        client,
                        agent_id,
                        file)
                    uploaded_assistant_files.append(asst_file)
            asst_files = client.beta.assistants.files.list(
                assistant_id=agent_id,
            )
            dprint(f"Assistant files: {asst_files}")
            # first_asst_file= asst_files.data[0].id
            # dprint(f"First Assistant file: {first_asst_file}")
            # asst_files = client.beta.assistants.files.list(
            #     assistant_id=agent_id,
            #     after=first_asst_file
            # )
            # dprint(f"New assistant files: {asst_files}")
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
            agent_thread = AgentThread(client, agent_id, self.validated.agent_context.prompt)
            self.unvalidated_data.set_data_for_state(
                'Initialised',
                agent_thread=agent_thread,
                asst_input_files=uploaded_assistant_files)
        elif current_state == 'Loaded':
            agent_thread = self.validated.agent_thread
        elif current_state == 'Running':
            dprint("In Running state, waiting for thread")
            #
            #
            self.validated.run_object.retrieve()

            # asst_file_output = self.validated.run_object.run_and_retrieve_output_file()
            #response = self.get_new_messages(self.active_thread())
            #response_asst_file = self.filehandler.txt_to_asst_file(self.client, response, "latest_response",
            #                                                       self.agent_id)
            #dprint(f"response from Agent = {response}")
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
                validated_workflow_context = WorkFlowContextModel(**unvalidated_data)
                agent_configs_valid = AgentConfigs.get_agent_details(validated_workflow_context.agent_type)
                agent_context_valid = AgentContextModel(**agent_configs_valid)
                print("Transition successful, context and files validated")
                self.validated.set_data('workflow_context', validated_workflow_context)
                self.validated.set_data('agent_config', agent_configs_valid)
                self.validated.set_data('agent_context', agent_context_valid)
                input_files_valid = None
                if self.user_data['input_files']:
                    input_files_valid = InputFilesModel(
                        client=self.validated.workflow_context.client,
                        agent_id=self.validated.agent_context.id,
                        input_files=self.user_data['input_files'])
                self.validated.set_data('input_files', input_files_valid)
                return True
            except Exception as e:
                print("Error while validating ZeroState data")
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
                agent_thread = unvalidated_data['agent_thread']
                dprint(f"picked agent_thread = {agent_thread} ")
                agent_thread_valid = AgentThreadModel(agent_thread=agent_thread)
                self.validated.set_data('agent_thread', agent_thread)
                self.validated.set_data('asst_input_files', asst_input_files)
                agent_thread = self.validated.agent_thread
                return True
            except ValidationError as e:
                print(f"Validation failed: {e}")
                return False
        elif current_state == 'Loaded':
            # TODO add validation logic for entering Run State
            # imporant check - is the run object
            # Validate and create a RunObjModel instance

            run_object = self.validated.agent_thread.new_runobj(
                parent=self.validated.agent_thread,
                input_files=self.validated.asst_input_files,
                retrieval_limit=20,
                requirements=self.validated.agent_context.requirements,
                output_schema=self.validated.agent_context.output_schema
            )
            self.validated.set_data('run_object',run_object)
            return True
        elif current_state == 'Running':
            dprint(f"Validating the run {current_state}")
            return True



    def after_validation(self, unvalidated_data):
        """ Execute AFTER validation but before state transition"""
        dprint(f"Running transition before state {self.state} to next state")
        current_state = self.state
        unvalidated_data = self.unvalidated_data.get_data_for_state(current_state)
        dprint(f"transition data for {self.state} = {unvalidated_data}")
        client = self.validated.workflow_context.client
        agent_id = self.validated.agent_context.id
        file_handler = self.validated.workflow_context.file_handler
        if current_state == "Initialised":
            # delete all the assistant files on the agent
            # asst_files = client.beta.assistants.files.list(
            #     assistant_id=agent_id,
            # )
            # dprint(f"Assistant files: {asst_files}")
            # # first_asst_file= asst_files.data[0].id
            # # dprint(f"First Assistant file: {first_asst_file}")
            # # asst_files = client.beta.assistants.files.list(
            # #     assistant_id=agent_id,
            # #     after=first_asst_file
            # # )
            # # dprint(f"New assistant files: {asst_files}")
            # for asst_file in asst_files.data:
            #     dprint(f"Assistant file: {asst_file}")
            #     try:
            #         dprint(f"Attempting to delete Assistant file-id: {asst_file.id}")
            #         client.beta.assistants.files.delete(
            #             assistant_id=agent_id,
            #             file_id=asst_file.id
            #         )
            #         dprint(f"Deleted Assistant file")
            #     except Exception as e:
            #         dprint(f"Error deleting Assistant file {e}")
            dprint(f"Initialised: Loading state Loaded")
        if current_state == 'Loaded':
            dprint(f"Exiting Loaded state 'Running'")
            # dprint(f"About to retreive run from state 'Running'")
            # self.validated.run_object.retrieve()
        elif current_state == 'Running':
            dprint(f"State '{current_state}'")
            # self.validated.run_object.retrieve()
        elif current_state == 'Returned':
            self.unvalidated_data.set_data_for_state('Running', client="")
        else:
            dprint(f"Completed state: {current_state}")
            return

    def after_transition(self, unvalidated_data):
        """ Execute AFTER  transition"""
        pass


    def to_error(self):
        logging.error("An error occurred during the state transitions.")
        self.machine.set_state('error')

    def define_permissions(self):
        self.permissions = {
            'Initialised': ['input_files', 'client'],
            'Processed': ['processed_data'],
            'Completed': []
        }

    def set_validated_data(self, key, value):
        if key in self.permissions.get(self.state, []):
            self.validated[key] = value
        else:
            raise PermissionError(f"Setting {key} is not allowed in the {self.state} state.")
