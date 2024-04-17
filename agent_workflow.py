from transitions import Machine
import logging
from state_transitions import (ZerotoInitialTransition, InitialtoLoadedTransition,
                               LoadedtoRunningTransition, RunningtoReturnedTransition, ReturnedtoCompleteTransition)
from validations import (ZerotoInitialValidationModel, ZerotoInitialConfigModel, ZerotoInitialContextModel,
                         InitialtoLoadedValidation, LoadedtoRunningValidation, RunningtoReturnedValidation, ReturnedtoCompleteValidation)
from transition_data import TransitionData
# Set up logging
from debug import dprint

class AgentWorkFlow:
    states = ['Zero', 'Initialised', 'Loaded', 'Running', 'Returned', 'Completed']

    def __init__(self, **kwargs):
        # set all class variables to None until validated
        self.transition_data = TransitionData()
        # passed data is unvalidated so stored only as "user_data" until validation
        self.user_data = kwargs

        self.qm_agent = self.thread = None
        self.agent_id = self.prompt = self.description = self.output_schema = self.context = None

        self.machine = Machine(model=self, states=AgentWorkFlow.states, initial='Zero')
        self.machine.add_transition('initialise', 'Zero', 'Initialised',
                                    prepare='generate_state_data',
                                    conditions=['run_validation'], before='run_transition', after='load')
        self.machine.add_transition('load', 'Initialised', 'Loaded',
                                    prepare='generate_state_data',
                                    conditions=['run_validation'], before='run_transition',after='run')
        self.machine.add_transition('run', 'Loaded', 'Running',
                                    conditions=['run_validation'], before='run_transition',after='return')
        self.machine.add_transition('return', 'Running', 'Returned',
                                    conditions=['run_validation'], before='run_transition',after='complete')
        self.machine.add_transition('complete', 'Returned', 'Completed',
                                    conditions=['run_validation'], after='run_transition')
        self.initialise(self.transition_data)


    def run_transition(self, transition_data):
        dprint(f"Running transition before state {self.state} to next state")
        current_state = self.state
        transition_data = self.transition_data.get_data_for_state(current_state)
        dprint(f"transition data for {self.state} = {transition_data}")
        if current_state == 'Zero':
            transition = ZerotoInitialTransition(self, **transition_data)
            dprint(f"created the {transition}")
            self.transition_data.set_data_for_state('Initialised', client="")
        elif current_state == 'Initialised':
            transition = InitialtoLoadedTransition(self, **transition_data)
            self.transition_data.set_data_for_state('Loaded', client="")
        elif current_state == 'Loaded':
            transition = LoadedtoRunningTransition(self, **transition_data)
            self.transition_data.set_data_for_state('Running', client="")
        elif current_state == 'Running':
            transition = RunningtoReturnedTransition(self, **transition_data)
            self.transition_data.set_data_for_state('Loaded', client="")
        elif current_state == 'Returned':
            transition = ReturnedtoCompleteTransition(self, **transition_data)
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
        if current_state == 'Loaded':

            self.transition_data.set_data_for_state(current_state, **self.user_data)
        return

    def run_validation(self, transition_data):
        """ the validation phase of the transition. The state transition will
        only happen if the validation returns True"""
        dprint(f"Running validations for state {self.state}")
        current_state = self.state
        transition_data = self.transition_data.get_data_for_state(current_state)
        dprint(f"validation data for {self.state} = {transition_data}")
        if current_state == 'Zero':
            validated_one = ZerotoInitialValidationModel(client=transition_data['client'],
                                                     file_handler=transition_data['file_handler'],
                                                     agent_type=transition_data['agent_type'],
                                                     qm=transition_data['qm']
                                                     )
            if validated_one:
                agent_config = ZerotoInitialConfigModel(agent_type=transition_data['agent_type'])
                agent_details = agent_config.get_agent_details()
                dprint("Agent details: ", agent_details)
                context_validation = ZerotoInitialContextModel(id=agent_details['id'],
                                                       description=agent_details['description'],
                                                       prompt=agent_details['prompt'],
                                                       reqs_schema=agent_details['output_schema'])
                if context_validation:
                    validated = True
        elif current_state == 'Initialised':
            validated = InitialtoLoadedValidation(self, **transition_data)
        elif current_state == 'Loaded':
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
