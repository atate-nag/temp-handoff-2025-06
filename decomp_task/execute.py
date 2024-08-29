import dotenv
dotenv.load_dotenv()
from decomp_task.writing import WritingTaskManager, ConstrainedWritingTask, ConstrainedWritingTaskDecomp, ConstrainedWritingCondition, WritingTaskExecuter, TaskGraph
import os
from typing import Tuple, Dict



def get_question(company):    
    contexts_questions = {        
        "Tesla": (
            "Scaling production efficiently amidst growing competition in the electric vehicle market is Tesla's challenge. Optimizing production capacity, reducing costs, and maintaining innovation leadership are key. The company's strategic focus centers on automation, battery technology, and global expansion. By fine-tuning its supply chain, investing in Gigafactories, and expanding charging infrastructure, Tesla can meet surging demand.",
            "How can Tesla balance rapid growth with quality control and sustainable practices, ensuring its electric vehicles remain at the forefront of the automotive industry?"
        ),
        # Amazon
        "Amazon" :(
            "Amazon's relentless expansion into new markets and services has positioned it as a retail behemoth. However, this growth brings challenges in sustainability and labor relations. As Amazon scales, it must balance efficiency with ethical practices, ensuring its vast workforce is supported and environmental impacts are minimized.", 
            "How can Amazon refine its growth strategy to enhance sustainability and worker welfare while maintaining its competitive edge?"
        ),
        # # ADM
        # ("ADM", "As a global leader in food processing and commodities trading, Archer Daniels Midland must navigate the complexities of international trade, fluctuating commodity prices, and sustainability concerns. With the world's food supply chain under pressure, ADM's strategic focus is crucial.", 
        # "How can Archer Daniels Midland ensure supply chain resilience and adapt to changing consumer preferences towards sustainable and ethical sourcing?" ),
    }

    return company, *contexts_questions[company]

def create_params(company:str, temperature:float , run_name:str , with_cache=True, with_execute= False)-> \
    Tuple[Dict, ConstrainedWritingTask, WritingTaskManager, TaskGraph, str]:
    
    llm_config={"config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}] , "temperature":temperature, "cache_seed" : 43 if with_cache else None }
    company, context, question = get_question(company)

    temp_str = str(temperature)
    temp_str = temp_str.replace(".", "-")

    NEO4J_URI = os.getenv("NEO4J_URL")
    NEO4J_USERNAME = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    NEO4J_DATABASE = "neo4j"

    file_name = f"{company}_run|{run_name}_temperature|{temp_str}"
    args = {
        "name":f"Strategy Report for {company}", 
        "description":f"Business Strategy report on the following strategy problem statement: '{question}'.",
        "objectives":[ f"A business strategy report that answers the strategy problem statement '{question}'."] ,
        "constraints":[ f"The report should discuss: '{context}' ", "main body must include strategy recommendation among other things"],
        "root_task":None,
        "id_str" : file_name
    }
   
    args = args|{"section_type":"main body"}
    root = ConstrainedWritingTask( **args)
    decomposer = ConstrainedWritingTaskDecomp(company=company, iterative=-1, llm_config=llm_config)
    condition = ConstrainedWritingCondition(llm_config=llm_config)

    executer = WritingTaskExecuter(company=company, llm_config=llm_config, database=NEO4J_DATABASE, uri=NEO4J_URI, password=NEO4J_PASSWORD, user=NEO4J_USERNAME) if with_execute else None

    task_manager = WritingTaskManager(
        root,
        task_decomposer=decomposer, 
        condition= condition, 
        executer= executer,
        threshold=2
    )
    
    task_graph = TaskGraph(
        NEO4J_URI = NEO4J_URI, 
        NEO4J_USERNAME = NEO4J_USERNAME, 
        NEO4J_PASSWORD = NEO4J_PASSWORD, 
        NEO4J_DATABASE = NEO4J_DATABASE
    )
    
    return args, root, task_manager, task_graph, file_name

def run_decomp(company, temperature=0.0, run_name="test", with_cache=False, with_execute=True, write_to_graph=True):
    
    args, root, task_manager, task_graph, file_name = \
        create_params(company, temperature, run_name, with_cache, with_execute)

    """Create Task Plan"""
    error_message = ""
    try:
        root.execution_output = task_manager.get_predicted_plan(lambda task : f"{task.name}:{task.id}")
        if with_execute:        
            task_manager.execute_tasks()
            task_manager.create_document(f"./Intermediates/{file_name}")
    except Exception as error:        
        error_message = f"Run failed for {file_name}, error raise is {error}."
   
    """Delete Graphs"""
    """Dump Task to Neo4j"""
    if write_to_graph:
        task_graph.delete_graph( root_task_id=str(root.id) )        
        keys = list(args)
        del keys[keys.index("root_task")]
        keys.append("execution_output")        
        task_manager.dump_to_neo4j(task_graph, keys)       
    
    if len(error_message) > 0 :
        output_message = error_message + " You may still be able to view the intermediate generated task (if chosen) at Neo4j using the query below"
    else:
        output_message = f"The {file_name} was successfully executed. Use the query below to view the intermediate outputs (if chosen)."
    query = f'\n\nMATCH (a:Task {{ root_task_id : "{str(root.id)}" }})-[b]-(c:Task {{ root_task_id : "{str(root.id)}" }}) RETURN a,b,c'

    return output_message + query           

if __name__ == "__main__":
    import dotenv
    import pathlib    
    dotenv.load_dotenv()

    print(run_decomp( "Amazon" , write_to_graph=True , with_cache=True, with_execute=True ))
   

        
