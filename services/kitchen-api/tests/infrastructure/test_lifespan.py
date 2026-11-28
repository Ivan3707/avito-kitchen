from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core import lifespan as lifespan_module
from app.main import app

pytestmark = pytest.mark.unit


def test_lifespan_reuses_and_closes_http_client(monkeypatch):
    dispose = AsyncMock()
    monkeypatch.setattr(
        lifespan_module, "engine", SimpleNamespace(dispose=dispose)
    )
    with TestClient(app):
        client = app.state.order_service.restaurant_client.client
        assert not client.is_closed
        assert (
            app.state.checkout_service.order_service is app.state.order_service
        )
        assert (
            app.state.checkout_service.cart_service is app.state.cart_service
        )
    assert client.is_closed
    dispose.assert_awaited_once()
