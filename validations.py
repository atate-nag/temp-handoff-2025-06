from debug import dprint
from agent_context import AgentContext
from agent_configs import AgentConfigs
from abc import ABC, abstractmethod

class BaseValidation(ABC):
    def __init__(self, agent, **kwargs):
        self.agent = agent
        self.params = kwargs  # Store additional parameters as a dictionary

    @abstractmethod
    def validate(self):
        """Implement validation logic that can use self.params"""
        pass

class ZerotoInitialValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent
        self.agent_key = kwargs.get('agent_key')
        self.client = kwargs.get('client')
        self.file_handler = kwargs.get('file_handler')
        self.agent_type = kwargs.get('agent_type')
        self.qm = kwargs.get('qm')

    def validate(self):
        # Example: Access a parameter named 'threshold'
        dprint("in validate for ZerotoInitial")
        agent_config = AgentConfigs().get_agent_details(self.agent_type)
        try:
            context = AgentContext(
                client=self.client,
                file_handler=self.file_handler,
                agent_type=self.agent_type,
                qm=self.qm,
                id=agent_config['id'],
                description=agent_config['description'],
                prompt=agent_config['prompt'],
                reqs_schema=agent_config.get('output_schema', None),
                qm_reqs_schema=self.params.get('requirements')
            )
            dprint(f"Validated ZerotoInitialState")
            return True
        except Exception as e:
            dprint(f"Failed Validation of InitialState")
            return False

class InitialtoLoadedValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent

    def validate(self):
        return True

class LoadedtoRunningValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent

    def validate(self):
        return True


class RunningtoReturnedValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent

    def validate(self):
        return True


class ReturnedtoCompleteValidation(BaseValidation):
    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent

    def validate(self):
        return True
