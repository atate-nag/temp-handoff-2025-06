from pydantic import BaseModel, create_model, Field
from typing import Dict, List, Tuple, Optional
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_openai import ChatOpenAI


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
    Source: str = Field(description="The source of the statement.")
    Quote: str = Field(description="A quote that demonstrate the statement.")


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
