"""Home Assistant configuration, coordinator and sensor regressions."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv.api import CannotConnect, InvalidAuth
from custom_components.ceny_paliv.const import DOMAIN


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


async def test_config_flow(hass, enable_custom_integrations, mock_frontend, marker):
    markers = [marker("Oblibena", 33)]
    with (
        patch("custom_components.ceny_paliv.config_flow.async_fetch_markers", new=AsyncMock(return_value=markers)) as fetch,
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        assert result["step_id"] == "city"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"city": "Praha"})
        assert result["step_id"] == "fuels"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "cs"},
        )
        assert result["step_id"] == "station"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station": "Oblibena"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {"key": "dummy", "city": "Praha"}
        assert result["options"]["homes"] == {"n95": "Oblibena"}
        assert fetch.await_count == 2
        await hass.async_block_till_done()


async def test_config_flow_invalid_key_and_duplicate_city(hass, enable_custom_integrations, mock_frontend, marker):
    entry = MockConfigEntry(domain=DOMAIN, data={"key": "dummy", "city": "Praha"}, unique_id="Praha")
    entry.add_to_hass(hass)
    with patch("custom_components.ceny_paliv.config_flow.async_fetch_markers", new=AsyncMock(side_effect=InvalidAuth)) as fetch:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        assert result["errors"]["base"] == "invalid_auth"
        fetch.side_effect = None
        fetch.return_value = [marker("Oblibena", 33)]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"city": "Praha"})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_options_flow_preserves_settings(hass, enable_custom_integrations, mock_frontend, marker):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Oblibena"}, "language": "cs"},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.ceny_paliv.config_flow.async_fetch_markers", new=AsyncMock(return_value=[marker("Oblibena", 33)])),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["step_id"] == "fuels"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "cs"},
        )
        assert result["step_id"] == "station"
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"station": "Oblibena"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options["homes"] == {"n95": "Oblibena"}
        assert entry.options["language"] == "cs"


async def test_coordinator_sensors_and_failed_refresh(hass, enable_custom_integrations, mock_frontend, marker):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95", "diesel"], "homes": {"n95": "Oblibena"}, "language": "cs"},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    markers = [marker("Oblibena", 35), marker("Levna", 33)]
    with patch("custom_components.ceny_paliv.coordinator.async_fetch_markers", new=AsyncMock(return_value=markers)) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert fetch.await_count == 2
        top = hass.states.get("sensor.ceny_paliv_n95_top5")
        home = hass.states.get("sensor.ceny_paliv_n95_home")
        position = hass.states.get("sensor.ceny_paliv_n95_1")
        assert top.state == "33"
        assert top.attributes["city_total"] == 2
        assert home.state == "35"
        assert home.attributes["rank"] == 2
        assert position.state == "33"
        assert position.attributes["latitude"] == 50.1
        saved = await entry.runtime_data._store.async_load()
        assert saved["n95"]["Oblibena"][-1][1] == 35

        async def partial_failure(session, key, fuel, *, cache=None):
            if fuel == "n95":
                raise CannotConnect()
            return [marker("Levna", 32)]

        fetch.side_effect = partial_failure
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        top = hass.states.get("sensor.ceny_paliv_n95_top5")
        assert top.state == "33"
        assert top.attributes["fetch_error"] == "CannotConnect"
        assert hass.states.get("sensor.ceny_paliv_diesel_top5").state == "32"
        assert await hass.config_entries.async_unload(entry.entry_id)
