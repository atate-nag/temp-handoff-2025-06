from transitions import Machine


class AgentStateMachineConfig:
    def __init__(self):
        self.permissions = {}
        self.permissions['Zero'] = ['workflow_context', 'agent_config', 'agent_context', 'input_files', 'agent_thread','agent_id','qm_id']
        self.permissions['Initialised'] = ['asst_input_files', 'agent_output_file', 'agent_response_file', 'agent_structured_output']
        self.permissions['Loaded'] = ['run_object']
        self.permissions['Running'] = ['retrieve_output']
        self.permissions['Retrieved'] = []

    def setup(self, agent):
        self.machine = Machine(model=agent, states=agent.states, initial='Zero')
        self.machine.add_transition('initial_trigger',
                                    'Zero',
                                    'Initialised',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation')
        self.machine.add_transition('load_trigger',
                                    'Initialised',
                                    'Loaded',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation'
                                    )
        self.machine.add_transition('load_trigger',
                                    'Running',
                                    'Loaded',
                                    prepare='before_validation',
                                    before='after_validation'
                                    )
        self.machine.add_transition('run_trigger',
                                    'Loaded',
                                    'Running',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation',
                                    after='retrieve_trigger')
        self.machine.add_transition('retrieve_trigger',
                                    'Running',
                                    'Retrieved',
                                    prepare='before_validation',
                                    conditions=['validation'],
                                    before='after_validation')
        # Transition to handle successful completion
        self.machine.add_transition('mark_complete', 'Retrieved', 'Completed')
        self.machine.add_transition('reissue_trigger', 'Running', 'Loaded', after='run_trigger')
        self.machine.add_transition('reinitialise', 'Retrieved', 'Initialised')

        return self.machine