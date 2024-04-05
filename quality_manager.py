import json
import time
from debug import dprint
class QualityManager:
    def __init__(self, agent, run_agent, output_agent, max_tries=4):
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
                qm_prompt = (f"You did not produce your output in the required method. You should write to an "
                             f" external JSON file and provide the fileID in "
                             f"the annotations or alternatively, write the JSON in triple-quoted text in your "
                             f"response directly.")
                self.qm_run_agent.add_message(self.qm_run_agent.active_thread().id, qm_prompt)
            else:
                qm_content_dict = self.qm_run_agent.retrieve_file_content(qm_file)
                dprint(f"output is {qm_content_dict}")
                dprint(f"Check of qm_content_dict['completed'] == {qm_content_dict['completed']} and type = "
                       f"{type(qm_content_dict['completed'])}")
                if qm_content_dict['completed']:
                    # this means the agent did complete the task as far as QM can see
                    file = self.agent.retrieve_output()
                    dprint(f"returned output file is is {file}")
                    if file:
                        return file
                else:
                    # this means the agent did not complete the task, set instructions and reissue
                    prompt = qm_content_dict['agent instructions']
                    if try_count < self.max_tries - 1:
                        dprint(f"Agent did not complete and will be informed: {prompt}")
                        self.agent.add_message(thread.id, prompt)
                        dprint(f"Going back to {self.agent}")
                        retrieve = self.agent.run_and_retrieve_thread()
                        response = self.agent.get_messages(thread)
                        agent_response_file = self.qm_run_agent.upload_text_to_file(response)
                        qm_prompt = (f"The agent has updated the response: {agent_response_file}. Read the full output,"
                                     f" not just a sample of it. The part that has changed is the useful part to you. "
                                     f"On the basis of the new information, please reassess if the agent completed the "
                                     f"task satisfactorily")
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
            dprint(f"Check of qm_content_dict['validated'] == {qm_content_dict['validated']} and type = "
                   f"{type(qm_content_dict['validated'])}")
            if qm_content_dict['validated']:
                # If validated, retrieve and return the output file
                file = self.qm_output_agent.retrieve_output()
                return file
            elif try_count < self.max_tries - 1:
                # If not validated and not the last try, inform the agent and retry
                if qm_content_dict['run problems']:
                    # if the output agent sees catastrophic errors then it will go back to run_problem QM (unlikely)
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
                                 "Please reassess according to the same schema. Read the full output, not just a sample"
                                 "of it. You must produce new agent instructions that are specifically related to the "
                                 f"new generated output in file {agent_output_file}. Do not send the existing/previous "
                                 f"agent instructions as they relate to previous analysis.")
                    dprint(f"Going back to QM output agent with prompt {qm_prompt}")
                    self.qm_output_agent.add_message(self.qm_output_agent.active_thread().id, qm_prompt, agent_output_file)
            else:
                # Last attempt and not validated, attempt to handle or return whatever is possible
                dprint("Last attempt was not validated. Attempting to proceed with available data.")
                file = self.agent.retrieve_output()
                if file:
                    return file
        dprint(f"Did not get a good response after {self.max_tries} attempts")
        return None

