"""The ceny_paliv.refresh action (quality scale: action-setup, action-exceptions, exception-translations)."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv.api import CannotConnect, RateLimited, shared_marker_cache
from custom_components.ceny_paliv.const import DOMAIN

FETCH = "custom_components.ceny_paliv.api._async_fetch_markers"


async def _refresh(hass, **data):
    await hass.services.async_call(DOMAIN, "refresh", data, blocking=True)


async def test_refresh_refuses_areas_that_are_not_running(hass, enable_custom_integrations, mock_frontend):
    # registered with the integration, before any area exists
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "refresh")

    with pytest.raises(ServiceValidationError) as err:
        await _refresh(hass)
    assert err.value.translation_key == "no_loaded_entries"

    with pytest.raises(ServiceValidationError) as err:
        await _refresh(hass, config_entry_id="missing")
    assert err.value.translation_key == "entry_not_found"

    other = MockConfigEntry(domain="sun")
    other.add_to_hass(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _refresh(hass, config_entry_id=other.entry_id)
    assert err.value.translation_key == "entry_not_found"

    stopped = MockConfigEntry(domain=DOMAIN, title="Ceny paliv Brno", data={"key": "dummy", "city": "Brno"})
    stopped.add_to_hass(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _refresh(hass, config_entry_id=stopped.entry_id)
    assert err.value.translation_key == "entry_not_loaded"
    # the message is translated (translations/en.json), with the area's name filled in
    assert str(err.value) == (
        "The Ceny paliv area Ceny paliv Brno is not running; see its state in Settings → Devices & services"
    )


async def test_refresh_downloads_again_at_most_every_30_minutes_and_reports_what_failed(
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
    downloads: list[str] = []
    failing: dict[str, Exception] = {}

    async def fetch(session, key, fuel, clock=None):
        downloads.append(fuel)
        if fuel in failing:
            raise failing[fuel]
        return [marker("Levna", 33)]

    with patch(FETCH, new=AsyncMock(side_effect=fetch)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # the shared cache counts its lifetimes on the event loop clock: let it follow the frozen time
        shared_marker_cache(hass)._monotonic = lambda: dt_util.utcnow().timestamp()
        assert downloads == ["n95", "diesel"]

        # data younger than 30 minutes is reused: a repeated call cannot flood mBenzin.cz
        freezer.tick(timedelta(minutes=10))
        await _refresh(hass)
        assert len(downloads) == 2

        freezer.tick(timedelta(minutes=25))
        await _refresh(hass, config_entry_id=entry.entry_id)
        assert downloads[2:] == ["n95", "diesel"]

        # mBenzin.cz does not answer for diesel: its cached prices (still within their lifetime) stay
        freezer.tick(timedelta(minutes=40))
        failing["diesel"] = CannotConnect()
        with pytest.raises(HomeAssistantError) as err:
            await _refresh(hass)
        assert err.value.translation_key == "refresh_failed"
        assert err.value.translation_placeholders == {"failed": "—", "kept": "Ceny paliv Praha · Diesel"}
        assert hass.states.get("sensor.ceny_paliv_diesel_top5").state == "33"

        # during a 429 cooldown nothing is downloaded and every cached price stays
        freezer.tick(timedelta(minutes=40))
        failing.clear()
        failing["n95"] = RateLimited(retry_after=600)
        count = len(downloads)
        with pytest.raises(HomeAssistantError) as err:
            await _refresh(hass)
        assert downloads[count:] == ["n95"]  # diesel waits for the cooldown of the key
        assert err.value.translation_placeholders["kept"] == "Ceny paliv Praha · Natural 95, Ceny paliv Praha · Diesel"

        # without cached prices a failing fuel fails, and its sensors become unavailable
        freezer.tick(timedelta(hours=6))
        failing.clear()
        failing["diesel"] = CannotConnect()
        with pytest.raises(HomeAssistantError) as err:
            await _refresh(hass)
        assert err.value.translation_placeholders == {"failed": "Ceny paliv Praha · Diesel (CannotConnect)", "kept": "—"}
        assert hass.states.get("sensor.ceny_paliv_diesel_top5").state == "unavailable"
        assert hass.states.get("sensor.ceny_paliv_n95_top5").state == "33"

        # nothing at all: the whole area failed
        freezer.tick(timedelta(hours=6))
        failing["n95"] = CannotConnect()
        with pytest.raises(HomeAssistantError) as err:
            await _refresh(hass)
        assert err.value.translation_placeholders["failed"] == (
            "Ceny paliv Praha (mBenzin.cz could not be reached for any fuel (n95: CannotConnect, diesel: CannotConnect))"
        )
        assert str(err.value).startswith("Not all prices could be refreshed from mBenzin.cz. Failed: Ceny paliv Praha")
    assert await hass.config_entries.async_unload(entry.entry_id)


def test_english_and_czech_translations_have_the_same_keys_and_placeholders():
    """Every action, field, exception and entity text exists in both languages, with the same placeholders."""
    import json
    import re
    from pathlib import Path

    from custom_components.ceny_paliv import const

    folder = Path(const.__file__).parent / "translations"

    def flatten(node, path=()):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from flatten(value, (*path, key))
        else:
            yield path, frozenset(re.findall(r"\{(\w+)\}", node))

    english = dict(flatten(json.loads((folder / "en.json").read_text("utf-8"))))
    czech = dict(flatten(json.loads((folder / "cs.json").read_text("utf-8"))))
    assert english == czech
    assert {path[1] for path in english if path[0] == "exceptions"} == {
        "update_failed", "invalid_auth", "no_loaded_entries", "entry_not_found", "entry_not_loaded", "refresh_failed",
    }
