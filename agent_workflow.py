from transitions import Machine
import logging
from state_transitions import (ZerotoInitialTransition, InitialtoLoadedTransition,
                               LoadedtoRunningTransition, RunningtoReturnedTransition, ReturnedtoCompleteTransition)
from validations import (ZerotoInitialValidation, InitialtoLoadedValidation,
                         LoadedtoRunningValidation, RunningtoReturnedValidation, ReturnedtoCompleteValidation)
from transition_data import TransitionData
# Set up logging
from debug import dprint

class AgentWorkFlow:
    states = ['Zero', 'Initialised', 'Loaded', 'Running', 'Returned', 'Completed']

    def __init__(self, client, file_handler, agent_type, qm=False, requirements=None ):
        # set all class variables to None until validated
        self.transition_data = TransitionData()
        self.transition_data.set_data_for_state('Zero', client=client, file_handler=file_handler, agent_type=agent_type, qm=qm, requirements=requirements)

        self.qm_agent = self.thread = None
        self.agent_id = self.prompt = self.description = self.output_schema = self.context = None

        self.machine = Machine(model=self, states=AgentWorkFlow.states, initial='Zero')
        self.machine.add_transition('initialise', 'Zero', 'Initialised',
                                    conditions=['run_validation'], before='run_transition', after='load')
        self.machine.add_transition('load', 'Initialised', 'Loaded', before='run_transition',after='run')
        self.machine.add_transition('run', 'Loaded', 'Running', before='run_transition',after='return')
        self.machine.add_transition('return', 'Running', 'Returned',before='run_transition',after='complete')
        self.machine.add_transition('complete', 'Returned', 'Completed',after='run_transition')
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
            logging.error(f"Unsupported state: {current_state}")
            return

        if not transition.run():
            dprint("transition had error")
            self.to_error()
        else:
            dprint("transition made")
        return



    def run_validation(self, transition_data):
        dprint(f"Running validations for state {self.state}")
        current_state = self.state
        transition_data = self.transition_data.get_data_for_state(current_state)
        dprint(f"validation data for {self.state} = {transition_data}")
        if current_state == 'Zero':
            validator = ZerotoInitialValidation(self, **transition_data)
        elif current_state == 'Initialised':
            validator = InitialtoLoadedValidation(self, **transition_data)
        elif current_state == 'Loaded':
            validator = LoadedtoRunningValidation(self, **transition_data)
        elif current_state == 'Running':
            validator = RunningtoReturnedValidation(self, **transition_data)
        elif current_state == 'Returned':
            validator = ReturnedtoCompleteValidation(self, **transition_data)
        else:
            logging.error(f"Unsupported state: {current_state}")
        validated = validator.validate()
        dprint(f"Validation = {validated}")
        if validated:
            return True
        else:
            logging.error(f"Unsupported state: {current_state}")
            return False

    def to_error(self):
        logging.error("An error occurred during the state transitions.")
        self.machine.set_state('error')
