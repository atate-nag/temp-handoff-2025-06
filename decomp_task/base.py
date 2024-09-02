import json
from jsonschema import validate
import os
from autogen import ConversableAgent, UserProxyAgent
from typing import Any, Callable, Generic, TypeVar, Dict, List, TypedDict
from neo4j import GraphDatabase, Result
import subprocess
import uuid
import numpy as np
import requests


def create_json_extractor(llm_config):
    # executor = LocalCommandLineCodeExecutor(
    #     timeout=10,  # Timeout for each code execution in seconds.
    #     work_dir=work_dir,  # Use the temporary directory to store the code files.
    # )
    json_extractor = ConversableAgent(
        name="json_extractor",
        system_message="Your task is to extract the valid json structure from a given text.\n\
        You will also be given json schema that will validate the extracted json structure. The json structure should match the schema.\n\
        Only extract 1 json structure.\n \
        If the valid json is found return the json structure. Only return the valid json structure. \
        If a json structure is found but is invalid, try to convert the json structure into a valid one. Then return the json structure. Only return the final json structure. \n\
        If no json structure is found at all, then return 'NO JSON, MISSION ACCOMPLISH'. ",
        llm_config=llm_config,
        human_input_mode="NEVER",
    )
    return json_extractor


def create_user(llm_config, is_termination_msg, system_prompt=None):

    system_prompt = system_prompt if system_prompt else "Initiate the Convo"

    user = UserProxyAgent(
        name="user_proxy",
        llm_config=llm_config,
        system_message=system_prompt,
        human_input_mode="NEVER",
        code_execution_config=False,
        is_termination_msg=is_termination_msg,
    )
    return user


def create_agents(
    llm_config, agents_config, is_termination_msg, code_execution_config=False
):

    if type(agents_config) != list:
        raise TypeError("Only list allowed")

    assert len(set([x["name"] for x in agents_config])) == len(agents_config)

    for i, agent in enumerate(agents_config):
        agents_config[i]["agent"] = UserProxyAgent(
            name=agent["name"],
            llm_config=llm_config,
            system_message=agent["system_message"],
            human_input_mode=agent.get("human_input_mode", "NEVER"),
            code_execution_config=agent.get("code_execution_config", False),
            is_termination_msg=is_termination_msg,
        )

    return agents_config


class SetupCOnfig(TypedDict):
    llm_config: Dict
    is_termination_msg: Callable
    user: UserProxyAgent
    silent: bool


class BaseAgents:
    def __init__(
        self,
        llm_config={},  # {"config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}] , "temperature":0.0, "cache_seed":None },
        is_termination_msg=None,
        silent=False,
        user_system_prompt=None,
        agents_config=[],  # required [{name: "", system_message: ""}]
    ):
        is_termination_msg = (
            is_termination_msg
            if is_termination_msg
            else self.termination_condition_autogen
        )
        if type(user_system_prompt) == UserProxyAgent:
            user = user_system_prompt
        else:
            user = create_user(
                llm_config=llm_config,
                is_termination_msg=is_termination_msg,
                system_prompt=user_system_prompt,
            )
        self.setup_config: SetupCOnfig = {
            "llm_config": llm_config,
            "is_termination_msg": is_termination_msg,
            "user": user,
            "silent": silent,
        }
        if len(agents_config) or agents_config is not None:
            self.agents_config = create_agents(
                llm_config=llm_config,
                is_termination_msg=is_termination_msg,
                agents_config=agents_config,
            )

    def termination_condition_autogen(self, msg):
        return msg.get("content", None) and "MISSION ACCOMPLISH" in msg["content"]

    def extract_json(self, message, schema):

        def extractor(text: str, schema: str | dict):
            try:
                if "NO JSON, MISSION ACCOMPLISH" in text:
                    return {}
                elif "```" in text:
                    text = text[text.find("```") : text.rindex("```")]

                text = text[text.find("{") : text.rindex("}") + 1]
                text = text.replace("\n", "")
                output = json.loads(text)
                schema = json.loads(schema) if type(schema) == str else schema
                validate(instance=output, schema=schema)
                return output
            except Exception as error:
                return error

        output = extractor(message, schema)

        if not (type(output) == Exception or issubclass(type(output), Exception)):
            return output

        llm_config = {
            "config_list": [
                {"model": "gpt-3.5-turbo-0125", "api_key": os.environ["OPENAI_API_KEY"]}
            ],
            "temperature": 0,
        }
        extraction_message = f"""Here is schema of the json structure that needs to be extracted\n{schema}\nHere is the message:\n"{message}" """
        arg_message = {
            "recipient": create_json_extractor(llm_config),
            "message": extraction_message,
            "silent": self.setup_config["silent"],
            "summary_method": "last_msg",
            "max_turns": 1,
        }

        chat_result = self.setup_config["user"].initiate_chat(**arg_message)
        chat_result = chat_result.summary
        output = extractor(chat_result, schema)

        if type(output) == Exception or issubclass(type(output), Exception):
            raise output

        return output

    def convo_with_structure(self, agent_name, message, structure_schema=None):
        agent = [agent for agent in self.agents_config if agent["name"] == agent_name][
            0
        ]

        chat_message = {
            "recipient": agent["agent"],
            "message": message,
            "silent": self.setup_config["silent"],
            "summary_method": agent.get("summary_method", "reflection_with_llm"),
            "max_turns": agent.get("max_turns", 1),
        }

        if (
            chat_message["summary_method"] == "reflection_with_llm"
            and "summary_args" in agent
        ):
            chat_message = chat_message | {
                "summary_args": agent["summary_args"]
            }  # { "summary_prompt": summary_prompt }

        results = self.setup_config["user"].initiate_chat(**chat_message)

        if chat_message["summary_method"] == "reflection_with_llm":
            results = results.summary
        elif chat_message["summary_method"] == "last_msg":
            results = results.chat_history[-1]
        else:
            return results

        if structure_schema:
            results = self.extract_json(results, structure_schema)

        return results

    def single_with_structure(self, message, structure_schema=None):
        reply = self.setup_config["user"].generate_reply(
            messages=[{"role": "user", "content": message}]
        )
        # if not self.setup_config["silent"]:
        #     print("User Message:\n", message)
        #     print("Reply:\n", reply)
        if structure_schema:
            reply = self.extract_json(reply, structure_schema)

        return reply

    @classmethod
    def single_query(cls, system_prompt, message, structure_schema=None, **class_args):
        instance = cls(user_system_prompt=system_prompt, **class_args)
        reply = instance.single_with_structure(message, structure_schema)
        return reply


class BaseTask:
    def __init__(
        self,
        name: str,
        description: str,
        objectives: list,
        constraints: list,
        root_task: Any,
        id_str: str = None,
    ) -> None:
        self.name = name
        self.description = description
        self.objectives = objectives
        self.constraints = constraints
        self.root_task = root_task
        self.is_decompose = (
            None
            if root_task
            else {"decompose": True, "reasoning": "Root must always be decomposed"}
        )
        self.execution_output = []
        self.id_str = id_str

    @property
    def id(self):
        return uuid.uuid5(
            uuid.NAMESPACE_OID,
            str(type(self)) + (self.id_str if self.id_str else self.name),
        )

    def _to_structure(self, keys: List[str]):
        keys = list(set(keys))
        id = root = False
        if "task_id" in keys:
            del keys[keys.index("task_id")]
            id = True
        if "root_task_id" in keys:
            del keys[keys.index("root_task_id")]
            root = True
        update = {}
        for key in keys:
            value = getattr(self, key)
            if type(value) == list and len(value) and type(value[0] == str):
                value = "|||".join(value)
            elif type(value) == dict:
                value = "|||".join([f"Key:{k},Value:{v}" for k, v in value.items()])
            elif type(value) == np.ndarray:
                value = [value.shape[0]] + value.reshape(-1).tolist()
            elif key == "execution_output":
                value = value[0] if len(value) > 0 else ""
            elif value and type(value) != str:
                raise Exception(key, " is not list, str or dict")

            update[key] = value

        if id:
            update = update | {"task_id": str(self.id)}
        if root:
            if self.root_task is not None:
                update = update | {"root_task_id": str(self.root_task.id)}
            else:
                update = update | {"root_task_id": str(self.id)}

        return update

    def workflow(self) -> Any:
        # returns the workflow, forwards or backwards, depends on the task manager
        raise NotImplementedError

    def _link_subtasks(self, output: Any) -> None:
        # this is to convert LLM output (json structure) subtasks to Task instance and link to current task
        raise NotImplementedError

    def decompose_message(self) -> str:
        raise NotImplementedError

    def _to_string(self) -> str:
        return f"{self.name}: {self.description}"

    def decompose_condition(self, condition_agent) -> None:
        self.is_decompose = condition_agent(self)

    def decompose(self, task_decomposer, condition_agent) -> None:
        if self.is_decompose is None:
            self.decompose_condition(condition_agent)

        if not self.is_decompose["decompose"]:
            return None  # Stop Process
        elif self.is_decompose is None:
            raise Exception("Error in the decompose condition output")

        task_decomposer(self)

    def execute(self, executer) -> None:
        self.execution_output = executer(self)


GenericTask = TypeVar("GenericTask", bound=BaseTask)


class BaseCondition(BaseAgents, Generic[GenericTask]):
    def __init__(self, user_system_prompt: str | None, **other_args: Dict) -> None:
        if user_system_prompt is None:
            user_system_prompt = (
                "You are a helpful assistant. Your role is to determine if task should be decomposed into sub-task."
                + 'Only reply in the following format: { "decompose" : "yes or no" , "reasoning" : ""  }. Dont forget the triple back ticks'
            )

        super().__init__(user_system_prompt=user_system_prompt, **other_args)

        self.schema = {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "type": "object",
            "properties": {
                "decompose": {"type": "string", "enum": ["yes", "no", "Yes", "No"]},
                "reasoning": {"type": "string"},
            },
            "required": ["decompose", "reasoning"],
            "additionalProperties": False,
        }

    def _generate_message(self, task: GenericTask) -> str:
        message = "Task\n" + task._to_string()
        return message

    def __call__(self, task: GenericTask) -> Dict:
        message = self._generate_message(task)

        reply = self.setup_config["user"].generate_reply(
            messages=[{"role": "user", "content": message}]
        )
        reply = self.extract_json(reply, self.schema)
        return reply


GenericCondition = TypeVar("GenericCondition", bound=BaseCondition)


class BaseTaskDecomp(BaseAgents, Generic[GenericTask]):
    def __init__(self, **other_args: Dict) -> None:
        super().__init__(**other_args)

    def _generate_message(self, task: GenericTask) -> str:
        raise NotImplementedError

    def decompose(self, message: str) -> Any:
        raise NotImplementedError

    def __call__(self, task: GenericTask) -> None:
        message = self._generate_message(task)
        return self.decompose(message, task)


GenericTaskDecomp = TypeVar("GenericTaskDecomp", bound=BaseTaskDecomp)


class BaseTaskExecuter(BaseAgents, Generic[GenericTask]):
    def __init__(self, **other_args: Dict) -> None:
        super().__init__(**other_args)
        self.execution_output = None

    def _generate_message(self, task: GenericTask) -> str:
        raise NotImplementedError

    def execute(self, message: str, task: GenericTask) -> str:
        raise NotImplementedError

    def __call__(self, task: GenericTask) -> Any:
        message = self._generate_message(task)
        return self.execute(message, task)


GenericTaskExecuter = TypeVar("GenericTaskExecuter", bound=BaseTaskExecuter)


class BaseTaskManager(
    Generic[GenericTask, GenericCondition, GenericTaskDecomp, GenericTaskExecuter]
):
    def __init__(
        self,
        root_task: GenericTask,
        task_decomposer: GenericTaskDecomp,
        condition: GenericCondition,
        executer: GenericTaskExecuter,
        threshold: int = 2,
        **other_args: Dict,
    ) -> None:
        self.threshold = threshold
        self.root_task: GenericTask = root_task
        self.task_decomposer = task_decomposer
        self.condition = condition
        self.executer = executer
        super().__init__(**other_args)

    def get_predicted_plan(self) -> Any:
        raise NotImplementedError

    def execution(self) -> Any:
        raise NotImplementedError


GenericTaskManager = TypeVar("GenericTaskManager", bound=BaseTaskManager)


class GraphExtractor:
    def __init__(self, database: str = "messy") -> None:  # "full0624"
        host_ip = subprocess.run(
            "ip route show | grep -i default | awk '{ print $3}'",
            shell=True,
            stdout=subprocess.PIPE,
        )
        host_ip = host_ip.stdout.strip().decode("UTF-8")
        uri = f"neo4j://{host_ip}:7687"  # "neo4j://172.28.112.1:7687"
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def run(self, query: str) -> Result:
        result = self.driver.execute_query(
            query,
            database_=self.database,
        )
        return result


def get_embeddings(sentences) -> np.ndarray:
    # Sending a GET request to the FastAPI app
    # url = "http://127.0.0.1:80/query/"
    url = "http://0.0.0.0:80/query/"
    response = requests.get(url, params={"sentences": sentences})
    # Checking if the request was successful
    if response.status_code == 200:
        # Parsing the JSON response
        embeddings = response.json().get("embeddings")
        return np.array(embeddings)
    else:
        raise Exception
