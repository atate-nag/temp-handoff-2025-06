from neo4j import GraphDatabase

class BaseGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

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
        MATCH (c:Company {name: $company_name})-[:PROVIDES_INSIGHT_ON]->(i:Insight)
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

class InsightGraph(BaseGraph):
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def add_insight(self, insight_data, company_name):
        with self.driver.session() as session:
            session.write_transaction(self._create_insight_and_link, insight_data, company_name)

    @staticmethod
    def _create_insight_and_link(tx, insight_data, company_name):
        query = (
            "MATCH (c:Company {name: $company_name}) "
            "CREATE (i:Insight {id: $id, description: $description, source: $source}) "
            "MERGE (i)-[:PROVIDES_INSIGHT_ON]->(c)"
        )
        for insight in insight_data:
            # Generate a unique UUID for each insight
            unique_id = str(uuid.uuid4())
            tx.run(query, company_name=company_name, id=unique_id, description=insight['description'],
                   source=insight['sourceDocument'])


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
