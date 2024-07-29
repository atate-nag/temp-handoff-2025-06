from pydantic import BaseModel, create_model, Field
from typing import Dict, List, Tuple, Optional
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json
from report import Report, contentSection

# from utility import dict_to_plain_text, invoke


def build_chain_action(tools):
    action_class = create_model(
        "ActionOutput",
        **{
            "action": (
                Optional[List[tools]],
                Field(description="List of actions to trigger"),
            ),
            "explanation": (
                str,
                Field(description="Explain why you want to trigger the action."),
            ),
        },
    )

    model_action = ChatOpenAI(model="gpt-4o", temperature=0.1)
    parser_action = JsonOutputParser(pydantic_object=action_class)
    prompt_action = PromptTemplate(
        template="""

""",
        input_variables=[],
        partial_variables={
            "format_instructions": parser_action.get_format_instructions()
        },
    )

    return prompt_action | model_action | parser_action


class Statement(BaseModel):
    statement: str = Field(description="The statement extracted from the document.")
    source: str = Field(description="The source of the statement.")
    quote: str = Field(description="A quote that demonstrate the statement.")
    relevant: bool = Field(
        description="Whether the statement is relevant to the problem statement."
    )


class validation_trend_cluster(BaseModel):
    Validated: bool = Field(
        description="Whether the trend cluster is useful for the problem statement."
    )
    Explanation: str = Field(
        description="Explanation of why the trend cluster is useful for the problem statement. and how to use it."
    )
    Statements: List[Statement] = Field(
        description="List of statements given by the trend."
    )


parser_trend_cluster = JsonOutputParser(pydantic_object=validation_trend_cluster)

prompt_trend_cluster = PromptTemplate(
    template="""Considering the following problem statement:
***
{problem_statement}
***

Analyse the trend cluster and determine if it is very useful for the problem statement. Provide an explanation of why the trend cluster is useful for the problem statement and how to use it:
***
{trend_summary}
***


{format_instructions}
""",
    input_variables=["trend_summary", "problem_statement"],
    partial_variables={
        "format_instructions": parser_trend_cluster.get_format_instructions()
    },
)


model_trend_cluster = ChatOpenAI(model="gpt-4o", temperature=0.1)

evaluate_trend_cluster = (
    prompt_trend_cluster | model_trend_cluster | parser_trend_cluster
)


###############


class validation_insights_cluster(BaseModel):
    Validated: bool = Field(
        description="Whether the insight cluster is useful for the problem statement."
    )
    Explanation: str = Field(
        description="Explanation of why the insight cluster is useful for the problem statement. and how to use it."
    )
    Statements: List[Statement] = Field(
        description="List of statements given by the insight cluster."
    )


parser_insight_cluster = JsonOutputParser(pydantic_object=validation_insights_cluster)

prompt_insight_cluster = PromptTemplate(
    template="""Considering the following problem statement:
***
{problem_statement}
***

Analyse the insight cluster and determine if it is very useful for the problem statement. Provide an explanation of why the insight cluster is useful for the problem statement and help understand {company} and how to use it:
***
{insights_summary}
***


{format_instructions}
""",
    input_variables=["insights_summary", "problem_statement", "company"],
    partial_variables={
        "format_instructions": parser_insight_cluster.get_format_instructions()
    },
)


model_insight_cluster = ChatOpenAI(model="gpt-4o", temperature=0.1)

evaluate_insight_cluster = (
    prompt_insight_cluster | model_insight_cluster | parser_insight_cluster
)


##################


class validation_capabilities_cluster(BaseModel):
    Validated: bool = Field(
        description="Whether the capability cluster is useful for the problem statement."
    )
    Explanation: str = Field(
        description="Explanation of why the capability cluster is useful for the problem statement. and how to use it."
    )
    Statements: List[Statement] = Field(
        description="List of statements given by the capability cluster."
    )


parser_capability_cluster = JsonOutputParser(
    pydantic_object=validation_capabilities_cluster
)

prompt_capability_cluster = PromptTemplate(
    template="""Considering the following problem statement:
***
{problem_statement}
***

Analyse the capability cluster and determine if it is very useful for the problem statement. Provide an explanation of why the capability cluster is useful for the problem statement and help understand {company} and how to use it:
***
{capabilities_summary}
***


{format_instructions}
""",
    input_variables=["capabilities_summary", "problem_statement", "company"],
    partial_variables={
        "format_instructions": parser_capability_cluster.get_format_instructions()
    },
)


model_capability_cluster = ChatOpenAI(model="gpt-4o", temperature=0.1)

evaluate_capability_cluster = (
    prompt_capability_cluster | model_capability_cluster | parser_capability_cluster
)


condense_model = ChatOpenAI(model="gpt-4o", temperature=0.9)
condense_parser = StrOutputParser()
condense_prompt = ChatPromptTemplate.from_template(
    template="""
This is the content statements extracted about {subject}:
*****
{content}
*****

This is the context for your task:
*****
{context}
*****

You have to create a summary of the content, you have to include citation and be factual. 

Your output will be used in strategic analysis and decision making. 
Format your output in a way that is easy to read and understand in prose.
"""
)

# Define the summary chain
condense_chain = condense_prompt | condense_model | condense_parser


############### Scenario Chain


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


#################### Framework Chain


class Capability(BaseModel):
    NameOfCapability: str = Field(
        description="The name of the specific capability of the company being analyzed."
    )
    Description: str = Field(
        description="A detailed description of the capability, including its relevance to the problem statement and its role within the company."
    )
    Importance: int = Field(
        description="A numerical score representing the importance of the capability in relation to the problem statement, assessed on axes such as Value Potential, Scarcity, Irreplaceability, and nonReplicability."
    )


class Framework(BaseModel):
    NameOfStrategicFramework: str = Field(
        description="The name of the strategic framework being applied to the problem statement (e.g., SWOT Analysis, PESTEL Analysis)."
    )
    Description: str = Field(
        description="A detailed description of the strategic framework, explaining how it is applied to analyze the problem and its relevance to the company’s situation."
    )
    TrendsReferenced: List[str] = Field(
        description="A list of trends that are relevant to the application of the strategic framework and the analysis of the problem."
    )
    Analysis: str = Field(
        description="Perform the analysis with the give framework and explain the results"
    )


class FrameworkAnalysis(BaseModel):
    ProblemStatement: str = Field(
        description="The specific strategic question or problem statement provided by the company that needs to be addressed."
    )
    problem_statement_breakdown: ProblemBreakdown = Field(
        description="A detailed breakdown of the problem statement into tasks, objectives, constraints, context, definitions, and concepts."
    )
    CapabilityAnalysis: List[Capability] = Field(
        description="An analysis of the company’s capabilities, including their importance and relevance to the problem statement."
    )
    StrategicFrameworks: List[Framework] = Field(
        description="A list of strategic frameworks applied to the problem, with detailed descriptions and references to relevant trends. Make sure to apply serveral framework analysis to give complete landscape to your audience"
    )
    Prioritization: str = Field(
        description="The prioritization of the strategic frameworks and capabilities based on their importance and relevance to solving the problem statement."
    )
    Analysis: str = Field(
        description="The final comprehensive analysis, summarizing all the data, capabilities, strategic frameworks, evaluations, and recommendations. This analysis is used for critical strategic decision-making and must be thorough and factual, meeting a requirement of at least 3000 words."
    )


frameworks_instruction = """
You are providing support for a production workflow in a strategy consultancy. This is not a simulation, you must perform real analysis on real data that will be used by your colleagues to provide services for clients. 

You are the strategic framework evaluator. You specialise in taking a set of data from a company, and some description of a strategic problem the company is facing and then generating a high-level framework analysis. You specialise in strategic frameworks in action. In particular you must always include a capability analysis, in which you assess the company's capabilities as it relates to the problem statement. 

The input files provide contain (do not load these files yet):

Input 1: A Problem Statement - a specific strategic question about the a company. Your job is to answer that question using scenario analysis. 
     
Input 2: Curated trend data of noted trends that potentially affect this analysis. 

Input 3 : Data regarding this company and its capabilities. 

** multi-step report generation ** 

Follow a multi process to perform the strategic analysis. 

Step 1: Load and examine the input files. 

Step 2: Create your output structure, with the following form

Step 3: Break down the problem statement. Create a set of questions that can be solved with strategic frameworks. Do not choose scenario analysis as that has been performed by other agents. Store the problem break down. Generate:
          "MainTask",
          "MainObjective",
          "ConstraintsRequirements",
          "InformationContext",
          "Definitions",
          "Concepts"
And focus your breakdown on the types of problem that can be solved with strategic frameworks. 

Step 4: Do a capability analysis. Study the capabilities from Input 3 as they relate to the problem. Score the capabilities on 4 axes - Value Potential, Scarcity, Irreplaceability, nonReplicability. Add a weight to each of those categories and calculate a total score for each capabilty. Look at any capabilities that have high combined scores. Create a short-list of capabilities that are either risks (as the scores are low) or opportunties because the scores are high. But most importantly, select the capabilities of most relevance to the problem statement, and asses the company's ability to respond. 

Step 5:
Choose one other framework from the following list and apply it to the problem:

SWOT Analysis: Identifies strengths, weaknesses, opportunities, and threats.
PESTEL Analysis: Assesses the external macro-environmental factors (Political, Economic, Social, Technological, Environmental, Legal).
Porter’s Five Forces: Evaluates industry competitiveness through five key forces: competition, potential entrants, substitutes, suppliers, and customers.
Value Chain Analysis: Analyzes internal company activities to understand how value is created.
BCG Matrix: Assesses the company's portfolio of products or business units based on market growth and market share.
VRIO Framework: Evaluates resources and capabilities to determine if they can provide sustained competitive advantage (Value, Rarity, Imitability, Organization).
McKinsey 7S Framework: Analyzes organizational effectiveness through seven interdependent factors: Strategy, Structure, Systems, Shared Values, Skills, Style, and Staff.
Balanced Scorecard: Measures organizational performance from four perspectives: Financial, Customer, Internal Processes, and Learning & Growth.
Ansoff Matrix: Identifies growth strategies through market penetration, market development, product development, and diversification.
GE/McKinsey Matrix: Evaluates business units based on industry attractiveness and business strength.
Porter’s Diamond Model: Analyzes the competitive advantage of nations or regions through four determinants: Factor Conditions, Demand Conditions, Related and Supporting Industries, Firm Strategy, Structure, and Rivalry.
Business Model Canvas: Visualizes the company's value proposition, infrastructure, customers, and finances.
Blue Ocean Strategy: Identifies opportunities for creating new, uncontested market spaces.
Core Competence Analysis: Identifies and evaluates the company’s core competencies.
Scenario Analysis: Explores and prepares for multiple future scenarios to understand potential impacts on the company.
STEP Analysis: Similar to PESTEL but focuses specifically on Social, Technological, Economic, and Political factors.
Bowman’s Strategy Clock: Analyzes competitive position and potential strategies based on price and perceived value.
SOAR Analysis: Focuses on Strengths, Opportunities, Aspirations, and Results, an alternative to SWOT with a more positive outlook.
Key Success Factors Analysis: Identifies critical factors necessary for success in a particular industry or market.
Strategic Group Analysis: Identifies and evaluates groups of firms with similar strategic characteristics within an industry.

Step 6: Perform the required strategic framework analysis and record the results in the output structure

Step 7: Add an analysis section to state why the provided analysis is important to the problem statement. Store the analysis in the output



Input 1: A Problem Statement - a specific strategic question about the a company. Your job is to answer that question using scenario analysis. The  key for the simple dictionary is "problem_statement". 

Input 2: Curated trend data of noted trends that potentially affect this analysis. 

Input 3 : Data regarding this company and its capabilities. 
"""


model_framework = ChatOpenAI(model="gpt-4o", temperature=0.0)
parser_framework = JsonOutputParser(pydantic_object=FrameworkAnalysis)
get_framework = PromptTemplate(
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
        "format_instructions": parser_framework.get_format_instructions(),
        "instruction": frameworks_instruction,
    },
)


chain_framework = get_framework | model_framework | parser_framework


################## Report Chain


report_instruction = """
You are providing support for a production workflow in a strategy consultancy. This is not a simulation, you must perform real analysis on real data that will be used by your colleagues to provide services for clients. 

You are the strategic reporter. A team of consultant colleagues have prepared a detailed and thorough analysis to a strategic question regarding a company. That strategic question has been mapped to the generation of scenarios pertinent to the problem question, and a utility score for each scenario.  Your job is to take the quantitative assessment of the strategic question, and provide a comprehensive, detailed report that outlines all the analytical stages in great depth and with great clarity. Where assumptions are made based on the data provided you, will cross-reference and cite those. For example, every reference to a capability of the company can be cross-referenced via the "EvidencedBy" property of the Capability, and from the Insight IDs that are referenced. Every Insight records its source document. You are an expert in tracing the provenance of assumptions and analysis to its source documents and citing those.  Cite the sources like this example, "Company X faces significant competitive pressure in the Consumer Health market, which we expect to increase over time due to AI adoption (Source: "AI Adoption in the Healthcare sector, MarketInsight Group" - Source document "AI_Adoption_Healthcare.pdf" ). Or reference the Capabilties of the company in the following manner "Company X may seek to leverage its unique capability in High-Performance Computing at  Scale (Source: Capability ID=94, name="High-Performance Computing at Scale"). The presence of multiple such citations will make our work accepted by the client, but do not create fake or placeholder citations, the sources that have been provided to you are sufficient. 

You must refer to the company by Name, and use the specific details that you have been given., such as examples of clients, new stories or real-life facts and figures about the company. Do not refer to it as "the company" but use its name and mention competitors where they are known. You will write in prose only. No bullets, no numbering, no short-hand. You must use complete, plain english sentences to describe anything. When you refer to numbers, you will generate sentences to encapsulate those numbers.   Do not add any more headings into the text you generate, simply encapsulate everything into the 5 sections that you have been informed of. Never use bullets or numerical lists. Use prose always. 

You will be given list of 3 or 4 files as input that will aid you in your task to write section of the report, see below for their expected format. Do not load these files yet. They are :

file_1 Company Insights containing insight potentially relevant for the report.
file_2  Scenario Analysis File. . Represents solutions to the given problem statement, also contains the detailed task breakdown for additional context.  
file_3: Strategic Frameworks File. Represents the analysis performed by strategic frameworks agents, such as SWOT or PESTLE. This analysis can support your report in various ways but usually in framing.
file_4 (if present) Trend data. Mainly used for cross-referencing purposes. You do not need to load the whole file yet.
** multi-step report generation ** 

You will follow a multi-step process to create your report. The general approach you will take it to cross-reference everything. Your ability to do so will dictate whether this analysis is grounded in facts/data or not. So every time you make a claim, back it with a citation to the Insight, Capability, or Trend that may have illuminated that Cite those sources in the analysis as often as possible. Cite every source of knowledge, insight or reasoning. 

1) Create markdown output structure, output_structure with the required sections : "introduction", "detailed_analysis", "prioritization", "barriers_risks_challenges" and "executive_summary". 

2) Load all files simultaneously. 

3) Introduction Section (1500 words).. Explain the methodology including data, capabilities, trends, frameworks and scenarios. Emphasis that real capabilities and trends are driving this analysis. Introduce and frme the problem outline. Give your response in a few paragraphs, DO NOT use bullet points or list unless required.  Show your response then update the output_structure with the response. Cite every source of knowledge, insight or reasoning. 

4) Detailed analysis Section (4000 words) Write a detail description of the analysis which MUST include the entire reasoning that the agent has performed to obtain the final answer.  Use the capability analysis, the other strategic framework and the scenarios. Allow equal weight to the capabilities and the scenarios, and use the numerical values to show a quantitative argument, but in qualitative language. Show any subtleties and deviations or contingencies in the reasoning. Provide real numbers in your analysis using the calculations that were provided. No need to mention prioritization in this section. Give your response in a several paragraphs, DO NOT use bullet points or numerical lists. Show your response then update the output_structure with the response. Cite every source of knowledge, insight or reasoning. 

5) Prioritization Section (1500 words).. Using the references to the previous scenarios and utilities, write what the priority of the company should be. What is the answer to the original problem statement? Give your response in a few paragraphs, DO NOT use bullet points or lists. Update the output_structure with your answer. Remember that all good strategies are trade-offs, therefore the recommended prioritisation should recommend one scenario over another. Do not recommend several courses of action unless there is extremely strong justification for this. Some aspects of a business must be stable while others change. Cite every source of knowledge, insight or reasoning. 

6) Barriers, Risks and Challenges Section  ( 1500 words ). Describe what barriers, risks and challenges the company will face when it attempts to implement your suggested approach. In particular, what should the company monitor that may mean the plan should change if new data is developed? Give your response in a few paragraphs, DO NOT use bullet points or lists. Show your response then update the output_structure with the response.Cite every source of knowledge, insight or reasoning. 

8) Executive Summary. (1000 words). Summarise the rest of the report. 

** general instructions ** 

Do not generalise or speak in high-level terms.  Be precise and use the available resources intelligently. You will write in clear, technical  professional, analytical style using plain English. The company in question is the client of out strategic consultancy. They will only pay for our report if we are able to evidence our reasoning with sufficient clarity, depth and transparency. The quality of your report will be judged using the following criteria. 

* Displaying analytical argument referring to real trends, capabilities, Insights of the company data.
* Showing the provenance of any analytical results including the source documents, also the provenance of Trends and Capabilities.
* Adherence between the quantitative analytical model and the qualitative reasoning and language in the report. 



Those targets should not be challenging to hit if you provide sufficiently rich and accurate descriptions of how the analysis was obtained, and from where the trends and capabilities were derived. Do not worry about patronising the client, explain everything as though there was no background context available and your report were the only source of truth. 
Provide the strongest citations possible - state the document name, or the source of the information. When you refer to strategic analysis don't just say "Analysis reveals" say that "Background detailed analysis has been performed and has shown that ...." This will differentiate your results from those generic results available elsewhere. When you reference scenairio analysis, speak in detail about the costs, benefits, risks and risk sensitivity. This analysis is the specialist of your firm, and it is likely to make a huge differentiation. 
Do not skip any sections. 
Fortmat your output as markdown file.
"""

get_report = PromptTemplate(
    template="""Follow the instructions:
                              ***
                              {instruction}
                              ***
                              
                              using company data: '
                              ***
                              {company_data}
                              ***
                              
                              using the following scenario analysis:
                              ***
                              {scenario_analysis}
                              ***
                              
                              using the following framework analysis:
                              ***
                              {framework_analysis}
                              ***
                              
                              using the following trends data:
                              ***
                              {trends}
                              ***
                              """,
    input_variables=[
        "company_data",
        "scenario_analysis",
        "framework_analysis",
        "trends",
    ],
    partial_variables={"instruction": report_instruction},
)


model_report = ChatOpenAI(model="gpt-4o", temperature=0.0)
parser_report = StrOutputParser()
chain_report = get_report | model_report | parser_report


def get_problem(company_name, problemsFile):
    """
    Retrieves the problem statement for a given company from a JSON file.
    """
    with open(problemsFile, "r") as file:
        problem_statements = json.load(file)
        # Retrieve the problem statement for the given company name
        statement = ""
    if company_name in problem_statements:
        statement = problem_statements[company_name]
        return json.dumps(statement).replace("'","\\'")
    else:
        print(f"Problem statement not found for the specified company {company_name}.")
        raise Exception(
            f"Problem statement not found for the specified company {company_name}."
        )


########### Summary Chain


summary_model = ChatOpenAI(model="gpt-4o", temperature=0.9)
summary_parser = StrOutputParser()
summary_prompt = ChatPromptTemplate.from_template(
    template="""
Giving this problem statement for the company {company}:
***
{problem_statement}
***

Make a short summary of the following data to extract potential strategic insights:
***
{data}
***
"""
)

summary_chain = summary_prompt | summary_model | summary_parser


def build_writing_chain():
    model = ChatOpenAI(model="gpt-4o", temperature=0.9)
    parser = JsonOutputParser(pydantic_object=contentSection)
    prompt = PromptTemplate(
        template="""You are working on a report with a team. Every one has a part to write. 
Make sure the part you just write is well formatted without too much line breaks or empty lines.
When writing the part, make sure to use the data provided to write the content of the section; and quote the the sources of the data.
This is the high level structure of the report:
***
{report_structure}
***

This is the data you have to use to write the part:
***
{data_input}
***

This is the part you have to write. Make sure to focus only on that part: 
***
{content_section}
***

Respect strictly the format of the output:
{format_instructions}
""",
        input_variables=["report_structure", "content_section", "data_input"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    return prompt | model | parser


class ValidationModel(BaseModel):
    validation: bool = Field("The validation if the input is valid or not")
    explaination: str = Field(
        "The explaination of the validation, and why it is valid or not, and how to fix it."
    )


class ValidationList(BaseModel):
    validations: List[ValidationModel] = Field("The list of validations")


def build_assessing_chain():
    model = ChatOpenAI(model="gpt-4o", temperature=0.9)
    parser = JsonOutputParser(pydantic_object=ValidationList)
    prompt = PromptTemplate(
        template="""You have to validate the input given some constraints.
The constraints are:
***
{constraints}
***

This is the input to assess: 
***
{input}
***

{format_instructions}
""",
        input_variables=["constraints", "input"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    return prompt | model | parser


class Content(BaseModel):
    content_statement: str = Field(description="The statement for the subsection.")


class Subsubsection(BaseModel):
    name: str = Field(description="The name of the subsubsection in the report.")
    content: Content = Field(
        description="The plan for the content of the subsubsection."
    )


class Subsection(BaseModel):
    name: str = Field(description="The name of the subsection in the report")
    content: List[Subsubsection] | Content = Field(
        description="The plan for the content of the subsection."
    )


class Section(BaseModel):
    name: str = Field(description="The name of the section in the report.")
    content: List[Subsection] | Content = Field(
        description="The plan for the content of the section."
    )


class reportPlan(BaseModel):
    plan: List[Section] = Field(description="The plan for generating the report.")


parser_generate_report_plan = JsonOutputParser(pydantic_object=reportPlan)

prompt_generate_report_plan = PromptTemplate(
    template="""Considering the following problem statement for the company {company}:
***
{problem_statement}
***

Using the following data summary, generate a plan for the report:
***
{data_summary}
***

The plan has to contain the following sections:
***
Introduction
Detailed analysis
Prioritization
Barriers, Risks and Challenges
Executive Summary
***


{format_instructions}
""",
    input_variables=["data_summary", "problem_statement", "company"],
    partial_variables={
        "format_instructions": parser_generate_report_plan.get_format_instructions()
    },
)


model_generate_report_plan = ChatOpenAI(model="gpt-4o", temperature=0.1)
generate_report_plan = (
    prompt_generate_report_plan
    | model_generate_report_plan
    | parser_generate_report_plan
)

########

summary_model = ChatOpenAI(model="gpt-4o", temperature=0.9)
summary_parser = StrOutputParser()
summary_prompt = ChatPromptTemplate.from_template(
    template="""
Giving this problem statement for the company {company}:
***
{problem_statement}
***

Make a short summary of the following data to extract potential strategic insights:
***
{data}
***
"""
)

summary_chain = summary_prompt | summary_model | summary_parser

# if __name__ == "__main__":
#     problem_data = get_problem("Tesla", "./problem_statements.json")
#     trends_file_path = "Intermediates/condensed_trends.json"
#     company_file_path = "Intermediates/condensed_company_data.json"

#     trends_data = json.load(open(trends_file_path))
#     company_data = json.load(open(company_file_path))
#     print("starting scenario chain")
#     print(
#         [
#             len(x)
#             for x in [
#                 dict_to_plain_text(problem_data),
#                 dict_to_plain_text(trends_data),
#                 dict_to_plain_text(company_data),
#             ]
#         ]
#     )

#     output_scenario = invoke(
#         chain_scenario,
#         {
#             "problem_statement": dict_to_plain_text(problem_data),
#             "trend_document": dict_to_plain_text(trends_data),
#             "company_data": dict_to_plain_text(company_data),
#             "company_name": "Tesla",
#         },
#     )

#     print("starting framework chain")

#     output_framework = invoke(
#         chain_framework,
#         {
#             "problem_statement": dict_to_plain_text(problem_data),
#             "trend_document": dict_to_plain_text(trends_data),
#             "company_data": dict_to_plain_text(company_data),
#             "company_name": "Tesla",
#         },
#     )
#     with open("Intermediates/scenario_output.json", "w") as file:
#         json.dump(output_scenario, file, indent=4)

#     with open("Intermediates/framework_output.json", "w") as file:
#         json.dump(output_framework, file, indent=4)

#     print("starting report chain")
#     print(
#         [
#             len(x)
#             for x in [
#                 dict_to_plain_text(company_data),
#                 dict_to_plain_text(output_scenario),
#                 dict_to_plain_text(output_framework),
#                 dict_to_plain_text(trends_data),
#             ]
#         ]
#     )
#     output_report = invoke(
#         chain_report,
#         {
#             "company_data": dict_to_plain_text(company_data),
#             "scenario_analysis": dict_to_plain_text(output_scenario),
#             "framework_analysis": dict_to_plain_text(output_framework),
#             "trends": dict_to_plain_text(trends_data),
#         },
#     )

#     print(output_report)
#     # Define the output file path
#     output_file = "report.txt"

#     # Write the report to the output file
#     with open(output_file, "w") as file:
#         file.write(output_report)
