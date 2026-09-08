from uuid import uuid4

import pytest

from app.infrastructure.database.models.customer import Customer
from app.infrastructure.unit_of_work import UnitOfWork


@pytest.mark.asyncio
async def test_add_and_get_by_id(
    uow: UnitOfWork,
):
    customer = Customer(
        email=f"customer-{uuid4()}@example.com",
    )

    uow.customers.add(customer)

    await uow.session.commit()

    saved_customer = await uow.customers.get_by_id(customer.id)

    assert saved_customer is not None
    assert saved_customer.id == customer.id
    assert saved_customer.email == customer.email


@pytest.mark.asyncio
async def test_get_by_email_returns_customer(
    uow: UnitOfWork,
):
    email = f"customer-{uuid4()}@example.com"

    customer = Customer(
        email=email,
    )

    uow.customers.add(customer)

    await uow.session.commit()

    saved_customer = await uow.customers.get_by_email(email)

    assert saved_customer is not None
    assert saved_customer.id == customer.id
    assert saved_customer.email == email


@pytest.mark.asyncio
async def test_get_by_email_returns_none_when_not_found(
    uow: UnitOfWork,
):
    customer = await uow.customers.get_by_email(
        f"missing-{uuid4()}@example.com"
    )

    assert customer is None
