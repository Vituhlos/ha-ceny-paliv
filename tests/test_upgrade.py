"""Upgrading an install of 0.5.3: everything carries over without the user doing anything."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv.api import MarkerSnapshot
from custom_components.ceny_paliv.const import DOMAIN

FETCH = "custom_components.ceny_paliv.coordinator.async_fetch_snapshot"
CITY = "Brandys-nad-Labem---Stara-Boleslav"


async def test_an_install_of_0_5_3_upgrades_by_itself(
    hass, hass_storage, enable_custom_integrations, mock_frontend, marker
):
    # what 0.5.3 left behind: its automatic title, entities without a device, named in code, with icons
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        title="Ceny paliv Brandys nad Labem   Stara Boleslav",
        data={"key": "dummy", "city": CITY},
        options={
            "fuels": ["n95"],
            "homes": {"n95": "Oblibena"},
            "language": "cs",
            # a favourite changed in 0.5: its old sensor is archived
            "home_history": {"n95": [{"identity": f"/Ceny-benzinu-a-nafty/{CITY}/Stara/1", "legacy": False}]},
        },
        unique_id=CITY,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = {
        "top5": ("Ceny paliv n95 top5", "mdi:gas-station"),
        "home": ("Ceny paliv n95 home", "mdi:gas-station-in-use"),
        "1": ("Ceny paliv n95 1", "mdi:gas-station"),
    }
    for suffix, (name, icon) in old.items():
        registry.async_get_or_create(
            "sensor", DOMAIN, f"{entry.entry_id}_n95_{suffix}",
            suggested_object_id=f"ceny_paliv_n95_{suffix}", config_entry=entry,
            original_name=name, original_icon=icon, has_entity_name=False,
        )
    yesterday = (dt_util.now().date() - timedelta(days=1)).isoformat()
    station = marker("Oblibena", 35, city=CITY)
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {"n95": {station["url"]: [[yesterday, 34]]}},
    }

    snapshot = MarkerSnapshot(markers=[station, marker("Levna", 33, city=CITY)], fetched_at=dt_util.now())
    with patch(FETCH, new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    # the entry is migrated; the area's device carries the tidied title
    assert entry.minor_version == 2
    assert entry.title == "Ceny paliv Brandys nad Labem Stara Boleslav"
    [device] = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.name == "Ceny paliv Brandys nad Labem Stara Boleslav"

    # the same entity ids (dashboards, automations and history keep working), now under the device
    for suffix in old:
        entity_id = f"sensor.ceny_paliv_n95_{suffix}"
        registered = registry.async_get(entity_id)
        assert registered.unique_id == f"{entry.entry_id}_n95_{suffix}"
        assert registered.device_id == device.id
        assert registered.has_entity_name is True
        assert registered.translation_key is not None
        assert registered.original_icon is None  # the icon comes from icons.json
    assert hass.states.get("sensor.ceny_paliv_n95_top5").attributes["friendly_name"] == (
        "Ceny paliv Brandys nad Labem Stara Boleslav Natural 95 · cheapest"  # the test runs in English
    )
    # the trends continue from the history 0.5 stored
    home = hass.states.get("sensor.ceny_paliv_n95_home")
    assert home.attributes["trends"]["1"]["ref_price"] == 34
    # the archive of the earlier favourite is now a diagnostic entity
    archives = [
        e for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.translation_key == "archived_favourite"
    ]
    assert len(archives) == 1
    assert archives[0].entity_category is EntityCategory.DIAGNOSTIC
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_a_title_the_user_typed_is_kept(hass, enable_custom_integrations, mock_frontend, marker):
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, minor_version=1, title="Benzín  u chalupy",
        data={"key": "dummy", "city": CITY}, options={"fuels": ["n95"], "homes": {}}, unique_id=CITY,
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Levna", 33, city=CITY)], fetched_at=dt_util.now())
    with patch(FETCH, new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.minor_version == 2
    assert entry.title == "Benzín  u chalupy"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_an_entry_from_a_newer_version_is_not_touched(hass, enable_custom_integrations, mock_frontend):
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, minor_version=1, title="Ceny paliv Praha",
        data={"key": "dummy", "city": "Praha"}, options={"fuels": ["n95"]}, unique_id="Praha",
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.title == "Ceny paliv Praha"
