"""A station map reads bounded cached area data using the selected sensor's permission."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web
import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv import CenyPalivStationsView
from custom_components.ceny_paliv.api import build_payload
from custom_components.ceny_paliv.const import DOMAIN


def test_map_bounds_preserve_favourite_and_exclude_old_prices(marker, now):
    markers = [marker(f"Station-{n}", 30 + n / 100, city="Brno") for n in range(90)]
    markers.extend([marker("Old", 20, city="Brno", fresh="1.1.2000"), marker("Elsewhere", 20, city="Lhota")])
    result = build_payload(markers, city="Brno", fuel="n95", home_slug="Station-89", now=now, history={})
    assert len(result["stations"]) == 5
    assert len(result["map_stations"]) == 80
    assert [r["rank"] for r in result["map_stations"]] == [*range(1, 80), 90]
    assert result["map_stations"][-1]["home"]
    assert all(r["name"].startswith("Station-") and "trends" not in r for r in result["map_stations"])


async def test_map_endpoint_tracks_entity_permissions_and_renames(hass, enable_custom_integrations, mock_frontend, marker):
    entry = MockConfigEntry(domain=DOMAIN, data={"key": "dummy", "city": "Brno"})
    entry.add_to_hass(hass)
    with patch("custom_components.ceny_paliv.api._async_fetch_markers", new=AsyncMock(return_value=[
        marker("Test", 30, city="Brno")
    ])):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        registry.async_update_entity("sensor.ceny_paliv_n95_top5", new_entity_id="sensor.test_map")
        view = CenyPalivStationsView(hass)
        assert view.requires_auth
        user = MagicMock()
        req = {"hass_user": user}
        user.permissions.check_entity.return_value = False
        with pytest.raises(web.HTTPForbidden):
            await view.get(req, "sensor.test_map")
        user.permissions.check_entity.assert_called_once_with("sensor.test_map", "read")
        user.permissions.check_entity.return_value = True
        for entity_id in ("sensor.nonexistent", "sensor.ceny_paliv_n95_area_average"):
            with pytest.raises(web.HTTPNotFound):
                await view.get(req, entity_id)
        response = await view.get(req, "sensor.test_map")
        assert json.loads(response.body)["stations"][0]["name"] == "Test"
        assert response.headers["Cache-Control"] == "no-store"
        assert "map_stations" not in hass.states.get("sensor.test_map").attributes
        assert await hass.config_entries.async_unload(entry.entry_id)
        with pytest.raises(web.HTTPNotFound):
            await view.get(req, "sensor.test_map")
