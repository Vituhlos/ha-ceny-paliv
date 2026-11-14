"""Shared test fixtures; tests never access the network."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def block_network():
    with patch("aiohttp.ClientSession._request", side_effect=AssertionError("Network access is forbidden")):
        yield


@pytest.fixture
def now():
    return datetime(2025, 1, 15, 12, 0)


@pytest.fixture
def marker():
    def make(slug, price, *, city="Praha", fresh="Dnes", name=None):
        return {
            "url": f"/Ceny-benzinu-a-nafty/{city}/{slug}/123",
            "name": name or slug,
            "price": price,
            "fresh": fresh,
            "lat": 50.1,
            "lng": 14.4,
        }

    return make


@pytest.fixture
def mock_frontend():
    with (
        patch("homeassistant.components.frontend.async_setup", new=AsyncMock(return_value=True)),
        patch("homeassistant.components.http.HomeAssistantHTTP.start", new=AsyncMock()),
        patch("custom_components.ceny_paliv.add_extra_js_url"),
        patch("custom_components.ceny_paliv.config_flow.async_get_clientsession", return_value=MagicMock()),
        patch("custom_components.ceny_paliv.coordinator.async_get_clientsession", return_value=MagicMock()),
    ):
        yield
