import json

from pydantic import BaseModel, create_model, Field, StringConstraints
from typing import Annotated

from typing import Dict, List, Tuple, Optional


class Section(BaseModel):
    title: str = Field(
        "the name you want to give to that function to identify the result afterward"
    )
    subsections: List[str] = Field("The id of the subparts in the part")
    summary: str = Field("A summary of the part")


class contentSection(BaseModel):
    title: str = Field(
        "the name you want to give to that function to identify the result afterward"
    )
    content: str = Field(
        "The content of the subpart. A content subart should be very precised and complete, with exemples and illustrations.",
        min_length=3000,
    )
    summary: str = Field("A summary of the section", max_length=300)
    data_needed: List[str] = Field(
        "The data needed to write the section to improve the content of the section and the quality of the report"
    )
    content_statements: List[str] = Field(
        "The statements that are affirmed content of the section"
    )


def get_keys(data, keys):
    for k, v in data.items():
        if isinstance(v, dict):
            get_keys(v, keys)
        elif k in keys or isinstance(v, dict):
            data[k] = v
        else:
            del data[k]


class Report:
    def __init__(self):
        self.data = {}
        self.fulldata = {}
        self.metadata = {}
        self.table_of_content = {}
        self.history = []

    def build_table_content(self):
        self.table_of_content = get_keys(self.fulldata.copy(), ["title", "subsections"])
        self.data = get_keys(self.fulldata.copy(), ["title", "subsections", "content"])
        self.metadata = get_keys(
            self.fulldata.copy(), ["title", "subsections", "summary"]
        )

    def add_subpart(self, index, content):
        if index not in self.data:
            self.data[index] = []
        self.data[index].append(content)
        self.history.append(f"Added subpart at index {index}: {content}")

    def update_subpart(self, index, subpart_index, new_content):
        if index in self.data and subpart_index < len(self.data[index]):
            self.data[index][subpart_index] = new_content
            self.history.append(
                f"Updated subpart at index {index}, subpart index {subpart_index}: {new_content}"
            )

    def remove_subpart(self, index, subpart_index):
        if index in self.data and subpart_index < len(self.data[index]):
            del self.data[index][subpart_index]
            self.history.append(
                f"Removed subpart at index {index}, subpart index {subpart_index}"
            )

    def to_json(self):
        return json.dumps(self.data)

    @classmethod
    def from_json(cls, json_data):
        report = cls()
        report.data = json.loads(json_data)
        return report
