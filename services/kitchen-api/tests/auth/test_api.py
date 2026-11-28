import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.dependencies import get_registration_service
from app.main import app

pytestmark = pytest.mark.contract


class FakeRegistrationService:
    def __init__(self):
        self.calls = []

    async def register(self, email, password):
        self.calls.append(("register", email))

    async def verify_email(self, token, password):
        self.calls.append(("verify", token))

    async def resend_verification(self, email):
        self.calls.append(("resend", email))


def test_auth_routes_and_safe_validation_response():
    service = FakeRegistrationService()
    app.dependency_overrides[get_registration_service] = lambda: service
    try:
        with TestClient(app) as client:
            register = client.post(
                "/api/v1/auth/register",
                json={"email": "A@EXAMPLE.COM", "password": "strong-password"},
            )
            verify = client.post(
                "/api/v1/auth/verify-email",
                json={"token": "a" * 32, "password": "strong-password"},
            )
            resend = client.post(
                "/api/v1/auth/resend-verification",
                json={"email": "A@EXAMPLE.COM"},
            )
            invalid = client.post(
                "/api/v1/auth/register",
                json={"email": "invalid", "password": "SENSITIVE_SENTINEL"},
            )
        assert [
            register.status_code,
            verify.status_code,
            resend.status_code,
        ] == [202, 200, 202]
        assert [x[0] for x in service.calls] == [
            "register",
            "verify",
            "resend",
        ]
        assert invalid.status_code == 422
        assert "SENSITIVE_SENTINEL" not in invalid.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("path", "body", "field", "invalid_value"),
    [
        (
            "/api/v1/auth/register",
            {"email": "invalid-email-secret", "password": "ValidPassword123!"},
            "email",
            "invalid-email-secret",
        ),
        (
            "/api/v1/auth/register",
            {"email": "user@example.com", "password": "short-secret"},
            "password",
            "short-secret",
        ),
        (
            "/api/v1/auth/verify-email",
            {"token": "invalid!token", "password": "ValidPassword123!"},
            "token",
            "invalid!token",
        ),
    ],
)
def test_invalid_auth_fields_do_not_expose_input_or_call_service(
    path, body, field, invalid_value
):
    service = FakeRegistrationService()
    app.dependency_overrides[get_registration_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(path, json=body)
        assert response.status_code == 422
        assert ["body", field] in [
            error["loc"] for error in response.json()["detail"]
        ]
        assert invalid_value not in response.text
        for sensitive_field in ("password", "token"):
            if sensitive_field in body:
                assert body[sensitive_field] not in response.text
        assert service.calls == []
    finally:
        app.dependency_overrides.clear()


def test_auth_rate_limit_sets_retry_after(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_REGISTER_RATE_LIMIT", 1)
    app.dependency_overrides[get_registration_service] = lambda: (
        FakeRegistrationService()
    )
    try:
        with TestClient(app) as client:
            body = {"email": "user@example.com", "password": "strong-password"}
            assert (
                client.post("/api/v1/auth/register", json=body).status_code
                == 202
            )
            limited = client.post("/api/v1/auth/register", json=body)
        assert limited.status_code == 429
        assert int(limited.headers["Retry-After"]) > 0
    finally:
        app.dependency_overrides.clear()
