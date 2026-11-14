"""Config and options flow paths not exercised by the end-to-end tests (quality scale: config-flow-test-coverage)."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv.config_flow import _station_slug
from custom_components.ceny_paliv.const import DOMAIN

FLOW = "custom_components.ceny_paliv.config_flow"
URL = "/Ceny-benzinu-a-nafty/Praha/Oblibena/123"


@pytest.mark.parametrize(
    ("marker", "slug"),
    [
        ("not a marker", None),
        ({"url": 123}, None),
        ({"url": "/Ceny-benzinu-a-nafty/Praha/Oblibena"}, None),
        ({"url": "/Jinde/Praha/Oblibena/123"}, None),
        ({"url": "/Ceny-benzinu-a-nafty//Oblibena/123"}, None),
        ({"url": "/Ceny-benzinu-a-nafty/Praha/Oblibena/"}, None),
        ({"url": URL}, "Oblibena"),
    ],
)
def test_station_slug_accepts_only_station_urls(marker, slug):
    assert _station_slug(marker) == slug


async def _configure(hass, flow_id, user_input, *, options=False):
    manager = hass.config_entries.options if options else hass.config_entries.flow
    return await manager.async_configure(flow_id, user_input)


async def test_city_flow_needs_a_fuel_and_downloads_the_ticked_logos(
    hass, enable_custom_integrations, mock_frontend, marker, tmp_path
):
    hass.config.config_dir = str(tmp_path)
    # another area's logos stay on disk: the sync gets the union
    MockConfigEntry(domain=DOMAIN, data={"key": "dummy", "city": "Brno"}, options={"logos": ["shell"]}, unique_id="Brno").add_to_hass(hass)
    index = [
        {"id": "orlen", "label": "Orlen", "match": ["orlen"]},
        {"id": "shell", "label": "Shell", "match": ["shell"]},
    ]
    with (
        patch(f"{FLOW}.async_fetch_markers", new=AsyncMock(return_value=[marker("Oblibena", 33, name="Orlen")])),
        patch(f"{FLOW}.async_fetch_index", new=AsyncMock(return_value=index)),
        patch(f"{FLOW}.async_sync", new=AsyncMock()) as sync,
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await _configure(hass, result["flow_id"], {"key": "dummy"})
        result = await _configure(hass, result["flow_id"], {"area_mode": "city"})
        result = await _configure(hass, result["flow_id"], {"city": "Praha"})
        result = await _configure(hass, result["flow_id"], {"fuels": [], "language": "en"})
        assert result["step_id"] == "fuels"
        assert result["errors"] == {"fuels": "no_fuel"}
        result = await _configure(hass, result["flow_id"], {"fuels": ["n95"], "language": "en"})
        result = await _configure(hass, result["flow_id"], {"station": "Oblibena"})
        assert result["step_id"] == "logos"
        (logos_key,) = result["data_schema"].schema
        assert logos_key.default() == ["orlen"]  # the chains of the city are preselected
        result = await _configure(hass, result["flow_id"], {"logos": ["orlen"]})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["logos"] == ["orlen"]
    assert sync.await_args.args[2] == index
    assert sync.await_args.args[3] == {"orlen", "shell"}


async def test_gps_flow_rejects_invalid_zone_point_and_radius(
    hass, enable_custom_integrations, mock_frontend, marker
):
    hass.states.async_set("zone.cottage", "0", {"latitude": 50.1, "longitude": 14.4})
    with (
        patch(f"{FLOW}.async_fetch_markers", new=AsyncMock(return_value=[marker("Oblibena", 33)])),
        patch(f"{FLOW}.async_fetch_index", new=AsyncMock(return_value=None)),
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await _configure(hass, result["flow_id"], {"key": "dummy"})
        result = await _configure(hass, result["flow_id"], {"area_mode": "gps"})
        result = await _configure(hass, result["flow_id"], {"location_method": "zone"})
        result = await _configure(hass, result["flow_id"], {"zone_entity": "zone.missing"})
        assert result["errors"] == {"zone_entity": "invalid_zone"}
        result = await _configure(hass, result["flow_id"], {"zone_entity": "zone.cottage"})
        assert result["step_id"] == "gps_radius"
        result = await _configure(hass, result["flow_id"], {"gps_radius_km": float("nan")})
        assert result["errors"] == {"gps_radius_km": "invalid_radius"}
        # the zone disappears before the fuels step: the stations are listed without an area
        hass.states.async_remove("zone.cottage")
        result = await _configure(hass, result["flow_id"], {"gps_radius_km": 40})
        result = await _configure(hass, result["flow_id"], {"fuels": ["n95"], "language": "en"})
        assert result["step_id"] == "station"
        hass.config_entries.flow.async_abort(result["flow_id"])

        for method, step, bad_input, errors in (
            ("map", "location_map", {"location": {"latitude": float("nan"), "longitude": 14.4}}, {"location": "invalid_coordinates"}),
            ("manual", "location_manual", {"latitude": float("nan"), "longitude": 14.4}, {"base": "invalid_coordinates"}),
        ):
            result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
            result = await _configure(hass, result["flow_id"], {"key": "dummy"})
            result = await _configure(hass, result["flow_id"], {"area_mode": "gps"})
            result = await _configure(hass, result["flow_id"], {"location_method": method})
            assert result["step_id"] == step
            result = await _configure(hass, result["flow_id"], bad_input)
            assert result["step_id"] == step
            assert result["errors"] == errors
            hass.config_entries.flow.async_abort(result["flow_id"])


async def test_gps_flow_with_an_invalid_home_location_still_lists_stations(
    hass, enable_custom_integrations, mock_frontend, marker
):
    hass.config.latitude = float("nan")
    with (
        patch(f"{FLOW}.async_fetch_markers", new=AsyncMock(return_value=[marker("Oblibena", 33)])),
        patch(f"{FLOW}.async_fetch_index", new=AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await _configure(hass, result["flow_id"], {"key": "dummy"})
        result = await _configure(hass, result["flow_id"], {"area_mode": "gps"})
        result = await _configure(hass, result["flow_id"], {"location_method": "home"})
        result = await _configure(hass, result["flow_id"], {"gps_radius_km": 40})
        result = await _configure(hass, result["flow_id"], {"fuels": ["n95"], "language": "en"})
        assert result["step_id"] == "station"
        hass.config_entries.flow.async_abort(result["flow_id"])


async def test_options_flow_resets_an_unknown_age_and_keeps_an_unresolved_favourite(
    hass, enable_custom_integrations, mock_frontend, marker
):
    hass.config.latitude, hass.config.longitude = 50.1, 14.4
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={
            "fuels": ["n95"],
            "homes": {"n95": URL},
            "area_mode": "gps",
            "location_method": "home",
            "max_age_days": 5,  # not one of the choices (edited by hand)
            "logos": ["orlen"],
        },
        unique_id="gps-1",
    )
    entry.add_to_hass(hass)
    # the saved favourite is still published, but without coordinates it cannot be placed in the area
    unplaced = {**marker("Oblibena", 33), "lat": None, "lng": None}
    with (
        patch(f"{FLOW}.async_fetch_markers", new=AsyncMock(return_value=[unplaced, marker("Levna", 31)])),
        patch(f"{FLOW}.async_fetch_index", new=AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await _configure(hass, result["flow_id"], {"area_mode": "gps"}, options=True)
        result = await _configure(hass, result["flow_id"], {"location_method": "home"}, options=True)
        result = await _configure(hass, result["flow_id"], {"gps_radius_km": 40}, options=True)
        assert result["step_id"] == "fuels"
        schema = result["data_schema"].schema
        assert next(key for key in schema if key == "max_age_days").default() == "1"
        result = await _configure(hass, result["flow_id"], {"fuels": ["n95"], "language": "en"}, options=True)
        assert result["step_id"] == "station"
        (station_key,) = result["data_schema"].schema
        assert station_key.default() == URL
        options = result["data_schema"].schema[station_key].config["options"]
        assert {"value": URL, "label": "Saved station (not resolved)"} in options
        result = await _configure(hass, result["flow_id"], {"station": URL}, options=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["homes"] == {"n95": URL}
    assert entry.options["logos"] == ["orlen"]  # no logo pack reachable: the saved choice is kept


async def test_options_flow_offers_the_saved_logos_and_replaces_only_its_own(
    hass, enable_custom_integrations, mock_frontend, marker
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {}, "logos": ["orlen"]},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    index = [
        {"id": "orlen", "label": "Orlen", "match": ["orlen"]},
        {"id": "shell", "label": "Shell", "match": ["shell"]},
    ]
    with (
        patch(f"{FLOW}.async_fetch_markers", new=AsyncMock(return_value=[marker("Oblibena", 33, name="Shell")])),
        patch(f"{FLOW}.async_fetch_index", new=AsyncMock(return_value=index)),
        patch(f"{FLOW}.async_sync", new=AsyncMock()) as sync,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await _configure(hass, result["flow_id"], {"area_mode": "city"}, options=True)
        result = await _configure(hass, result["flow_id"], {"city": "Praha"}, options=True)
        result = await _configure(hass, result["flow_id"], {"fuels": ["n95"], "language": "en"}, options=True)
        result = await _configure(hass, result["flow_id"], {}, options=True)
        assert result["step_id"] == "logos"
        (logos_key,) = result["data_schema"].schema
        assert logos_key.default() == ["orlen"]  # the saved choice, not the city's chains
        result = await _configure(hass, result["flow_id"], {"logos": ["shell"]}, options=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["logos"] == ["shell"]
    assert sync.await_args.args[3] == {"shell"}  # its own old choice is not kept by "other areas"
