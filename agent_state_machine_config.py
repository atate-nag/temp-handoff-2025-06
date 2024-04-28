from transitions import Machine


class AgentStateMachineConfig:
    def __init__(self):
        self.permissions = {}
        self.permissions['Zero'] = ['workflow_context', 'agent_config', 'agent_context', 'input_files', 'agent_thread',
                                    'agent_id','qm_id']
        self.permissions['Initialised'] = ['asst_input_files', 'agent_output_file', 'agent_response_file',
                                           'agent_structured_output','agent_requirements', 'agent_schema_errors']
        self.permissions['Loaded'] = ['run_object']
        self.permissions['Running'] = ['retrieve_output']
        self.permissions['Retrieved'] = []

    def setup(self, agent):
        self.machine = Machine(model=agent, states=agent.states, initial='Zero')
        self.machine.add_transition('initial_trigger',
                                    'Zero',
                                    'Initialised',
                                    prepare='before_zero_to_initialised',
                                    conditions=['zero_to_initialised_validation'],
                                    before='after_validation_running_to_retrieved')
        self.machine.add_transition('load_trigger',
                                    'Initialised',
                                    'Loaded',
                                    prepare='before_initialised_to_loaded',
                                    conditions=['initialised_to_loaded_validation'],
                                    )
        self.machine.add_transition('run_trigger',
                                    'Loaded',
                                    'Running',
                                    prepare='before_loaded_to_running',
                                    conditions=['loaded_to_running_validation'],
                                    after='retrieve_trigger')
        self.machine.add_transition('retrieve_trigger',
                                    'Running',
                                    'Retrieved',
                                    prepare='before_running_to_retrieved',
                                    conditions=['running_to_retrieved_validation'],
                                    before='after_validation_running_to_retrieved')
        # Transition to handle successful completion
        self.machine.add_transition('mark_complete', 'Retrieved', 'Completed')
        self.machine.add_transition('reissue_trigger', 'Running', 'Loaded', after='run_trigger')
        self.machine.add_transition('reinitialise', 'Retrieved', 'Initialised')

        return self.machine