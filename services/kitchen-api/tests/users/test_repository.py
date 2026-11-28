from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.users.models.user import User

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_add_and_get_by_id(uow: UnitOfWork):
    user = User(
        email=f"user-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    uow.users.users.add(user)
    await uow.session.commit()

    saved_user = await uow.users.users.get_by_id(user.id)

    assert saved_user is not None
    assert saved_user.id == user.id
    assert saved_user.email == user.email


@pytest.mark.asyncio
async def test_get_by_email_returns_user(uow: UnitOfWork):
    email = f"user-{uuid4()}@example.com"
    user = User(email=email, password_hash="test-password-hash")
    uow.users.users.add(user)
    await uow.session.commit()

    saved_user = await uow.users.users.get_by_email(email)

    assert saved_user is not None
    assert saved_user.id == user.id
    assert saved_user.email == email


@pytest.mark.asyncio
async def test_get_by_email_returns_none_when_not_found(uow: UnitOfWork):
    user = await uow.users.users.get_by_email(f"missing-{uuid4()}@example.com")
    assert user is None
