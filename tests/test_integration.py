"""Home Assistant configuration, coordinator and sensor regressions."""
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv.api import CannotConnect, InvalidAuth, MarkerSnapshot
from custom_components.ceny_paliv.config_flow import _valid_coordinates
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
        assert result["step_id"] == "area_mode"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"area_mode": "city"})
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"area_mode": "city"}
        )
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
        assert result["step_id"] == "area_mode"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "city"}
        )
        assert result["step_id"] == "city"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"city": "Praha"}
        )
        assert result["step_id"] == "fuels"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "cs"},
        )
        assert result["step_id"] == "station"
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"station": "Oblibena"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options["homes"] == {"n95": "Oblibena"}
        assert entry.options["language"] == "cs"


async def test_gps_config_flow_with_home_location(hass, enable_custom_integrations, mock_frontend, marker):
    hass.config.latitude = 50.1
    hass.config.longitude = 14.4
    with (
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(return_value=[marker("Oblibena", 33)]),
        ),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"area_mode": "gps"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location_method": "home"}
        )
        assert result["step_id"] == "gps_radius"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"gps_radius_km": 40}
        )
        assert result["step_id"] == "fuels"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"station": "/Ceny-benzinu-a-nafty/Praha/Oblibena/123"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["city"] == ""
        assert result["options"]["area_mode"] == "gps"
        assert result["options"]["location_method"] == "home"
        assert result["options"]["gps_radius_km"] == 40
        assert result["options"]["homes"]["n95"].endswith("/Oblibena/123")
        entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
        assert entry.unique_id.startswith("gps-")
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("method", "location_step", "location_input"),
    [
        ("manual", "location_manual", {"latitude": 49.2, "longitude": 16.6}),
        ("zone", "location_zone", {"zone_entity": "zone.cottage"}),
    ],
)
async def test_gps_manual_and_zone_location_flows(
    hass,
    enable_custom_integrations,
    mock_frontend,
    marker,
    method,
    location_step,
    location_input,
):
    if method == "zone":
        hass.states.async_set(
            "zone.cottage", "Cottage", {"latitude": 49.2, "longitude": 16.6}
        )
    selected_marker = {
        **marker("Oblibena", 33),
        "lat": 49.2,
        "lng": 16.6,
    }
    with (
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(return_value=[selected_marker]),
        ),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"area_mode": "gps"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location_method": method}
        )
        assert result["step_id"] == location_step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], location_input
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"gps_radius_km": 40}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"station": "/Ceny-benzinu-a-nafty/Praha/Oblibena/123"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        options = result["options"]
        assert options["location_method"] == method
        if method == "zone":
            assert options["zone_entity"] == "zone.cottage"
        else:
            assert options["location"] == location_input


@pytest.mark.parametrize(
    ("latitude", "longitude", "valid"),
    [
        (0, 0, True),
        (90, 180, True),
        (-90, -180, True),
        (91, 0, False),
        (0, 181, False),
        (float("nan"), 0, False),
        (0, float("inf"), False),
        (None, 0, False),
        (True, 1, False),
        ("50", 14, True),
    ],
)
def test_config_location_coordinate_validation(latitude, longitude, valid):
    assert _valid_coordinates(latitude, longitude) is valid


async def test_gps_map_options_and_city_switch_preserve_entry_identity(
    hass, enable_custom_integrations, mock_frontend, marker
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Oblibena"}},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    original_entry_id = entry.entry_id
    with (
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(return_value=[marker("Oblibena", 33)]),
        ),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "gps"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"location_method": "map"}
        )
        assert result["step_id"] == "location_map"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"location": {"latitude": 50.1, "longitude": 14.4}},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"gps_radius_km": 50}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.entry_id == original_entry_id
        assert entry.unique_id == "Praha"
        assert entry.options["area_mode"] == "gps"
        assert entry.options["location"] == {"latitude": 50.1, "longitude": 14.4}
        assert entry.options["gps_radius_km"] == 50
        assert entry.options["homes"]["n95"] == "Oblibena"


async def test_changing_favourite_archives_old_statistics_identity(
    hass, enable_custom_integrations, mock_frontend, marker
):
    old = marker("Oblibena", 33)
    new = marker("Nova", 32)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Oblibena"}},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(return_value=[old, new]),
        ),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "city"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"city": "Praha"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"station": "Nova"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options["homes"]["n95"] == "Nova"
        assert entry.options["home_identities"]["n95"] == new["url"]
        assert entry.options["home_history"]["n95"] == [
            {"identity": old["url"], "legacy": True}
        ]


async def test_city_change_same_slug_uses_distinct_station_urls_and_statistics(
    hass, enable_custom_integrations, mock_frontend, marker
):
    prague_station = {
        **marker("Shared", 30, city="Praha"),
        "url": "/Ceny-benzinu-a-nafty/Praha/Shared/101",
    }
    brno_station = {
        **marker("Shared", 40, city="Brno"),
        "url": "/Ceny-benzinu-a-nafty/Brno/Shared/202",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Shared"}},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(return_value=[prague_station, brno_station]),
        ),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "city"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"city": "Brno"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"station": "Shared"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["city"] == "Brno"
    assert entry.options["homes"]["n95"] == "Shared"
    assert entry.options["home_identities"]["n95"] == brno_station["url"]
    assert entry.options["home_history"]["n95"] == [
        {"identity": prague_station["url"], "legacy": True}
    ]

    from custom_components.ceny_paliv.coordinator import CenyPalivCoordinator
    from custom_components.ceny_paliv.sensor import CenyPalivArchivedHomeSensor, CenyPalivHomeSensor

    coordinator = CenyPalivCoordinator(hass, entry)
    active = CenyPalivHomeSensor(coordinator, entry, "n95")
    archived = CenyPalivArchivedHomeSensor(
        coordinator, entry, "n95", prague_station["url"], True
    )
    assert active.unique_id != archived.unique_id
    assert active.unique_id.endswith(
        hashlib.sha256(brno_station["url"].encode()).hexdigest()[:12]
    )


async def test_favourite_identity_cycles_modes_and_reloads_without_collisions(
    hass, enable_custom_integrations, mock_frontend, marker
):
    from custom_components.ceny_paliv.coordinator import CenyPalivCoordinator
    from custom_components.ceny_paliv.sensor import (
        CenyPalivArchivedHomeSensor,
        CenyPalivHomeSensor,
    )

    hass.config.latitude = 50.1
    hass.config.longitude = 14.4
    stations = [marker(name, price) for name, price in (("Alpha", 30), ("Beta", 31), ("Gamma", 32))]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Alpha"}, "language": "en"},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)

    def assert_active_and_archived_ids_are_safe():
        coordinator = CenyPalivCoordinator(hass, entry)
        active = CenyPalivHomeSensor(coordinator, entry, "n95")
        known = {active.unique_id}
        archives = []
        for record in coordinator.home_history.get("n95", []):
            archived = CenyPalivArchivedHomeSensor(
                coordinator,
                entry,
                "n95",
                record["identity"],
                record["legacy"],
            )
            if archived.unique_id not in known:
                archives.append(archived)
                known.add(archived.unique_id)
        assert len(known) == 1 + len(archives)
        return active, archives

    async def choose_favourite(area_mode, choice, center=(50.1, 14.4)):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": area_mode}
        )
        if area_mode == "city":
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"city": "Praha"}
            )
        else:
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"location_method": "map"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {"location": {"latitude": center[0], "longitude": center[1]}},
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"gps_radius_km": 40}
            )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"station": choice}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    with (
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(return_value=stations),
        ),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
    ):
        await choose_favourite("city", "Beta")
        assert entry.options["home_identities"]["n95"] == stations[1]["url"]
        assert entry.options["home_history"]["n95"] == [
            {"identity": stations[0]["url"], "legacy": True}
        ]
        active, archives = assert_active_and_archived_ids_are_safe()
        assert active.unique_id != archives[0].unique_id

        await choose_favourite("city", "Alpha")
        assert "home_identities" not in entry.options
        active, archives = assert_active_and_archived_ids_are_safe()
        assert active.unique_id == f"{entry.entry_id}_n95_home"
        assert all(archived.unique_id != active.unique_id for archived in archives)

        await choose_favourite("gps", "Alpha", center=(49.2, 16.6))
        assert entry.options["homes"]["n95"] == "Alpha"
        assert "home_identities" not in entry.options
        await choose_favourite("gps", stations[2]["url"])
        assert entry.options["home_identities"]["n95"] == stations[2]["url"]
        await choose_favourite("gps", stations[1]["url"])
        assert entry.options["home_identities"]["n95"] == stations[1]["url"]
        await choose_favourite("gps", stations[0]["url"])
        assert "home_identities" not in entry.options
        active, archives = assert_active_and_archived_ids_are_safe()
        assert active.unique_id == f"{entry.entry_id}_n95_home"
        assert all(archived.unique_id != active.unique_id for archived in archives)
        assert len({archived.unique_id for archived in archives}) == len(archives)

        await choose_favourite("city", "__none__")
        assert "n95" not in entry.options["homes"]
        assert "home_identities" not in entry.options
        active, archives = assert_active_and_archived_ids_are_safe()
        assert all(archive.available is False for archive in archives)
        assert active.unique_id not in {archive.unique_id for archive in archives}

        await choose_favourite("city", "Beta")
        assert entry.options["home_identities"]["n95"] == stations[1]["url"]
        beta_id = assert_active_and_archived_ids_are_safe()[0].unique_id
        assert beta_id != f"{entry.entry_id}_n95_home"

        await choose_favourite("city", "Alpha")
        assert "home_identities" not in entry.options
        active, archives = assert_active_and_archived_ids_are_safe()
        assert active.unique_id == f"{entry.entry_id}_n95_home"
        assert len({active.unique_id, *(archive.unique_id for archive in archives)}) == len(archives) + 1

    snapshot = MarkerSnapshot(markers=stations, fetched_at=dt_util.now())
    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot",
        new=AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        active_home = next(
            state
            for state in hass.states.async_all("sensor")
            if state.attributes.get("cp_config_id") == entry.entry_id
            and state.attributes.get("cp_role") == "home"
        )
        assert active_home.state == "30"
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        reloaded_home = hass.states.get(active_home.entity_id)
        assert reloaded_home is not None
        assert reloaded_home.state == "30"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_gps_sensor_attributes_stay_below_recorder_limit_for_large_feed(
    hass, enable_custom_integrations, mock_frontend
):
    hass.config.latitude = 50.1
    hass.config.longitude = 14.4
    long_text = "Long station name " * 120
    markers = [
        {
            "url": f"/Ceny-benzinu-a-nafty/Praha/Station-{index}/{index}",
            "name": f"{long_text}-{index}",
            "chain": long_text,
            "price": 30 + index / 1000,
            "fresh": "Dnes",
            "lat": 50.1 + index / 1000000,
            "lng": 14.4,
        }
        for index in range(1200)
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": ""},
        options={
            "area_mode": "gps",
            "location_method": "home",
            "gps_radius_km": 5,
            "fuels": ["n95"],
            "homes": {},
        },
        unique_id="gps-load-test",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=markers, fetched_at=dt_util.now())
    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot",
        new=AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        top = next(
            state
            for state in hass.states.async_all("sensor")
            if state.attributes.get("cp_config_id") == entry.entry_id
            and state.attributes.get("cp_role") == "top5"
        )
        serialized = json.dumps(top.attributes, ensure_ascii=False).encode("utf-8")
        assert len(serialized) < 16 * 1024
        assert len(top.attributes["stations"]) == 5
        assert len(top.attributes["gps_nearest_stations"]) == 10
        assert top.attributes["gps_area"]["station_count"] == 1200
        nearest = top.attributes["gps_nearest_stations"]
        assert all("trends" not in station and "maps" not in station for station in nearest)
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_home_sensor_ids_keep_legacy_and_separate_changed_station_statistics(
    hass, enable_custom_integrations, mock_frontend
):
    import hashlib

    from custom_components.ceny_paliv.coordinator import CenyPalivCoordinator
    from custom_components.ceny_paliv.sensor import (
        CenyPalivArchivedHomeSensor,
        CenyPalivHomeSensor,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={
            "fuels": ["n95"],
            "homes": {"n95": "/Ceny-benzinu-a-nafty/Praha/Nova/123"},
            "home_identities": {"n95": "/Ceny-benzinu-a-nafty/Praha/Nova/123"},
            "home_history": {
                "n95": [{"identity": "/Ceny-benzinu-a-nafty/Praha/Oblibena/456", "legacy": True}]
            },
        },
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    coordinator = CenyPalivCoordinator(hass, entry)
    current = CenyPalivHomeSensor(coordinator, entry, "n95")
    archived = CenyPalivArchivedHomeSensor(
        coordinator, entry, "n95", "/Ceny-benzinu-a-nafty/Praha/Oblibena/456", True
    )
    assert archived.unique_id == f"{entry.entry_id}_n95_home"
    assert current.unique_id == (
        f"{entry.entry_id}_n95_home_"
        + hashlib.sha256(entry.options["home_identities"]["n95"].encode()).hexdigest()[:12]
    )
    assert current.unique_id != archived.unique_id
    assert archived.available is False


async def test_removed_legacy_favourite_reuses_only_its_original_registry_identity(
    hass, enable_custom_integrations, mock_frontend, marker
):
    station = marker("Alpha", 30)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={
            "fuels": ["n95"],
            "homes": {},
            "home_history": {
                "n95": [{"identity": station["url"], "legacy": True}]
            },
        },
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[station], fetched_at=dt_util.now())
    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot",
        new=AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.home_history["n95"] == [
            {"identity": station["url"], "legacy": True}
        ]
        registry = er.async_get(hass)
        archived_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_n95_home"
        )
        assert archived_id is not None
        assert hass.states.get(archived_id).state == "unavailable"
        assert not any(
            state.attributes.get("cp_config_id") == entry.entry_id
            and state.attributes.get("cp_role") == "home"
            for state in hass.states.async_all("sensor")
        )

        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "homes": {"n95": "Alpha"}}
        )
        await hass.async_block_till_done()
        active = hass.states.get(archived_id)
        assert active is not None
        assert active.state == "30"
        assert active.attributes["cp_role"] == "home"
        assert len(
            [
                entity
                for entity in hass.states.async_all("sensor")
                if entity.attributes.get("cp_config_id") == entry.entry_id
                and entity.attributes.get("cp_role") in {"home", "home_archive"}
            ]
        ) == 1
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_coordinator_sensors_and_failed_refresh(hass, enable_custom_integrations, mock_frontend, marker):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95", "diesel"], "homes": {"n95": "Oblibena"}, "language": "cs"},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    markers = [marker("Oblibena", 35), marker("Levna", 33)]
    snapshot = MarkerSnapshot(markers=markers, fetched_at=dt_util.now())
    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)) as fetch:
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
        assert saved["n95"][markers[0]["url"]][-1][1] == 35

        async def partial_failure(session, key, fuel, *, cache=None):
            if fuel == "n95":
                raise CannotConnect()
            return MarkerSnapshot(markers=[marker("Levna", 32)], fetched_at=dt_util.now())

        fetch.side_effect = partial_failure
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        top = hass.states.get("sensor.ceny_paliv_n95_top5")
        assert top.state == "33"
        assert top.attributes["fetch_error"] == "CannotConnect"
        assert hass.states.get("sensor.ceny_paliv_diesel_top5").state == "32"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_gps_coordinator_uses_home_location_and_exposes_area_data(
    hass, enable_custom_integrations, mock_frontend, marker
):
    hass.config.latitude = 50.1
    hass.config.longitude = 14.4
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": ""},
        options={
            "area_mode": "gps",
            "location_method": "home",
            "gps_radius_km": 5,
            "fuels": ["n95"],
            "homes": {},
        },
        unique_id="gps-test",
    )
    entry.add_to_hass(hass)
    nearby = marker("Nearby", 30)
    outside = {**marker("Outside", 20), "lat": 51.0}
    snapshot = MarkerSnapshot(markers=[nearby, outside], fetched_at=dt_util.now())
    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot",
        new=AsyncMock(return_value=snapshot),
    ) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        top = next(
            state for state in hass.states.async_all("sensor")
            if state.attributes.get("cp_config_id") == entry.entry_id
            and state.attributes.get("cp_role") == "top5"
        )
        assert top.attributes["gps_area"]["method"] == "home"
        assert top.attributes["gps_area"]["latitude"] == 50.1
        assert top.attributes["gps_area"]["radius_km"] == 5
        assert [station["name"] for station in top.attributes["stations"]] == ["Nearby"]
        assert [station["name"] for station in top.attributes["gps_nearest_stations"]] == [
            "Nearby"
        ]
        assert fetch.await_count == 1
        hass.config.latitude = 52.0
        await entry.runtime_data.async_refresh()
        top = hass.states.get(top.entity_id)
        assert top.attributes["gps_area"]["latitude"] == 52.0
        assert top.attributes["stations"] == []
        assert fetch.await_count == 2
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_two_gps_areas_for_same_fuel_keep_distinct_sensor_identity_and_data(
    hass, enable_custom_integrations, mock_frontend, marker
):
    first_location = (50.1, 14.4)
    second_location = (51.0, 15.0)
    markers = [
        {**marker("First-area", 30), "lat": first_location[0], "lng": first_location[1]},
        {**marker("Second-area", 31), "lat": second_location[0], "lng": second_location[1]},
    ]
    entries = [
        MockConfigEntry(
            domain=DOMAIN,
            data={"key": "dummy", "city": ""},
            options={
                "area_mode": "gps",
                "location_method": "map",
                "location": {"latitude": latitude, "longitude": longitude},
                "gps_radius_km": 5,
                "fuels": ["n95"],
            },
            unique_id=f"gps-{index}",
        )
        for index, (latitude, longitude) in enumerate(
            [first_location, second_location], start=1
        )
    ]
    snapshot = MarkerSnapshot(markers=markers, fetched_at=dt_util.now())
    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot",
        new=AsyncMock(return_value=snapshot),
    ):
        for entry in entries:
            entry.add_to_hass(hass)
            if entry.state is ConfigEntryState.NOT_LOADED:
                assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    top_sensors = [
        state for state in hass.states.async_all("sensor")
        if state.attributes.get("cp_role") == "top5"
        and state.attributes.get("cp_config_id") in {entry.entry_id for entry in entries}
    ]
    assert len(top_sensors) == 2
    by_config = {state.attributes["cp_config_id"]: state for state in top_sensors}
    assert by_config[entries[0].entry_id].attributes["stations"][0]["name"] == "First-area"
    assert by_config[entries[1].entry_id].attributes["stations"][0]["name"] == "Second-area"
    assert by_config[entries[0].entry_id].entity_id != by_config[entries[1].entry_id].entity_id
    assert by_config[entries[0].entry_id].attributes["cp_config_id"] != by_config[
        entries[1].entry_id
    ].attributes["cp_config_id"]
    for entry in entries:
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_gps_zone_updates_and_missing_zone_empty_area(
    hass, enable_custom_integrations, mock_frontend, marker
):
    hass.states.async_set(
        "zone.work", "Work", {"latitude": 50.1, "longitude": 14.4}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": ""},
        options={
            "area_mode": "gps",
            "location_method": "zone",
            "zone_entity": "zone.work",
            "gps_radius_km": 5,
            "fuels": ["n95"],
        },
        unique_id="gps-zone",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Nearby", 30)], fetched_at=dt_util.now())
    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot",
        new=AsyncMock(return_value=snapshot),
    ) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set(
            "zone.work", "Work", {"latitude": 51.0, "longitude": 14.4}
        )
        await hass.async_block_till_done()
        top = next(
            state for state in hass.states.async_all("sensor")
            if state.attributes.get("cp_config_id") == entry.entry_id
            and state.attributes.get("cp_role") == "top5"
        )
        assert top.attributes["gps_area"]["latitude"] == 51.0
        assert top.attributes["stations"] == []
        hass.states.async_remove("zone.work")
        await hass.async_block_till_done()
        top = hass.states.get(top.entity_id)
        assert top.attributes["gps_area"]["error"] == "zone_unavailable"
        assert top.attributes["stations"] == []
        assert fetch.await_count == 3
        assert await hass.config_entries.async_unload(entry.entry_id)
