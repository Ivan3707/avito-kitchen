from typing import Protocol


class VerificationEmailGateway(Protocol):
    async def send_verification_email(
        self, recipient: str, token: str
    ) -> None: ...
