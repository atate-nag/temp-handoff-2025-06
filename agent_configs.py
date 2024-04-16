import json

class AgentConfigs:
    _instance = None
    _configs = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentConfigs, cls).__new__(cls)
            cls._instance.init_config()
        return cls._instance

    def init_config(self):
        if AgentConfigs._configs is None:
            AgentConfigs._configs = self.load_config("known_agents.json")

    def load_config(self, config_path):
        with open(config_path, 'r') as file:
            return json.load(file)

    def get_config(self, key):
        return AgentConfigs._configs.get(key)

    def get_agent_details(self, agent_type):
        """Retrieve detailed configuration for a specific agent type."""
        known_agents = self._get_known_agents()
        if agent_type not in known_agents:
            raise ValueError(f"Agent type {agent_type} is not valid. Must be one of {list(known_agents.keys())}.")
        return known_agents[agent_type]

    @staticmethod
    def validate_agent_type(agent_type: str):
        known_agents = AgentConfigs()._get_known_agents()
        if agent_type not in known_agents:
            raise ValueError(f"agent_type {agent_type} is not valid. Must be one of {list(known_agents.keys())}")
        return agent_type

    def _get_known_agents(self):
        return self.get_config('known_agents')

