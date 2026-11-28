from unittest.mock import AsyncMock

import aiosmtplib
import pytest
from aiosmtplib import SMTPException

from app.infrastructure.clients.email import EmailClient
from app.modules.auth.errors import EmailDeliveryError

pytestmark = pytest.mark.unit


def client():
    return EmailClient(
        host="smtp.example",
        port=2525,
        sender="sender@example.com",
        timeout=7.0,
        use_tls=False,
        start_tls=True,
        validate_certs=True,
        base_url="https://app.example/verify#old-fragment",
        username="smtp-user",
        password="smtp-password",
    )


@pytest.mark.asyncio
async def test_send_verification_email_preserves_message_link_and_smtp_settings(
    monkeypatch,
):
    send = AsyncMock()
    monkeypatch.setattr(aiosmtplib, "send", send)

    await client().send_verification_email("user@example.com", "a/b +")

    send.assert_awaited_once()
    args, kwargs = send.await_args
    message = args[0]
    assert message["From"] == "sender@example.com"
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Confirm your Avito-Kitchen email"
    body = message.get_content()
    assert "Confirm your email within 24 hours." in body
    assert (
        "Verification link: https://app.example/verify#token=a%2Fb%20%2B"
        in body
    )
    assert "POST /api/v1/auth/verify-email" in body
    assert kwargs == {
        "hostname": "smtp.example",
        "port": 2525,
        "username": "smtp-user",
        "password": "smtp-password",
        "timeout": 7.0,
        "use_tls": False,
        "start_tls": True,
        "validate_certs": True,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [SMTPException("smtp failed"), OSError("network failed")]
)
async def test_transport_errors_become_email_delivery_error(
    monkeypatch, error
):
    monkeypatch.setattr(aiosmtplib, "send", AsyncMock(side_effect=error))
    with pytest.raises(EmailDeliveryError, match="delivery failed"):
        await client().send_verification_email("user@example.com", "token")
