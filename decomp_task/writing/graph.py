from decomp_task.base import BaseAgents, GraphExtractor, get_embeddings
from typing import Dict, List, Any, Iterable
from langchain_community.graphs import Neo4jGraph
from openai import OpenAI
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor


class TaskGraph:
    def __init__(self, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE):

        # self.OPENAI_API_KEY = OPENAI_API_KEY
        # self.OPENAI_ENDPOINT = OPENAI_ENDPOINT

        self.kg = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
        )
        self.db = NEO4J_DATABASE
        self.indexes = {}
        # self.client = OpenAI(api_key=OPENAI_API_KEY)

        self.merge_document_query = """
            MERGE(sec:Document {name: $DocParams.name})
                ON CREATE SET                    
                    sec.name = $DocParams.name,
                    sec.summary = $DocParams.summary,
                    sec.embeddings = $DocParams.embeddings
            RETURN sec
            """

    def clear_database(self):
        self.kg.query("match () -[r] -> () delete r")
        self.kg.query("match (a) delete a")

    def add_task(self, task, keys):
        attributes = ",\n".join(
            [f"                    task.{key} = $taskParams.{key}" for key in keys]
        )
        task_params = task._to_structure(["task_id", "root_task_id"] + keys)
        merge_task = f"""
            MERGE(task:Task {{task_id: $taskParams.task_id, root_task_id: $taskParams.root_task_id}})
                ON CREATE SET 
                    {attributes}
            RETURN task
            """
        ret = self.kg.query(merge_task, params={"taskParams": task_params})
        print(ret)

    def update_task(self, task, update_keys):
        update_keys = list(set(["task_id", "root_task_id"] + update_keys))

        if type(task) == dict:
            task_params = {k: task[k] for k in update_keys}
        else:
            task_params = task._to_structure(update_keys)

        attributes = ",\n".join(
            [
                f"                    task.{key} = $taskParams.{key}"
                for key in update_keys
                if key not in ["task_id", "root_task_id"]
            ]
        )
        update_task = f"""
            MATCH(task:Task {{task_id: $taskParams.task_id, root_task_id: $taskParams.root_task_id}})
                SET 
                    {attributes}
            RETURN task
            """
        ret = self.kg.query(update_task, params={"taskParams": task_params})
        print(ret)

    def link_sibling_tasks(self, previous_task, next_task):
        assert previous_task is not next_task
        previous_params = previous_task._to_structure(["task_id", "root_task_id"])
        next_params = next_task._to_structure(["task_id", "root_task_id"])
        assert previous_params["root_task_id"] == next_params["root_task_id"]
        ret = self.kg.query(
            """
            MATCH (previous:Task {task_id: $previousParams.task_id, root_task_id: $previousParams.root_task_id})           
            MATCH (next:Task  {task_id: $nextParams.task_id, root_task_id: $nextParams.root_task_id})
            MERGE (previous)-[rel:Sibling]->(next)
                ON CREATE SET 
                    rel.previous_task_id = $previousParams.task_id,
                    rel.next_task_id = $nextParams.task_id,
                    rel.root_task_id =$nextParams.root_task_id
                        
            """,
            params={"previousParams": previous_params, "nextParams": next_params},
        )
        print(ret)

    def link_child_tasks(self, parent_task, child_task):
        assert parent_task is not child_task
        parent_params = parent_task._to_structure(["task_id", "root_task_id"])
        child_params = child_task._to_structure(["task_id", "root_task_id"])
        assert parent_params["root_task_id"] == child_params["root_task_id"]
        ret = self.kg.query(
            """
            MATCH (parent:Task {task_id: $parentParams.task_id, root_task_id: $parentParams.root_task_id})           
            MATCH (child:Task  {task_id: $childParams.task_id, root_task_id: $childParams.root_task_id})
            MERGE (parent)-[rel:Parent]->(child)
                ON CREATE SET 
                    rel.parent_task_id = $parentParams.task_id,
                    rel.child_task_id = $childParams.task_id,
                    rel.root_task_id =$parentParams.root_task_id
            """,
            params={"parentParams": parent_params, "childParams": child_params},
        )
        print(ret)

    def get_graph(self, root_task_id):
        sibling_edges = self.kg.query(
            f"""
            MATCH (a:Task {{root_task_id: "{root_task_id}" }})-[b:Sibling {{root_task_id: "{root_task_id}"}} ]-(c:Task {{root_task_id: "{root_task_id}" }})
            RETURN DISTINCT a,b,c
            """
        )
        sibling_edges = [edge["b"] for edge in sibling_edges]

        parent_edges = self.kg.query(
            f"""
            MATCH (a:Task {{root_task_id: "{root_task_id}" }})-[b:Parent {{root_task_id: "{root_task_id}"}} ]-(c:Task {{root_task_id: "{root_task_id}" }})
            RETURN DISTINCT a,b,c
            """
        )
        parent_edges = [edge["b"] for edge in parent_edges]
        nodes = self.kg.query(
            f"""
            MATCH (a:Task {{root_task_id: "{root_task_id}" }})
            RETURN DISTINCT a
            """
        )
        nodes = [node["a"] for node in nodes]
        return nodes, parent_edges, sibling_edges

    def delete_graph(self, root_task_id):
        self.kg.query(
            f"""
            MATCH (a:Task {{root_task_id: "{root_task_id}" }})-[b:Sibling {{root_task_id: "{root_task_id}"}} ]-(c:Task {{root_task_id: "{root_task_id}" }})
            DELETE b
            """
        )

        self.kg.query(
            f"""
            MATCH (a:Task {{root_task_id: "{root_task_id}" }})-[b:Parent {{root_task_id: "{root_task_id}"}} ]-(c:Task {{root_task_id: "{root_task_id}" }})
            DELETE b
            """
        )

        self.kg.query(
            f"""
            MATCH (a:Task {{root_task_id: "{root_task_id}" }})
            DELETE a
            """
        )
