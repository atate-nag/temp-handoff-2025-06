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

        tries = 0
        while tries < self.max_tries:
            if tries == self.max_tries - 1:
                print(f"QM did not manage to get a good result after {tries + 1} attempts")
                return None
            response = self.agent.get_messages(thread)
            llm_response_file = self.agent.upload_text_to_file(response)
            self.qm_agent.set_prompt(f"Check if the agent completed the task in the given "
                                     f"response file {llm_response_file.id}")
            qm_run = self.qm_agent.setup_run(llm_response_file, qm=False)  # Do not QM the QM
            qm_file = self.qm_agent.run_agent()
            qm_content_dict = self.qm_agent.retrieve_file_content(qm_file)

            # qm_prompt = f"Check if the agent completed the task in the given response file {llm_response_file.id}"
            # qm_thread = self.qm_agent.create_thread(qm_prompt, llm_response_file.id)
            # qm_response = self.qm_agent.run_and_retrieve_thread()
            # qm_file = self.qm_agent.retrieve_output_or_reissue(qm_thread)
            # qm_content_dict = self.qm_agent.retrieve_file_content(qm_file)
            # # qm_content_dict = json.loads(self.client.files.retrieve_content(qm_file))
            #
            # if qm_content_dict["completed"]:
            #     agent_output_file = self.agent.retrieve_output()
            #     print(f"QM: returning file {agent_output_file}")
            #     return agent_output_file

            prompt = qm_content_dict["agent instructions"]
            print(f"QM: Agent did not complete and will be informed: {prompt}")
            self.agent.add_message(thread.id, prompt)
            print(f"QM: Going back to {self.agent}")
            response = self.agent.run_and_retrieve_thread()
            file = self.agent.retrieve_output()

            tries += 1
