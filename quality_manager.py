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
        response = self.agent.get_messages(thread)
        agent_response_file = self.agent.upload_text_to_file(response)
        qm_run = self.qm_run_agent.setup_run(agent_response_file, qm=False)
        for try_count in range(self.max_tries):
            qm_file = self.qm_run_agent.run_agent()
            if not qm_file:
                # agent did not produce output!
                qm_prompt = (f"You did not produce your output in the required method. You should use code_interpreter"
                             f"to generate a JSON file of your dictionary output, and provide the fileID in "
                             f"the annotations")
                self.qm_run_agent.add_message(self.qm_run_agent.active_thread().id, qm_prompt)
            else:
                qm_content_dict = self.qm_run_agent.retrieve_file_content(qm_file)
                dprint(f"output is {qm_content_dict}")
                # TODO fix the logic problem of last iteration (as per output qm)
                if qm_content_dict['completed']:
                    file = self.agent.retrieve_output()
                    if file:
                        return file
                else:
                    prompt = qm_content_dict['agent instructions']
                    if try_count < self.max_tries - 1:
                        dprint(f"Agent did not complete and will be informed: {prompt}")
                        self.agent.add_message(thread.id, prompt)
                        dprint(f"Going back to {self.agent}")
                        retrieve = self.agent.run_and_retrieve_thread()
                        response = self.agent.get_messages(thread)
                        agent_response_file = self.agent.upload_text_to_file(response)
                        qm_prompt = (f"The agent has updated the response: {agent_response_file}. Please reassess "
                                     f"if it completed the task satisfactorily")
                        self.qm_run_agent.add_message(self.qm_run_agent.active_thread().id, qm_prompt, agent_response_file)
                    else:
                        # Last attempt and not validated, attempt to handle or return whatever is possible
                        dprint("Last attempt was not validated. Attempting to proceed with available data.")
                        file = self.agent.retrieve_output()
                        if file:
                            return file


    def assess_output_quality(self, agent, agent_output_file, agent_thread):
        """The output passed is the external output of an agent run. The QM will assess if
        the output is generated to the correct quality according to pre-defined schema."""
        qm_run = self.qm_output_agent.setup_run(agent_output_file, qm=False)  # Do not QM the QM
        for try_count in range(self.max_tries):
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
                    qm_prompt = (f"The agent has produced new output {agent_output_file} following your advice. "
                                 "Please reassess.")
                    self.qm_run_agent.add_message(self.qm_run_agent.active_thread().id, qm_prompt, agent_output_file)
            else:
                # Last attempt and not validated, attempt to handle or return whatever is possible
                dprint("Last attempt was not validated. Attempting to proceed with available data.")
                file = self.agent.retrieve_output()
                if file:
                    return file
        dprint(f"Did not get a good response after {self.max_tries} attempts")
        return None

