import json
from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
user = "neo4j"
password = ""
database = "neo4j"

with open(f"basic_company_data.json", "r", encoding="utf-8") as f:
    # write to file
    file_contents = f.read()
    parsed_json = json.loads(file_contents)

keys = [
    "name",
    "industry",
    "city",
    "state",
    "zip",
    "website",
    "Employees",
    "Revenue",
    "Valuation",
    "Profits",
    "Profits percent",
    "Ticker",
    "CEO",
    "description",
    "products",
]
for company_dict in parsed_json:
    company_name = company_dict["name"]
    company_data = {key: company_dict[key] for key in keys}
    query = (
        "MERGE (c:Company {name: $company_name}) " "SET c += $company_data " "RETURN c"
    )
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database=database) as session:
        result = session.run(
            query, company_name=company_name, company_data=company_data
        )
