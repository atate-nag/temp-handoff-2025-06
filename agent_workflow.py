from transitions import Machine
import logging
from pydantic import ValidationError
from state_transitions import (ZerotoInitialTransition, InitialtoLoadedTransition,
                               LoadedtoRunningTransition, RunningtoReturnedTransition, ReturnedtoCompleteTransition)
from validations import (WorkFlowContextModel, AgentConfigs, AgentContextModel, InputFilesModel,
                         AsstFilesModel, AgentThreadModel,
                         InitialtoLoadedValidation, LoadedtoRunningValidation, RunningtoReturnedValidation,
                         ReturnedtoCompleteValidation)
from transition_data import TransitionData, ValidatedData
# Set up logging
from debug import dprint
from quality_manager import QualityManager
from collections import defaultdict
from openai_asst import AgentThread


class AgentWorkFlow:
    states = ['Zero', 'Initialised', 'Loaded', 'Running', 'Returned', 'Completed']

    def __init__(self, **kwargs):
        # set all class variables to None until validated
        self.transition_data = TransitionData()
        # passed data is unvalidated so stored only as "user_data" until validation
        # defaultdict will add optional arguments to None so they can still be queried without key error
        self.user_data = defaultdict(lambda: None, **kwargs)

        self.qm_agent = self.thread = self.agent_details = self.input_files = None
        self.agent_id = self.prompt = self.description = self.output_schema = self.context = None

        self.validated = ValidatedData(self)  # container for validated data
        self.permissions = {}

        """
            Generation  ->  Validation ->  Transition ->  Trigger 
            (set up         (True or       (Modify        (trigger
            validation)      False   )     State Data)    next state)
        """

        self.machine = Machine(model=self, states=AgentWorkFlow.states, initial='Zero')
        self.machine.add_transition('initialise', 'Zero', 'Initialised',
                                    prepare='generate_state_data',
                                    conditions=['run_validation'], before='run_transition', after='load')
        self.permissions['Zero'] = ['workflow_context', 'agent_config', 'agent_context', 'input_files']
        self.machine.add_transition('load', 'Initialised', 'Loaded',
                                    prepare='generate_state_data',
                                    conditions=['run_validation'], before='run_transition', after='run')
        self.permissions['Initialised'] = ['asst_input_files','agent_thread']
        self.machine.add_transition('run', 'Loaded', 'Running',
                                    conditions=['run_validation'], before='run_transition', after='return')
        self.permissions['Loaded'] = []
        self.machine.add_transition('return', 'Running', 'Returned',
                                    conditions=['run_validation'], before='run_transition', after='complete')
        self.permissions['Running'] = []
        self.machine.add_transition('complete', 'Returned', 'Completed',
                                    conditions=['run_validation'], after='run_transition')
        self.permissions['Returned'] = []

        self.initialise(self.transition_data)

    def run_transition(self, transition_data):
        dprint(f"Running transition before state {self.state} to next state")
        current_state = self.state
        transition_data = self.transition_data.get_data_for_state(current_state)
        dprint(f"transition data for {self.state} = {transition_data}")

        agent_context = self.validated.agent_context
        workflow_context = self.validated.workflow_context

        client = self.validated.workflow_context.client
        agent_id = self.validated.agent_context.id
        file_handler = self.validated.workflow_context.file_handler

        if current_state == 'Zero':
            file_handler.delete_asst_files(
                client,
                agent_id
            )
            uploaded_assistant_files = None
            if self.user_data['input_files']:
                uploaded_assistant_files = []
                for file in transition_data['input_files']:
                    asst_file = file_handler.create_asst_file_from_local(
                        client,
                        agent_id,
                        file)
                    uploaded_assistant_files.append(asst_file)
            transition = ZerotoInitialTransition(self, **transition_data)
            dprint(f"created the {transition}")
            qm_agent = qm_class = qm_agent_thread = None
            if workflow_context.qm:
                qm_agent = AgentWorkFlow(client=client,
                                         file_handler=file_handler,
                                         agent_type="qm_agent",
                                         qm=False,
                                         requirements=self.validated.agent_context.output_schema)
                qm_class = QualityManager(self, qm_agent)
                qm_agent_thread = AgentThread(client, agent_id, self.validated.agent_context.prompt)
            agent_thread = AgentThread(client, agent_id, self.validated.agent_context.prompt)
            agent_thread.generate_runtime_prompt(
                input_files=uploaded_assistant_files,
                requirements=agent_context.requirements
            )
            self.transition_data.set_data_for_state(
                'Initialised',
                qm_agent=qm_agent,
                qm_class=qm_class,
                qm_agent_thread=qm_agent_thread,
                agent_thread=agent_thread,
                asst_input_files=uploaded_assistant_files)
        elif current_state == 'Initialised':
            # agent_thread = AgentThread(client, agent_id, self.validated.agent_context.prompt)
            # agent_thread.generate_runtime_prompt(
            #     input_files=self.validated.asst_input_files,
            #     requirements=self.validated.agent_context.requirements
            # )
            transition = InitialtoLoadedTransition(self, **transition_data)
            # self.transition_data.set_data_for_state(
            #     'Initialised',
            #      agent_threaed=agent_thread)
        elif current_state == 'Loaded':
            agent_thread = self.validated.agent_thread
            transition = LoadedtoRunningTransition(self, **transition_data)
            self.transition_data.set_data_for_state('Running', client="")
        elif current_state == 'Running':
            transition = RunningtoReturnedTransition(self, **transition_data)
            self.transition_data.set_data_for_state('Loaded', client="")
        elif current_state == 'Returned':

            # qm_agent = None
            # qm_class = None
            # if workflow_context.qm:
            #     qm_agent = AgentWorkFlow(client=client,
            #                              file_handler=file_handler,
            #                              agent_type="qm_agent",
            #                              qm=False,
            #                              requirements=self.validated.agent_context.output_schema)
            #     qm_class = QualityManager(self, qm_agent)
            #     qm_agent_thread = AgentThread(client, agent_id, self.validated.agent_context.prompt)
            #     self.transition_data.set_data_for_state('Loaded',
            #                                             qm_agent=qm_agent,
            #                                             qm_class=qm_class,
            #                                             qm_agent_thread=qm_agent_thread)
            # transition = ReturnedtoCompleteTransition(self, **transition_data)
            self.transition_data.set_data_for_state('Running', client="")
        else:
            dprint(f"Completed state: {current_state}")
            return

        if not transition.run():
            dprint("transition had error")
            self.to_error()
        else:
            dprint("transition made")
        return

    def generate_state_data(self, transition_data):
        """ The generation phase of state transition, will
        generate the appropriate data into the transition_data """
        dprint(f"Generating state data for state {self.state}")
        current_state = self.state
        if current_state == 'Zero':
            self.transition_data.set_data_for_state(current_state, **self.user_data)
        # if current_state == 'Initialised':
        # self.transition_data.set_data_for_state(current_state,
        #                                        uploaded_assistant_files=uploaded_assistant_files)
        return

    def run_validation(self, transition_data):
        """ the validation phase of the transition. The state transition will
        only happen if the validation returns True"""
        dprint(f"Running validations for state {self.state}")
        current_state = self.state
        transition_data = self.transition_data.get_data_for_state(current_state)
        dprint(f"validation data for {self.state} = {transition_data}")

        if current_state == 'Zero':
            try:
                # Validate initial data
                validated_workflow_context = WorkFlowContextModel(**transition_data)
                # Retrieve and validate agent details
                agent_configs_valid = AgentConfigs.get_agent_details(validated_workflow_context.agent_type)
                agent_context_valid = AgentContextModel(**agent_configs_valid)
                input_files_valid = None
                if self.user_data['input_files']:
                    input_files_valid = InputFilesModel(
                        client=validated_workflow_context.client,
                        agent_id=agent_context_valid.id,
                        input_files=self.user_data['input_files'])
                self.validated.set_data('input_files', input_files_valid)
                print("Transition successful, context and files validated")
                self.validated.set_data('workflow_context', validated_workflow_context)
                # self.validated.set_data('agent_config', agent_configs_valid)
                self.validated.set_data('agent_context', agent_context_valid)
                dprint(f"Validation successful, context and files validated context = {agent_context_valid}")
                return True
            except ValidationError as e:
                print(f"Validation failed: {e}")
                return False
        elif current_state == 'Initialised':
            try:
                asst_input_files = None
                if transition_data['asst_input_files']:
                    dprint(f"Transition contains Asst files, validating...")
                    asst_files_valid = AsstFilesModel(
                        client=self.validated.workflow_context.client,
                        agent_id=self.validated.agent_context.id,
                        input_files=transition_data['asst_input_files'])
                    dprint(f"Validation successful, asst_files{asst_files_valid}")
                    asst_input_files = transition_data['asst_input_files']
                agent_thread = transition_data['agent_thread']
                dprint(f"picked agent_thread = {agent_thread} ")
                try:
                    agent_thread_valid = AgentThreadModel(agent_thread=agent_thread)
                except ValidationError as e:
                    print(f"Validation failed: {e}")
                    return False
                self.validated.set_data('agent_thread', agent_thread)
                self.validated.set_data('asst_input_files', asst_input_files)
                return True
            except ValidationError as e:
                print(f"Validation of StateZero data failed: {e}")
            return False
        elif current_state == 'Loaded':
            agent_thread = self.validated.agent_thread
            """create a RunObj instance for a new run"""
            validated = LoadedtoRunningValidation(self, **transition_data)
        elif current_state == 'Running':
            validated = RunningtoReturnedValidation(self, **transition_data)
        elif current_state == 'Returned':
            validated = ReturnedtoCompleteValidation(self, **transition_data)
        else:
            logging.error(f"Unsupported state: {current_state}")
        # validated = validator.validate()
        dprint(f"Validation = {validated}")
        if validated:
            return True
        else:
            logging.error(f"Unsupported state: {current_state}")
            return False

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
