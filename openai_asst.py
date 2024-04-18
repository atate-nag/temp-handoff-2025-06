from debug import dprint
class OpenAIAsst():
    def __init__(self,client,agent_id,prompt):
        self.client = client
        self.agent_id = agent_id
        self.prompt = prompt
        self.thread = None

    def generate_thread(self, data):
        prompt = self.prompt
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
        prompt = self.prompt
        for placeholder, value in placeholder_values.items():
            # Convert list to string if necessary
            if isinstance(value, list):
                value_str = ', '.join(map(str, value))  # Ensure all elements are converted to strings
            else:
                value_str = str(value)
            prompt = prompt.replace(f"{{{placeholder}}}", value_str)
        # self.prompt = prompt
        dprint(f"End self-prompt is {self.prompt}")
        return prompt