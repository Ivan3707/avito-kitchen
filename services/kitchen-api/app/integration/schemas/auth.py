from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.security.email import NormalizedEmail
from app.core.security.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
)

Password = Annotated[
    str,
    StringConstraints(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
    ),
]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegistrationRequest(StrictRequest):
    email: NormalizedEmail
    password: Password


class VerifyEmailRequest(StrictRequest):
    token: str = Field(
        min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )
    password: Password


class ResendVerificationRequest(StrictRequest):
    email: NormalizedEmail


class MessageResponse(BaseModel):
    message: str
