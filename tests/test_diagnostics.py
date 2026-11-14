"""Diagnostics download (quality scale: diagnostics): useful state, no key, no home location."""
from http import HTTPStatus
import json
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from yarl import URL

from custom_components.ceny_paliv.api import CannotConnect, MarkerSnapshot
from custom_components.ceny_paliv.const import DOMAIN

KEY = "secret-key-123"
REDACTED = "**REDACTED**"


@pytest.fixture(autouse=True)
def block_network():
    """The download goes through Home Assistant's HTTP API on the loopback test server: allow only that host.

    The threaded resolver keeps aiohttp from starting aiodns, whose shutdown thread outlives the test on
    Home Assistant 2025.1 and fails its thread check; the test server's address is an IP, so nothing is resolved.
    """
    real_request = aiohttp.ClientSession._request

    async def loopback_only(self, method, url, *args, **kwargs):
        assert URL(str(url)).host == "127.0.0.1", f"Network access is forbidden: {url}"
        return await real_request(self, method, url, *args, **kwargs)

    with (
        patch("aiohttp.ClientSession._request", loopback_only),
        patch("aiohttp.connector.DefaultResolver", aiohttp.ThreadedResolver),
    ):
        yield


async def _download(hass, hass_client, entry):
    """What the user gets from Settings → Devices & services → Ceny paliv → Download diagnostics."""
    assert await async_setup_component(hass, "diagnostics", {})
    client = await hass_client()
    response = await client.get(f"/api/diagnostics/config_entry/{entry.entry_id}")
    assert response.status == HTTPStatus.OK
    return (await response.json())["data"]


async def test_city_diagnostics_show_the_refresh_without_the_key_or_favourite(
    hass, hass_client, enable_custom_integrations, mock_frontend, marker
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ceny paliv Praha",
        data={"key": KEY, "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Oblibena"}, "language": "cs", "logos": ["orlen"]},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Oblibena", 35), marker("Levna", 33)], fetched_at=dt_util.now())
    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        data = await _download(hass, hass_client, entry)

    dump = json.dumps(data)
    assert KEY not in dump
    assert "Oblibena" not in dump  # neither the favourite nor the station list
    assert data["entry"]["data"] == {"key": REDACTED, "city": "Praha"}
    assert data["entry"]["options"]["homes"] == REDACTED
    assert data["entry"]["options"]["logos"] == ["orlen"]
    assert data["coordinator"] == {
        "last_update_success": True,
        "last_exception": None,
        "update_interval": "6:00:00",
        "failed_fuels": [],
    }
    n95 = data["fuels"]["n95"]
    assert n95["stations"] == 2
    assert n95["city_name"] == "Praha"
    assert n95["fetch_error"] is None
    assert n95["home_found"] is True
    assert n95["home_rank"] == 2
    assert n95["gps_nearest_stations"] == 0
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_gps_diagnostics_hide_the_centre_and_show_a_failing_fuel(
    hass, hass_client, enable_custom_integrations, mock_frontend, marker
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ceny paliv GPS area",
        data={"key": KEY, "city": "Praha"},
        options={
            "fuels": ["n95", "diesel"],
            "homes": {},
            "area_mode": "gps",
            "location_method": "manual",
            "location": {"latitude": 50.0875, "longitude": 14.4214},
            "gps_radius_km": 10,
        },
        unique_id="gps-diagnostics",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Levna", 33)], fetched_at=dt_util.now())
    fetch = AsyncMock(return_value=snapshot)
    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=fetch):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        async def diesel_fails(session, key, fuel, *, cache=None, max_age=None):
            if fuel == "diesel":
                raise CannotConnect()
            return snapshot

        fetch.side_effect = diesel_fails
        await entry.runtime_data.async_refresh()
        data = await _download(hass, hass_client, entry)

    dump = json.dumps(data)
    assert KEY not in dump
    assert "50.0875" not in dump and "14.4214" not in dump
    assert data["entry"]["options"]["location"] == REDACTED
    assert data["coordinator"]["failed_fuels"] == ["diesel"]
    assert data["fuels"]["diesel"]["fetch_error"] == "CannotConnect"
    area = data["fuels"]["n95"]["gps_area"]
    assert area["latitude"] == REDACTED and area["longitude"] == REDACTED
    assert area["radius_km"] == 10
    assert area["method"] == "manual"
    assert data["fuels"]["n95"]["home_found"] is False
    assert await hass.config_entries.async_unload(entry.entry_id)
