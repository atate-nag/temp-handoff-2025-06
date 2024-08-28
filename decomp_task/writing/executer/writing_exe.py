from decomp_task.base import BaseAgents, BaseTaskExecuter, GraphExtractor
from decomp_task.writing.task import WritingTask
from typing import List
from neo4j import GraphDatabase,Result
from openai import OpenAI
import os
import numpy as np
from sklearn.metrics.pairwise import cosine_distances, cosine_similarity

class Condenser(BaseAgents):
    def __init__(self, **other_args):
        super().__init__(
            user_system_prompt= \
                'Your task is write 1 to 2 paragraph summary on [Topic], using the provided text chucks. ' + \
                'You can only use the provided text chunks to write the paragraphs. ', **other_args
        )

    def get_chunks(self, topic, raw_output:List, filtered_output:List):            
        for i,fo in enumerate(filtered_output):
            inter = {}
            inter["text_chunk_num"] = raw_output.index(fo)
            inter["original_text"] = fo
            filtered_output[i] = inter  

        inputs_str = self.array_to_string(filtered_output)

        return inputs_str

    def array_to_string(self, array_in:List)-> str:
        output_str = []
        for chunk in array_in:
            output_str.append(f"*******Text Chunk: {chunk['text_chunk_num']}*******")
            [ output_str.append( "    " + f"{line}" ) for line in chunk[ "original_text" ].splitlines() ]
            output_str.append("\n\n\n")
        return  "\n".join(output_str)

class GraphExtractorOnline(GraphExtractor):
    def __init__(self, database: str = "neo4j") -> None: #"full0624"
        
        uri = f"neo4j+s://a27a90ed.databases.neo4j.io" # "neo4j://172.28.112.1:7687"
        user = "neo4j"
        password = "E_ASaLIxAM8obpa10K-DhQU92W3wkm2awSbME-oZ6BE"

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def run(self, query: str) -> Result:
        result = self.driver.execute_query(
            query,
            database_=self.database,
        )
        return result

class IndustryExtractorOnline(BaseAgents):
    def __init__(self, gics_code:str, graph_extractor:GraphExtractorOnline, **other_args):
        super().__init__(**other_args)
        self.gics_code = gics_code
        self.ge = graph_extractor
        self.extract_raw_trends()

    def extract_raw_trends(self):
        query = f"""
        MATCH (n:Trend{{gics_code:"{self.gics_code}"}}) RETURN DISTINCT n
        """ 
        #WITH [ n IN nodes WHERE (n: Chunk) ] as nodes
        records, summary, keys = self.ge.run(query)

        trends = [ (rec[keys[0]]["Description"], np.array(rec[keys[0]]["DescriptionEmbedding"])) for rec in records ]

        self.raw_trends = trends
    
    def filter_trends(self, topic:str, threshold:float = 0.8):
        topic_embedding = self.get_embedding(topic)
        trends_embeddings = np.stack( [ r[1] for r in self.raw_trends ] , axis= 0 )
        sim = cosine_similarity( trends_embeddings, topic_embedding )
        sim = sim.reshape( (len(self.raw_trends)) )
        sim = (sim > 0.9).tolist()
        assert len(sim) == len(self.raw_trends)
        filtered_trends = [ r[0] for r,cond in zip(self.raw_trends, sim) if cond ]

        return filtered_trends
    
    def get_embedding(self, topic:str):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return np.array(client.embeddings.create(model="text-embedding-ada-002", input=topic).data[0].embedding).reshape((1,-1))

class CompanyExtractorOnline(BaseAgents):
    def __init__(self, company:str, graph_extractor:GraphExtractorOnline, **other_args):        
        super().__init__(**other_args)
        self.ge = graph_extractor
        self.company = company
        self.extract_raw_insights()
        # self._add_embeddings()

    def extract_raw_insights(self):
        query = f"""
        MATCH (c:Company {{name: "{self.company}"}})
        CALL apoc.path.subgraphAll(c, {{minLevel: 0, maxLevel: 10}})
        YIELD nodes, relationships
        WITH [ n IN nodes WHERE (n: Insight) ] as nodes
        UNWIND nodes as x
        RETURN DISTINCT x
        """ 
        #WITH [ n IN nodes WHERE (n: Chunk) ] as nodes
        records, summary, keys = self.ge.run(query)
        insights = [ (rec[keys[0]]["description"], np.array(rec[keys[0]].get("descriptionEmbedding", [])), 
                      rec[keys[0]]["insightId"] , rec[keys[0]]["source"] ) for rec in records ]

        self.raw_insights = insights
        
    
    def filter_insights(self, topic:str, threshold:float = 0.8):
        topic_embedding = self.get_embedding(topic)
        insights_embeddings = np.stack( [ r[1] for r in self.raw_insights ] , axis= 0 )
        sim = cosine_similarity( insights_embeddings, topic_embedding )
        sim = sim.reshape( (len(self.raw_insights)) )
        sim = (sim > 0.9).tolist()
        assert len(sim) == len(self.raw_insights)
        filtered_insights = [ r[0] for r,cond in zip(self.raw_insights, sim) if cond ]

        return filtered_insights
    
    def _add_embeddings(self):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        for i, (r, emb) in enumerate(self.raw_insights):
            if len(emb) == 0:
                emb = np.array(client.embeddings.create(model="text-embedding-ada-002", input=r).data[0].embedding)
                self.raw_insights[i] = (r, emb)


    def get_embedding(self, topic:str):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return np.array(client.embeddings.create(model="text-embedding-ada-002", input=topic).data[0].embedding).reshape((1,-1))
    

class WritingTaskExecuter(BaseTaskExecuter):
    def __init__(self, company, company_extractor:CompanyExtractorOnline = None, industry_extractor:IndustryExtractorOnline=None,  **other_args):
        super().__init__(**other_args)
        self.system_message = create_writer()        
        self.company = company
        self.company_extractor = CompanyExtractorOnline(company, GraphExtractorOnline(), llm_config= other_args["llm_config"]) if company_extractor is None else company_extractor
        # self.industry_extractor = IndustryExtractorOnline(company_to_gics_code(company), GraphExtractorOnline(), other_args["llm_config"]) if industry_extractor is None else industry_extractor
        self.company_info = None
        self.industry_info = None

    def _prepare_company_background_info(self, task: WritingTask):        
        provided_text = []
        for constraint in task.constraints:
            filtered_insights = self.company_extractor.filter_insights(constraint)            
            provided_text = filtered_insights + provided_text
        provided_text = list(set(provided_text))
        paragraphs = Condenser(
            llm_config=self.setup_config["llm_config"],
            silent= self.setup_config["silent"],
            is_termination_msg=self.setup_config["is_termination_msg"],
        ).get_chunks(constraint, [ r[0] for r in self.company_extractor.raw_insights], provided_text)
        self.company_info = paragraphs
    
    # def _prepare_industry_background_info(self, task: WritingTask):
    #     provided_text = []
    #     for constraint in task.constraints:
    #         filtered_trends = self.industry_extractor.filter_trends(constraint)
            
    #         provided_text = filtered_trends + provided_text
    #     provided_text = list(set(provided_text))
    #     paragraphs = Condenser(
    #         llm_config=self.setup_config["llm_config"],
    #         silent= self.setup_config["silent"],
    #         is_termination_msg=self.setup_config["is_termination_msg"],
    #     ).get_chunks(constraint, [ r[0] for r in self.industry_extractor.raw_trends], provided_text)
    #     self.industry_info = paragraphs
    
    def _prepare_background_info(self, task: WritingTask ):
        if self.company_info is None:
            self._prepare_company_background_info(task)
        # if self.industry_info is None:
        #     self._prepare_industry_background_info(task)
        
        return self.company_info #,self.industry_info

    def _generate_message(self, task: WritingTask):
        company_infos = self._prepare_background_info(task) # , industry_infos
        indent = "   "
        constraints_str = '\n'.join([indent+ '    ' + constraint for constraint in task.constraints])
        
        current_workflow = task.root_task.workflow(lambda x : f"{x.name}:{x.description}", as_string=False)[1:]
        for i,task_str in enumerate(current_workflow):
            num = task_str["prefix"] + [ task_str["num"] ]
            num = num[1:]
            current_workflow[i] = "    "*(len(num)-1) + ".".join([f"{n}" for n in num]) + ") " + task_str["string"]
        current_workflow = "\n".join(current_workflow)

        message = \
            f'Write the following section.\n' + \
            f'{indent}section title: {task.name}\n' + \
            f'{indent}section description: {task.description}\n' + \
            f'{indent}section content: {constraints_str}\n' + \
            "\n" + \
            f"relevant company information\n\n{company_infos}\n\n" + \
            f"overall_report\n\n{current_workflow}"
            # f"Relevant industry information\n{industry_infos}"
                       # f'{indent}Section Content Constraints:\n{constraints_str}\n' + \
        return message     
        
    def execute(self, message:List[str], task: WritingTask):        
        
        raw_section = BaseAgents(
                llm_config= self.setup_config["llm_config"],
                silent= self.setup_config["silent"],
                is_termination_msg=self.setup_config["is_termination_msg"],
                user_system_prompt=self.system_message[1]
        ).single_with_structure(message)

        
        if raw_section.startswith( f"### {task.name}" ):
            raw_section = raw_section[ len(f"### {task.name}") :  ].strip()
        elif raw_section.startswith( f"** {task.name} **" ):
            raw_section = raw_section[ len(f"** {task.name} **") :  ].strip()
        
        if "All Text Chunks Cited:" in raw_section: #and section.strip()[-1] == "]":
            section = raw_section[:raw_section.find("All Text Chunks Cited")].strip()
            cites = raw_section[raw_section.find("All Text Chunks Cited"):]            
            try:
                assert "[" in cites and "]" in cites
                cites = cites[ cites.find("[") + 1 : cites.rfind("]") ]
                cites = cites.split(",")
                cites = [ int(cite) for cite in cites if len(cite) > 0 ]
            except:
                cites = []
        else:
            section = raw_section
            cites = []


        return section, cites
    
######################################################

def create_writer():
    paragraph_system_prompt = "You are a brilliant strategy consultant, fantastic at writing a business report in collaboration with other consultants." + \
                    "Your task is to write several paragraphs based on the given [topic] for [company]." + \
                    "You will be provided relevant information about the [company] and their industry.\n\n" + \
                    "You can only write the paragraphs using the provided information and must not contain any sections."
    
    section_writer_prompts = "You are a brilliant strategy consultant, fantastic at writing a business report in collaboration with other consultants." + \
                    "Your task is to  write section titled [title] based on the [section description]." + \
                    "You must follow the rule below when writing the strategy report's section:\n" + \
                    "   - You can only utilize [relevant company information] to write the section."+\
                    "   - WHen writing, you must cite inline which relevant company text chunks were used. Cite inline using the format '[text chunk number]', and list all text chucks used at the end." + \
                    "   - The section can not contain any sub-sections, the section should also 5-6 paragraphs." + \
                    "   - Do not include any conclusion or summary paragraphs to ensure that the section flows with [overall report]." + \
                    "   - Start the section with '### [title]' and end the section with 'All Text Chunks Cited: [..., ...]'" + \
                    "You will be provided [section description], [company], [overall report] and [relevant company information].\n\n"                    

    return paragraph_system_prompt, section_writer_prompts

def company_to_gics_code(company:str)-> str:
    mapping = {
        "Amazon" : "30"
    }

    return mapping[company]

if __name__ == "__main__":
    IndustryExtractorOnline("Amazon")