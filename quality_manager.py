import json
import time
class QualityManager:
    def __init__(self, agent, qm_agent=None, max_tries=3):
        self.agent = agent
        self.max_tries = max_tries
        self.agent_thread = qm_agent.active_thread
        self.qm_agent = qm_agent

    def assess_run_quality(self, thread):
        """The thread passed is the result of agent run, QM will make sure that it has solved
        the task, is not awaiting further instruction and has generated output.
        """
        for try_count in range(self.max_tries):
            if try_count == self.max_tries - 1:
                print(f"QM did not manage to get a good result after {try_count + 1} attempts")
                return None
            response = self.agent.get_messages(thread)
            llm_response_file = self.agent.upload_text_to_file(response)
            self.qm_agent.set_prompt(f"Check if the agent completed the task in the given "
                                     f"response file {llm_response_file}")
            qm_run = self.qm_agent.setup_run(llm_response_file, qm=False)  # Do not QM the QM
            qm_file = self.qm_agent.run_agent()
            qm_content_dict = self.qm_agent.retrieve_file_content(qm_file)
            if not qm_content_dict['completed']:
                prompt = qm_content_dict['agent instructions']
                print(f"QM: Agent did not complete and will be informed: {prompt}")
                self.agent.add_message(thread.id, prompt)
                print(f"QM: Going back to {self.agent}")
                response = self.agent.run_and_retrieve_thread()
            file = self.agent.retrieve_output()
            if file:
                return file

    def assess_output_quality(self, agent, qm_agent, agent_output_file):
        """The output passed is the external output of an agent run. The QM will assess if
        the output is generated to the correct quality according to pre-defined schema."""
        self.qm_agent.set_prompt(f"Check if the agent's output file {agent_output_file} adheres to the agent's  "
                                 f" output_requirements_schema={agent.output_schema}")
        for try_count in range(self.max_tries):
            qm_run = self.qm_agent.setup_run(agent_output_file, qm=False)  # Do not QM the QM
            qm_file = self.qm_agent.run_agent()
            qm_content_dict = self.qm_agent.retrieve_file_content(qm_file)
            if not qm_content_dict["validated"]:
                prompt = qm_content_dict["agent instructions"]
                print(f"QM: Agent did not complete and will be informed: {prompt}")
                self.agent.add_message(agent.active_thread().id, prompt)
                print(f"QM: Going back to {self.agent}")
                response = self.agent.run_and_retrieve_thread()
            file = self.agent.retrieve_output()
            if file:
                return file
        return None


