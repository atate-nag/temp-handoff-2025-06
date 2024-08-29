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
from utility import retry, logger

tika.initVM()
# import openai
# import keybert.llm as llm
# from keybert import KeyBERT
import os
import uuid
import multiprocessing as mp
import logging

try:
    logger.debug(f"{mp.get_start_method()} ---- {__name__}")
    mp.set_start_method("spawn")
except Exception as e:
    logger.error(__name__ + " - " + str(e))

# def extract_keywords(documents):

#     kw_model = KeyBERT()
#     keywords = kw_model.extract_keywords([documents])

#     # keywords.extend(kw_model.extract_keywords([documents], keyphrase_ngram_range=(1, 2), stop_words=None))
#     # logger.info(f"keywords: {[keyword[0] for keyword in keywords]}")
#     return [keyword[0] for keyword in keywords]


class graph_explorer:
    def __init__(self, graph):
        self.graph = graph

    def get_chunk(self, chunk_id):
        return self.graph.kg.query(
            """
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            RETURN chunk
            """,
            params={"chunk_id": chunk_id},
        )

    def get_document(self, doc_id):
        return self.graph.kg.query(
            """
            MATCH (doc:Document {docId: $doc_id})
            RETURN doc
            """,
            params={"doc_id": doc_id},
        )

    def get_class(self, class_id):
        return self.graph.kg.query(
            """
            MATCH (class:Class {classId: $class_id})
            RETURN class
            """,
            params={"class_id": class_id},
        )


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
OPENAI_EMBEDDINGS_URL = os.getenv("OPENAI_EMBEDDINGS_URL")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

NEO4J_URI = os.getenv("NEO4J_URL")
NEO4J_USERNAME = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")


@retry(number_of_retry=3)
def compute_bucket_embeddings(bucket_str_list_nodes, node, lower_node, field):
    kg = Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    )
    query = f"""MATCH (n:{node}) WHERE n.{lower_node}Id in {bucket_str_list_nodes}
            WITH n, genai.vector.encode(
            n.{field}, 
            "OpenAI", 
            {{
                token: $openAiApiKey, 
                endpoint: $openAiEndpoint
            }}) AS vector
            CALL db.create.setNodeVectorProperty(n, "{field}Embedding", vector)
            """

    # logger.info(f"query: {query}")
    kg.query(
        query,
        params={
            "openAiApiKey": OPENAI_API_KEY,
            "openAiEndpoint": OPENAI_ENDPOINT,
        },
    )
    return True


class RAG_graph:
    def __init__(
        self,
        NEO4J_URI,
        NEO4J_USERNAME,
        NEO4J_PASSWORD,
        NEO4J_DATABASE,
        OPENAI_API_KEY,
        OPENAI_ENDPOINT,
        text_splitters=None,
    ):
        self.OPENAI_API_KEY = OPENAI_API_KEY
        self.OPENAI_ENDPOINT = OPENAI_ENDPOINT

        self.text_chunkers = [
            (SemanticChunker(OpenAIEmbeddings()), "semantic_chunker"),
        ]
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
        self.NEO4J_USERNAME = NEO4J_USERNAME
        self.NEO4J_PASSWORD = NEO4J_PASSWORD
        self.NEO4J_DATABASE = NEO4J_DATABASE
        self.NEO4J_URI = NEO4J_URI
        self.kg = Neo4jGraph(
            url=self.NEO4J_URI,
            username=self.NEO4J_USERNAME,
            password=self.NEO4J_PASSWORD,
            database=self.NEO4J_DATABASE,
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
                    t.gics_code = $trendParam.gics_code,
                    t.gics_name = $trendParam.gics_name,
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
                    c.gics_codes = $clusterParam.gics_codes,
                    c.gics_names = $clusterParam.gics_names,
                    c.titles = $clusterParam.titles,
                    c.AffectedAreas = $clusterParam.AffectedAreas,
                    c.id_ = $clusterParam.clusterId
            RETURN c
        """

    # def create_vector_index(self, index_name, node, property):
    #     params ={'index_name': index_name, 'node': '(node.'+node+')', 'properties': property}
    #     logger.info(params)
    #     self.kg.query(f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS " +
    #      f"FOR (node:{node}) ON (node.{property}) " +
    #      "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'} }", params={})

    #     self.indexes[index_name] = {'node': node, 'properties': property, 'type': 'vector_index'}
    def __enter__(self):
        self.kg._driver.close()
        self.kg = Neo4jGraph(
            url=self.NEO4J_URI,
            username=self.NEO4J_USERNAME,
            password=self.NEO4J_PASSWORD,
            database=self.NEO4J_DATABASE,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.kg._driver.close()
        self.kg = Neo4jGraph(
            url=self.NEO4J_URI,
            username=self.NEO4J_USERNAME,
            password=self.NEO4J_PASSWORD,
            database=self.NEO4J_DATABASE,
        )

    def create_vector_index(self, index_name, node, property):
        self.kg.query(
            f"""
         CREATE VECTOR INDEX {index_name} IF NOT EXISTS
          FOR (node:{node}) ON (node.{property}) 
          OPTIONS {{ indexConfig: {{
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'    
                }}}}
        """,
            params={},
        )
        self.indexes[index_name] = {
            "node": node,
            "properties": property,
            "type": "vector_index",
        }

    def create_index(self, index_name, node, property):
        self.kg.query(
            f"""
            CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS
            FOR (node:{node}) 
            ON EACH [node.{property}]
            """,
            params={},
        )
        self.indexes[index_name] = {
            "node": node,
            "properties": property,
            "type": "fulltext_index",
        }

    def delete_index(self, index_name):
        try:
            self.kg.query(
                f"""
            DROP INDEX {index_name}
            """
            )
            del self.indexes[index_name]
        except Exception as e:
            logger.info(e)

    def fetch_indexes(self):
        try:
            indexes = self.kg.query(
                f"""
            SHOW INDEXES
            """
            )
            logger.info(indexes)
            return indexes
        except Exception as e:
            logger.info(e)

    def get_indexes(self):
        for index in self.indexes:
            logger.info(index)
        return self.indexes

    def add_company(self, company_name):
        self.kg.query(
            """
            MERGE (c:Company {name: $company_name})
            """,
            params={"company_name": company_name},
        )

    def add_chunk(self, chunk):
        # logger.info(f"Chunk: {chunk}")
        self.kg.query(self.merge_chunk_node_query, params={"chunkParam": chunk})

    def add_insight(self, insight):
        # logger.info(f"Chunk: {chunk}")
        self.kg.query(self.merge_insight_node_query, params={"insightParam": insight})

    def add_trend(self, trend):
        # logger.info(f"Chunk: {chunk}")
        self.kg.query(self.merge_trend_node_query, params={"trendParam": trend})

    def add_capability(self, capability):
        # logger.info(f"Chunk: {chunk}")
        self.kg.query(
            self.merge_capability_node_query, params={"capabilityParam": capability}
        )

    def add_class(self, classParam):
        self.kg.query(self.merge_class_node_query, params={"classParam": classParam})

    def add_cluster(self, clusterParam):
        self.kg.query(
            self.merge_cluster_node_query, params={"clusterParam": clusterParam}
        )

    def add_document(self, document):
        self.kg.query(self.merge_document_node_query, params={"docParam": document})

    def add_document_and_chunks(
        self, document, title, source, source_location, creation_time
    ):
        parsed = parser.from_file(document)

        return self.add_document_and_chunks_from_text(
            parsed["content"], title, source, source_location, creation_time
        )

    def add_document_and_chunks_from_text(
        self, document, title, source, source_location, creation_time
    ):
        # t = time.time()

        chunks_id = []
        keywords_ = []

        set_of_chunks = []
        for chunker, name in self.text_chunkers:
            logger.info(f"document: {document}")
            chunks = chunker.create_documents([document])
            set_of_chunks.append((chunks, name))
        chunks_id = []
        for chunks, name in set_of_chunks:
            for i, chunk in enumerate(chunks):
                # logger.info(f"Chunk: {chunk}")

                # keywords = extract_keywords(chunk.page_content)
                keywords = []
                chk = {
                    "chunkId": str(uuid.uuid4()),
                    "name": f"{title}_chunk_{i:04d}",
                    "source": source,
                    "source_location": source_location,
                    "created": creation_time,
                    "chunkSeqId": i,
                    "chunkType": name,
                    "text": chunk.page_content,
                    "keywords": keywords,
                }
                chunks_id.append(chk["chunkId"])
                keywords_.extend(keywords)
                self.add_chunk(chk)

        doc = {
            "docId": str(uuid.uuid4()),
            "name": title,
            "source": source,
            "source_location": source_location,
            "created": creation_time,
            "text": document,
            "keywords": list(set(keywords_)),
        }

        self.add_document(doc)
        for chunk_id in chunks_id:
            self.link_document_to_chunk(doc["docId"], chunk_id)
        return doc

    def link_document_to_chunk(self, docId, chunkId):
        self.kg.query(
            """
            MATCH (doc:Document {docId: $docId})
            MATCH (chunk:Chunk {chunkId: $chunkId})
            MERGE (doc)-[:CONTAINS]->(chunk)
            """,
            params={"docId": docId, "chunkId": chunkId},
        )

    def add_attribute(self, node, property, value):
        query = f"""MATCH (n {{id_: '{node}'}})
            SET n.{property} = "{str(value).replace('"', '').replace("'", '')}"
            RETURN n"""
        # logger.info(query)
        self.kg.query(query)

    def link_elements(self, type1, type2, typeID1, typeID2, ID1, ID2, relationship):
        self.kg.query(
            """
            MATCH (elt1:$type1 {$typeID1: $ID1})
            MATCH (elt2:$type2 {$typeID2: $ID2})
            MERGE (elt1)-[:$relationship]->(elt2)
            """,
            params={
                "type1": type1,
                "type2": type2,
                "typeID1": typeID1,
                "typeID2": typeID2,
                "ID1": ID1,
                "ID2": ID2,
                "relationship": relationship,
            },
        )

    def link_company_to_element(self, company_name, elementType, elementID):
        self.kg.query(
            """
            MATCH (c:Company {name: $company_name})
            MATCH (element:$elementType {$elementType: $elementID})
            MERGE (company)-[:CONTAINS]->(element)
            """,
            params={
                "companyID": company_name,
                "elementType": elementType,
                "elementID": elementID,
            },
        )

    def create_relationship(self, company_name, relationship, elementID):
        self.kg.query(
            """
            MATCH (c:Company {name: $company_name})
            MATCH (element {id_: $elementID})
            MERGE (company)-[:"""
            + relationship
            + """]->(element)
            """,
            params={
                "company_name": company_name,
                "relationship": relationship,
                "elementID": elementID,
            },
        )

    def link_company_to_class(self, company_name, class_id):
        self.kg.query(
            """
            MATCH (c:Company {name: $company_name})
            MATCH (class:Class {classId: $class_id})
            MERGE (c)-[:DESCRIBED_BY]->(class)
            """,
            params={"company_name": company_name, "class_id": class_id},
        )

    def link_class_to_document(self, class_name, document_name):
        self.kg.query(
            """
            MATCH (class:Class {name: $class_name})
            MATCH (doc:Document {name: $document_name})
            MERGE (class)-[:SPECIFIED_BY]->(doc)
            """,
            params={"class_name": class_name, "document_name": document_name},
        )

    def link_insights_to_cluster(self, insight_id, cluster_id):
        self.kg.query(
            """
            MATCH (c:Cluster {clusterId: $cluster_id})
            MATCH (i:Insight {insightId: $insight_id})
            MERGE (i)-[:SUMMARIZED_BY]->(c)
            """,
            params={"cluster_id": cluster_id, "insight_id": insight_id},
        )

    def link_trend_to_cluster(self, trend_id, cluster_id):
        self.kg.query(
            """
            MATCH (c:Cluster {clusterId: $cluster_id})
            MATCH (t:Trend {trendId: $trend_id})
            MERGE (t)-[:SUMMARIZED_BY]->(c)
            """,
            params={"cluster_id": cluster_id, "trend_id": trend_id},
        )

    def link_cluster_to_capability(self, cluster_id, capability_id):
        self.kg.query(
            """
            MATCH (cl:Cluster {clusterId: $cluster_id})
            MATCH (ca:Capability {capabilityId: $capability_id})
            MERGE (cl)-[:DESCRIBED_BY]->(ca)
            """,
            params={"cluster_id": cluster_id, "capability_id": capability_id},
        )

    def link_class_to_chunk(self, class_id, chunk_id):
        self.kg.query(
            """
            MATCH (class:Class {classId: $class_id})
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            MERGE (class)-[:POSTED]->(chunk)
            """,
            params={"class_id": class_id, "chunk_id": chunk_id},
        )

    def link_chunk_to_insight(self, chunk_id, insight_id):
        self.kg.query(
            """
            MATCH (insight:Insight {insightId: $insight_id})
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            MERGE (chunk)-[:EXTRACTED_FROM]->(insight)
            """,
            params={"insight_id": insight_id, "chunk_id": chunk_id},
        )

    def link_chunk_to_trend(self, chunk_id, trend_id):
        self.kg.query(
            """
            MATCH (trend:Trend {trendId: $trend_id})
            MATCH (chunk:Chunk {chunkId: $chunk_id})
            MERGE (chunk)-[:EXTRACTED_FROM]->(trend)
            """,
            params={"trend_id": trend_id, "chunk_id": chunk_id},
        )

    def get_document_text(self, name):
        return self.kg.query(
            """
            MATCH (node {name: $name})-[r]->(doc:Document)
            RETURN doc.text
            """,
            params={"name": name},
        )

    def compute_embeddings(self, node="Chunk", field="text"):
        # logger.info(f"OPENAI_ENDPOINT: {self.OPENAI_ENDPOINT}")

        self.kg.query(
            f"""
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
            params={
                "openAiApiKey": self.OPENAI_API_KEY,
                "openAiEndpoint": self.OPENAI_ENDPOINT,
            },
        )

    @retry(number_of_retry=3)
    def compute_insight_embeddings_for_company(
        self, company="NAG", field="text", number_of_processes=5, bucket_size=50
    ):
        query = f"""MATCH (i:Insight)-[]-()-[]-()-[]-()-[]-(c:Company) 
        WHERE c.name = '{company}' AND 
            i.{field}Embedding IS NULL AND 
            i.{field} IS NOT NULL AND 
            SIZE(i.{field}) < 8192 AND SIZE(i.{field}) > 2
        return DISTINCT i.insightId as id"""
        nodes = self.kg.query(query)
        node = "Insight"
        lower_node = node.lower()
        l = len(nodes)
        with mp.Pool(number_of_processes) as pool:
            results = []
            for i in range((l // bucket_size) + 1):
                logger.info(f"\nnumber of nodes {l}")
                logger.info(f"Starting bucket: {i * bucket_size}")
                logger.info(f"ending bucket: {min((i + 1) * bucket_size, l)}")
                bucket_nodes_id = [
                    n["id"]
                    for n in nodes[i * bucket_size : min((i + 1) * bucket_size, l)]
                ]
                # logger.info(bucket_nodes_id)
                # logger.info(f"bucket list nodes: {bucket_nodes_id}")
                bucket_str_list_nodes = [str(b) for b in bucket_nodes_id]
                # self.compute_bucket_embeddings( bucket_str_list_nodes, node, lower_node, field)
                results.append(
                    pool.apply_async(
                        compute_bucket_embeddings,
                        args=(
                            bucket_str_list_nodes,
                            node,
                            lower_node,
                            field,
                        ),
                    )
                )
            while not all([r.ready() for r in results]):
                logger.info(
                    f"embeddings {[r.ready() for r in results].count(True)} / {len(results)} for {node}."
                )
                time.sleep(5)

    def compute_embeddings_parallel(
        self, node="Chunk", field="text", bucket_size=50, number_of_processes=5
    ):
        # logger.info(field)
        lower_node = node.lower()
        query = f"""MATCH (n:{node}) 
        WHERE n.{field}Embedding IS NULL AND 
            n.{field} IS NOT NULL AND 
            SIZE(n.{field}) < 8192 AND SIZE(n.{field}) > 2 
        return distinct n.{lower_node}Id as id"""
        nodes = self.kg.query(query)
        # logger.info(nodes)
        # logger.info(query)
        l = len(nodes)
        with mp.Pool(number_of_processes) as pool:
            results = []
            for i in range((l // bucket_size) + 1):
                logger.info(f"\nnumber of nodes {l}")
                logger.info(f"Starting bucket: {i * bucket_size}")
                logger.info(f"ending bucket: {min((i + 1) * bucket_size, l)}")
                bucket_nodes_id = [
                    n["id"]
                    for n in nodes[i * bucket_size : min((i + 1) * bucket_size, l)]
                ]
                # logger.info(bucket_nodes_id)
                # logger.info(f"bucket list nodes: {bucket_nodes_id}")
                bucket_str_list_nodes = [str(b) for b in bucket_nodes_id]
                # self.compute_bucket_embeddings( bucket_str_list_nodes, node, lower_node, field)
                results.append(
                    pool.apply_async(
                        compute_bucket_embeddings,
                        args=(
                            bucket_str_list_nodes,
                            node,
                            lower_node,
                            field,
                        ),
                    )
                )
            while not all([r.ready() for r in results]):
                logger.info(
                    f"embeddings {[r.ready() for r in results].count(True)} / {len(results)} for {node}."
                )
                time.sleep(5)
            # logger.info([r.get() for r in results])

    def link_close_chunks(self, threshold=0.85):
        self.kg.query(
            """
        MATCH (chunk1:Chunk), (chunk2:Chunk) WHERE chunk1.source <> chunk2.source
        WITH chunk1, chunk2, vector.similarity.cosine(chunk1.textEmbedding, chunk2.textEmbedding) AS similarity
        WHERE similarity > $threshold
        MERGE (chunk1)-[:SIMILAR {similarity: similarity}]-(chunk2)
        """,
            params={"threshold": threshold},
        )

    def link_close_insights(self, threshold=0.95):
        self.kg.query(
            """
        MATCH (chunk1:Insight), (chunk2:Insight) WHERE chunk1.company = 'Tesla' and chunk2.company = 'Tesla' and ID(chunk1) <> ID(chunk2)
        WITH chunk1, chunk2, vector.similarity.cosine(chunk1.descriptionEmbedding, chunk2.descriptionEmbedding) AS similarity
        WHERE similarity > $threshold
        MERGE (chunk1)-[:SIMILAR {similarity: similarity}]-(chunk2)
        """,
            params={"threshold": threshold},
        )

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
        similar = self.kg.query(
            vector_search_query,
            params={
                "question": question,
                "openAiApiKey": self.OPENAI_API_KEY,
                "openAiEndpoint": self.OPENAI_ENDPOINT,
                "index_name": VECTOR_INDEX_NAME,
                "top_k": top_k,
            },
        )
        return similar

    def create_vector_index(self):
        self.kg.query(
            """
         CREATE VECTOR INDEX `chunk_text` IF NOT EXISTS
          FOR (c:Chunk) ON (c.textEmbedding) 
          OPTIONS { indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'    
         }}
"""
        )

    def deep_search(self, depth, nodeType=None, node="n", relationship="r", where=None):
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
        logger.info(f"Query: {query}")
        return self.kg.query(query)

    # def sub_graph(self, nodeType=None, node='n',maxLevel=3, relationship='r', where=None):
    #     nodeType = ":"+nodeType if nodeType is not None else ''
    #     query = f"""MATCH ({node}{nodeType}) WHERE {where}
    #         CALL apoc.path.subgraphAll(c, {{maxLevel: {maxLevel}}}) YIELD nodes, relationships
    #         RETURN nodes, relationships"""
    #     logger.info(f"Query: {query}")
    #     return self.kg.query(query)

    # def sub_graph(self, node, nodeType=None, where=None):
    #     nodeType = node+":"+nodeType if nodeType is not None else node
    #     query = f"MATCH ({nodeType})-[*]-(connected) WHERE {where} AND {node} <> connected RETURN distinct connected"

    #     return self.kg.query(query)

    # def inject_sub_graph()

    def company_sub_graph(
        self, company, label_filters=[], relationship_exclusions=[], depth=8
    ):
        edges = self.kg.query("MATCH ()-[r]->() RETURN DISTINCT type(r) as edge")
        edges = [
            edge["edge"]
            for edge in edges
            if edge["edge"] not in relationship_exclusions
        ]
        # logger.info(edges)

        filters = (
            f"WITH [x IN nodes Where {' or '.join([f'(x:{label_filter})' for label_filter in label_filters]) }  ] AS nodes"
            if len(label_filters) > 0
            else " "
        )
        query = (
            f"""MATCH (c:Company {{name: '{company}'}})
    CALL apoc.path.subgraphAll(c, {{ 
            relationshipFilter: '{'|'.join(edges)}',
        minLevel: 0,
        maxLevel: {depth}
    }})
        YIELD nodes, relationships """
            + filters
            + """
        RETURN DISTINCT nodes;"""
        )

        return self.kg.query(query)[0]["nodes"]

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
