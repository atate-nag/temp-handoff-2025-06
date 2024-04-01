import json
import time
from debug import dprint
class QualityManager:
    def __init__(self, agent, run_agent, output_agent, max_tries=3):
        self.qm_run_agent = run_agent
        self.qm_output_agent = output_agent
        self.agent = agent
        self.max_tries = max_tries

    def assess_run_quality(self, thread):
        """The thread passed is the result of agent run, QM will make sure that it has solved
        the task, is not awaiting further instruction and has generated output.
        """
        for try_count in range(self.max_tries):
            response = self.agent.get_messages(thread)
            llm_response_file = self.agent.upload_text_to_file(response)
            self.qm_run_agent.set_prompt(f"Check if the agent completed the task in the given "
                                     f"response file {llm_response_file}")
            qm_run = self.qm_run_agent.setup_run(llm_response_file, qm=False)  # Do not QM the QM
            qm_file = self.qm_run_agent.run_agent()
            qm_content_dict = self.qm_run_agent.retrieve_file_content(qm_file)
            dprint(f"output is {qm_content_dict}")
            # TODO fix the logic problem of last iteration (as per output qm)
            if not qm_content_dict['completed']:
                prompt = qm_content_dict['agent instructions']
                dprint(f"Agent did not complete and will be informed: {prompt}")
                self.agent.add_message(thread.id, prompt)
                dprint(f"Going back to {self.agent}")
                response = self.agent.run_and_retrieve_thread()
            file = self.agent.retrieve_output()
            if file:
                return file

    def assess_output_quality(self, agent, agent_output_file, agent_thread):
        """The output passed is the external output of an agent run. The QM will assess if
        the output is generated to the correct quality according to pre-defined schema."""
        self.qm_output_agent.set_prompt(f"Check if the agent's output file {agent_output_file} adheres to the agent's  "
                                 f" output_requirements_schema={agent.output_schema}")
        dprint(f"prompt will be {self.qm_output_agent.prompt}")
        for try_count in range(self.max_tries):
            qm_run = self.qm_output_agent.setup_run(agent_output_file, qm=False)  # Do not QM the QM
            qm_file = self.qm_output_agent.run_agent()
            qm_content_dict = self.qm_output_agent.retrieve_file_content(qm_file)
            dprint(qm_content_dict)
            if qm_content_dict['validated']:
                # If validated, retrieve and return the output file
                file = self.qm_output_agent.retrieve_output()
                return file
            elif try_count < self.max_tries - 1:
                # If not validated and not the last try, inform the agent and retry
                if qm_content_dict['run problems']:
                    agent_output_file = self.assess_run_quality(agent_thread)
                else:
                    if isinstance(qm_content_dict['agent instructions'], list):
                        prompt = ' '.join(qm_content_dict['agent instructions'])
                    else:
                        prompt = str(qm_content_dict['agent instructions'])
                    dprint(f"Agent did not complete and will be informed: {prompt}")
                    self.agent.add_message(self.agent.active_thread().id, prompt)
                    dprint(f"Going back to {self.agent}")
                    retrieve = self.agent.run_and_retrieve_thread()
                    agent_output_file = self.agent.retrieve_output()
            else:
                # Last attempt and not validated, attempt to handle or return whatever is possible
                dprint("Last attempt was not validated. Attempting to proceed with available data.")
                file = self.agent.retrieve_output()
                if file:
                    return file
        dprint(f"Did not get a good response after {self.max_tries} attempts")
        return None

