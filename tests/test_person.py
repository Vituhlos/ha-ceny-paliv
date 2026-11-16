"""The GPS area that follows a person: it moves with them and sends no extra request to mBenzin.cz."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.ceny_paliv.const import DOMAIN

FLOW = "custom_components.ceny_paliv.config_flow"
PRAHA = (50.08, 14.42)
BRNO = (49.19, 16.61)
PERSON = "person.driver"


def _station(marker, slug, price, city, where):
    return {**marker(slug, price, city=city), "lat": where[0], "lng": where[1]}


def _at(hass, where, *, state="not_home"):
    attributes = {"latitude": where[0], "longitude": where[1]} if where else {}
    hass.states.async_set(PERSON, state, attributes)


async def test_the_flow_follows_a_person_chosen_by_the_user(hass, enable_custom_integrations, mock_frontend, marker):
    hass.config.latitude, hass.config.longitude = PRAHA
    _at(hass, BRNO)
    markers = [_station(marker, "Praha-1", 33, "Praha", PRAHA), _station(marker, "Brno-1", 34, "Brno", BRNO)]
    with (
        patch(f"{FLOW}.async_fetch_markers", new=AsyncMock(return_value=markers)),
        patch(f"{FLOW}.async_fetch_index", new=AsyncMock(return_value=None)),
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"area_mode": "gps"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"location_method": "person"})
        assert result["step_id"] == "location_person"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"person_entity": "person.nobody"})
        assert result["errors"] == {"person_entity": "invalid_person"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"person_entity": PERSON})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"gps_radius_km": 10})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"fuels": ["n95"], "language": "en"})
        assert result["step_id"] == "station"
        # the favourites offered are around the person, not around home
        (station_key,) = result["data_schema"].schema
        labels = [option["label"] for option in result["data_schema"].schema[station_key].config["options"]]
        assert any("Brno" in label for label in labels)
        assert not any("Praha" in label for label in labels)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["location_method"] == "person"
    assert result["options"]["person_entity"] == PERSON


async def test_the_area_moves_with_the_person_without_new_downloads(
    hass, enable_custom_integrations, mock_frontend, marker, freezer
):
    from custom_components.ceny_paliv.diagnostics import async_get_config_entry_diagnostics

    hass.config.latitude, hass.config.longitude = PRAHA
    _at(hass, PRAHA)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ceny paliv GPS area",
        data={"key": "dummy", "city": ""},
        options={
            "fuels": ["n95"],
            "homes": {},
            "area_mode": "gps",
            "location_method": "person",
            "person_entity": PERSON,
            "gps_radius_km": 10,
        },
        unique_id="gps-person",
    )
    entry.add_to_hass(hass)
    markers = [_station(marker, "Praha-1", 33, "Praha", PRAHA), _station(marker, "Brno-1", 34, "Brno", BRNO)]
    downloads = AsyncMock(return_value=markers)

    def nearest():
        state = hass.states.get("sensor.ceny_paliv_n95_top5")
        return [station["name"] for station in state.attributes["stations"]], state.attributes["gps_area"]

    async def moved(where, **kwargs):
        # Home Assistant runs one requested refresh at once and gathers the next ones for 10 seconds
        _at(hass, where, **kwargs)
        await hass.async_block_till_done()
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    issue_id = f"gps_location_{entry.entry_id}"
    with patch("aiombenzin.async_fetch_markers", new=downloads):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert nearest()[0] == ["Praha-1"]
        assert downloads.await_count == 1

        # a few hundred metres: nothing is computed again
        await moved((PRAHA[0] + 0.003, PRAHA[1]))
        assert nearest()[1]["latitude"] == PRAHA[0]

        # to Brno: the area follows, from the download already made
        await moved(BRNO)
        names, area = nearest()
        assert names == ["Brno-1"]
        assert (area["latitude"], area["longitude"], area["method"]) == (*BRNO, "person")
        assert downloads.await_count == 1

        # no location (phone off): the area waits at home, without a Repairs issue
        await moved(None, state="unknown")
        assert nearest()[0] == ["Praha-1"]
        assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None

        # who is followed stays out of the diagnostics
        data = await async_get_config_entry_diagnostics(hass, entry)
        assert data["entry"]["options"]["person_entity"] == "**REDACTED**"

        # the person is deleted: Repairs says so
        hass.states.async_remove(PERSON)
        await hass.async_block_till_done()
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
        assert issue.translation_key == "person_missing"
        assert issue.translation_placeholders == {"title": "Ceny paliv GPS area", "person": PERSON}
        assert downloads.await_count == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_leaving_the_person_source_forgets_who_was_followed(
    hass, enable_custom_integrations, mock_frontend, marker
):
    hass.config.latitude, hass.config.longitude = PRAHA
    _at(hass, PRAHA)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": ""},
        options={
            "fuels": ["n95"], "homes": {}, "area_mode": "gps", "location_method": "person",
            "person_entity": PERSON, "gps_radius_km": 10,
        },
        unique_id="gps-forget",
    )
    entry.add_to_hass(hass)
    markers = [_station(marker, "Praha-1", 33, "Praha", PRAHA)]
    with (
        patch(f"{FLOW}.async_fetch_markers", new=AsyncMock(return_value=markers)),
        patch(f"{FLOW}.async_fetch_index", new=AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"area_mode": "gps"})
        assert result["data_schema"].schema["location_method"].config["options"][1] == "person"
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"location_method": "home"})
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"gps_radius_km": 10})
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["location_method"] == "home"
    assert "person_entity" not in entry.options
