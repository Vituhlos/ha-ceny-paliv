"""Repairs issues (quality scale: repair-issues): raised only for what the user can fix, cleared by itself."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv.api import CannotConnect, MarkerSnapshot
from custom_components.ceny_paliv.const import DOMAIN

FETCH = "custom_components.ceny_paliv.coordinator.async_fetch_snapshot"


def _issue(hass, issue_id):
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


async def test_a_deleted_zone_raises_an_issue_until_it_is_back(
    hass, enable_custom_integrations, mock_frontend, marker
):
    hass.states.async_set("zone.cottage", "0", {"latitude": 50.1, "longitude": 14.4, "radius": 100})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ceny paliv GPS area",
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {}, "area_mode": "gps", "location_method": "zone", "zone_entity": "zone.cottage"},
        unique_id="gps-zone",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Levna", 33)], fetched_at=dt_util.now())
    issue_id = f"gps_location_{entry.entry_id}"
    with patch(FETCH, new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert _issue(hass, issue_id) is None

        hass.states.async_remove("zone.cottage")  # the zone listener refreshes at once
        await hass.async_block_till_done()
        issue = _issue(hass, issue_id)
        assert issue.translation_key == "zone_missing"
        assert issue.severity is ir.IssueSeverity.ERROR
        assert issue.is_fixable is False
        assert issue.translation_placeholders == {"title": "Ceny paliv GPS area", "zone": "zone.cottage"}

        hass.states.async_set("zone.cottage", "0", {"latitude": 50.1, "longitude": 14.4, "radius": 100})
        await hass.async_block_till_done()
        assert _issue(hass, issue_id) is None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_an_invalid_home_location_raises_an_issue(hass, enable_custom_integrations, mock_frontend, marker):
    hass.config.latitude = float("nan")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ceny paliv GPS area",
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {}, "area_mode": "gps", "location_method": "home"},
        unique_id="gps-home",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Levna", 33)], fetched_at=dt_util.now())
    with patch(FETCH, new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        issue = _issue(hass, f"gps_location_{entry.entry_id}")
        assert issue.translation_key == "invalid_location"
        assert issue.translation_placeholders == {"title": "Ceny paliv GPS area"}

        hass.config.latitude = 50.1
        await entry.runtime_data.async_refresh()
        assert _issue(hass, f"gps_location_{entry.entry_id}") is None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_prices_missing_for_a_day_raise_an_issue_that_clears_itself(
    hass, enable_custom_integrations, mock_frontend, marker, freezer
):
    freezer.move_to("2026-11-14 10:00:00+01:00")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ceny paliv Praha",
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95", "diesel"], "homes": {}},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    failing: set[str] = set()

    async def fetch(session, key, fuel, *, cache=None, max_age=None):
        if fuel in failing:
            raise CannotConnect()
        return MarkerSnapshot(markers=[marker("Levna", 33)], fetched_at=dt_util.now())

    issue_id = f"no_data_{entry.entry_id}"
    with patch(FETCH, new=AsyncMock(side_effect=fetch)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data

        # a missed refresh or three is an outage, not something to repair
        failing.add("n95")
        freezer.tick(timedelta(hours=18))
        await coordinator.async_refresh()
        assert _issue(hass, issue_id) is None

        freezer.tick(timedelta(hours=7))  # 25 hours without Natural 95
        await coordinator.async_refresh()
        issue = _issue(hass, issue_id)
        assert issue.translation_key == "no_data"
        assert issue.severity is ir.IssueSeverity.WARNING
        assert issue.translation_placeholders == {
            "title": "Ceny paliv Praha",
            "fuels": "Natural 95",
            "since": dt_util.as_local(dt_util.parse_datetime("2026-11-14T10:00:00+01:00")).strftime("%Y-%m-%d %H:%M"),
            "url": "https://www.mbenzin.cz",
        }

        # every fuel failing: the issue is updated before the coordinator fails
        failing.add("diesel")
        freezer.tick(timedelta(hours=25))
        await coordinator.async_refresh()
        assert not coordinator.last_update_success
        assert _issue(hass, issue_id).translation_placeholders["fuels"] == "Natural 95, Diesel"

        failing.clear()
        await coordinator.async_refresh()
        assert _issue(hass, issue_id) is None

        # deleting the area takes its issues with it
        failing.add("n95")
        freezer.tick(timedelta(hours=25))
        await coordinator.async_refresh()
        assert _issue(hass, issue_id) is not None
        assert await hass.config_entries.async_remove(entry.entry_id)
        assert _issue(hass, issue_id) is None
