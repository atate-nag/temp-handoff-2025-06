from debug import dprint
import time
class AgentThread():
    def __init__(self,client,agent_id, initial_prompt):
        self.client = client
        self.agent_id = agent_id
        self.initial_prompt = initial_prompt
        self.run_prompt = None
        self.thread = None

    def generate_thread(self, data):
        if self.run_prompt is None:
            print("Error: Running agent with empty Prompt")
        prompt = self.run_prompt
        self.thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )
        return

    def generate_runtime_prompt(self,input_files=None,input_response=None,agent_output=None, requirements=None):
        """
            Generate a prompt using runtime information. Note placeholder values
            appear in the prompt in known_agents.json in the "prompt" field.
        """
        placeholder_values = {
            "INPUT_FILES": input_files,
            "AGENT_RESPONSE": input_response,
            "AGENT_OUTPUT" : agent_output,
            "AGENT_REQUIREMENTS": requirements,
        }
        # Prepare the prompt by replacing placeholders with actual runtime values
        dprint("placeholder values:", placeholder_values)
        prompt = self.initial_prompt
        for placeholder, value in placeholder_values.items():
            # Convert list to string if necessary
            if isinstance(value, list):
                value_str = ', '.join(map(str, value))  # Ensure all elements are converted to strings
            else:
                value_str = str(value)
            prompt = prompt.replace(f"{{{placeholder}}}", value_str)
        # self.prompt = prompt
        dprint(f"End self-prompt is {prompt}")
        self.run_prompt = prompt
        return

class RunObj():

    """The RunObj class instance will dictate
    an single run of Agent, defining the input, status
    and outputs, correlating each of the above.
    hence the same RubObj can only make one run """

    def __init__(self, parent):
        self.parent = parent
        self.run = None
        self.input_files = None
        self.retrieval_limit = 20

    def create_run(self):
        client = self.parent.client
        self.openai_run = client.beta.threads.runs.create(
            thread_id=self.parent.thread.id,
            assistant_id=self.parent.agent_id,
            model="gpt-4-turbo-preview",
            tools=[{"type": "code_interpreter"}],
        )
        return

    def retrieve_run(self):
        start_time = time.time()
        retrieve = self.retrieve_run_and_retry(self.openai_run.id)
        end_time = time.time()
        dprint("Retrieve time: " + str(end_time - start_time))
        return retrieve

    def retrieve_run_and_retry(self, run_id ):
        """
            from a run_id, retrieve a run and report status
        """
        retries = 0
        client = self.parent.client
        thread_id = self.parent.thread
        start_time = time.time()
        while retries < self.retrieval_limit:
            try:
                retrieve = client.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run_id
                )
                dprint(f" Assistant {self.description} status: {retrieve.status}")
                if retrieve.status == "completed":
                    return retrieve
                elif retrieve.status == "failed" or retrieve.status == "expired":
                    dprint(f"Run {run_id} failed.")
                    return None
                time.sleep(5)
            except Exception as e:
                dprint(f"Error retrieving run {run_id} for thread {thread_id}: {e}")
                retries += 1
                time.sleep(5)  # Wait before retrying
        dprint(f"Run {run_id} did not complete after {self.max_retries} retries.")
        return None
