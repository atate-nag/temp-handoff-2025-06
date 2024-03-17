from neo4j import GraphDatabase
from datetime import datetime
from utility import clean_text
import uuid
import json
import logging
class BaseGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def retrieve_entire_graph(self):
        with self.driver.session() as session:
            result = session.run(
                "MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m"
            )
            for record in result:
                print(record)

class CompanyGraph(BaseGraph):
    def delete_company(self, company_name):
        with self.driver.session() as session:
            session.write_transaction(self._delete_company_node, company_name)

    def add_company_info(self, company_name, company_data):
        with self.driver.session() as session:
            session.write_transaction(self._create_or_update_company_node, company_name, company_data)

    def create_company_only(self, company_name):
        with self.driver.session() as session:
            session.write_transaction(self._create_company_node_without_data, company_name)
        print(f"CompanyGraph: created a node for {company_name}")

    def delete_company_insights(self, company_name):
        with self.driver.session() as session:
            session.write_transaction(self._prune_company_insights, company_name)

    def delete_orphan_insights(self):
        with self.driver.session() as session:
            session.write_transaction(self._prune_orphan_insights)

    @staticmethod
    def _prune_orphan_insights(tx):
        query = """
        MATCH (i:Insight)
        WHERE NOT (i)-[:PROVIDES_INSIGHT_ON]->(:Company)
        DETACH DELETE i
        """
        tx.run(query)

    @staticmethod
    def _prune_company_insights(tx, company_name):
        query = """
        MATCH (i:Insight)-[:PROVIDES_INSIGHT_ON]->(c:Company {name: $company_name})
        DETACH DELETE i
        """
        tx.run(query, company_name=company_name)

    @staticmethod
    def _delete_company_node(tx, company_name):
        query = """
        MATCH (c:Company {name: $company_name})
        DETACH DELETE c
        """
        tx.run(query, company_name=company_name)

    def get_company_info(self, company_name):
        with self.driver.session() as session:
            result = session.read_transaction(self._retrieve_company_node, company_name)
            return result

    @staticmethod
    def _retrieve_company_node(tx, company_name):
        query = """
        MATCH (c:Company {name: $company_name})
        RETURN c AS company
        """
        result = tx.run(query, company_name=company_name).single()
        if result:
            return result["company"]._properties
        else:
            return None

    @staticmethod
    def _create_or_update_company_node(tx, company_name, company_data):
        query = (
            "MERGE (c:Company {name: $company_name}) "
            "SET c += $company_data "
            "RETURN c"
        )
        result = tx.run(query, company_name=company_name, company_data=company_data)
        return result.single()

    @staticmethod
    def _create_company_node_without_data(tx, company_name):
        query = (
            "CREATE (c:Company {name: $company_name}) "
            "RETURN c"
        )
        result = tx.run(query, company_name=company_name)
        return result.single()
    def dump_company_graph_to_json(self, company_name):

        '''dumps the whole company graph to json including all fields of the insight nodes. This is useful for
        printing and debugging but is probably overkill to agents. Instead,  use the
        dump_company_insight_graph_to_json method to send more selective information to agents'''

        with self.driver.session() as session:
            # Example Cypher query to retrieve a company, its insights, and relationships
            result = session.run("""
                MATCH (i:Insight)-[r:PROVIDES_INSIGHT_ON]->(c:Company {name: $company_name})
                RETURN c AS company, collect(i) AS insights, collect(type(r)) AS relationships
            """, company_name=company_name)

            # Assuming only one company node is targeted ( TODO support more companies also later?)
            record = result.single()
            if record:
                # Construct a dict structure for the company and its insights
                graph_data = {
                    "company": record["company"]._properties,
                    "insights": [insight._properties for insight in record["insights"]],
                }
                # Serialize to JSON
                json_data = json.dumps(graph_data, indent=4)
                return json_data
            else:
                return None

    def delete_company_capabilities(self, company_name):
        with self.driver.session() as session:
            session.write_transaction(self._delete_company_capabilities, company_name)

    @staticmethod
    def _delete_company_capabilities(tx, company_name):
        query = """
        MATCH (c:Company {name: $company_name})-[:POSSESSES]->(b: Capability)
        DETACH DELETE b
        """
        tx.run(query, company_name=company_name)

    def dump_company_insight_graph_to_json(self, company_name):

        ''' this function does not dump the full graph, it will only return the true insight ID , description
        and confidence of the insight. Then a walker will be able to derive the provenance of relationships'''

        with self.driver.session() as session:
            # Example Cypher query to retrieve a company, its insights, and relationships
            result = session.run("""
                   MATCH (i:Insight)-[r:PROVIDES_INSIGHT_ON]->(c:Company {name: $company_name})
                   RETURN c AS company, collect(i) AS insights, collect(type(r)) AS relationships
               """, company_name=company_name)
            # Assuming only one company node is targeted; adjust as needed for your schema
            record = result.single()
            if record:
                # Construct a dict structure for the company and its insights
                graph_data = {
                    "company": record["company"]._properties,
                    "insights": [
                        {
                            # Directly access properties from the Node object
                            "id": insight.id,  # Accessing the Neo4j internal ID of the node
                            "description": clean_text(insight["description"]),  # Directly access the 'description' property
                            "relevanceScore": insight.get("relevanceScore", None)  # Safely get 'confidenceScore'
                        }
                        for insight in record["insights"] if insight is not None  # Ensure insight is not None
                    ]
                }
                # Serialize to JSON
                json_data = json.dumps(graph_data, indent=4)
                return json_data
            else:
                return None

    def add_capability_and_evidence(self, company_name, capability_data):
        with self.driver.session() as session:
            session.write_transaction(self._create_capability_and_link, company_name, capability_data)

    @staticmethod
    def _create_capability_and_link(tx, company_name, capability_data):
        for capability in capability_data:
            # Create the Capability node and link it to the Company node
            name = capability["capability"]
            capability_result = tx.run(
                "MATCH (company:Company {name: $companyName}) "
                "CREATE (capability:Capability {uuid: $uuid, name: $name, valuePotential: $valuePotential, "
                "scarcity: $scarcity, nonReplicability: $nonReplicability, "
                "irreplaceability: $irreplaceability, confidence: $confidence}) "
                "MERGE (company)-[:POSSESSES]->(capability) "
                "RETURN capability",
                uuid=str(uuid.uuid4()),
                companyName=company_name,
                name=name,
                valuePotential=capability["value potential"],
                scarcity=capability["scarcity"],
                nonReplicability=capability["non-replicability"],
                irreplaceability=capability["irreplaceability"],
                confidence=capability["confidence"]
            ).single()[0]

            for insight_id in capability["evidenced by"]:
                print(f"evidence from {insight_id} for capability {name}")
                tx.run(
                    "MATCH (cap:Capability {name: $name}), (i:Insight) "
                    "WHERE ID(i) = $insight_id "
                    "MERGE (cap)-[:EVIDENCED_BY]->(i)",
                    name=name, insight_id=insight_id
                )
    def display_company_capabilities(self, company_name):
        with self.driver.session() as session:
            result = session.read_transaction(self._get_company_capabilities, company_name)
            #print(f"display result is {result}")
            # for capability, insights in result:
            #     print(f"insights for {capability}are {insights}")
            # import sys
            # print(f"Printing capabilities {capabilities} with insights ?")
            self._print_capabilities(result)

    @staticmethod
    def _get_company_capabilities(tx, company_name):
        query = """
                MATCH (company:Company {name: $company_name})-[:POSSESSES]->(capability:Capability)
                OPTIONAL MATCH (capability)-[:EVIDENCED_BY]->(insight:Insight)
                RETURN capability AS Capability, collect({id: ID(insight), description: insight.description, source: insight.source, relevanceScore: insight.relevanceScore, extractionDate: insight.extractionDate}) AS Insights
                """
        result = tx.run(query, company_name=company_name)
        return [(record["Capability"], record["Insights"]) for record in result]


    def _print_capabilities(self, capabilities):
        for capability, insights in capabilities:
            print(f"Capability: {capability['name']}")
            print(f"Details:")
            print(f"  Value Potential: {capability['valuePotential']}")
            print(f"  Scarcity: {capability['scarcity']}")
            print(f"  Non-replicability: {capability['nonReplicability']}")
            print(f"  Irreplaceability: {capability['irreplaceability']}")
            print(f"  Confidence: {capability['confidence']}")
            print("Derived from Insights:")
            print(f"  - Insight ID:")
            for insight in insights:
                print({insight['id']})
                #"Description: {insight['description']}, Source: {insight['source']}, Relevance Score: {insight['relevanceScore']}, Extraction Date: {insight['extractionDate']}")
            print("\n")

    def prune_company_capabilities(self, company_name):
        with self.driver.session() as session:
            session.write_transaction(self._prune_company_capability, company_name)

    def link_insight_to_capability(self, capability_name, insight_id):
        with self.driver.session() as session:
            session.write_transaction(self._link_insight_to_capability, capability_name, insight_id)

    @staticmethod
    def _prune_company_capability(tx, company_name):
        query = """
            MATCH (c:Capability)
            WHERE NOT (c)-[:EVIDENCED_BY]->(:Insight)
            OPTIONAL MATCH (c)-[r]-()
            DELETE r, c"""
        tx.run(query, company_name=company_name)

    @staticmethod
    def _link_insight_to_capability(tx, capability_name, insight_id):
        query = """
        MATCH (cap:Capability {name: $capability_name})
        MATCH (i:Insight)
        WHERE ID(i) = $insight_id
        CREATE (cap)-[:EVIDENCED_BY]->(i)
        RETURN cap, i
        """
        result = tx.run(query, capability_name=capability_name, insight_id=insight_id)
        return result.single()

class InsightGraph(BaseGraph):
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def add_insight(self, insight_data, company_name):
        with self.driver.session() as session:
            session.write_transaction(self._create_insight_and_link, insight_data, company_name)

    def get_company_insights_above_relevance(self, company_name, relevance_threshold):
        with self.driver.session() as session:
            result = session.read_transaction(self._find_company_insights_above_relevance, company_name,
                                              relevance_threshold)
            print(f"result is {result}")
            return [record["i"]._properties for record in result]

    @staticmethod
    def _find_company_insights_above_relevance(tx, company_name, relevance_threshold):
        print(f"Company name is {company_name} and relevance threshold is {relevance_threshold}")
        query = """
        MATCH (i: Insight) - [:PROVIDES_INSIGHT_ON] -> (c:Company {name: $company_name}) 
        WHERE i.relevanceScore >= $relevance_threshold
        RETURN i
        """
        print(query)
        result = tx.run(query, company_name=company_name, relevance_threshold=relevance_threshold)
        return list(result)

    from datetime import datetime
    import uuid

    @staticmethod
    def _create_insight_and_link(tx, insight_data, company_name):
        # Define the query outside the loop to ensure it's available
        query = (
            "MATCH (c:Company {name: $company_name}) "
            "CREATE (i:Insight {id: $id, description: $description, categories: $categories, "
            "relevanceScore: $relevanceScore, source: $source, extractionDate: $extractionDate}) "
            "MERGE (i)-[:PROVIDES_INSIGHT_ON]->(c)"
        )

        # Ensure insight_data is a list
        if not isinstance(insight_data, list):
            logging.error("Insight data is not in expected format (list).")
            return  # Optionally, raise an exception

        for insight in insight_data:
            # Ensure each insight is a dictionary
            if not isinstance(insight, dict):
                logging.warning(f"Skipping invalid insight format: {insight}")
                continue  # Skip this iteration

            # Ensure 'categories' is a list and 'extractionDate' is properly formatted
            categories = insight.get('categories', [])
            extractionDate = insight.get('extractionDate', datetime.today().strftime('%Y-%m-%d'))

            # Generate a unique UUID for each insight if not provided
            unique_id = insight.get('id', str(uuid.uuid4()))

            # Execute the query with all provided insight data
            tx.run(query, company_name=company_name, id=unique_id, description=insight.get('description', ''),
                   categories=categories, relevanceScore=insight.get('relevanceScore', 0),
                   source=insight.get('sourceDocument', ''), extractionDate=extractionDate)

    def remove_non_integer_ids(self):
        with self.driver.session() as session:
            modified_count = session.write_transaction(self._remove_non_integer_ids)
            print(f"Modified {modified_count} nodes.")
        return

    @staticmethod
    def _remove_non_integer_ids(tx):
        # This query fetches IDs that are non-integer strings.
        # It assumes all IDs should be numeric, and any non-numeric string is invalid.
        query = """
        MATCH (i:Insight)
        WHERE NOT i.id =~ '^\\d+$'  
        REMOVE i.id  
        RETURN count(i) as modifiedCount
        """
        result = tx.run(query)
        return result.single()[0]

def map_json_to_company_schema(company_data):
    company_node_data = {}
    for child in company_data['children']:
        if child['title'] == "Name":
            company_node_data['Name'] = child['content'][0]
        elif child['title'] == "HQ":
            company_node_data['HQ'] = child['content'][0]
        # Continue for other fields...
        elif child['title'] == "Leadership":
            company_node_data['Leadership'] = ', '.join(child['content'])
        # Handle nested children for products, services, markets, etc.
        elif child['title'] == "Products and services":
            for grandchild in child['children']:
                if grandchild['title'] == "Products":
                    company_node_data['Products'] = grandchild['content']
                elif grandchild['title'] == "Services":
                    company_node_data['Services'] = grandchild['content']
        # Add more conditions as needed for other fields

    return company_node_data
