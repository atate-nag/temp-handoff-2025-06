from langchain_community.vectorstores import Neo4jVector
from langchain_community.graphs import Neo4jGraph
from langchain.chains import GraphCypherQAChain
from langchain.docstore.document import Document
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_experimental.text_splitter import SemanticChunker
# export TIKA_SERVER_JAR="file:/Users/leogrill/Work/core-components/tests/building_graph/tika-server-standard-2.9.2.jar"
import tika
import time
from tika import parser
tika.initVM()
import openai
import keybert.llm as llm
from keybert import KeyBERT
import os
import uuid

def extract_keywords(documents):

    kw_model = KeyBERT()
    keywords = kw_model.extract_keywords([documents])
    
    # keywords.extend(kw_model.extract_keywords([documents], keyphrase_ngram_range=(1, 2), stop_words=None))
    # print(f"keywords: {[keyword[0] for keyword in keywords]}")
    return [keyword[0] for keyword in keywords]

class graph_explorer:
    def __init__(self, graph):
        self.graph = graph
        
    def get_chunk(self, chunk_id):
        return self.graph.kg.query("""
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            RETURN chunk
            """, params={'chunk_id': chunk_id})
        
    def get_document(self, doc_id):
        return self.graph.kg.query("""
            MATCH (doc:Document {docId: $doc_id})
            RETURN doc
            """, params={'doc_id': doc_id})
        
    
        
    def get_class(self, class_id):
        return self.graph.kg.query("""
            MATCH (class:Class {classId: $class_id})
            RETURN class
            """, params={'class_id': class_id})

class RAG_graph:
    def __init__(self, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE, OPENAI_API_KEY, OPENAI_ENDPOINT, text_splitters=None):
        
        self.OPENAI_API_KEY = OPENAI_API_KEY
        self.OPENAI_ENDPOINT = OPENAI_ENDPOINT

        self.text_chunkers = [(SemanticChunker(OpenAIEmbeddings()),'semantic_chunker'),]
            # (RecursiveCharacterTextSplitter(
            #     chunk_size = 1400,
            #     chunk_overlap  = 50,
            #     length_function = len,
            #     is_separator_regex = False,
            # ), 'recursive_chunker')] if text_splitters is None else text_splitters
        
        # self.parent_retriever = GraphCypherQAChain(
        #     vectorstore=self.vector_store,
        #     docstore=self.store,
        #     child_splitter=self.text_chunkers,
        # )
        self.kg = Neo4jGraph(
            url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD, database=NEO4J_DATABASE
        )
        self.db = NEO4J_DATABASE
        self.indexes = {}
        
        self.merge_chunk_node_query = """
            MERGE(mergedChunk:Chunk {chunkId: $chunkParam.chunkId})
                ON CREATE SET 
                    mergedChunk.name = $chunkParam.name, 
                    mergedChunk.source = $chunkParam.source, 
                    mergedChunk.source_location = $chunkParam.source_location, 
                    mergedChunk.timestamp = TIMESTAMP(),
                    mergedChunk.created = $chunkParam.created,
                    mergedChunk.chunkSeqId = $chunkParam.chunkSeqId, 
                    mergedChunk.chunkType = $chunkParam.chunkType,
                    mergedChunk.text = $chunkParam.text,
                    mergedChunk.keywords = $chunkParam.keywords,
                    mergedChunk.id_ = $chunkParam.chunkId
            RETURN mergedChunk
            """
            
        self.merge_insight_node_query = """
            MERGE(mergedInsight:Insight {insightId: $insightParam.insightId})
                ON CREATE SET 
                    mergedInsight.name = $insightParam.name, 
                    mergedInsight.description = $insightParam.description, 
                    mergedInsight.source = $insightParam.source,  
                    mergedInsight.extractionDate = TIMESTAMP(),
                    mergedInsight.created = $insightParam.created,
                    mergedInsight.relevanceScore = $insightParam.relevanceScore,
                    mergedInsight.categories = $insightParam.categories,
                    mergedInsight.insightId = $insightParam.insightId
            RETURN mergedInsight
            """
            
        self.merge_trend_node_query = """
            MERGE(t:Trend {trendId: $trendParam.trendId})
                ON CREATE SET 
                    t.trendId = $trendParam.trendId,
                    t.title = $trendParam.title,
                    t.Summary = $trendParam.Summary,
                    t.Description = $trendParam.Description,
                    t.AffectedAreas = $trendParam.AffectedAreas,
                    t.EvidencedBy = $trendParam.EvidencedBy,
                    t.source =$trendParam.source,
                    t.created =$trendParam.created
            RETURN t
            """
            
        self.merge_capability_node_query = """
            MERGE(c:Capability {capabilityId: $capabilityParam.capabilityId})
                ON CREATE SET 
                    c.capability = $capabilityParam.capability, 
                    c.value_potentential = $capabilityParam.value_potentential, 
                    c.source = $capabilityParam.source,  
                    c.scarcity = $capabilityParam.scarcity,
                    c.created = $capabilityParam.created,
                    c.non_replicability = $capabilityParam.non_replicability,
                    c.irreplaceability = $capabilityParam.irreplaceability,
                    c.confidence = $capabilityParam.confidence,
                    c.evidenced_by = $capabilityParam.evidenced_by,
                    c.categories = $capabilityParam.categories
            RETURN c
            """
            
        self.merge_document_node_query = """
            MERGE(mergedDoc:Document {docId: $docParam.docId})
                ON CREATE SET 
                    mergedDoc.name = $docParam.name, 
                    mergedDoc.source = $docParam.source, 
                    mergedDoc.source_location = $docParam.source_location, 
                    mergedDoc.timestamp = TIMESTAMP(),
                    mergedDoc.created = $docParam.created,
                    mergedDoc.text = $docParam.text,
                    mergedDoc.keywords = $docParam.keywords,
                    mergedDoc.id_ = $docParam.docId
            RETURN mergedDoc
            """
            
        self.merge_class_node_query = """
            MERGE(mergedclass:Class {classId: $classParam.classId})
                ON CREATE SET 
                    mergedclass.name = $classParam.name, 
                    mergedclass.source = $classParam.source, 
                    mergedclass.timestamp = TIMESTAMP(),
                    mergedclass.created = $classParam.created,
                    mergedclass.text = $classParam.text,
                    mergedclass.id_ = $classParam.classId
            RETURN mergedclass
        """
        
        self.merge_cluster_node_query = """
            MERGE(c:Cluster {clusterId: $clusterParam.clusterId})
                ON CREATE SET 
                    c.number = $clusterParam.number, 
                    c.source = $clusterParam.source, 
                    c.category = $clusterParam.category, 
                    c.timestamp = TIMESTAMP(),
                    c.created = $clusterParam.created,
                    c.description = $clusterParam.description,
                    c.summary = $clusterParam.summary,
                    c.type = $clusterParam.type,
                    c.id_ = $clusterParam.clusterId
            RETURN c
        """
    
    # def create_vector_index(self, index_name, node, property):
    #     params ={'index_name': index_name, 'node': '(node.'+node+')', 'properties': property}
    #     print(params)
    #     self.kg.query(f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS " +
    #      f"FOR (node:{node}) ON (node.{property}) " +
    #      "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'} }", params={})
        
    #     self.indexes[index_name] = {'node': node, 'properties': property, 'type': 'vector_index'}
    def create_vector_index(self, index_name, node, property):
        self.kg.query(f"""
         CREATE VECTOR INDEX {index_name} IF NOT EXISTS
          FOR (node:{node}) ON (node.{property}) 
          OPTIONS {{ indexConfig: {{
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'    
                }}}}
        """, params={})
        self.indexes[index_name] = {'node': node, 'properties': property, 'type': 'vector_index'}
    
    def create_index(self, index_name, node, property):
        self.kg.query(f"""
            CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS
            FOR (node:{node}) 
            ON EACH [node.{property}]
            """, params={})
        self.indexes[index_name] = {'node': node, 'properties': property, 'type': 'fulltext_index'}
        
    def delete_index(self, index_name):
        try:
            self.kg.query(f"""
            DROP INDEX {index_name}
            """)
            del self.indexes[index_name]
        except Exception as e:
            print(e)
  
        
    def fetch_indexes(self):
        try:
            indexes = self.kg.query(f"""
            SHOW INDEXES
            """)
            print(indexes)
            return indexes
        except Exception as e:
            print(e)
        
    def get_indexes(self):
        for index in self.indexes:
            print(index)
        return self.indexes
        
    
    def add_chunk(self, chunk):
        # print(f"Chunk: {chunk}")
        self.kg.query(self.merge_chunk_node_query, 
                    params={
                        'chunkParam': chunk
                    })
        
    def add_insight(self, insight):
        # print(f"Chunk: {chunk}")
        self.kg.query(self.merge_insight_node_query, 
                    params={
                        'insightParam': insight
                    })
        
    def add_trend(self, trend):
        # print(f"Chunk: {chunk}")
        self.kg.query(self.merge_trend_node_query, 
                    params={
                        'trendParam': trend
                    })
        
    def add_capability(self, capability):
        # print(f"Chunk: {chunk}")
        self.kg.query(self.merge_capability_node_query, 
                    params={
                        'capabilityParam': capability
                    })
        
    
        
    def add_class(self, classParam):
        self.kg.query(self.merge_class_node_query,
                      params={'classParam': classParam})
        
    def add_cluster(self, clusterParam):
        self.kg.query(self.merge_cluster_node_query,
                      params={'clusterParam': clusterParam})
        
    def add_document(self, document):
        self.kg.query(self.merge_document_node_query, 
                    params={
                        'docParam': document
                    })
        
    def add_document_and_chunks(self, document, title, source, source_location, creation_time):
        # print(f"Document: {document}")
        parsed = parser.from_file(document)
        # print(parsed['metadata'].keys())
        # print(parsed['metadata']["meta:last-author"])
        # print(parsed['metadata']['dc:creator'])
        # print(parsed['metadata']['Content-Type'])
        # assert parsed['metadata']["meta:last-author"] == "Adrian Tate"
        
        return self.add_document_and_chunks_from_text(parsed["content"], title, source, source_location, creation_time)
        
        
        
        # t = time.time()
        # keywords_ = []
        # set_of_chunks = []
        # for chunker, name in self.text_chunkers:
        #     chunks = chunker.create_documents([parsed["content"]])
        #     set_of_chunks.append((chunks, name))
        # chunks_id = []
        # for chunks, name in set_of_chunks:
        #     for i, chunk in enumerate(chunks):
        #         # print(f"Chunk: {chunk}")
                
        #         # keywords = extract_keywords(chunk.page_content)
        #         keywords = []
        #         chk = {"chunkId": str(uuid.uuid4()),
        #             "name": f'{document.split("/")[-1]}_chunk_{i:04d}', 
        #             "source": document.split('/')[-1], 
        #             "source_location": document, 
        #             "created": t,
        #             "chunkSeqId": i,
        #             "chunkType": name,
        #             "text": chunk.page_content,
        #             "keywords": keywords}
        #         chunks_id.append(chk["chunkId"])
        #         keywords_.extend(keywords)
                
                
        #         self.add_chunk(chk)
        # keywords_count = [(x,keywords_.count(x)) for x in set(keywords_)]
        # doc = {"docId": str(uuid.uuid4()),
        #     "name": document.split('/')[-1], 
        #     "source": document.split('/')[-1], 
        #     "source_location": document, 
        #     "created": t,
        #     "text": parsed["content"],
        #     "keywords": list(set(keywords_))}
        
        # self.add_document(doc)
        # for chk_id in chunks_id:
        #     self.link_document_to_chunk(doc["docId"], chk_id) 
        # print(f"Count of keywords for {document.split('/')[-1]}: {dict((x,keywords_.count(x)) for x in set(keywords_))}")
        # return doc
    
    def add_document_and_chunks_from_text(self, document, title, source, source_location, creation_time):
        # t = time.time()
        
        chunks_id = []
        keywords_ = []
        
        set_of_chunks = []
        for chunker, name in self.text_chunkers:
            print(f"document: {document}")
            chunks = chunker.create_documents([document])
            set_of_chunks.append((chunks, name))
        chunks_id = []
        for chunks, name in set_of_chunks:
            for i, chunk in enumerate(chunks):
                # print(f"Chunk: {chunk}")
                
                # keywords = extract_keywords(chunk.page_content)
                keywords = []
                chk = {"chunkId": str(uuid.uuid4()),
                    "name": f'{title}_chunk_{i:04d}', 
                    "source": source, 
                    "source_location": source_location, 
                    "created": creation_time,
                    "chunkSeqId": i,
                    "chunkType": name,
                    "text": chunk.page_content,
                    "keywords": keywords}
                chunks_id.append(chk["chunkId"])
                keywords_.extend(keywords)
                self.add_chunk(chk)
            
        doc = {"docId": str(uuid.uuid4()),
            "name": title, 
            "source": source, 
            "source_location": source_location, 
            "created": creation_time,
            "text": document,
            "keywords": list(set(keywords_))}
        
        self.add_document(doc)
        for chunk_id in chunks_id:
            self.link_document_to_chunk(doc["docId"], chunk_id)
        return doc
        
    def link_document_to_chunk(self, docId, chunkId):
        self.kg.query("""
            MATCH (doc:Document {docId: $docId})
            MATCH (chunk:Chunk {chunkId: $chunkId})
            MERGE (doc)-[:CONTAINS]->(chunk)
            """, params={'docId': docId, 'chunkId': chunkId})
        
    def add_attribute(self, node, property, value):
        
        query = f"""MATCH (n {{id_: '{node}'}})
            SET n.{property} = "{str(value).replace('"', '').replace("'", '')}"
            RETURN n"""
        # print(query)
        self.kg.query(query)
        
    def link_elements(self, type1, type2,typeID1,typeID2,ID1,ID2,relationship):
        self.kg.query("""
            MATCH (elt1:$type1 {$typeID1: $ID1})
            MATCH (elt2:$type2 {$typeID2: $ID2})
            MERGE (elt1)-[:$relationship]->(elt2)
            """, params={'type1': type1,'type2': type2,'typeID1': typeID1,'typeID2': typeID2,
                         'ID1': ID1,'ID2': ID2, 'relationship':relationship})
        
    def link_company_to_element(self, company_name, elementType, elementID):
        self.kg.query("""
            MATCH (c:Company {name: $company_name})
            MATCH (element:$elementType {$elementType: $elementID})
            MERGE (company)-[:CONTAINS]->(element)
            """, params={'companyID': company_name, 'elementType': elementType, 'elementID': elementID})
        
    def create_relationship(self, company_name, relationship, elementID):
        
        self.kg.query("""
            MATCH (c:Company {name: $company_name})
            MATCH (element {id_: $elementID})
            MERGE (company)-[:"""+relationship+"""]->(element)
            """, params={'company_name': company_name, 'relationship': relationship, 'elementID': elementID})
        
    def link_company_to_class(self, company_name, class_id):
        self.kg.query("""
            MATCH (c:Company {name: $company_name})
            MATCH (class:Class {classId: $class_id})
            MERGE (c)-[:DESCRIBED_BY]->(class)
            """, params={'company_name': company_name, 'class_id': class_id})
        
    def link_class_to_document(self, class_name, document_name):
        self.kg.query("""
            MATCH (class:Class {name: $class_name})
            MATCH (doc:Document {name: $document_name})
            MERGE (class)-[:SPECIFIED_BY]->(doc)
            """, params={'class_name': class_name, 'document_name': document_name})
        
    def link_insights_to_cluster(self, insight_id, cluster_id):
        self.kg.query("""
            MATCH (c:Cluster {clusterId: $cluster_id})
            MATCH (i:Insight {insightId: $insight_id})
            MERGE (i)-[:SUMMARIZED_BY]->(c)
            """, params={'cluster_id': cluster_id, 'insight_id': insight_id})
        
    def link_trend_to_cluster(self, trend_id, cluster_id):
        self.kg.query("""
            MATCH (c:Cluster {clusterId: $cluster_id})
            MATCH (t:Trend {trendId: $trend_id})
            MERGE (t)-[:SUMMARIZED_BY]->(c)
            """, params={'cluster_id': cluster_id, 'trend_id': trend_id})
        
    def link_cluster_to_capability(self, cluster_id, capability_id):
        self.kg.query("""
            MATCH (cl:Cluster {clusterId: $cluster_id})
            MATCH (ca:Capability {capabilityId: $capability_id})
            MERGE (cl)-[:DESCRIBED_BY]->(ca)
            """, params={'cluster_id': cluster_id, 'capability_id': capability_id})
        
        
    def link_class_to_chunk(self, class_id, chunk_id):
        self.kg.query("""
            MATCH (class:Class {classId: $class_id})
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            MERGE (class)-[:POSTED]->(chunk)
            """, params={'class_id': class_id, 'chunk_id': chunk_id})
        
    def link_chunk_to_insight(self, chunk_id, insight_id):
        self.kg.query("""
            MATCH (insight:Insight {insightId: $insight_id})
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            MERGE (chunk)-[:EXTRACTED_FROM]->(insight)
            """, params={'insight_id': insight_id, 'chunk_id': chunk_id})
        
    def link_chunk_to_trend(self, chunk_id, trend_id):
        self.kg.query("""
            MATCH (trend:Trend {trendId: $trend_id})
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            MERGE (chunk)-[:EXTRACTED_FROM]->(trend)
            """, params={'trend_id': trend_id, 'chunk_id': chunk_id})
        
        
    def get_document_text(self, name):
        return self.kg.query("""
            MATCH (node {name: $name})-[r]->(doc:Document)
            RETURN doc.text
            """, params={'name': name})
        
        
    def compute_embeddings(self,node='Chunk', field='text'):
        # print(f"OPENAI_ENDPOINT: {self.OPENAI_ENDPOINT}")
        
        self.kg.query(f"""
        MATCH (chunk:{node}) WHERE chunk.textEmbedding IS NULL AND chunk.{field} IS NOT NULL AND SIZE(chunk.{field}) < 8192 AND SIZE(chunk.{field}) > 2
        WITH chunk, genai.vector.encode(
        chunk.{field}, 
        "OpenAI", 
        {{
            token: $openAiApiKey, 
            endpoint: $openAiEndpoint
        }}) AS vector
        CALL db.create.setNodeVectorProperty(chunk, "{field}Embedding", vector)
        """, 
        params={"openAiApiKey":self.OPENAI_API_KEY, "openAiEndpoint": self.OPENAI_ENDPOINT} )
        
    def link_close_chunks(self, threshold=0.85):
        self.kg.query("""
        MATCH (chunk1:Chunk), (chunk2:Chunk) WHERE chunk1.source <> chunk2.source
        WITH chunk1, chunk2, vector.similarity.cosine(chunk1.textEmbedding, chunk2.textEmbedding) AS similarity
        WHERE similarity > $threshold
        MERGE (chunk1)-[:SIMILAR {similarity: similarity}]-(chunk2)
        """, params={'threshold': threshold})
    
    def link_close_insights(self, threshold=0.95):
        self.kg.query("""
        MATCH (chunk1:Insight), (chunk2:Insight) WHERE chunk1.company = 'Tesla' and chunk2.company = 'Tesla' and ID(chunk1) <> ID(chunk2)
        WITH chunk1, chunk2, vector.similarity.cosine(chunk1.descriptionEmbedding, chunk2.descriptionEmbedding) AS similarity
        WHERE similarity > $threshold
        MERGE (chunk1)-[:SIMILAR {similarity: similarity}]-(chunk2)
        """, params={'threshold': threshold})
    
    def neo4j_vector_search(self, question, top_k=10):
        """Search for similar nodes using the Neo4j vector index"""
        vector_search_query = """
            WITH genai.vector.encode(
            $question, 
            "OpenAI", 
            {
                token: $openAiApiKey,
                endpoint: $openAiEndpoint
            }) AS question_embedding
            CALL db.index.vector.queryNodes($index_name, $top_k, question_embedding) yield node, score
            RETURN score, node.text AS text
        """
        similar = self.kg.query(vector_search_query, 
                            params={
                            'question': question, 
                            'openAiApiKey': self.OPENAI_API_KEY,
                            'openAiEndpoint': self.OPENAI_ENDPOINT,
                            'index_name':VECTOR_INDEX_NAME, 
                            'top_k': top_k})
        return similar
    
    def create_vector_index(self):
        self.kg.query("""
         CREATE VECTOR INDEX `chunk_text` IF NOT EXISTS
          FOR (c:Chunk) ON (c.textEmbedding) 
          OPTIONS { indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'    
         }}
""")
    
    def deep_search(self, depth,nodeType=None, node='n', relationship='r', where=None):
        if nodeType is None:
            query = f"match ({node}) "
        else:
            query = f"match ({node}:{nodeType}) "
        output = [node]
        for i in range(depth):
            query += f"-[{relationship}_{i}]-> ({node}_{i}) "
            output.append(f"{relationship}_{i}")
            output.append(f"{node}_{i}")
        query += f"WHERE {where} " if where else " "
        query += f"return {', '.join(output)}"
        print(f"Query: {query}")
        return self.kg.query(query)
    
    # def sub_graph(self, nodeType=None, node='n',maxLevel=3, relationship='r', where=None):
    #     nodeType = ":"+nodeType if nodeType is not None else ''
    #     query = f"""MATCH ({node}{nodeType}) WHERE {where}
    #         CALL apoc.path.subgraphAll(c, {{maxLevel: {maxLevel}}}) YIELD nodes, relationships 
    #         RETURN nodes, relationships"""
    #     print(f"Query: {query}")
    #     return self.kg.query(query)
    
    # def sub_graph(self, node, nodeType=None, where=None):
    #     nodeType = node+":"+nodeType if nodeType is not None else node
    #     query = f"MATCH ({nodeType})-[*]-(connected) WHERE {where} AND {node} <> connected RETURN distinct connected"
     
    #     return self.kg.query(query)
    
    # def inject_sub_graph()
    
    def company_sub_graph(self, company, label_filters=[], relationship_exclusions=[],depth=5):
        edges = self.kg.query("MATCH ()-[r]->() RETURN DISTINCT type(r) as edge")
        edges = [edge['edge'] for edge in edges if edge['edge'] not in relationship_exclusions]
        # print(edges)
       
        filters = f"WITH [x IN nodes Where {' or '.join([f'(x:{label_filter})' for label_filter in label_filters]) }  ] AS nodes" if len(label_filters) > 0 else " " 
        query = f"""MATCH (c:Company {{name: '{company}'}})
    CALL apoc.path.subgraphAll(c, {{ 
            relationshipFilter: '{'|'.join(edges)}',
        minLevel: 0,
        maxLevel: {depth}
    }})
        YIELD nodes, relationships """ +\
        filters +\
        """
        RETURN DISTINCT nodes;"""

        return self.kg.query(query)[0]['nodes']
    
   
   
    def build_store(self, file):
        neo4j_vector_store = Neo4jVector.from_existing_graph(
            embedding=OpenAIEmbeddings(),
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            index_name=VECTOR_INDEX_NAME,
            node_label=VECTOR_NODE_LABEL,
            text_node_properties=[VECTOR_SOURCE_PROPERTY],
            embedding_node_property=VECTOR_EMBEDDING_PROPERTY,
        )
        return neo4j_vector_store
    
    def clear_database(self):
        self.kg.query("match (a) -[r] -> () delete a, r")
        self.kg.query("match (a) delete a")
        
    # def close(self):
    #     self.kg.close()
        
    # def split_form10k_data_from_file(self, file):
    #     chunks_with_metadata = [] # use this to accumlate chunk records
    #     file_as_object = json.load(open(file)) # open the json file
    #     for item in ['item1','item1a','item7','item7a']: # pull these keys from the json
    #         print(f'Processing {item} from {file}') 
    #         item_text = file_as_object[item] # grab the text of the item
    #         item_text_chunks = text_splitter.split_text(item_text) # split the text into chunks
    #         chunk_seq_id = 0
    #         for chunk in item_text_chunks[:20]: # only take the first 20 chunks
    #             form_id = file[file.rindex('/') + 1:file.rindex('.')] # extract form id from file name
    #             # finally, construct a record with metadata and the chunk text
    #             chunks_with_metadata.append({
    #                 'text': chunk, 
    #                 # metadata from looping...
    #                 'f10kItem': item,
    #                 'chunkSeqId': chunk_seq_id,
    #                 # constructed metadata...
    #                 'formId': f'{form_id}', # pulled from the filename
    #                 'chunkId': f'{form_id}-{item}-chunk{chunk_seq_id:04d}',
    #                 # metadata from file...
    #                 'names': file_as_object['names'],
    #                 'cik': file_as_object['cik'],
    #                 'cusip6': file_as_object['cusip6'],
    #                 'source': file_as_object['source'],
    #             })
    #             chunk_seq_id += 1
    #         print(f'\tSplit into {chunk_seq_id} chunks')
    #     return chunks_with_metadata
    
    
    
if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    import shutil
    from ..DocumentLoader.document_retriever_sharepoint import (
        SharePointRetriever,
    )
    from ..TrendAgent.trendAgent import (
        TrendAgent,
    )
    import tika
    import time
    from tika import parser
    load_dotenv()
    tika.initVM()
    
    NEO4J_URI = os.getenv('NEO4J_URL')
    NEO4J_USER = os.getenv('NEO4J_USER')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
    NEO4J_DATABASE = 'test_database'
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_ENDPOINT = os.getenv('OPENAI_ENDPOINT')
    OPENAI_EMBEDDINGS_URL = os.getenv('OPENAI_EMBEDDINGS_URL')
    sharepoint_base_url = os.getenv("sharepoint_base_url")
    sharepoint_user = os.getenv("sharepoint_user")
    sharepoint_password = os.getenv("sharepoint_password")
    
    # rag_graph = RAG_graph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
    # rag_graph = RAG_graph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, OPENAI_API_KEY, OPENAI_ENDPOINT, 'neo4j')
    load_dotenv()
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # setup neo4j database

    uri = os.getenv("NEO4J_URL")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE")

    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_ENDPOINT = os.getenv('OPENAI_ENDPOINT')
    OPENAI_EMBEDDINGS_URL = os.getenv('OPENAI_EMBEDDINGS_URL')
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
    
    rag_graph = RAG_graph('bolt://localhost:7687', user, password, database, OPENAI_API_KEY,OPENAI_EMBEDDINGS_URL)
    # def sub_graph(self, nodeType=None, node='n',maxLevel=3, relationship='r', where=None):
    # print(rag_graph.sub_graph(maxLevel='4', node='n', nodeType="Company",where='n.name = "World_Fuel_Services"'))
    print(rag_graph.sub_graph( node='n',nodeType='Company', where='n.name = "World_Fuel_Services"'))
    
    
    
    
    # rag_graph.clear_database()
    
    # sharepoint_retriever = SharePointRetriever(
    #     sharepoint_base_url, sharepoint_user, sharepoint_password
    # )
    
    # files = sharepoint_retriever.find_and_download_files(
    #     "Shared Documents/Research/Incubation/Socrates/Documents/test_retrieval/"
    # )
    # folder = "data"
    # files_to_remove = [
    #         os.path.join(folder, f)
    #         for f in os.listdir(folder)
    #         if os.path.isfile(os.path.join(folder, f))
    #     ]
    
    # for f in files_to_remove:
    #     os.remove(f)
        
    # docs = []
        
    # rag_graph.kg.query("""
    #         CREATE CONSTRAINT unique_chunk IF NOT EXISTS 
    #             FOR (c:Chunk) REQUIRE c.chunkId IS UNIQUE
    #         """)    
    # rag_graph.kg.query("""
    #     CREATE CONSTRAINT unique_document IF NOT EXISTS 
    #         FOR (d:Document) REQUIRE d.docId IS UNIQUE
    #     """)    
    # for file in files[:4]:
    #     try:
    #         print(os.path.join(folder, file.split("/")[-1]))
    #         # shutil.copyfile(file, os.path.join(folder, file.split("/")[-1]))
    #         parsed = parser.from_file(file)
    #         print(str(parsed)[:20])
    #         # doc = Document(
    #         #     page_content=parsed["content"], metadata={"source": file}
    #         # )  # TODO metadata=parsed["metadata"])
    #         # print(parsed["metadata"])
    #         # print(doc.metadata)
    #         # docs.append(doc)
    #         t = time.time()
    #         chunks = rag_graph.text_chunkers[0].create_documents([parsed["content"]])
    #         doc = {"docId": file.split("/")[-1],
    #             "name": file.split('/')[-1], 
    #             "source": file.split('/')[-1], 
    #             "source_location": file, 
    #             "created": t,
    #             "text": parsed["content"]}
    #         rag_graph.add_document(doc)
    #         for i, chunk in enumerate(chunks):
    #             # print(f"Chunk: {chunk}")
    #             chk = {"chunkId": f'{file.split("/")[-1]}_chunk_{i:04d}',
    #                 "name": file.split('/')[-1], 
    #                 "source": file.split('/')[-1], 
    #                 "source_location": file, 
    #                 "created": t,
    #                 "chunkSeqId": i,
    #                 "text": chunk.page_content}
    #             rag_graph.add_chunk(chk)
    #             rag_graph.link_document_to_chunk(doc["docId"], chk["chunkId"])
    #         rag_graph.compute_embeddings()
    #     except Exception as e:
    #         print(e)
            
    
    # rag_graph.compute_embeddings()
    # rag_graph.link_close_chunks(.9)
    
        # os.rename(file,os.path.join(name,file.split("/")[-1]))