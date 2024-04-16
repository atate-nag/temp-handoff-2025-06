from abc import ABC, abstractmethod
from debug import dprint
from transitions import Machine
from abc import ABC, abstractmethod
from agent_context import AgentContext
from agent_configs import AgentConfigs
import logging

# Set up logging
from abc import ABC, abstractmethod

class BaseTransition(ABC):
    def __init__(self, agent, **kwargs):
        self.agent = agent
        self.params = kwargs  # Store additional parameters as a dictionary

    def run(self):
        self.generate()
        self.modify_state()
        self.trigger()
        return True

    @abstractmethod
    def generate(self):
        pass

    @abstractmethod
    def modify_state(self):
        pass

    @abstractmethod
    def trigger(self):
        self.agent.load()
        pass

class ZerotoInitialTransition(BaseTransition):

    def __init__(self, agent, **kwargs):
        super().__init__(agent)
        self.agent = agent
    def generate(self):
        dprint("Preparing S1 operations...")
        return True

    def modify_state(self):
        dprint("Executing S1 tasks...")
        return True

    def trigger(self):
        dprint("Cleaning up S1 and moving to S2")
        return True

class InitialtoLoadedTransition(BaseTransition):

    def generate(self):
        dprint("Preparing InitialtoLoadedTransition operations...")
        return True

    def modify_state(self):
        dprint("Executing InitialtoLoadedTransition tasks...")
        return True

    def trigger(self):
        dprint("Cleaning up InitialtoLoadedTransition...")


class LoadedtoRunningTransition(BaseTransition):

    def generate(self):
        dprint("Preparing LoadedtoRunningTransition operations...")

        return True

    def modify_state(self):
        dprint("Executing LoadedtoRunningTransition tasks...")
        return True

    def trigger(self):
        dprint("Cleaning up LoadedtoRunningTransition...")
        return True

class RunningtoReturnedTransition(BaseTransition):

    def generate(self):
        dprint("Preparing RunningtoReturnedTransition operations...")

        return True

    def modify_state(self):
        dprint("Executing RunningtoReturnedTransition tasks...")
        return True

    def trigger(self):
        dprint("Cleaning up RunningtoReturnedTransition...")
        return True

class ReturnedtoCompleteTransition(BaseTransition):

    def generate(self):
        dprint("Preparing ReturnedtoCompleteTransition operations...")

        return True

    def modify_state(self):
        dprint("Executing ReturnedtoCompleteTransition tasks...")
        return True

    def trigger(self):
        dprint("Cleaning up ReturnedtoCompleteTransition...")
        return True