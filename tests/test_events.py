"""Price-change events and the blueprints that use them, run as real automations."""
import json
import shutil
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.ceny_paliv.api import MarkerSnapshot
from custom_components.ceny_paliv.const import DOMAIN

ROOT = Path(__file__).parents[1]
FETCH = "custom_components.ceny_paliv.coordinator.async_fetch_snapshot"
PRAHA = (50.08, 14.42)


@pytest.fixture
def prices(marker):
    """The markers the next refresh returns: set `prices.markers` to change them."""

    class Prices:
        markers: list = []

        async def fetch(self, *args, **kwargs):
            return MarkerSnapshot(markers=[dict(m) for m in self.markers], fetched_at=dt_util.now())

    return Prices()


async def _setup(hass, entry, prices):
    entry.add_to_hass(hass)
    with patch(FETCH, new=AsyncMock(side_effect=prices.fetch)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def _refresh(hass, entry, prices):
    with patch(FETCH, new=AsyncMock(side_effect=prices.fetch)):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()


def _city_entry():
    return MockConfigEntry(
        domain=DOMAIN, title="Ceny paliv Praha", data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Oblibena"}}, unique_id="Praha",
    )


async def test_the_event_entity_reports_real_price_changes(hass, enable_custom_integrations, mock_frontend, marker, prices):
    entry = _city_entry()
    prices.markers = [marker("Oblibena", 35), marker("Levna", 33)]
    await _setup(hass, entry, prices)
    entity_id = "event.ceny_paliv_n95_price_change"
    state = hass.states.get(entity_id)
    assert state.state == "unknown"  # the prices at start-up are only the baseline
    assert state.attributes["event_types"] == ["favourite_cheaper", "favourite_dearer", "cheapest_cheaper"]
    assert state.attributes["friendly_name"] == "Ceny paliv Praha Natural 95 · price change"

    seen = []
    hass.bus.async_listen("state_changed", lambda event: seen.append(event.data["new_state"].attributes.get("event_type")) if event.data["entity_id"] == entity_id else None)

    # nothing changed: no event
    await _refresh(hass, entry, prices)
    assert seen == [None] or seen == []

    # the favourite drops below the cheapest: two events from one refresh, both seen
    seen.clear()
    prices.markers = [marker("Oblibena", 32.5), marker("Levna", 33)]
    await _refresh(hass, entry, prices)
    events = [event for event in seen if event]
    assert events == ["favourite_cheaper", "cheapest_cheaper"]
    state = hass.states.get(entity_id)
    assert state.attributes["station"] == "Oblibena · Praha"
    assert (state.attributes["price"], state.attributes["previous_price"]) == (32.5, 33.0)  # the cheapest was 33

    seen.clear()
    prices.markers = [marker("Oblibena", 34), marker("Levna", 33)]
    await _refresh(hass, entry, prices)
    assert [event for event in seen if event] == ["favourite_dearer"]
    state = hass.states.get(entity_id)
    assert (state.attributes["price"], state.attributes["previous_price"], state.attributes["change"]) == (34.0, 32.5, 1.5)
    assert state.attributes["fuel"] == "Natural 95"
    assert state.attributes["unit"] == "Kč/l"

    # mBenzin cannot be reached: the last prices stay and nothing is reported
    seen.clear()
    with patch(FETCH, new=AsyncMock(side_effect=__import__("aiombenzin").CannotConnect("down"))):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
    assert not [event for event in seen if event]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_choosing_another_favourite_is_not_a_price_change(hass, enable_custom_integrations, mock_frontend, marker, prices):
    entry = _city_entry()
    prices.markers = [marker("Oblibena", 35), marker("Jina", 34), marker("Levna", 33)]
    await _setup(hass, entry, prices)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "homes": {"n95": "Jina"}})
    await hass.async_block_till_done()
    with patch(FETCH, new=AsyncMock(side_effect=prices.fetch)):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    await _refresh(hass, entry, prices)
    assert hass.states.get("event.ceny_paliv_n95_price_change").state == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)


def test_event_translations_and_icon():
    root = ROOT / "custom_components" / "ceny_paliv"
    for language in ("en", "cs"):
        event = json.loads((root / "translations" / f"{language}.json").read_text("utf-8"))["entity"]["event"]
        assert set(event) == {"price_change"}
        assert "{fuel}" in event["price_change"]["name"]
        states = event["price_change"]["state_attributes"]["event_type"]["state"]
        assert set(states) == {"favourite_cheaper", "favourite_dearer", "cheapest_cheaper"}
    icons = json.loads((root / "icons.json").read_text("utf-8"))["entity"]["event"]
    assert set(icons) == {"price_change"}


@pytest.fixture
def blueprints(hass, tmp_path):
    """The repository's blueprints, installed in a configuration folder of their own."""
    hass.config.config_dir = str(tmp_path)
    shutil.copytree(ROOT / "blueprints", tmp_path / "blueprints")
    return async_mock_service(hass, "test", "notify")


def _automation(path, **inputs):
    return {
        "use_blueprint": {
            "path": f"ceny_paliv/{path}",
            "input": {**inputs, "actions": [{"action": "test.notify", "data": {"title": "{{ title }}", "message": "{{ message }}"}}]},
        }
    }


async def test_favourite_price_change_blueprint(hass, enable_custom_integrations, mock_frontend, marker, prices, blueprints):
    entry = _city_entry()
    prices.markers = [marker("Oblibena", 35), marker("Levna", 33)]
    await _setup(hass, entry, prices)
    assert await async_setup_component(hass, "automation", {"automation": [
        _automation("favourite_price_change.yaml", price_events="event.ceny_paliv_n95_price_change", language="cs"),
        _automation("favourite_price_change.yaml", price_events="event.ceny_paliv_n95_price_change", direction="both", min_change=1),
    ]})
    await hass.async_block_till_done()

    prices.markers = [marker("Oblibena", 34.5), marker("Levna", 33)]
    await _refresh(hass, entry, prices)
    # the first automation: any drop; the second ignores a change under 1 Kč
    assert [call.data["message"] for call in blueprints] == ["Oblibena · Praha: 34.50 Kč/l (▼ 0.50, dříve 35.00)"]
    assert blueprints[0].data["title"] == "⛽ Natural 95: cena klesla"

    blueprints.clear()
    prices.markers = [marker("Oblibena", 36), marker("Levna", 33)]
    await _refresh(hass, entry, prices)
    # dearer: only the second one, which follows both directions
    assert [call.data["message"] for call in blueprints] == ["Oblibena · Praha: 36.00 Kč/l (▲ 1.50, was 34.50)"]
    assert blueprints[0].data["title"] == "⛽ Natural 95: price up"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_price_below_limit_blueprint(hass, enable_custom_integrations, mock_frontend, marker, prices, blueprints):
    entry = _city_entry()
    prices.markers = [marker("Oblibena", 35), marker("Levna", 33)]
    await _setup(hass, entry, prices)
    assert await async_setup_component(hass, "automation", {"automation": [
        _automation("price_below_limit.yaml", price_sensor="sensor.ceny_paliv_n95_top5", limit=32),
        _automation("price_below_limit.yaml", price_sensor="sensor.ceny_paliv_n95_home", limit=34, language="cs"),
    ]})
    await hass.async_block_till_done()

    prices.markers = [marker("Oblibena", 33.9), marker("Levna", 31.9)]
    await _refresh(hass, entry, prices)
    assert sorted(call.data["message"] for call in blueprints) == [
        "Ceny paliv Praha Natural 95 · cheapest: 31.90 Kč/l · Levna · Praha",
        "Ceny paliv Praha Natural 95 · favourite station: 33.90 Kč/l · Oblibena · Praha",
    ]
    assert sorted(call.data["title"] for call in blueprints) == ["⛽ Cena pod 34 Kč/l", "⛽ Price under 32 Kč/l"]

    # still under the limit: not again
    blueprints.clear()
    prices.markers = [marker("Oblibena", 33.8), marker("Levna", 31.8)]
    await _refresh(hass, entry, prices)
    assert blueprints == []
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_cheap_station_nearby_blueprint(hass, enable_custom_integrations, mock_frontend, marker, prices, blueprints, freezer):
    hass.config.latitude, hass.config.longitude = PRAHA
    hass.states.async_set("person.driver", "not_home")
    entry = MockConfigEntry(
        domain=DOMAIN, title="Ceny paliv GPS area", data={"key": "dummy", "city": ""},
        options={"fuels": ["n95"], "homes": {}, "area_mode": "gps", "location_method": "home", "gps_radius_km": 20},
        unique_id="gps-nearby",
    )

    def at(slug, price, north_km):
        return {**marker(slug, price), "lat": PRAHA[0] + north_km / 111.2, "lng": PRAHA[1]}

    prices.markers = [at("Daleko", 33, 15), at("Blizko", 36, 2)]
    await _setup(hass, entry, prices)
    assert await async_setup_component(hass, "automation", {"automation": [
        _automation("cheap_station_nearby.yaml", cheapest_sensor="sensor.ceny_paliv_n95_top5", person="person.driver",
                    max_price=35, max_distance=10, pause=3),
    ]})
    await hass.async_block_till_done()

    # cheap but far, near but dear: nothing
    await _refresh(hass, entry, prices)
    assert blueprints == []

    prices.markers = [at("Daleko", 33, 15), at("Blizko", 34.5, 2)]
    await _refresh(hass, entry, prices)
    assert [call.data["message"] for call in blueprints] == ["Blizko · Praha: 34.50 Kč/l, 2.0 km"]
    assert blueprints[0].data["title"] == "⛽ Cheap station nearby"

    # within the pause: quiet; after it, again
    blueprints.clear()
    prices.markers = [at("Daleko", 33, 15), at("Blizko", 34.4, 2)]
    await _refresh(hass, entry, prices)
    assert blueprints == []
    freezer.tick(timedelta(hours=3, minutes=1))
    prices.markers = [at("Daleko", 33, 15), at("Blizko", 34.3, 2)]
    await _refresh(hass, entry, prices)
    assert len(blueprints) == 1

    # at home: never
    blueprints.clear()
    hass.states.async_set("person.driver", "home")
    freezer.tick(timedelta(hours=4))
    prices.markers = [at("Daleko", 33, 15), at("Blizko", 34.2, 2)]
    await _refresh(hass, entry, prices)
    assert blueprints == []
    assert await hass.config_entries.async_unload(entry.entry_id)
