# from agent_workflow import Agent
# from debug import dprint
#
# class AgentManager:
#     def __init__(self, client, file_handler, agent_configs, input_files):
#         self.client = client
#         self.file_handler = file_handler
#         self.input_files = input_files
#         self.agents = {}
#         self.qm_agents = {}
#
#         dprint("Initializing AgentManager with agent configurations.")
#         # Initialize operational agents and their corresponding QM agents
#         for agent_config in agent_configs:
#             dprint(f"Creating operational agent for type: {agent_config['agent_type']}")
#             operational_agent = self.create_agent(agent_config['agent_type'], input_files)
#             self.agents[agent_config['agent_type']] = operational_agent
#             self.print_state()
#
#             dprint(f"Creating QM agent for operational type: {agent_config['agent_type']}")
#             qm_agent = self.create_agent('qm_agent', None)  # QM agents do not need input files
#             self.qm_agents[agent_config['agent_type']] = qm_agent
#             self.print_state()
#
#         # Optionally start the workflow processing
#         self.run_workflow()
#
#     def create_agent(self, agent_type, input_files):
#         """ Factory method to instantiate agents. """
#         dprint(f"Initialising {agent_type} with input files: {input_files}")
#         agent = Agent(client=self.client, file_handler=self.file_handler,
#                       agent_type=agent_type, input_files=input_files)
#         agent.initialise()
#         return agent
#
#     def run_workflow(self):
#         """ Manage the complete workflow across all agents and their individual QMs. """
#         for agent_type, agent in self.agents.items():
#             dprint(f"Starting workflow for {agent_type}")
#             self.run_agent_workflow(agent, self.qm_agents[agent_type])
#
#     def run_agent_workflow(self, agent, qm_agent):
#         """ Runs the workflow for an individual agent and its corresponding QM. """
#         completed = False
#         initial_run = True
#         qm_instructions = None
#
#         while not completed:
#             agent.receive_input(qm_instructions=qm_instructions)
#             agent.load(initial_run=initial_run)
#             self.print_state()
#             agent_output = agent.run()
#             self.print_state()
#             dprint(f"agent output is {agent_output}")
#             qm_agent.receive_input(agent_output=agent_output, agent_requirements=agent.requirements())
#             qm_agent.load(initial_run=initial_run)
#             self.print_state()
#             qm_output = qm_agent.run()
#             self.print_state()
#
#             if qm_output is not None and 'structured_output' in qm_output:
#                 dict_output = qm_output['structured_output']
#                 completed = dict_output['completed']
#                 qm_instructions = dict_output.get('agent instructions', None)
#
#                 if not completed:
#                     dprint(f"{agent.agent_type} will be rerun with instructions: {qm_instructions}")
#                     agent.reinitialise()
#                     qm_agent.reinitialise()
#                     self.print_state()
#                 else:
#                     dprint(f"{agent.agent_type} completed successfully.")
#             else:
#                 dprint(f"Error getting output from QM for {agent.agent_type}")
#                 break
#             initial_run = False  # Subsequent runs are not initial anymore
#
#     def print_state(self):
#         """ Print the current state of all agents and QM agents. """
#         for agent_type, agent in self.agents.items():
#             dprint(f"State of {agent_type}: {agent.state}")
#         for qm_agent_type, qm_agent in self.qm_agents.items():
#             dprint(f"State of {qm_agent_type}_qm: {qm_agent.state}")
#

# Example usage
# agent_configs = [{'agent_type': 'competition_agent'}, {'agent_type': 'analysis_agent'}]
# agent_manager = AgentManager(client, file_handler, agent_configs, input_files)

#
from agent_workflow import Agent
from debug import dprint

# class AgentManager:
#     def __init__(self, client, file_handler, agent_configs, input_files):
#         self.client = client
#         self.file_handler = file_handler
#         self.agent_types = agent_configs
#         self.input_files = input_files
#         self.agents = {}
#         self.qm_agents = {}
#         self.return_data = None
#
#         operational_agent = qm_agent = None
#         for agent_config in agent_configs:
#             dprint(f"Creating QM agent for operational type: {agent_config['agent_type']}")
#             qm_agent = self.create_agent('qm_agent', None)  # QM agents do not need input files
#             self.qm_agents[agent_config['agent_type']] = qm_agent
#             self.print_state()
#
#             dprint(f"Creating operational agent for type: {agent_config['agent_type']}")
#             operational_agent = self.create_agent(agent_config['agent_type'], input_files, qm_id=qm_agent.get_id())
#             self.agents[agent_config['agent_type']] = operational_agent
#             self.print_state()
#
#         self.run_workflow(operational_agent, qm_agent)

# def run_workflow(self, agent, qm):
#     self.print_state()
#     completed = False
#     qm_instructions = None
#     initial_run = True
#     while completed is False:
#         agent.receive_input(qm_instructions=qm_instructions)
#         agent.load(initial_run=initial_run)
#         self.print_state()
#         competition_outputs = agent.run()
#         self.print_state()
#         qm.receive_input(
#             agent_output=competition_outputs,
#             agent_requirements=agent.requirements())
#         qm.load(initial_run=initial_run)
#         self.print_state()
#         qm_output = qm.run()
#         self.print_state()
#         dprint(f"QM output = {qm_output}")
#         if qm_output is not None or qm != "Retrieved":
#             dict = qm_output['structured_output']
#             completed = dict['completed']
#             qm_instructions = dict['agent instructions']
#             if dict['completed']:
#                 dprint(f"Completed, will exit now")
#             else:
#                 # both agent and qm qill need to be reverted back to Initialised state
#                 dprint(f"Agent will be rerun with instructions {qm_instructions}")
#                 agent.reinitialise()
#                 qm.reinitialise()
#         else:
#             dprint("Error getting output from QM")
#         initial_run = False
#     self.print_state()
#     dprint(f"Finalised output is {competition_outputs['structured_output']}")
#     self.return_data = competition_outputs['structured_output']

class AgentManager:
    def __init__(self, client, file_handler, agent_configs, input_files):
        self.client = client
        self.file_handler = file_handler
        self.input_files = input_files
        self.agents = {}
        self.qm_agents = {}
        self.return_data = None

        for agent_config in agent_configs:
            qm_agent = self.create_agent('qm_agent', None)
            self.qm_agents[agent_config['agent_type']] = qm_agent
            operational_agent = self.create_agent(agent_config['agent_type'], input_files, qm_id=qm_agent.get_id())
            self.agents[agent_config['agent_type']] = operational_agent

    # def create_agent(self, agent_type, input_files, qm_id=None):
    #     dprint(f"Initialising {agent_type} with input files: {input_files}")
    #     agent = Agent(client=self.client, file_handler=self.file_handler,
    #                   agent_type=agent_type, input_files=input_files)
    #     agent.initialise(qm_id=qm_id)
    #     return agent

    def run_workflow(self):
        for agent_type, agent in self.agents.items():
            dprint(f"Starting dynamic workflow for {agent_type}")
            self.run_agent_workflow(agent, self.qm_agents[agent_type])

    # def handle_workflow(self, agent, qm_agent):
    #     initial_run = True
    #     qm_output = None
    #     while True:
    #         agent.receive_input()
    #         agent.load(initial_run=initial_run)
    #         output = agent.run()
    #         if not output:
    #             break  # Handle error or completion condition
    #         qm_agent.receive_input(output)
    #         qm_agent.load(initial_run=initial_run)
    #         qm_output = qm_agent.run()
    #         if self.evaluate_qm_output(qm_output):
    #             break  # If QM validates the output, break the loop
    #         agent.reinitialise()  # Prepare the agent for reprocessing
    #         initial_run = False  # Subsequent runs are not initial
    #     self.return_data = qm_output

    def run_agent_workflow(self, agent, qm_agent):
        """
        Runs the workflow for an individual agent and its corresponding QM.
        Manages the state transitions based on the output validation and the QM's instructions.
        """
        completed = False
        initial_run = True
        qm_instructions = None

        while not completed:
            agent.receive_input(qm_instructions=qm_instructions)
            agent.load(initial_run=initial_run)
            agent_output = agent.run()
            qm_agent.receive_input(agent_output=agent_output, agent_requirements=agent.requirements())
            qm_agent.load(initial_run=initial_run)
            qm_output = qm_agent.run()
            completed, qm_instructions = self.evaluate_qm_output(qm_output)
            if not completed:
                dprint(f"{agent.agent_type} will be rerun with instructions: {qm_instructions}")
                agent.reinitialise()
                qm_agent.reinitialise()
            else:
                dprint(f"{agent.agent_type} completed successfully.")
            initial_run = False  # Subsequent runs are not initial anymore

    def evaluate_qm_output(self, qm_output):
        """
        Evaluate the QM output to decide if the operational agent's output has passed the required conditions,
        extract any instructions for re-running the agent, and determine if the workflow should continue or the agent needs to be rerun.
        """
        if 'structured_output' in qm_output:
            dict_output = qm_output['structured_output']
            completed = dict_output.get('completed', False)
            qm_instructions = dict_output.get('agent instructions', None)
            return completed, qm_instructions
        else:
            # Log an error if the expected output structure is not met
            dprint("Error: QM output is missing 'structured_output'.")
            return False, None

    def create_agent(self, agent_type, input_files, qm_id=None):
        """ Factory method to instantiate agents. """
        dprint(f"Initialising {agent_type} with input files: {input_files}")
        agent = Agent(client=self.client, file_handler=self.file_handler,
                      agent_type=agent_type, input_files=input_files)
        agent.initialise(qm_id)
        return agent

    def return_dict(self):
        return self.return_data

    def print_state(self):
        """ Print the current state of all agents and QM agents. """
        for agent_type, agent in self.agents.items():
            dprint(f"State of {agent_type}: {agent.state}")
        for qm_agent_type, qm_agent in self.qm_agents.items():
            dprint(f"State of {qm_agent_type}_qm: {qm_agent.state}")