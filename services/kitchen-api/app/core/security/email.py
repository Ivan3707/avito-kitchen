from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, EmailStr, TypeAdapter


def _strip_email(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _lower_email(value: EmailStr) -> str:
    return str(value).lower()


NormalizedEmail = Annotated[
    EmailStr,
    BeforeValidator(_strip_email),
    AfterValidator(_lower_email),
]

_email_adapter = TypeAdapter(NormalizedEmail)


def normalize_email(value: str) -> str:
    return str(_email_adapter.validate_python(value))
