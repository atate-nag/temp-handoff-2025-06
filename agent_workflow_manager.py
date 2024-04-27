from agent_workflow import Agent
from debug import dprint

class AgentManager:
    def __init__(self, client, file_handler, agent_types, input_files):
        self.client = client
        self.file_handler = file_handler
        self.agent_types = agent_types
        self.input_files = input_files
        self.agents = {}

        for agent_type in agent_types:
            self.agents[agent_type] = Agent(client=client,
                                            file_handler=file_handler,
                                            agent_type=agent_type,
                                            input_files=input_files if agent_type != 'qm_agent' else None,
                                            qm=agent_type == 'qm_agent')

        self.agents['qm_agent'].initialise()
        qm_id = self.agents['qm_agent'].get_id()
        dprint(f"QM ID return: {qm_id}")
        self.print_state()
        self.agents['competition_agent'].initialise(qm_id=qm_id)
        self.print_state()
        completed = False
        qm_instructions = None
        initial_run = True
        while completed is False:
            self.agents['competition_agent'].load(qm_instructions=qm_instructions, initial_run=initial_run)
            self.print_state()
            self.agents['competition_agent'].run()
            self.print_state()
            competition_outputs = self.agents['competition_agent'].retrieve()
            self.print_state()
            self.agents['qm_agent'].load(
                agent_output=competition_outputs,
                initial_run=initial_run,
                agent_requirements=self.agents['competition_agent'].requirements())
            self.print_state()
            self.agents['qm_agent'].run()
            self.print_state()
            qm_output = self.agents['qm_agent'].retrieve()
            self.print_state()
            dprint(f"QM output = {qm_output}")
            if qm_output is not None or self.agents['qm_agent'] != "Retrieved":
                dict = qm_output['structured_output']
                completed = dict['completed']
                qm_instructions = dict['agent instructions']
                if dict['completed']:
                    dprint(f"Completed, will exit now")
                else:
                    # both agent and qm qill need to be reverted back to Initialised state
                    dprint(f"Agent will be reissued with instructions {qm_instructions}")
                    self.agents['competition_agent'].reinitialise()
                    self.agents['qm_agent'].reinitialise()
            else:
                dprint("Error getting output from QM")
            initial_run = False
        self.print_state()
        dprint(f"Finalised output is {competition_outputs['structured_output']}")

    def print_state(self):
        dprint(f"States = {self.agents['competition_agent'].state} and {self.agents['qm_agent'].state} ")