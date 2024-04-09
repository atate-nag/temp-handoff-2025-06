import json
import time
import sys
from debug import dprint
class QualityManager:
    def __init__(self, agent, run_agent, max_tries=4):
        self.qm_agent = run_agent
        self.agent = agent
        self.max_tries = max_tries

    def quality_manage_agent(self, thread):
        """
            Assess whether an agent has completed the task satisfactorily. The QM process is defined in the agent
            definition. Run the QM, check its analysis, reissue the agent, repeat until the task is done or
            the limit is hit.
        """
        qm_agent_output_file = self.agent.latest_output_file()
        qm_agent_response_file = self.agent.response_file
        dprint(f"qm_agent_response_file: {qm_agent_response_file} and qm_agent_output_file: {qm_agent_output_file}")
        qm_run = self.qm_agent.setup_qm_run(qm_agent_response_file, qm_agent_output_file)
        for try_count in range(self.max_tries):
            dprint(f"Checking that QM assistant has the input file {qm_agent_response_file} accessible")
            self.qm_agent.check_asst_files(qm_agent_response_file)
            dprint(f"Checking that QM assistant has the agent output file {qm_agent_output_file} accessible")
            self.qm_agent.check_asst_files(qm_agent_response_file)
            # qm_file = self.qm_agent.run_agent()
            qm_content_dict = self.qm_agent.run_agent()
            dprint(f"Returned output from QM agent run is {qm_content_dict}")
            if not qm_content_dict or 'completed' not in qm_content_dict or 'agent instructions' not in qm_content_dict:
                # agent did not produce output or correct output!
                qm_prompt = (f"You did not produce your output in the required method. You should write to an "
                             f" external JSON file and provide the fileID in "
                             f"the annotations or alternatively, write the JSON in triple-quoted text in your "
                             f"response directly. Your content should be a dictionary with fields 'completed' and "
                             f"'agent_instructions' and should not contain anything else")
                self.qm_agent.add_message(self.qm_agent.active_thread().id, qm_prompt)
            else:
                # needs a check to make sure that the QM output is
                # qm_content_dict = self.qm_agent.retrieve_file_content(qm_file)
                dprint(f"output is {qm_content_dict}")
                dprint(f"Check of qm_content_dict['completed'] == {qm_content_dict['completed']} and type = "
                       f"{type(qm_content_dict['completed'])}")
                if qm_content_dict['completed']:
                    # this means the agent did complete the task as far as QM can see
                    file = self.agent.latest_output_file()
                    dprint(f"returned output file is is {file}")
                    return file
                else:
                    # this means the agent did not complete the task, set instructions and reissue
                    prompt = qm_content_dict['agent instructions']
                    if try_count < self.max_tries - 1:
                        dprint(f"Agent did not complete and will be informed: {prompt}")
                        self.agent.add_message(thread.id, prompt)
                        dprint(f"Going back to {self.agent}")
                        agent_response_file, agent_output_file = self.agent.run_and_retrieve_response_and_output()
                        qm_agent_response_file = self.qm_agent.create_asst_file_from_id(agent_response_file)
                        # TODO all this prompt mess can be moved into an agent method?
                        qm_prompt_intro = f"The agent has followed your advice and an updated response is in {qm_agent_response_file}"
                        dprint(f"Agent response file is {qm_agent_response_file}")
                        qm_prompt_output = ""
                        if agent_output_file:
                            qm_agent_output_file = self.qm_agent.create_asst_file_from_id(agent_output_file)
                            qm_prompt_output = (f"and produced a new external output file at {qm_agent_output_file}")
                        qm_prompt_tail = (f". Read the full response and new output file if it is present. "
                                          f"On the basis of the new information, please reassess "
                                            f"whether the agent completed the task satisfactorily and "
                                          f"produce new agent instructions")
                        qm_prompt = qm_prompt_intro + qm_prompt_output + qm_prompt_tail
                        dprint(f"QM reissue prompt = {qm_prompt}")
                        self.qm_agent.qm_add_message(qm_prompt, qm_agent_response_file, qm_agent_output_file)
                    else:
                        # Last attempt and not validated, attempt to handle or return whatever is possible
                        dprint("Last attempt was not validated. Attempting to proceed with available data.")
                        return self.agent.latest_output_file()

