from decomp_task.base import BaseTaskDecomp, BaseAgents, BaseCondition, get_embeddings
from decomp_task.writing.task import WritingTask
import json
from typing import List, Dict
from decomp_task.writing.sections import section_dict
from sklearn.metrics.pairwise import cosine_similarity

class WritingTaskDecomp(BaseTaskDecomp):
    def __init__(self, company:str, iterative:int=False, **other_args )->None:        
        super().__init__(**other_args)
        self.company = company
        self.iterative_toggle = iterative
        
    def iterative(self, task):
        return self.iterative_toggle > 0
    
    def _generate_message(self, task:WritingTask)->str:
        message = f"""{task.task_details_str(indent=1)}"""  
       
        return message
    
    def decompose(self, message, task:WritingTask)->None:
        if not self.iterative(task):
            self._planning_decomp_single(message, task)
        else:
            self._planning_decomp_iter(message, task)
        
    def _planning_decomp_single(self, message, task:WritingTask)->None:
        message = f"Decompose parent section:\n{message}"
        agent_config, schema = create_decomposer()
        planing_results = BaseAgents(
            llm_config=self.setup_config["llm_config"],
            silent= self.setup_config["silent"],
            is_termination_msg=self.setup_config["is_termination_msg"],
            user_system_prompt=self.setup_config["user"],
            agents_config=[agent_config]
        ).convo_with_structure(agent_name=agent_config["name"], message=message, structure_schema=schema)["sections"]
        
        # planing_results = [ self._add_embeddings(res) for res in planing_results ]
        # for i in range( 1 , len(planing_results) ):
        #     others = [ x for j,x in enumerate(planing_results) if j != i ]
        #     self._validate_result(task, others, planing_results[i])

        current = task
        for i,next_section_content in enumerate(planing_results):           
            overriding_args = {
                "name" : next_section_content["section_title"],
                "description" : next_section_content["summary_section_content"],
                "objectives" : [ f"A sub-section, titled '{next_section_content['section_title']}', of the parent section, titled '{task.name}'." ],
                "constraints" : next_section_content["detailed_section_content"]                
            }            
            current = current.create_task(overriding_args, parent_or_previous= True if i == 0 else False )
            # current.constraint_embeddings = next_section_content["constraint_embeddings"]

    # def _validate_result(self, parent_task:WritingTask, sibling_tasks:List[WritingTask|Dict], current_task:WritingTask|Dict, threshold=0.9)->None:
    #     sibling_tasks_emb = [ task["constraint_embeddings"]  if type(task) == dict else task.constraint_embeddings for task in sibling_tasks ]
    #     current_task_emb = current_task["constraint_embeddings"]  if type(current_task) == dict else current_task.constraint_embeddings
        
    #     """Similarity with parent task"""
    #     parent_sim = cosine_similarity(parent_task.constraint_embeddings, current_task_emb )
    #      # each constraint of the child task must 0.8 similar to at least one of the parent constraints
    #     for i in range(parent_sim.shape[1]):
    #         max_sim = parent_sim[:,i].max()
    #         # min_sim = parent_sim[:,i].min()
    #         if max_sim > 0.8: # too similar
    #             pass
    #         elif max_sim < 0.3: # Too dissimilar
    #             pass
    #         else: # Just Nice
    #             pass
                        
    #     """Similarity with sibling task"""
    #     for i,task_emb in enumerate(sibling_tasks_emb):
    #         distance = cosine_similarity( task_emb, current_task_emb )
    #         sort_distance = distance.copy().reshape((-1,))
    #         sort_distance.sort()
    #         assert distance.max() == sort_distance[-1], "Sorting didnt work"
    #         if distance.max() >= threshold and sort_distance[-2] >= threshold:
    #             # raise Exception("Current Task too similar to other task")
    #             pass
                
                

    def _planning_decomp_iter(self, message, task:WritingTask)->None:     
        while not self._is_done(message, task):
            self._get_next_step(message, task)  

    def _get_next_step(self, message, task:WritingTask )->None:
        next_section_content = self._get_section_content(message, task)
        # self._validate_result(task, task._get_child_tasks(), next_section_content)
        parent_or_previous =  False if task.child_task else True        
        overriding_args = {
            "name" : next_section_content["section_title"],
            "description" : next_section_content["summary_section_content"],
            "objectives" : [ f"A sub-section, titled '{next_section_content['section_title']}', of the parent section, titled '{task.name}'." ],
            "constraints" : next_section_content["detailed_section_content"]
        }
        
        if parent_or_previous:            
            new_task = task.create_task(overriding_args, parent_or_previous=parent_or_previous)
        else:
            new_task = task._get_child_tasks()[-1].create_task(overriding_args, parent_or_previous=parent_or_previous)
        
        # new_task.constraint_embeddings = next_section_content["constraint_embeddings"]
    
    def _is_done(self, message, task:WritingTask )->bool:
        current_sequence = task._get_child_tasks()
                
        # Is long enough        
        if len(current_sequence) <= 1:
            return False
        elif len(current_sequence) > 10:
            return True
        
        # Determine if we are done        
        system_prompt, schema = create_is_done_agent()          
        prompt= "\Created sub-section are: \n" +  task.child_task.workflow(as_string=True) + "\n\nParent Section: \n" + message
        reply = BaseAgents(
                    llm_config=self.setup_config["llm_config"],
                    silent= self.setup_config["silent"],
                    is_termination_msg=self.setup_config["is_termination_msg"],
                    user_system_prompt=system_prompt
        ).single_with_structure(prompt, schema)
        
        return reply["additional_sub_section"].lower() == "no"
    
    def _get_section_content(self, message, task:WritingTask )->Dict:
        message =   f"Create sub-section for parent section:\n{message}\n\n"
        
        if task.child_task:
            message = f"{message}Complement current created sections: \n{task.child_task.workflow(as_string=True)}"
            message = F"{message}\n\nAvoid overlap with previous section:\n{task._get_child_tasks()[-1].task_details_str(indent=1)} "
        
        agent_config, schema = create_iter_step_decomposer()
        results = BaseAgents(
            llm_config=self.setup_config["llm_config"],
            silent= self.setup_config["silent"],
            is_termination_msg=self.setup_config["is_termination_msg"],
            user_system_prompt=self.setup_config["user"],
            agents_config=[agent_config]
        ).convo_with_structure(agent_name=agent_config["name"], message=message, structure_schema=schema)
        # results = self._add_embeddings(results)
        return results
    
    # def _add_embeddings(self, results)->Dict:
    #     results["constraint_embeddings"] = get_embeddings(results["detailed_section_content"])
    #     return results

class WritingCondition(BaseCondition):
    def __init__(self, **other_args)->None:
        super().__init__(user_system_prompt= \
                        'You are a helpful assistant. Your role is to determine if a section should be decomposed into sub-sections.' + \
                        'You will be given information about the section which includes the expected content of the section.' +\
                        'You will be given information about the report and current report structure/outline.' +\
                        'A section should be decomposed into sub-sections only if its content require further clarification given the report structure and topic.' + \
                        'Only reply in the following format: { "decompose" : "yes or no" , "reasoning" : ""  }. Dont forget the triple back ticks' , **other_args )

    def _generate_message(self, task)->str:
        message = \
        f"Section information\n{task.task_details_str(indent=1)}" + \
        "\n\nReport information\n" + \
        f"    Report Summary: '{task.root_task.description}'\n" #+ \
        # f"    Report Workflow:\n{self.root_task.workflow()}"
        #
        return message

###############################################################

def get_schema( add_section_type=False, ret_section=True ):
    base_schema = {"$schema": "http://json-schema.org/draft-07/schema#"}
    schema = {
        "type": "object",
        "properties": {
            "num": {    "type": "integer"   },
            "detailed_section_content": {  
                "type": "array",
                "items" : {  "type": "string"     },
                "description" : " a list of at most six sentences representing expected content or topics that need to be discuss in the section or sub-section."
            },
            "summary_section_content": {  
                "type": "string",
                "description" : "a summary of the expected content of the sub-section to 1-2 sentence"      
            },
            "section_title": {  
                "type": "string",
                "description" : "a title for the sub-section that reflects the expected content"        
            },
            "section_content_reasoning": {  
                "type": "string",
                "description" : "clear reasoning how the step is connected to the report and other sub-sections"        
            },
        },
        "required": [
            "num",
            "detailed_section_content",
            "summary_section_content",
            "section_title",
            "section_content_reasoning"
            
        ],
        "additionalProperties": False
    }
    
    structure = {
        "num": 1,
        "detailed_section_content": [ "" ],
        "summary_section_content" : "",
        "section_title" : "",
        "section_content_reasoning": ""
    }

    if add_section_type:
        structure = {"section_type" : ""} | structure
        st_description = "The most appropriate type from the available section types for the sub-section." + \
                " Appropriate is based on the position of the sub-section as well as preceding sub-sections."

        schema["properties"] = { 
            "section_type" : {
                "type": "string",
                "description" : st_description,
                "enum" : list(section_dict)
            } 
        } | schema["properties"]
        schema["required"] = ["section_type"] + schema["required"]
        schema["properties"]["detailed_section_content"]["description"] = \
            "using the section type definition and parent section expected content " + schema["properties"]["detailed_section_content"]["description"]
        schema["properties"]["section_title"]["description"] = schema["properties"]["section_title"]["description"] + \
            ", don't use the type definition in the title"

    desc = {   key:value["description"] for key,value in schema["properties"].items() if key != "num"}

    if not ret_section:
        schema = {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": schema
                }
            },
            "required": [
                "sections"
            ],
            "additionalProperties": False
        }

        structure = {
            "sections" : [
                structure
            ]
        }
    
    return structure, base_schema|schema, desc

def create_decomposer():
    structure, schema, desc = get_schema(add_section_type=False, ret_section=False)
    desc = [ f"       {i+1}) {k}: {v}" for i,(k,v) in enumerate(desc.items()) ]
    base = \
        'You are a helpful assistant. Your task is to decompose the parent section into sub-sections based on criteria below.\n\n' + \
        'The decomposition must adhere to the following criteria:\n' + \
        "    - The sub-sections should related to each other and together form the parent section of the report.\n" + \
        "    - There is no need for any sections that are introduction or conclusions. Go straight to the addressing the topic.\n" + \
        "    - There should be at most 4 sub-sections.\n" + \
        "    - Each decomposed step should contain:\n" + \
        "\n".join(desc)
        
    end = \
        f"\nLastly convert the instructions into a JSON object as shown below:\n" + \
        json.dumps(structure, indent=4 ) + \
        """Add as many steps as needed. Replace the placeholders with relevant information from the JSON input. Show all your reasoning throughout the process."""
    summary = """Extract the output json plan from the conversation above. Only return the json, dont say anything else."""

    return {"name": "decomp", "system_message" : base+end, "summary_method" : "reflection_with_llm", "summary_args":  { "summary_prompt": summary } } , schema # 

def create_iter_step_decomposer():
    structure, schema, desc = get_schema(add_section_type=False, ret_section=True)
    desc =  "\n".join([ f"   {i+1}) {k}: {v}" for i,(k,v) in enumerate(desc.items()) if k != "section_type"])
    system_message = \
        'You are a helpful assistant, decomposing parent section into sub-sections.\n\n' + \
        'Your task is to create one sub-section based on the following criteria' + \
        "    - The sub-section must complement the created sub-sections, must not overlap with previous section, and must related to the parent section. \n" + \
        "    - There is no need for any sub-section that are introduction or conclusions. Go straight to the addressing the topic.\n" + \
        "    - Each sub-section must contain:\n" + \
        "\n".join(desc)   
    
    summary_prompt = f"""From the conversation above, extract the information to fill up the json structure.\n{json.dumps(structure,indent=4)}.\nDont forget the triple back tick."""
    
    return {"name": "iter_decomp", "system_message" : system_message, "summary_method" : "reflection_with_llm",  "summary_args":  { "summary_prompt": summary_prompt } }, schema

def create_is_done_agent():
    system_prompt = \
            "You are part of a process that decomposes a parent section into sub-sections." + \
            "You will be given a list of created sub-sections and parent section, and will need to determine if additional sub-sections are needed." + \
            "Additional sub-section are needed if the expected content constraints of the parent section are all met by the created sub-sections." + \
            """Provide your reasoning and decision in the following json structure format: { "reasoning" : "" , "additional_sub_section" : "yes or no" }. Dont forget the triple back tick."""
    
    schema = \
    {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {            
            "reasoning": {
            "type": "string",
            },
            "additional_sub_section": {
            "type": "string",
            "enum": ["yes", "no", "Yes", "No"]
            }
        },
        "required": [            
            "reasoning", "additional_sub_section"
        ]
    }
    return system_prompt, schema