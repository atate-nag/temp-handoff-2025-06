get_nodes_per_company = """
    MATCH (c:Company {name: '{company}'})
    CALL apoc.path.subgraphAll(c, { 
            relationshipFilter: '||',
        minLevel: 0,
        maxLevel: {depth}
    })
        YIELD nodes, relationships 
        WITH [x IN nodes Where x:{node1} or x:{node2} ] AS nodes
        RETURN DISTINCT nodes;
"""

get_edges = """
    MATCH ()-[r]->() RETURN DISTINCT type(r) as edge
"""


t = """ MATCH (c:Company {name: 'Tesla'})
    CALL apoc.path.subgraphAll(c, { 
            relationshipFilter: 'CONTAINS|DESCRIBED_BY|SPECIFIED_BY|EXTRACTED_FROM|SUMMARIZED_BY',
        minLevel: 0,
        maxLevel: 7
    })
        YIELD nodes, relationships 
        RETURN distinct nodes;
    """

delete = """
MATCH (c:Company {name: 'Tesla'})
    CALL apoc.path.subgraphAll(c, { 
            relationshipFilter: 'CONTAINS|DESCRIBED_BY|SPECIFIED_BY|EXTRACTED_FROM|SUMMARIZED_BY',
        minLevel: 0,
        maxLevel: 6
    })
        YIELD nodes, relationships 
        WITH [x IN nodes Where x:Cluster or x:Capability ] AS nodes
        unwind nodes as n
        detach delete n;"""
