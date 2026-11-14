"""Long-term statistics per station: a station's price history survives a new favourite or a new setup."""
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_metadata, statistics_during_period
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.ceny_paliv.api import MarkerSnapshot
from custom_components.ceny_paliv.const import DOMAIN
from custom_components.ceny_paliv.statistics import async_import_station_statistics, station_statistic_id

FETCH = "custom_components.ceny_paliv.coordinator.async_fetch_snapshot"
FAVOURITE = "/Ceny-benzinu-a-nafty/Praha/Oblibena/123"
OTHER = "/Ceny-benzinu-a-nafty/Praha/Levna/123"


def _noon(day: str) -> datetime:
    return dt_util.as_utc(datetime.combine(datetime.fromisoformat(day).date(), time(12), dt_util.get_default_time_zone()))


async def _rows(hass, statistic_id):
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utcnow() - timedelta(days=40),
        None,
        {statistic_id},
        "hour",
        None,
        {"mean", "min", "max"},
    )
    return {datetime.fromtimestamp(row["start"], dt_util.UTC): row["mean"] for row in rows.get(statistic_id, [])}


def _entry(hass, favourite="Oblibena"):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ceny paliv Praha",
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": favourite}},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    return entry


async def test_the_favourite_keeps_its_history_per_station(
    recorder_mock, hass, hass_storage, enable_custom_integrations, mock_frontend, marker, freezer
):
    await hass.config.async_set_time_zone("Europe/Prague")
    freezer.move_to("2026-11-14 15:30:00+01:00")
    statistic_id = station_statistic_id("n95", FAVOURITE)
    entry = _entry(hass)
    # the daily price log the integration already kept for this station
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.{entry.entry_id}",
        # an entry the log should never hold is skipped, not recorded
        "data": {"n95": {FAVOURITE: [["not-a-date", 1], ["2026-11-12", 34.5], ["2026-11-13", 35.0]]}},
    }
    snapshot = MarkerSnapshot(markers=[marker("Oblibena", 35.5), marker("Levna", 33)], fetched_at=dt_util.now())
    with patch(FETCH, new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        home = hass.states.get("sensor.ceny_paliv_n95_home")
        assert home.attributes["statistic_id"] == statistic_id
        hour = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
        assert await _rows(hass, statistic_id) == {
            _noon("2026-11-12"): 34.5,
            _noon("2026-11-13"): 35.0,
            _noon("2026-11-14"): 35.5,  # today's sample, already past noon
            hour: 35.5,
        }
        metadata = await get_instance(hass).async_add_executor_job(
            lambda: get_metadata(hass, statistic_ids={statistic_id})
        )
        assert metadata[statistic_id][1]["name"] == "Natural 95 · Oblibena · Praha"
        assert metadata[statistic_id][1]["unit_of_measurement"] == "Kč/l"
        assert metadata[statistic_id][1]["source"] == DOMAIN

        # the integration is removed and added again: the station's history is still there and continues
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        freezer.tick(timedelta(hours=6))
        again = _entry(hass)
        assert await hass.config_entries.async_setup(again.entry_id)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
        rows = await _rows(hass, statistic_id)
        assert _noon("2026-11-12") in rows and _noon("2026-11-13") in rows
        assert rows[hour + timedelta(hours=6)] == 35.5

        # another favourite gets its own statistics; the first station's are not touched
        hass.config_entries.async_update_entry(again, options={"fuels": ["n95"], "homes": {"n95": "Levna"}})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
        other = station_statistic_id("n95", OTHER)
        assert other != statistic_id
        assert set((await _rows(hass, other)).values()) == {33.0}
        assert len(await _rows(hass, statistic_id)) == len(rows)
    assert await hass.config_entries.async_unload(again.entry_id)


async def test_without_the_recorder_only_the_statistic_id_is_given(hass):
    home = {"url": FAVOURITE, "price": 35.5, "title": "Oblibena · Praha"}
    assert "recorder" not in hass.config.components
    assert async_import_station_statistics(hass, "n95", home, [], dt_util.now()) == station_statistic_id(
        "n95", FAVOURITE
    )
    # nothing to identify the station by, or no price: nothing to record
    assert async_import_station_statistics(hass, "n95", {"price": 35.5}, [], dt_util.now()) is None
    assert async_import_station_statistics(hass, "n95", {"url": FAVOURITE, "price": True}, [], dt_util.now()) is None


def test_statistic_ids_are_valid_and_stable():
    from homeassistant.components.recorder.statistics import valid_statistic_id

    statistic_id = station_statistic_id("dieselplus", FAVOURITE)
    assert valid_statistic_id(statistic_id)
    assert statistic_id == station_statistic_id("dieselplus", FAVOURITE)
    assert statistic_id != station_statistic_id("diesel", FAVOURITE)
