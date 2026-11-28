from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

NonEmptyString = Annotated[str, Field(min_length=1)]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
