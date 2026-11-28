from email.message import EmailMessage
from urllib.parse import quote

import aiosmtplib
from aiosmtplib import SMTPException

from app.modules.auth.errors import EmailDeliveryError


class EmailClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        timeout: float,
        use_tls: bool,
        start_tls: bool,
        validate_certs: bool,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.sender = sender
        self.timeout = timeout
        self.use_tls = use_tls
        self.start_tls = start_tls
        self.validate_certs = validate_certs
        self.base_url = base_url
        self.username = username
        self.password = password

    async def send_verification_email(
        self, recipient: str, token: str
    ) -> None:
        base_url = self.base_url.partition("#")[0]
        link = f"{base_url}#token={quote(token, safe='')}"
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = "Confirm your Avito-Kitchen email"
        message.set_content(
            "Confirm your email within 24 hours.\n\n"
            f"Verification link: {link}\n\n"
            "If the page does not submit the token automatically, copy the "
            "token from the link and use POST /api/v1/auth/verify-email in "
            "Swagger."
        )
        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                use_tls=self.use_tls,
                start_tls=self.start_tls,
                validate_certs=self.validate_certs,
            )
        except (SMTPException, OSError) as exc:
            raise EmailDeliveryError(
                "Verification email delivery failed"
            ) from exc
