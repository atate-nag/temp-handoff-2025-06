import os
import openai
from dotenv import load_dotenv
import os

load_dotenv()


from graph_workflow.graph_rag_lc import RAG_graph
from filehandler import FileHandler
from utility import retry
import time

# from dochandler import import_data_files
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from multiprocessing import Pool
from filehandler import FileHandler
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.prompts import PromptTemplate

# import pydantic.datetime as pydantic_datetime
import json, re


client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={"OpenAI-Beta": "assistants=v1"},
)
file_handler = FileHandler(client)
import json
import sys
import uuid

load_dotenv()
# client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
uri = os.getenv("NEO4J_URL")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
OPENAI_EMBEDDINGS_URL = os.getenv("OPENAI_EMBEDDINGS_URL")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
from datetime import datetime

rag_graph = RAG_graph(
    uri,
    user,
    password,
    database,
    OPENAI_API_KEY,
    OPENAI_EMBEDDINGS_URL,
)


class Insight(BaseModel):
    description: str = Field(description="Description of the insight")
    categories: list[str] = Field(
        description="The list of categories that are involved in the question"
    )
    relevanceScore: int = Field(
        description="The relevance score of the insight to the company's strategy, between 0 and 99"
    )
    extractionDate: datetime = Field(
        description="The date of the extraction of the insight"
    )
    name: str = Field(description="The name of the insight")
    statement: str = Field(description="The statement of the insight")


class InsightList(BaseModel):
    insights: list[Insight] = Field(
        description="The list of insights extracted from the documents"
    )


### CLASSIFICATIONS

model_insights = ChatOpenAI(model="gpt-4o", temperature=0.1)
parser_insights = JsonOutputParser(pydantic_object=InsightList)
get_insights = PromptTemplate(
    template="""Give me the relevant insights for the company: {company} using only the data provided in this document: '{document}'\n{format_instructions}""",
    input_variables=["company", "document"],
    partial_variables={
        "format_instructions": parser_insights.get_format_instructions()
    },
)
chain_insights = get_insights | model_insights | parser_insights

general_classification_instruction = ChatPromptTemplate.from_template(
    """ You will classify this text:
    '{text}' 
    
    based on the following categories:
    '{categories}'
    
    For this you will use the following instructions:
    '{instructions}'
    
    You must return the classification of the text in the following format, no quote just plain text:
    Category 1, Category 2, ...
    
    You have to return at least one categeory. If you are not sure about the classification, you can return None as a category.
    """
)

topic_type = [
    "Technology",
    "Sports",
    "Politics",
    "Entertainment",
    "Business",
    "Health",
    "Science",
    "Education",
    "Environment",
    "Fashion",
    "Travel",
    "None",
]
topic_instruction = """Topics of Text for Classification

    Technology: Covers developments, innovations, and trends in technology. This can include computing, gadgets, software, and telecommunications.

    Sports: Discusses sports events, athlete profiles, analyses of games, and sports-related news.

    Politics: Includes discussion on political affairs, policy analyses, election coverage, and profiles of political figures.

    Entertainment: Encompasses movies, television, music, celebrity culture, and the entertainment industry.

    Business: Related to the business world including finance, startups, management strategies, and industry trends.

    Health: Focuses on health topics, including medical advancements, wellness tips, health policy, and fitness.

    Science: Covers scientific discoveries, research updates, and discussions on various branches of science like biology, chemistry, and physics.

    Education: Discusses educational policies, teaching strategies, educational technology, and school systems.

    Environment: Focuses on environmental issues, conservation efforts, climate change, and sustainability practices.

    Fashion: Covers fashion trends, fashion industry news, and profiles on designers and fashion events.

    Travel: Includes travel guides, tips, cultural insights, and information on destinations.

    None: This category is reserved for texts that do not fit clearly into any of the other topics listed. It can be used for texts that are too broad, too niche, or too general to be categorized under a specific topic."""


sentiment_type = [
    "Positive",
    "Negative",
    "Neutral",
    "Slightly Positive",
    "Slightly Negative",
    "None",
]
sentiment_instruction = """Categories of Sentiment in Text for Classification

    Positive: Texts that convey a positive outlook, satisfaction, happiness, or praise. Typically includes content that expresses approval, enthusiasm, or pleasure.

    Negative: Texts that express dissatisfaction, sadness, anger, or criticism. These often include complaints, expressions of disappointment, or discontent.

    Neutral: Texts that display neither clear positive nor negative sentiment. These are typically factual, objective, or devoid of emotional expressions.

    Slightly Positive: Texts that exhibit mild approval or contentment. This sentiment is not as strong as fully positive but suggests a generally favorable tone.

    Slightly Negative: Texts that contain mild criticism or displeasure. These express negative sentiment but in a less intense or overt manner than fully negative texts.

    None: This category is used for texts where sentiment is ambiguous, mixed, or where an analysis tool fails to determine the prevailing sentiment. This could be due to lack of sufficient emotional cues, conflicting sentiments within the same text, or highly technical language that obfuscates emotional tone."""

intent_type = [
    "Information Request",
    "Service Request",
    "Complaint",
    "Greeting",
    "Feedback",
    "Purchase Intent",
    "Booking Intent",
    "Cancellation",
    "None",
]
intent_instruction = """Categories of Intent in Text for Classification

    Information Request: Texts where the user seeks specific information or data. Examples include questions about products, services, or factual queries.

    Service Request: Texts where the user is asking for a particular service to be performed. Examples include requests for technical support, booking appointments, or requesting repairs.

    Complaint: Texts where dissatisfaction with a service or product is expressed, often seeking resolution or response from the provider.

    Greeting: Texts that are used to initiate conversation or to acknowledge the presence of the other party, often polite and formal or casual.

    Feedback: Texts where the user provides opinions or evaluations about a service, product, or experience, whether positive or negative.

    Purchase Intent: Texts that indicate a desire or intention to buy a product or service. This can be inquiries about product availability, prices, or purchasing procedures.

    Booking Intent: Texts indicating a desire to reserve a service or space, such as hotel rooms, restaurant tables, or event tickets.

    Cancellation: Texts where the intent is to cancel a service, order, or reservation.

    Slightly Positive: Expresses a mildly positive reaction or approval toward a service, product, or interaction, without a strong commitment.

    Slightly Negative: Indicates slight dissatisfaction or minor concerns about a service or product, often looking for minor adjustments or clarifications.

    None: This category is used for texts that do not clearly express any of the specific intents listed above or whose intent is ambiguous or irrelevant to the typical categories. This might include general statements, mixed messages, or contextually vague texts."""

urgency_type = ["Non-Urgent", "Low Urgency", "Medium Urgency", "High Urgency"]
urgent_instruction = """Categories of Urgency in Text for Classification

    Non-Urgent: Texts that require no immediate action or response. These are routine communications that can be addressed in regular workflow or timing, such as general inquiries or updates.

    Low Urgency: Texts that are not critical but should be addressed soon. These might include non-critical updates, scheduling future meetings, or non-urgent requests that do not require immediate action but should not be delayed excessively.

    Medium Urgency: Texts that demand timely attention and should be prioritized over low urgency items. These could include issues that could escalate if not addressed promptly, such as initial complaints that are not yet severe or operational issues that are not currently impacting core functions.

    High Urgency: Texts requiring immediate attention and action. These often pertain to critical issues, emergencies, or situations where delay could result in significant consequences. Examples include severe complaints, emergency requests, or significant operational disruptions.
    
    This classification system helps in prioritizing tasks and responses effectively, especially in environments like customer service, incident response, or any area where timely communication is crucial."""

emotion_type = [
    "Happiness",
    "Sadness",
    "Anger",
    "Fear",
    "Surprise",
    "Disgust",
    "Trust",
    "Anticipation",
    "None",
]
emotion_instruction = """Categories of Emotion in Text for Classification

    Happiness: Texts that express joy, satisfaction, or positive excitement. These include expressions of gratitude, celebration, or pleasure.

    Sadness: Texts that convey sorrow, melancholy, or disappointment. This can include expressions of grief, loss, or frustration.

    Anger: Texts that reflect feelings of irritation, anger, or rage. These might involve complaints, confrontations, or expressions of displeasure.

    Fear: Texts that express fear, anxiety, or apprehension. Examples include worries about future events, expressions of fear regarding specific situations, or concerns about safety.

    Surprise: Texts that indicate shock or surprise. This could be in response to unexpected news, events, or actions.

    Disgust: Texts that show feelings of disgust or revulsion. These might be in response to unpleasant situations, behaviors, or tastes.

    Trust: Texts that convey a sense of trust, reliability, or confidence. This can include messages that express loyalty, reassurance, or commitment.

    Anticipation: Texts that express anticipation or excitement for a future event or outcome. This includes looking forward to something positive or preparing for potential challenges.

    None: This category is for texts where emotional content is ambiguous, mixed, or where an analysis tool fails to identify clear emotional expressions. This could be due to neutral language, technical content, or conflicting emotions within the same text.

This comprehensive set of categories can be used to fine-tune emotion detection systems, allowing for nuanced understanding and response to human emotions in text-based communications."""

quality_type = ["High Quality", "Low Quality", "Medium Quality", "Spam", "None"]
quality_instruction = """Categories of Quality in Text for Classification

    High Quality: Texts that are well-written, informative, and engaging. These typically include clear organization, thorough research, accurate information, and good grammar.

    Medium Quality: Texts that are adequate but may lack in certain areas such as depth of information, creativity, or some aspects of writing style. These texts generally meet basic requirements but do not excel.

    Low Quality: Texts that are poorly written or uninformative. These may include numerous grammatical or spelling errors, lack coherence, or fail to provide useful information.

    Spam: Texts that are unsolicited, irrelevant, or inappropriate for the intended audience. This includes promotional content that is intrusive or repetitive.

    None: This category is used for texts that do not clearly fit into the quality categories above due to mixed elements or ambiguous characteristics. It could be used for texts where the quality is not the primary concern or is not assessable due to lack of context or clarity.

This classification system helps in assessing the content quality for various applications, such as content moderation, editorial review, or automated recommendations."""

legal_compliance_type = [
    "GDPR Compliance",
    "Financial Regulation Compliance",
    "Safety Compliance",
    "Ethical Standards",
    "Contractual Obligations",
    "Non-Compliant",
    "Compliant,",
    "Borderline",
    "None",
]
legal_compliance_instruction = """Categories of Legal and Compliance in Text for Classification

    GDPR Compliance: Texts that specifically adhere to or violate the General Data Protection Regulation requirements. This includes handling of personal data in line with EU laws.

    Financial Regulation Compliance: Texts that conform to or fail financial regulations such as SEC rules, banking laws, or other financial standards.

    Safety Compliance: Texts related to adherence or non-adherence to safety standards and regulations, applicable in industries like manufacturing, construction, and healthcare.

    Ethical Standards: Texts that address or breach ethical guidelines, which could include business ethics, professional conduct, and corporate responsibility.

    Contractual Obligations: Texts discussing or failing to meet stipulated terms in contracts, which can include service agreements, employment contracts, or lease agreements.

    Non-Compliant: Texts that do not meet the specified legal, regulatory, or contractual requirements across any category.

    Compliant: Texts that fully meet legal, regulatory, ethical, or contractual requirements as appropriate.

    Borderline: Texts where compliance status is unclear or potentially at risk, requiring further review to determine if they meet legal standards.

    None: This category is for texts where compliance is not relevant, cannot be determined, or is outside the scope of the specific legal frameworks in question.

This classification system helps organizations to systematically assess and manage compliance across various legal and regulatory frameworks, ensuring thorough monitoring and enforcement of compliance standards."""

discourse_type = [
    "Explanatory",
    "Descriptive",
    "Narrative",
    "Persuasive",
    "Instructional",
]
discourse_instruction = """Types of Text for Classification

    Explanatory: Explanatory texts are intended to clarify, explain, or inform. They often detail how something works or why something happens. This type can be recognized by:
        Use of cause-and-effect language
        Logical sequencing (first, then, finally)
        Presence of facts and data
        Explanations or definitions of concepts

    Descriptive: Descriptive texts aim to provide a detailed description of a person, place, object, or event, focusing on sensory details. Key features include:
        Use of vivid adjectives and adverbs
        Focus on sensory details (sight, sound, touch, taste, smell)
        More elaborate use of figurative language (similes, metaphors)
        Detailed visualizations

    Narrative: Narrative texts tell a story or recount events. They often have characters, a setting, a plot, and a point of view. They may include:
        Chronological order of events
        Direct dialogue among characters
        A clear beginning, middle, and end
        Conflict and resolution

    Persuasive: Persuasive texts aim to convince the reader of the writer's point of view. They might include:
        Arguments supported by evidence
        Appeals to the reader’s emotions or logic
        Use of strong, convincing language
        Often includes a call to action

    Instructional: Instructional texts are written to give directions or instructions. These might feature:
        Step-by-step instructions
        Use of command language or imperatives
        Sequential organization
        List of materials or requirements

    None: This category is used for texts that do not clearly fit into any of the aforementioned categories. It might include generic, non-specific or ambiguous texts that lack distinct features of the other defined types."""

classifications = [
    ("discourse", discourse_type, discourse_instruction),
    ("topic", topic_type, topic_instruction),
    ("sentiment", sentiment_type, sentiment_instruction),
    ("intent", intent_type, intent_instruction),
    ("urgency", urgency_type, urgent_instruction),
    ("emotion", emotion_type, emotion_instruction),
    ("quality", quality_type, quality_instruction),
    ("legal_compliance", legal_compliance_type, legal_compliance_instruction),
]


### DETECTIONS
general_detection_instruction = ChatPromptTemplate.from_template(
    """ You will detect the following concept:
    {concept}
    
    in the following text:
    {text}
    
    You must return the detected elements of the text and their description in the following format, no quote just plain text. The elements and the description separated by a new line:
    first element, second element, ... 
    Description of the first element detected; Description of the second element detected; ...
    
    You have to return at least one word per line. If you are not sure about the detection, you can return None as an element and empty for the description, and if you don't have the name use a category (i.e. the product is not named but is food then just use food).
    """
)

product_instruction = """PRODUCT DETECTION
A product can be defined as any item or service that is manufactured or provided for consumer use. It can range from physical goods (like electronics, clothing, food items) to services (like software, cleaning services, or educational courses). Products are typically named explicitly but can also be described by their functions, features, or brand names.
You have to return the product name or category if the product is not named. If you are not sure about the detection, you can return None as a product name, you have to also provide a description of the product detected.
"""

insight_instruction = """Your role is to retrieve all the insights about a company, its competitors and its environment. You will be provided one document. The document contains the information that we are searching for further insights within. 

An insight is one or more sentences that communicate something coherent and relevant to the target company's strategy. Read a proposed insight in full. Include it if it relates directly to the company, or to the products of the company, or to competitors of the company, and exclude it if this is not clear. Do not include statements that do not relate directly to the company, its competitors or products. For example, insights that pertain to the structure, purpose, theory or methodology of a document are not relevant to the company's strategy and should be excluded. 

You will return a structured list of insights. You must be thorough and not miss any insights that are related to the target company. Only exclude information that does not seem related to the target company, its competitors, or its environment. Otherwise, include all relevant content. Return your results in a structured JSON file and provide the download location. 

You will write the "insight", "description", "categories", "sourceDocument" , "extractionDate" in a dictionary and then dump to JSON, adhering to the following schema.

For the relevanceScore, rate how strongly the particular fragment of text is obviously relevant to the company's strategy, out of 100.
You are thorough and methodical, you have a team of strategy consultants awaiting the outcome and their progress depends on you reliably extracting every insight related to the target company.  
When complete, repeat the process by reading each insight and making sure that the relevance to the company, products or competitors is strong enough to include. """


def wrap(s, w):
    return [s[i : i + w] for i in range(0, len(s), w)]


def add_to_dict(dict, key, value):
    if key in dict:
        dict[key] = ", ".join([dict[key] + value])
    else:
        dict[key] = value
    return dict


model_classification = ChatOpenAI(model="gpt-4o")
model_detection = ChatOpenAI(model="gpt-4o")
output_parser_classification = StrOutputParser()
output_parser_detection = StrOutputParser()
chain_classification = (
    general_classification_instruction
    | model_classification
    | output_parser_classification
)
chain_detection = (
    general_detection_instruction | model_detection | output_parser_detection
)


def add_insight(name, text, dict):
    # print("Adding insight")
    response_insight = chain_insights.invoke({"company": name, "document": text})
    # print(response_insight)
    insights = [
        {
            "insightId": str(uuid.uuid4()),
            "description": i["description"],
            "name": i["name"],
            "categories": i["categories"],
            "relevanceScore": i["relevanceScore"],
            "source": dict["source"],
            "created": datetime.today().strftime("%Y-%m-%d"),
        }
        for i in response_insight["insights"]
    ]
    for insight in insights:
        insight_id = insight["insightId"]
        # print("Adding insight to graph")
        rag_graph.add_insight(insight)
        # print("Linking insight to chunk")
        # print(f"Chunk id is {dict['chunkId']}")
        # print(f"Insight id is {insight_id}")
        rag_graph.link_chunk_to_insight(dict["chunkId"], insight_id)
    return insights


def get_insights(companies, delete_existing_insights=False, number_of_processes=5):
    names = [c.replace(" ", "_").replace(".", "").replace("'", "") for c in companies]
    for name in names:
        name = name.replace(" ", "_").replace(".", "").replace("'", "")
        res = rag_graph.company_sub_graph(
            name, label_filters=["Chunk"], relationship_exclusions=["SIMILAR"], depth=5
        )

        # Delete insights if already exist
        if delete_existing_insights:
            ins = rag_graph.company_sub_graph(
                name,
                label_filters=["Insight"],
                relationship_exclusions=["SIMILAR"],
                depth=5,
            )

            for i in ins:
                rag_graph.kg.query(
                    f"MATCH (n:Insight) WHERE n.insightId = '{i['insightId']}' DETACH DELETE n"
                )

        # create_insights(res, company_data, name)
        # if len(ins) == 0:
        with Pool(processes=number_of_processes) as pool:
            results = []
            for dict in res:
                # try:
                text = dict["text"]
                # print(f"Creating insights for {text}")
                graph_params = [
                    uri,
                    user,
                    password,
                    database,
                    OPENAI_API_KEY,
                    OPENAI_EMBEDDINGS_URL,
                ]
                # add_insight(name, text, dict, chain_insights, rag_graph, graph_params)
                results.append(pool.apply_async(add_insight, args=(name, text, dict)))
            print("Waiting for processes to finish...")
            while not all([r.ready() for r in results]):

                print(
                    f"insights added for chunk {[r.ready() for r in results].count(True)} / {len(results)} for {name}."
                )
                time.sleep(5)

        print(f"Insights for {name} were created")
