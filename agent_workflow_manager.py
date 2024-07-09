
from agent import Agent
from debug import dprint

class AgentManager:
    def __init__(self, client, file_handler, agent_configs, input_files, use_qm_agents=True, qm_inputs=None):
        self.client = client
        self.file_handler = file_handler
        self.input_files = input_files
        self.use_qm_agents = use_qm_agents  # Flag to control QM agent usage
        self.agents = {}
        self.qm_agents = {}
        self.return_data = None

        dprint(f"input_files: {input_files}")
        for agent_config in agent_configs:
            if self.use_qm_agents:
                # qm_agent = self.create_agent('qm_assessor_agent', qm_inputs)
                qm_agent = self.create_agent('full_graph_qm_agent', qm_inputs)
                self.qm_agents[agent_config['agent_type']] = qm_agent
            operational_agent = self.create_agent(agent_config['agent_type'], input_files, qm_id=qm_agent.get_id() if self.use_qm_agents else None)
            self.agents[agent_config['agent_type']] = operational_agent

    def run_workflow(self):
        for agent_type, agent in self.agents.items():
            dprint(f"Starting dynamic workflow for {agent_type}")
            self.run_agent_workflow(agent, self.qm_agents.get(agent_type))

    def run_agent_workflow(self, agent, qm_agent):
        completed = False
        initial_run = True
        qm_instructions = None
        agent_output = None

        while not completed:
            try:
                agent.receive_input(qm_instructions=qm_instructions)
                agent.load(initial_run=initial_run)
                agent_output = agent.run()
                self.agent_output = agent_output
                if agent_output is None:
                    dprint(f"none returned from operational agent - Aborting")
                    raise Exception

                if self.use_qm_agents:
                    qm_agent.receive_input(agent_output=agent_output, agent_requirements=agent.requirements())
                    qm_agent.load(initial_run=initial_run)
                    qm_output = qm_agent.run()
                    if qm_output:
                        completed, qm_instructions = self.evaluate_qm_output(qm_output)
                else:
                    completed = True

                if not completed:
                    dprint(f"{agent.agent_type} will be rerun with instructions: {qm_instructions}")
                    agent.reinitialise()
                    if self.use_qm_agents:
                        qm_agent.reinitialise()
                else:
                    dprint(f"{agent.agent_type} completed successfully.")
                    agent.cleanup()
                    if self.use_qm_agents:
                        qm_agent.cleanup()
            except Exception as e:
                dprint(f"Error processing {agent.agent_type}: {str(e)} Aborting")
                raise Exception
            finally:
                initial_run = False
            self.print_state()
            if agent_output and isinstance(agent_output, dict):
                self.return_data = agent_output.get('structured_output', {})
                self.return_response = agent.agent_response
            else:
                self.return_data = None

    def evaluate_qm_output(self, qm_output):
        """
        Evaluate the QM output to decide if the operational agent's output has passed the required conditions,
        extract any instructions for re-running the agent, and determine if the workflow should continue or the agent needs to be rerun.
        """
        if 'structured_output' in qm_output:
            dict_output = qm_output['structured_output']
            completed = dict_output.get('completed', False)

            # Ensure 'completed' is treated as a boolean
            if isinstance(completed, str):
                completed = completed.lower() == 'true'

            dprint(f"pulled out the completed value of {completed}")
            qm_instructions = dict_output.get('agent instructions', None)
            dprint(f"pulled out the agent instructions of {qm_instructions}")
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
        if self.use_qm_agents:
            for qm_agent_type, qm_agent in self.qm_agents.items():
                dprint(f"State of {qm_agent_type}_qm: {qm_agent.state}")


