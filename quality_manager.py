import json
import time
from debug import dprint
class QualityManager:
    def __init__(self, agent, run_agent, max_tries=4):
        self.qm_agent = run_agent
        self.agent = agent
        self.max_tries = max_tries

    def assess_run_quality(self, thread):
        """The thread passed is the result of agent run, QM will make sure that it has solved
        the task, has been exhaustive, is not awaiting further instruction and has generated output.
        """
        # TODO might be able to access both of these in agent's own fields
        qm_agent_response_file = self.agent.upload_text_to_file("agent_response_0",self.agent.response_file)
        qm_agent_output_file = self.qm_agent.create_asst_file_from_id(self.agent.latest_output_file())
        qm_run = self.qm_agent.setup_qm_run(qm_agent_response_file, qm_agent_output_file)

        for try_count in range(self.max_tries):
            dprint(f"Checking that QM assistant has the input file {qm_agent_response_file} accessible")
            self.qm_agent.check_asst_files(qm_agent_response_file)
            dprint(f"Checking that QM assistant has the agent output file {qm_agent_output_file} accessible")
            self.qm_agent.check_asst_files(qm_agent_response_file)
            qm_file = self.qm_agent.run_agent()
            dprint(f"Returned file from QM agent run is {qm_file} ")
            if not qm_file:
                # agent did not produce output!
                qm_prompt = (f"You did not produce your output in the required method. You should write to an "
                             f" external JSON file and provide the fileID in "
                             f"the annotations or alternatively, write the JSON in triple-quoted text in your "
                             f"response directly.")
                self.qm_agent.add_message(self.qm_agent.active_thread().id, qm_prompt)
            else:
                qm_content_dict = self.qm_agent.retrieve_file_content(qm_file)
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
                        retrieve = self.agent.run_and_retrieve_thread()
                        response = self.agent.response_file
                        qm_agent_response_file = self.qm_agent.upload_text_to_file(f"agent_response_{try_count + 1}"
                                                                                , response)
                        qm_prompt_intro = f"The agent has followed your advice and an updated response is in {qm_agent_response_file}"
                        agent_output_file = self.agent.latest_output_file()
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

    # def assess_output_quality(self, agent, agent_output_file, agent_thread):
    #     """The output passed is the external output of an agent run. The QM will assess if
    #     the output is generated to the correct quality according to pre-defined schema."""
    #     qm_run = self.qm_output_agent.setup_run(agent_output_file, qm=False)  # Do not QM the QM
    #     for try_count in range(self.max_tries):
    #         qm_file = self.qm_output_agent.run_agent()
    #         qm_content_dict = self.qm_output_agent.retrieve_file_content(qm_file)
    #         dprint(qm_content_dict)
    #         dprint(f"Check of qm_content_dict['validated'] == {qm_content_dict['validated']} and type = "
    #                f"{type(qm_content_dict['validated'])}")
    #         if qm_content_dict['validated']:
    #             # If validated, retrieve and return the output file
    #             file = self.qm_output_agent.retrieve_output()
    #             return file
    #         elif try_count < self.max_tries - 1:
    #             # If not validated and not the last try, inform the agent and retry
    #             if qm_content_dict['run problems']:
    #                 # if the output agent sees catastrophic errors then it will go back to run_problem QM (unlikely)
    #                 agent_output_file = self.assess_run_quality(agent_thread)
    #             else:
    #                 if isinstance(qm_content_dict['agent instructions'], list):
    #                     prompt = ' '.join(qm_content_dict['agent instructions'])
    #                 else:
    #                     prompt = str(qm_content_dict['agent instructions'])
    #                 dprint(f"Agent did not complete and will be informed: {prompt}")
    #                 self.agent.add_message(self.agent.active_thread().id, prompt)
    #                 dprint(f"Going back to {self.agent}")
    #                 retrieve = self.agent.run_and_retrieve_thread()
    #                 agent_output_file = self.agent.retrieve_output()
    #
    #                 qm_prompt = (f"The agent has produced new output {agent_output_file} following your advice. "
    #                              "Please reassess according to the same schema. Read the full output, not just a sample"
    #                              "of it. You must produce new agent instructions that are specifically related to the "
    #                              f"new generated output in file {agent_output_file}. Do not send the existing/previous "
    #                              f"agent instructions as they relate to previous analysis.")
    #                 dprint(f"Going back to QM output agent with prompt {qm_prompt}")
    #                 qm_agent_output_file = self.qm_output_agent.create_asst_file_from_id(agent_output_file)
    #                 self.qm_output_agent.add_message(self.qm_output_agent.active_thread().id, qm_prompt,
    #                                                  agent_output_file)
    #
    #         else:
    #             # Last attempt and not validated, attempt to handle or return whatever is possible
    #             dprint("Last attempt was not validated. Attempting to proceed with available data.")
    #             file = self.agent.retrieve_output()
    #             if file:
    #                 return file
    #     dprint(f"Did not get a good response after {self.max_tries} attempts")
    #     return None

