from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as Obj
from uuid import uuid4

import pytest

from app.modules.auth import registration
from app.modules.auth.registration import RegistrationService
from app.modules.users.service import UserService

pytestmark = pytest.mark.unit


class FakeUsers:
    def __init__(self, user=None):
        self.user = user

    async def lock_email(self, email):
        return None

    async def get_by_email(self, email):
        return self.user

    async def get_by_id(self, user_id):
        return self.user

    async def get_by_id_for_update(self, user_id):
        return self.user

    def add(self, user):
        self.user = user
        return user


class FakeTokens:
    def __init__(self, token=None):
        self.token = token
        self.revoked = False

    def add(self, token):
        self.token = token

    async def get_by_hash(self, token_hash):
        return self.token

    async def get_by_hash_for_update(self, token_hash):
        return self.token

    async def revoke_active(self, *args, **kwargs):
        self.revoked = True


class FakeUow:
    def __init__(self, users, tokens):
        self.users = Obj(users=users)
        self.auth = Obj(user_action_tokens=tokens)
        self.flush_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def flush(self):
        self.flush_count += 1
        self.users.users.user.id = uuid4()


class FakeEmailClient:
    def __init__(self):
        self.sent = []

    async def send_verification_email(self, email, token):
        self.sent.append((email, token))


@pytest.mark.asyncio
async def test_registration_creates_user_through_user_service_in_shared_uow(
    monkeypatch,
):
    async def fake_hash(password):
        return "password-hash"

    monkeypatch.setattr(registration, "hash_password", fake_hash)
    monkeypatch.setattr(
        registration, "generate_action_token", lambda: "raw-token"
    )
    users, tokens = FakeUsers(), FakeTokens()
    uow = FakeUow(users, tokens)
    email_client = FakeEmailClient()
    service = RegistrationService(email_client, lambda: uow, UserService())
    await service.register("USER@EXAMPLE.COM", "password")
    assert users.user.email == "user@example.com"
    assert users.user.password_hash == "password-hash"
    assert tokens.token.user_id == users.user.id
    assert uow.flush_count == 1
    assert email_client.sent == [("user@example.com", "raw-token")]


@pytest.mark.asyncio
async def test_verification_marks_user_through_user_service_in_shared_uow(
    monkeypatch,
):
    async def fake_verify(password, password_hash):
        return True

    monkeypatch.setattr(registration, "verify_password", fake_verify)
    user = Obj(
        id=uuid4(),
        is_active=True,
        email_verified_at=None,
        password_hash="password-hash",
    )
    token = Obj(
        id=uuid4(),
        user_id=user.id,
        purpose="email_verification",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        used_at=None,
        revoked_at=None,
    )
    users, tokens = FakeUsers(user), FakeTokens(token)
    uow = FakeUow(users, tokens)
    service = RegistrationService(
        FakeEmailClient(), lambda: uow, UserService()
    )
    await service.verify_email("raw-token", "password")
    assert user.email_verified_at is not None
    assert token.used_at == user.email_verified_at
    assert tokens.revoked is True
