from langchain.evaluation import EmbeddingDistance
from langchain.evaluation import load_evaluator
from scipy.spatial.distance import cosine, euclidean, chebyshev, hamming
from pydantic import BaseModel, ConfigDict, Field, conint
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate
from socrates_main import (
    get_file_paths,
    get_company_data,
    get_trends,
    get_gics_code_and_name,
    generate_scenarios,
)
from graph_workflow.full_graph import (
    get_trends_from_gics_code,
    dump_company_graph_to_plain_txt,
    dump_company_graph_to_json,
)
from enum import Enum
from typing import Dict, List, Optional
from utility import dict_to_plain_text, invoke, embed, condense
import numpy as np
import time
import json
import sys
import multiprocessing as mp
import uuid

# from scenario_analysis import chain_scenario
from openai import OpenAI

client = OpenAI()


class Utility_Assessment(BaseModel):
    ParameterRequirements: List[str] = Field(
        description="A list of specific parameters and requirements needed to perform the utility assessment."
    )
    RequestedBy: str = Field(
        description="The name or identifier of the person or team requesting the utility assessment."
    )


class ProblemBreakdown(BaseModel):
    main_task: List[str] = Field(
        description="A list of primary actions or tasks that need to be addressed to solve the problem statement."
    )
    main_objective: List[str] = Field(
        description="A list of key goals or outcomes that the company aims to achieve by addressing the problem statement."
    )
    constraints_requirements: List[str] = Field(
        description="A list of limitations, constraints, and requirements that need to be considered when addressing the problem statement."
    )
    information_context: List[str] = Field(
        description="A list of background information and context necessary to understand the problem statement and the scenarios being analyzed."
    )
    definitions: List[str] = Field(
        description="A list of specific definitions for key terms and concepts mentioned in the problem statement to ensure clarity and precision."
    )
    concepts: List[str] = Field(
        description="A list of key concepts and theoretical ideas that are relevant to the problem statement and its solution."
    )


class Scenario(BaseModel):
    ScenarioID: str = Field(
        description="A unique identifier for the scenario being analyzed."
    )
    Description: str = Field(
        description="A detailed description of the scenario, including the strategic approach and actions proposed."
    )
    TrendsReferenced: List[str] = Field(
        description="A list of trends that are relevant to the scenario and affect the analysis."
    )
    Cost: int = Field(description="The estimated cost of implementing the scenario.")
    OpportunityCost: int = Field(
        description="The estimated opportunity cost of choosing this scenario over alternative options."
    )
    ValueGain: int = Field(
        description="The estimated potential value gain from implementing the scenario."
    )
    Risk: int = Field(
        description="The estimated level of risk associated with the scenario."
    )
    RiskAversionLambda: int = Field(
        description="A numerical value representing the company’s level of risk aversion, where higher values indicate greater aversion."
    )
    UtilityScore: int = Field(
        description="The calculated utility score of the scenario, representing its overall desirability after considering cost, opportunity cost, value gain, and risk."
    )


keys = [
    "ProblemStatement",
    "ProblemStatementBreakdown",
    "Scenarios",
    "UtilityAssessment",
    "Prioritization",
    "Analysis",
]


class Scenarios(BaseModel):
    ProblemStatement: str = Field(
        description="The specific strategic question or problem statement provided by the company that needs to be addressed."
    )
    ProblemStatementBreakdown: ProblemBreakdown = Field(
        description="A detailed breakdown of the problem statement into tasks, objectives, constraints, context, definitions, and concepts."
    )
    Scenarios: List[Scenario] = Field(
        description="A list of scenarios that have been analyzed, each with detailed descriptions and quantitative evaluations."
    )
    UtilityAssessment: Utility_Assessment = Field(
        description="An assessment of the utility of the scenarios, including parameter requirements and the requester information."
    )
    Prioritization: str = Field(
        description="The prioritization of the scenarios based on their utility scores and strategic fit. You have to explain in details why and how to prioritize the scenario, it should be clear for the executive to implement it."
    )
    Analysis: str = Field(
        description="The final comprehensive analysis, summarizing all the data, scenarios, evaluations, and recommendations. This analysis is used for critical strategic decision-making and must be thorough and factual, meeting a requirement of at least 3000 words. You have explain in details the analysis will details every element of the assessment and quote when possible."
    )


# Task Scenario Analysis Tesla


# scenario_output = chain_scenario.invoke(
#             {
#                 "problem_statement": problem,
#                 "trend_document": dict_to_plain_text(trends),
#                 "company_data": "\n****\n\n".join(insights),
#             }
#         )


# class Distances(Enum):
#     cosine = cosine
#     euclidean = euclidean
#     # manhattan = manhattan
#     chebyshev = chebyshev
#     hamming = hamming

Distances = {
    "cosine": cosine,
    "euclidean": euclidean,
    "chebyshev": chebyshev,
    "hamming": hamming,
}

# class EmbeddingFunction(Enum):
#     openAI = OpenAIEmbeddings

def scenario_wrapper(company_name, problemsFile, company_file, trend_file):
    _, scenarios_path = generate_scenarios(company_name, problemsFile, company_file, trend_file)
    scenario = json.load(open(scenarios_path))
    return scenario
    
def measure_stability(
    model, inputs, distance, embedding_function, n_samples=100, name=""
):
    with mp.Pool(mp.cpu_count()) as pool:
        # outputs = [pool.apply_async(model, args=(inputs,)) for _ in range(n_samples)]
        inputs = [inputs] * n_samples
        # print(f"\ninputs: {inputs}")
        outputs = pool.starmap(model, inputs)

    keys = [
        "ProblemStatement",
        "ProblemStatementBreakdown",
        "Scenarios",
        "UtilityAssessment",
        "Prioritization",
        "Analysis",
    ]

    # outputs = [json.load(open(output[1])) for output in outputs]
    print(f"\noutputs: {outputs}")
    [print(output.keys()) for output in outputs]
    # print(f"\noutputs: {outputs[0].keys()}")
    outputs = [output['output_schema'] if 'output_schema' in output.keys() else output for output in outputs]
    outputs = [
        {key: dict_to_plain_text(output[key]) for key in keys} for output in outputs
    ]

    # print(f"\nembeddings outputs: {outputs}")

    embeddings = np.array(
        [
            {
                # key: client.embeddings.create(
                #     input=output[key], model="text-embedding-3-large"
                # )
                # .data[0]
                # .embedding
                key: embed(text=output[key], model="text-embedding-3-large")
                for key in keys
            }
            for output in outputs
        ]
    )
    print(embeddings)
    # embeddings = np.array(embedding_function.embed_documents(outputs))
    # np.mean([[embedding[key] for key in keys] for embedding in embeddings], axis=0)
    means = {
        key: np.mean(np.array([embedding[key] for embedding in embeddings]), axis=0)
        for key in keys
    }
    # print(f"means: {means}")
    # print(f"means: {embeddings}")
    # print(np.shape(embeddings[0]["ProblemStatement"]))

    for key in keys:
        for embedding in embeddings:
            print("\n")
            print(np.shape(embedding[key]))
            print(np.shape(means[key]))
    distances = {
        key: [distance(means[key], embedding[key]) for embedding in embeddings]
        for key in keys
    }
    # print(f"distances: {distances}")
    results = {
        key: {
            "mean": np.mean(distances[key]),
            "std": np.std(distances[key]),
            "min": np.min(distances[key]),
            "max": np.max(distances[key]),
            "distances": distances[key],
        }
        for key in keys
    }

    print(f"Stability results: {results}")
    # Convert results to JSON format
    results_json = json.dumps(results)

    # Write results to a file
    if len(name) > 0:
        name = name + "_"
    with open("results_" + name + str(uuid.uuid4()) + ".json", "w") as f:
        f.write(results_json)
    return results


# COSINE = 'cosine'

# EUCLIDEAN = 'euclidean'

# MANHATTAN = 'manhattan'

# CHEBYSHEV = 'chebyshev'

# HAMMING = 'hamming'


evaluators = {
    "embedding_distance_cosine": load_evaluator(
        "embedding_distance", distance_metric=EmbeddingDistance.COSINE
    ),
    "evaluator_euclidian": load_evaluator(
        "embedding_distance", distance_metric=EmbeddingDistance.EUCLIDEAN
    ),
    "evaluator_manhattan": load_evaluator(
        "embedding_distance", distance_metric=EmbeddingDistance.MANHATTAN
    ),
    "evaluator_chebyshev": load_evaluator(
        "embedding_distance", distance_metric=EmbeddingDistance.CHEBYSHEV
    ),
    "evaluator_hamming": load_evaluator(
        "embedding_distance", distance_metric=EmbeddingDistance.HAMMING
    ),
}


scenario_instruction = """
You are providing support for a production workflow in a strategy consultancy. This is not a simulation, you must perform real analysis on real data that will be used by your colleagues to provide services for clients. 

You are the strategic scenario evaluator. You specialise in taking a set of data from a company, and some description of a strategic problem the company is facing, including some scenarios, and then generating a quantitative response to the problem question.  The input data contains three things a) data about the company in question b) a specific problem statement that we are trying to answer and c) trend data of trends that affect multiple industries. 

Input 1: A Problem Statement - a specific strategic question about the a company. Your job is to answer that question using scenario analysis. The  key for the simple dictionary is "problem_statement". 

Input 2: Curated trend data of noted trends that potentially affect this analysis. 

Input 3 : Data regarding this company and its capabilities. 




You will look at the various provided data and you will run through a multi-step process.  You should express all your analysis in terms of the provided company's products, markets, capabilities and resources. 

It is essential that you realise that this is a real exercise, not a template for generating real data later. Although you may not have access to up-to-date information and real-time data, this is not important. You have general knowledge that can lead to realistic best estimates of numerical data that you can use in your scenario modelling. To generate best-guess data from learned observations is your expertise. Be careful and digest all of the company's capabilities. Examine every insight for clues as to where real data estimates may come from. Do not make wild guesses, but based your reasoned estimates in the real world knowledge you have available and in the dataset (combined). 

STEP 0) Reproduce the input file contents to make sure that they are as required. Not summarise or change the inputs, this will result in drastic problems in the client delivery. Just reproduce some data from each file and show that it is correct. 

STEP 1) breakdown the problem statement logically. From the original problem statement, produce the following 

    "problem_statement_breakdown": {
        "main_task": [],
        "main_objective": [],
        "constraints_requirements": [],
        "information_context": [],
        "definitions": [],
        "concepts": []
    }

STEP 2) Consider what scenarios to model to solve the problem for this company. Pay attention to the trends that affect this company and the severity of those trends. For each scenario that you wish to model, perform steps 2-6.
STEP 3) estimate the cost of that scenario, pay attention to the capabilities of the company - store this as C
STEP 4) estimate the opportunity cost of attending to the scenario - pay attention to the products and strengths of the products in the markets - store this value as O
STEP 5) estimate the potential value gain in attending to the scenario. - pay attention to market  and competitive trends. Store this as V
STEP 6) estimate the risk aversion for this company. Pay attention to any cultural, regulatory or other indicators that suggest the company is highly risk averse.  Store this as Lamda, where the value is between -infinity (ultra risk taking) to infinity (ultra risk-averse) with zero being the neutral state. 
STEP 7) calculate the utility per scenario : U(x)=R(x)−C(x)−λ⋅Risk(x)
STEP 8) Generate your output. Your output will be an updated json object with the scenarios completed, expressed in terms of the other model parameters. Produce a json output adding the cost, opportunity cost, risk, risk aversion and utility scores to each provided scenario. 

Your data should adhere to the following schema : 


The prioritization that you choose should relate to the problem statement. How do the scenarios that you have evaluated solve the problem? All strategies are resource-constrained decisions. You should not recommend several things, each scenario should be in trade-off with most other options. You should choose one based on the analysis, then describe the impact of both doing it and not doing it. refer to the trends that have been noticed, and the capabilities of the company, they are the main drivers and levers of this decision. 

Your work will be subject to QM by a QM strategy specialist who will ask you to adhere to the schema and the quality requirements. Do not pass back to the user a sample or simulated or incomplete attempt to generate the scenarios. The guidance you need is here in this description, so please read it carefully and then follow the guidance to try and solve the task. QMs are not there to ask questions to. 

Record every step of the reasoning. in your analysis section. You cannot provide too much detail. The analysts need to see how you arrived at every single calculation. When you refer to a capability, cite the insights that have led to this. When you cite any secondary analysis, re-state the reasoning and analysis. Your analysis should contain every step of the reasoning and calculation with meticulous detail. 

"""

model_scenario = ChatOpenAI(model="gpt-4o", temperature=0.0)
parser_scenario = JsonOutputParser(pydantic_object=Scenarios)
get_scenario = PromptTemplate(
    template="""Follow the instructions:
***
{instruction}
***

For the company {company_name}, based on the following problem:
***
{problem_statement}
***

using the current trends: '
***
{trend_document}
***

using company data: '
***
{company_data}
***


***
{format_instructions}
***""",
    input_variables=[
        "problem_statement",
        "trend_document",
        "company_data",
        "company_name",
    ],
    partial_variables={
        "format_instructions": parser_scenario.get_format_instructions(),
        "instruction": scenario_instruction,
    },
)


chain_scenario = get_scenario | model_scenario | parser_scenario


def use_chain_scenario(company_name, problemsFile, company_file, trend_file):
    # problem_file_path, trends_file_path, company_file_path = get_file_paths(
    #     company_name, problemsFile
    # )

    # print(
    #     f"""
    #       company_name: {company_name}
    #       problemsFile: {problemsFile}
    #       problem_file_path: {problem_file_path}
    #       trends_file_path: {trends_file_path}
    #       company_file_path: {company_file_path}
    #       """
    # )
    problem = json.load(open(problemsFile))
    trends = json.load(open(trend_file))
    company = json.load(open(company_file))

    output = invoke(
        chain_scenario,
        {
            "problem_statement": dict_to_plain_text(problem),
            "trend_document": dict_to_plain_text(trends),
            "company_data": dict_to_plain_text(company),
            "company_name": company_name,
        },
    )
    # output = chain_scenario.invoke(
    #     {
    #         "problem_statement": dict_to_plain_text(problem),
    #         "trend_document": dict_to_plain_text(trends),
    #         "company_data": dict_to_plain_text(company),
    #         "company_name": company_name,
    #     }
    # )

    return output


if __name__ == "__main__":
    # (model, inputs, distance, embedding_function, n_samples=100)
    problem = json.load(open("Intermediates/local_problem_Tesla.json"))
    # g_code, _ = get_gics_code_and_name("Tesla")
    # trends = get_trends_from_gics_code(g_code, problem)
    # with open("Intermediates/trends.json", "w") as f:
    #     json.dump(trends, f)
    # print(trends)
    # trends = dict_to_plain_text(json.load(open("Intermediates/trends.json")))
    print(problem)
    #     trends = json.load(open("Intermediates/trends.json"))
    #     # trends = [*x for x in ]
    #     trends = [x for l in trends["trends"] for x in l]
    #     context = problem
    #     subject = """
    # The trends that can impact Tesla
    #     """
    #     condensed_trends = condense(
    #         trends,
    #         "statement",
    #         context,
    #         subject,
    #         number_of_clusters=10,
    #         number_of_processes=5,
    #     )
    #     with open("Intermediates/condensed_trends.json", "w") as f:
    #         json.dump(condensed_trends, f)
    #     print(
    #         f"""Condense: {[len(x) for x in condensed_trends]}
    # versus {len(dict_to_plain_text(json.load(open("Intermediates/trends.json"))))}
    # """
    #     )

    with open("Intermediates/condensed_trends.json", "r") as f:
        condensed_trends = json.load(f)
    print(condensed_trends)
    print("Condensed trends")
    #     assert False
    # company_data = dump_company_graph_to_json("Tesla", problem)

    # # Write problem as JSON file
    # with open("Intermediates/company_data.json", "w") as f:
    #     json.dump(company_data, f)

    #     company_data_full = json.load(open("Intermediates/company_data.json"))
    #     # trends = [*x for x in ]
    #     company_data = [x for l in company_data_full["insights"] for x in l]
    #     company_data.extend([x for l in company_data_full["capabilities"] for x in l])
    #     context = problem
    #     subject = """
    # The insights and capabilities of Tesla
    #     """
    #     condensed_company_data = condense(
    #         company_data,
    #         "statement",
    #         context,
    #         subject,
    #         number_of_clusters=50,
    #         number_of_processes=5,
    #     )
    #     with open("Intermediates/condensed_company_data.json", "w") as f:
    #         json.dump(condensed_company_data, f)
    #     print(
    #         f"""Condense: {[len(x) for x in condensed_company_data]}
    # versus {len(dict_to_plain_text(json.load(open("Intermediates/company_data.json"))))}
    # """
    #     )

    with open("Intermediates/condensed_company_data.json", "r") as f:
        condensed_company_data = json.load(f)
    # Write trends as JSON file
    # with open("Intermediates/trends.json", "w") as f:
    #     json.dump(trends, f)

    # company_name, problemsFile, company_file, trend_file
    inputs = (
        "Tesla",
        "./problem_statements.json",
        "Intermediates/condensed_company_data.json",
        "Intermediates/condensed_trends.json",
    )
    # print(
    #     measure_stability(
    #         use_chain_scenario,
    #         inputs,
    #         Distances["cosine"],
    #         None,
    #         50,
    #         name='chains'
    #     )
    # )

    print(
        measure_stability(
            scenario_wrapper, inputs, Distances["cosine"], None, 50, name="assistants"
        )
    )
