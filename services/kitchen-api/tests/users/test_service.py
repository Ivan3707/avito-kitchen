from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.modules.users.service import UserService

pytestmark = pytest.mark.unit


def test_user_mutations_use_supplied_uow():
    saved = []

    class Users:
        def add(self, user):
            saved.append(user)
            return user

    uow = SimpleNamespace(users=SimpleNamespace(users=Users()))
    service = UserService()
    user = service.create_pending_user(uow, "user@example.com", "hash")
    assert user.email == "user@example.com"
    assert user.password_hash == "hash"
    assert user.email_verified_at is None
    assert user.is_active is True
    assert saved == [user]
    now = datetime.now(UTC)
    service.mark_email_verified(uow, user, now)
    assert user.email_verified_at == now
