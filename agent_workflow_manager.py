# from agent_workflow import Agent
# class AgentManager:
#     def __init__(self, client, file_handler, agent_types):
#         self.client = client
#         self.file_handler = file_handler
#         self.agents = {}
#         self.initialize_agents(agent_types)
#
#     def initialize_agents(self, agent_configs):
#         """ Initialize operational agents and their corresponding QM agents. """
#         for config in agent_configs:
#             operational_agent = self.create_agent(config['operational'])
#             qm_agent = self.create_agent(config['qm'], is_qm=True)
#             self.agents[operational_agent.agent_type] = operational_agent
#             self.agents[qm_agent.agent_type] = qm_agent
#
#         # Initialize the integrator agent, which collates all results
#         integrator_config = {'agent_type': 'integrator', 'input_files': None}
#         self.integrator = self.create_agent(integrator_config)
#         self.integrator_qm = self.create_agent({'agent_type': 'integrator_qm'}, is_qm=True)
#
#     def create_agent(self, config, is_qm=False):
#         """ Factory method to create and initialize agents. """
#         input_files = None if is_qm else config.get('input_files', None)
#         agent = Agent(
#             client=self.client,
#             file_handler=self.file_handler,
#             agent_type=config['agent_type'],
#             input_files=input_files,
#             qm=is_qm)
#         agent.initialise()
#         return agent
#
#     def run_workflow(self):
#         """ Manage the complete workflow across all agents and their QMs. """
#         for agent_type, agent in self.agents.items():
#             if 'qm' not in agent_type:  # Avoid running QMs directly
#                 self.process_agent(agent)
#
#         # Once all individual agents and their QMs have processed, run the integrator
#         self.process_integrator()
#
#     def process_agent(self, agent):
#         """ Processes an individual agent and its corresponding QM. """
#         agent.load()
#         agent.run()
#         output = agent.retrieve()
#
#         # Load and run the corresponding QM agent
#         qm_agent = self.agents[f"{agent.agent_type}_qm"]
#         qm_agent.receive_input(output)
#         qm_agent.load()
#         qm_agent.run()
#         qm_validation = qm_agent.retrieve()
#
#         # Handle the output of the QM process, possibly reissue tasks
#         if not qm_validation['passed']:
#             agent.reinitialise()  # Reset agent for reprocessing if needed
#
#     def process_integrator(self):
#         """ Processes the integrator agent which collates all outputs. """
#         # Gather outputs from all agents
#         inputs_for_integration = [self.agents[atype].get_latest_output() for atype in self.agents if 'qm' not in atype]
#         self.integrator.receive_inputs(inputs_for_integration)
#         self.integrator.load()
#         self.integrator.run()
#         final_output = self.integrator.retrieve()
#
#         # Validate final output with its QM
#         self.integrator_qm.receive_input(final_output)
#         self.integrator_qm.load()
#         self.integrator_qm.run()
#         final_validation = self.integrator_qm.retrieve()
#
#         if final_validation['passed']:
#             print("Workflow completed successfully with validated final output.")
#         else:
#             print("Final output did not pass validation; adjustments needed.")

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
                                            input_files=input_files if agent_type != 'qm_agent' else None)

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
            competition_outputs = self.agents['competition_agent'].run()
            self.print_state()
            self.agents['qm_agent'].load(
                agent_output=competition_outputs,
                initial_run=initial_run,
                agent_requirements=self.agents['competition_agent'].requirements())
            self.print_state()
            qm_output = self.agents['qm_agent'].run()
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
                    dprint(f"Agent will be rerun with instructions {qm_instructions}")
                    self.agents['competition_agent'].reinitialise()
                    self.agents['qm_agent'].reinitialise()
            else:
                dprint("Error getting output from QM")
            initial_run = False
        self.print_state()
        dprint(f"Finalised output is {competition_outputs['structured_output']}")
        self.return_dict = competition_outputs['structured_output']

    def return_dict(self):
        return self.return_dict

    def print_state(self):
        dprint(f"States = {self.agents['competition_agent'].state} and {self.agents['qm_agent'].state} ")