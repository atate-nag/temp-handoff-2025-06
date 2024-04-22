from agent_workflow import Agent
from validations import WorkFlowContextModel
from debug import dprint

from pubsub import pub
from agent_workflow import Agent
from validations import WorkFlowContextModel
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

        # Setup event subscriptions
        for name, agent in self.agents.items():
            pub.subscribe(self.handle_output, f'{name}_output')

        # Initialize agents (assuming this triggers their internal setup and state transitions)
        for agent in self.agents.values():
            agent.initialise()

    def handle_output(self, sender, output):
        # Output handling logic based on the sender
        if sender == 'AI':
            # AI agent has produced output, pass it to the QM agent
            pub.sendMessage('QM_input', input=output)
        elif sender == 'QM':
            # QM agent has validated or processed the AI's output
            if self.agents['AI'].is_complete():
                pub.sendMessage('AI_complete')
            else:
                pub.sendMessage('AI_reprocess', input=output)

# class AgentManager:
#     def __init__(self, client, file_handler, agent_type, input_files, qm=False):
#         self.client = client
#         self.file_hander = file_handler
#         self.agent_type = agent_type
#         self.qm=qm
#         self.input_files = input_files
#         self.agents = {
#             'AI': Agent(client=client,
#                         file_handler=file_handler,
#                         agent_type=agent_type,
#                         qm=True,
#                         input_files=input_files),
#             'QM': Agent(client=client,
#                         file_handler=file_handler,
#                         agent_type="qm_agent",
#                         qm=False)
#         }
#         dprint(f"agent states = AI:{self.agents['AI'].state} QM:{self.agents['QM'].state}")
#         self.setup_workflow()
#         dprint(f"Agents are {self.agents}")
#         dprint(f"agent states = AI:{self.agents['AI'].state} QM:{self.agents['QM'].state}")
#
#
#     def setup_workflow(self):
#         validated_workflow_context = WorkFlowContextModel(
#             client=self.client,
#             file_handler=self.file_hander,
#             agent_type=self.agent_type,
#             qm=self.qm
#         )
#         # get the AI agent into loaded state
#         self.agents['AI'].initialise(
#         )
#         self.agents['QM'].initialise(
#         )
#         dprint(f"agent states = AI:{self.agents['AI'].state} QM:{self.agents['QM'].state}")
#         self.agents['AI'].load()
#         dprint(f"agent states = AI:{self.agents['AI'].state} QM:{self.agents['QM'].state}")
#         dprint(f" Agent[AI] has thread object {self.agents['AI'].validated.agent_thread} ")
#         self.agents['AI'].run()
#         dprint(f"agent states = AI:{self.agents['AI'].state} QM:{self.agents['QM'].state}")
#         self.agents['AI'].retrieve()
#         dprint(f"agent states = AI:{self.agents['AI'].state} QM:{self.agents['QM'].state}")
#
#         # self.agents['AI'].run_agent()
#     def handle_output(self, sender, output):
#         # Decide next steps based on the sender's output
#         if sender.agent_type == 'AI':
#             self.agents['QM'].receive_input(output)
#         elif sender.agent_type == 'QM':
#             if self.agents['AI'].is_complete():
#                 self.agents['AI'].machine.trigger('complete')
#             else:
#                 self.agents['AI'].receive_input(output)
#
#     def check_complete(self):
#         # Check if the workflow is complete
#         if all(agent.machine.state == 'completed' for agent in self.agents.values()):
#             print("Workflow completed successfully.")
