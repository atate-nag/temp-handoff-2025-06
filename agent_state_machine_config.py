from transitions import Machine


class AgentStateMachineConfig:
    def __init__(self):
        self.permissions = {}
        self.permissions['Zero'] = ['workflow_context', 'agent_config', 'agent_context', 'input_files', 'agent_thread']
        self.permissions['Initialised'] = ['asst_input_files', 'agent_output', 'agent_response', 'output_file', 'structured_output']
        self.permissions['Loaded'] = ['run_object']
        self.permissions['Running'] = ['output_dict']
        self.permissions['Retrieved'] = []

    def setup(self, agent):
        self.machine = Machine(model=agent, states=agent.states, initial='Zero')
        # ZeroState confgis
        self.machine.add_transition('initial_trigger',
                                    'Zero',
                                    'Initialised',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation')
        # Initialised State Configs
        # self.machine.add_transition(
        #     trigger='wait_trigger',
        #     source='Initialised',
        #     dest='Waiting')
        self.machine.add_transition('load_trigger',
                                    'Initialised',
                                    'Loaded',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation'
                                    )
        # Loadedstate configs

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
        self.machine.add_transition('complete', 'Returned', 'Completed',
                                    conditions=['validation'])

        return self.machine