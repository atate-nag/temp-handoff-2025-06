from debug import dprint
from pydantic import (
    BaseModel,
    FilePath,
    field_validator,
    validator,
    ValidationError,
    Field,
)
from typing import Any, Optional, List, Dict
import os


def assistant_file_accessible(client, file_id, agent_id):
    dprint(f"Retrieving file {file_id} for agent {agent_id}")
    asst_file = client.beta.assistants.files.retrieve(
        assistant_id=agent_id, file_id=file_id
    )
    dprint(f"asst_file {asst_file}")
    # content = client.files.retrieve_content(file)
    return asst_file is not None


class InputFilesModel(BaseModel):
    input_files: list = Field(default=[])

    @validator("input_files", each_item=True)
    def check_input_files(cls, v, values):
        # None is OK for input files
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError(
                f"v={v}: Each item in input_files must be a string representing a file path."
            )
        dprint(f"filepath OK")
        # Optional: Check if the file path exists in the filesystem
        if not os.path.exists(v):
            raise ValueError(f"File path {v} does not exist.")
        dprint(f"filepath exists")
        return v

        class Config:
            validate_assignment = True


"""Initialised State Validations """


class AsstFilesModel(BaseModel):
    client: Any  # Assuming this has a specific class that you have defined.
    agent_id: str = Field()
    asst_files: list = Field(default=[])

    @validator("asst_files", each_item=True)
    def check_asst_files(cls, v, values):
        if not isinstance(v, str):
            raise ValueError(
                f"v={v}: Each item in input_files must be a string representing a file path."
            )
        dprint(f"filepath OK")
        client = values["client"]
        agent_id = values["agent_id"]
        # Optional: Check if the file path exists in the filesystem
        if assistant_file_accessible(client, agent_id, v):
            dprint(f"asst_file exists and is accessible")
        return v

        class Config:
            validate_assignment = True
