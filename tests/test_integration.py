"""Home Assistant configuration, coordinator and sensor regressions."""
from datetime import timedelta
import hashlib
import json
import re
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv.api import (
    CannotConnect,
    InvalidAuth,
    MarkerSnapshot,
    RateLimited,
)
from custom_components.ceny_paliv.config_flow import _valid_coordinates
from custom_components.ceny_paliv.const import DOMAIN


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


@pytest.mark.parametrize("area_mode", ["city", "gps"])
async def test_config_flow_allows_fuel_without_favourite(
    hass, enable_custom_integrations, mock_frontend, marker, area_mode
):
    hass.config.latitude = 50.1
    hass.config.longitude = 14.4
    favourite = "Oblibena" if area_mode == "city" else "/Ceny-benzinu-a-nafty/Praha/Oblibena/123"
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
            result["flow_id"], {"area_mode": area_mode}
        )
        if area_mode == "city":
            result = await hass.config_entries.flow.async_configure(result["flow_id"], {"city": "Praha"})
        else:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"location_method": "home"}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"gps_radius_km": 40}
            )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"fuels": ["n95", "lpg"], "language": "en"}
        )
        assert result["step_id"] == "station"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station": favourite})
        assert result["step_id"] == "station"
        # "—" is the form's default: submitting the form unchanged must not fail
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["options"]["homes"] == {"n95": favourite}
        assert "home_identities" not in result["options"]
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
            result["flow_id"], {"fuels": ["n95"], "language": "cs", "max_age_days": "7"},
        )
        assert result["step_id"] == "station"
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"station": "Oblibena"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options["homes"] == {"n95": "Oblibena"}
        assert entry.options["language"] == "cs"
        assert entry.options["max_age_days"] == 7

        # the next options flow offers the saved choice
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"area_mode": "city"})
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"city": "Praha"})
        schema = result["data_schema"].schema
        assert next(k for k in schema if k == "max_age_days").default() == "7"


@pytest.mark.parametrize("failure", [CannotConnect, RateLimited])
async def test_options_flow_opens_without_api_even_during_failure(
    hass, enable_custom_integrations, mock_frontend, failure
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={
            "fuels": ["diesel"],
            "homes": {"diesel": "Saved"},
            "language": "cs",
        },
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    original_options = dict(entry.options)
    with patch(
        "custom_components.ceny_paliv.config_flow.async_fetch_markers",
        new=AsyncMock(side_effect=failure),
    ) as fetch:
        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["step_id"] == "area_mode"
    fetch.assert_not_awaited()
    assert entry.options == original_options


async def test_options_gps_diesel_only_never_fetches_n95_or_city_list(
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
            "gps_radius_km": 40,
            "fuels": ["diesel"],
            "homes": {},
        },
        unique_id="gps-diesel",
    )
    entry.add_to_hass(hass)
    diesel = marker("Diesel", 39)
    with patch(
        "custom_components.ceny_paliv.config_flow.async_fetch_markers",
        new=AsyncMock(return_value=[diesel]),
    ) as fetch:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["step_id"] == "area_mode"
        fetch.assert_not_awaited()

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "gps"}
        )
        assert result["step_id"] == "location_method"
        fetch.assert_not_awaited()

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"location_method": "home"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"gps_radius_km": 40}
        )
        assert result["step_id"] == "fuels"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["diesel"], "language": "en"}
        )

    assert result["step_id"] == "station"
    assert [call.args[2] for call in fetch.await_args_list] == ["diesel"]
    assert fetch.await_args.kwargs["cache"] is __import__(
        "custom_components.ceny_paliv.api", fromlist=["shared_marker_cache"]
    ).shared_marker_cache(hass)


async def test_options_gps_to_city_failure_is_retryable_and_preserves_settings(
    hass, enable_custom_integrations, mock_frontend, marker
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": ""},
        options={
            "area_mode": "gps",
            "location_method": "manual",
            "location": {"latitude": 50.1, "longitude": 14.4},
            "gps_radius_km": 25,
            "fuels": ["diesel"],
            "homes": {"diesel": "/Ceny-benzinu-a-nafty/Praha/Saved/1"},
            "language": "cs",
        },
        unique_id="gps-city-failure",
    )
    entry.add_to_hass(hass)
    original_options = dict(entry.options)
    fetch = AsyncMock(side_effect=[CannotConnect(), [marker("Diesel", 39)]])
    with patch("custom_components.ceny_paliv.config_flow.async_fetch_markers", new=fetch):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "city"}
        )

        assert result["step_id"] == "area_mode"
        assert result["errors"] == {"base": "cannot_connect"}
        assert entry.options == original_options
        area_defaults = {
            key.schema: key.default() if callable(key.default) else key.default
            for key in result["data_schema"].schema
            if hasattr(key, "default")
        }
        assert area_defaults["area_mode"] == "city"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "city"}
        )

    assert result["step_id"] == "city"
    assert [call.args[2] for call in fetch.await_args_list] == ["diesel", "diesel"]
    assert entry.options == original_options


async def test_options_city_discovery_handles_invalid_key_and_empty_results(
    hass, enable_custom_integrations, mock_frontend
):
    for failure, expected_error in ((InvalidAuth(), "invalid_auth"), ([], "no_cities")):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"key": "dummy", "city": "Praha"},
            options={"fuels": ["lpg"], "homes": {"lpg": "Saved"}},
            unique_id=f"city-error-{expected_error}",
        )
        entry.add_to_hass(hass)
        with patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(side_effect=failure if isinstance(failure, Exception) else None,
                          return_value=None if isinstance(failure, Exception) else failure),
        ) as fetch:
            result = await hass.config_entries.options.async_init(entry.entry_id)
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"area_mode": "city"}
            )
        assert result["step_id"] == "area_mode"
        assert result["errors"] == {"base": expected_error}
        assert fetch.await_args.args[2] == "lpg"
        assert entry.options == {"fuels": ["lpg"], "homes": {"lpg": "Saved"}}


async def test_options_city_discovery_retry_reuses_flow_and_shared_cooldown(
    hass, enable_custom_integrations, mock_frontend, marker
):
    from custom_components.ceny_paliv.api import shared_marker_cache

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": ""},
        options={"area_mode": "gps", "fuels": ["diesel"], "homes": {}},
        unique_id="gps-city-cooldown",
    )
    entry.add_to_hass(hass)
    original_options = dict(entry.options)
    underlying_fetch = AsyncMock(side_effect=RateLimited(120))
    with patch(
        "custom_components.ceny_paliv.api._async_fetch_markers",
        new=underlying_fetch,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["step_id"] == "area_mode"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "city"}
        )
        assert result["errors"] == {"base": "rate_limited"}
        assert entry.options == original_options

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "city"}
        )
        assert result["errors"] == {"base": "rate_limited"}
        assert underlying_fetch.await_count == 1
        assert underlying_fetch.await_args.args[2] == "diesel"
        assert shared_marker_cache(hass) is not None
        assert entry.options == original_options


async def test_options_city_to_gps_does_not_fetch_city_list_during_outage(
    hass, enable_custom_integrations, mock_frontend
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={
            "area_mode": "city",
            "fuels": ["n95"],
            "homes": {"n95": "Saved"},
            "language": "en",
        },
        unique_id="city-gps-offline",
    )
    entry.add_to_hass(hass)
    original_options = dict(entry.options)
    with patch(
        "custom_components.ceny_paliv.config_flow.async_fetch_markers",
        new=AsyncMock(side_effect=CannotConnect()),
    ) as fetch:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "gps"}
        )

    assert result["step_id"] == "location_method"
    fetch.assert_not_awaited()
    assert entry.options == original_options


async def test_options_fuels_failure_preserves_pending_choices_for_retry(
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
            "gps_radius_km": 40,
            "fuels": ["diesel"],
            "homes": {},
            "language": "en",
        },
        unique_id="gps-fuels-retry",
    )
    entry.add_to_hass(hass)
    original_options = dict(entry.options)
    fetch = AsyncMock(side_effect=[CannotConnect(), [marker("LPG", 20)]])
    with patch("custom_components.ceny_paliv.config_flow.async_fetch_markers", new=fetch):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"area_mode": "gps"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"location_method": "home"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"gps_radius_km": 40}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["lpg"], "language": "cs"}
        )

        assert result["step_id"] == "fuels"
        assert result["errors"] == {"base": "cannot_connect"}
        assert entry.options == original_options
        schema_defaults = {
            getattr(key, "schema", key): (
                key.default() if callable(key.default) else key.default
            )
            for key in result["data_schema"].schema
            if hasattr(key, "default")
        }
        assert schema_defaults["fuels"] == ["lpg"]
        assert schema_defaults["language"] == "cs"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["lpg"], "language": "cs"}
        )

    assert result["step_id"] == "station"
    assert [call.args[2] for call in fetch.await_args_list] == ["lpg", "lpg"]
    assert entry.options == original_options


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
        # the entry's identity and automatic title follow the new area
        assert entry.unique_id.startswith("gps-")
        assert entry.title == "Mock Title"  # not an automatic title, so it is kept
        assert entry.options["area_mode"] == "gps"
        assert entry.options["location"] == {"latitude": 50.1, "longitude": 14.4}
        assert entry.options["gps_radius_km"] == 50
        # the kept favourite is now its exact URL; its sensor keeps the legacy statistics identity
        assert entry.options["homes"]["n95"] == "/Ceny-benzinu-a-nafty/Praha/Oblibena/123"
        assert "home_identities" not in entry.options


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


async def test_city_change_unresolved_same_slug_does_not_keep_legacy_identity(
    hass, enable_custom_integrations, mock_frontend, marker
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Shared"}},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    brno_station = marker("Other", 40, city="Brno")

    with (
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(return_value=[brno_station]),
        ),
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_index",
            new=AsyncMock(return_value=None),
        ),
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
    assert entry.options["homes"]["n95"] == "Shared"
    assert entry.options["home_history"]["n95"] == [
        {"identity": "Shared", "legacy": True}
    ]
    assert entry.options["home_identities"]["n95"] != "Shared"
    assert entry.options["home_identities"]["n95"].startswith("unresolved:")

    from custom_components.ceny_paliv.coordinator import CenyPalivCoordinator
    from custom_components.ceny_paliv.sensor import (
        CenyPalivArchivedHomeSensor,
        CenyPalivHomeSensor,
    )

    coordinator = CenyPalivCoordinator(hass, entry)
    active = CenyPalivHomeSensor(coordinator, entry, "n95")
    archived = CenyPalivArchivedHomeSensor(
        coordinator, entry, "n95", "Shared", True
    )
    assert active.unique_id != archived.unique_id


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

        await choose_favourite("gps", stations[0]["url"], center=(49.2, 16.6))
        # the kept City favourite is stored as its exact URL, never as a bare slug in GPS mode
        assert entry.options["homes"]["n95"] == stations[0]["url"]
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
        # quality scale entity-category / entity-disabled-by-default: an archive only keeps statistics
        archived_entry = registry.async_get(archived_id)
        assert archived_entry.entity_category is EntityCategory.DIAGNOSTIC
        assert archived_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(archived_id) is None
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


async def test_coordinator_sensors_and_failed_refresh(
    hass, enable_custom_integrations, mock_frontend, marker, caplog
):
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
        # condition of the mBenzin key: the source is shown with the prices
        assert top.attributes["attribution"] == "Ceny: mbenzin.cz"
        assert home.attributes["attribution"] == "Ceny: mbenzin.cz"
        assert home.state == "35"
        assert home.attributes["rank"] == 2
        assert position.state == "33"
        assert position.attributes["latitude"] == 50.1
        # the map card labels its markers with the bare price
        assert position.attributes["price"] == 33
        assert home.attributes["price"] == 35
        # a position without a station keeps its identity attributes for the card (unknown, not unavailable)
        empty_position = hass.states.get("sensor.ceny_paliv_n95_3")
        assert empty_position.state == "unknown"
        assert empty_position.attributes["cp_role"] == "position"
        assert empty_position.attributes["cp_index"] == 3
        assert empty_position.attributes["cp_config_id"] == entry.entry_id
        saved = await entry.runtime_data._store.async_load()
        assert saved["n95"][markers[0]["url"]][-1][1] == 35

        async def partial_failure(session, key, fuel, *, cache=None, max_age=None):
            if fuel == "n95":
                raise CannotConnect()
            return MarkerSnapshot(markers=[marker("Levna", 32)], fetched_at=dt_util.now())

        coordinator = entry.runtime_data
        fetch.side_effect = partial_failure
        caplog.clear()
        for _ in range(2):  # quality scale log-when-unavailable: the failure is logged once
            await coordinator.async_refresh()
            await hass.async_block_till_done()
        assert caplog.text.count("n95 prices cannot be refreshed from mBenzin.cz (CannotConnect)") == 1
        # quality scale entity-unavailable: only the failing fuel's sensors are unavailable
        for entity_id in ("sensor.ceny_paliv_n95_top5", "sensor.ceny_paliv_n95_home", "sensor.ceny_paliv_n95_1"):
            assert hass.states.get(entity_id).state == "unavailable"
        assert hass.states.get("sensor.ceny_paliv_diesel_top5").state == "32"
        assert coordinator.data["n95"]["fetch_error"] == "CannotConnect"  # the last prices are kept

        fetch.side_effect = None
        fetch.return_value = snapshot
        caplog.clear()
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert caplog.text.count("n95 prices are refreshed again") == 1
        assert hass.states.get("sensor.ceny_paliv_n95_top5").state == "33"

        # every fuel failing: the coordinator itself fails, every sensor is unavailable, and the old data stays
        fetch.side_effect = RateLimited()
        caplog.clear()
        for _ in range(2):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
        assert not coordinator.last_update_success
        failures = [r for r in caplog.records if r.levelname == "ERROR" and "could not be reached" in r.getMessage()]
        assert len(failures) == 1
        # quality scale exception-translations: the message comes from translations/en.json
        assert failures[0].getMessage().endswith(
            "mBenzin.cz could not be reached for any fuel (n95: RateLimited, diesel: RateLimited)"
        )
        assert hass.states.get("sensor.ceny_paliv_diesel_top5").state == "unavailable"
        assert coordinator.data["n95"]["stations"]

        # the recovery after a full outage is logged once, by the coordinator, not again per fuel
        fetch.side_effect = None
        caplog.clear()
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert "refreshed again" not in caplog.text
        assert hass.states.get("sensor.ceny_paliv_diesel_top5").state == "33"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_entities_share_the_area_device_and_translated_names(
    hass, enable_custom_integrations, mock_frontend, marker
):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers.device_registry import DeviceEntryType

    from custom_components.ceny_paliv import sensor

    assert sensor.PARALLEL_UPDATES == 0
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ceny paliv Praha",
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95", "cng"], "homes": {"n95": "Oblibena"}},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    # an entity registered by 0.5 keeps its entity id (and so its history): the unique id has not changed
    registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_n95_top5", suggested_object_id="my_cheapest", config_entry=entry
    )
    snapshot = MarkerSnapshot(markers=[marker("Oblibena", 35), marker("Levna", 33)], fetched_at=dt_util.now())
    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        [device] = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        assert device.identifiers == {(DOMAIN, entry.entry_id)}
        assert device.name == "Ceny paliv Praha"
        assert device.entry_type is DeviceEntryType.SERVICE
        assert device.manufacturer == "mBenzin.cz"
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(entities) == 2 * 6 + 1  # per fuel: top5 and 5 positions; the n95 favourite
        assert {e.device_id for e in entities} == {device.id}
        assert all(e.has_entity_name for e in entities)
        assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_n95_top5") == "sensor.my_cheapest"

        names = {
            entity_id: hass.states.get(entity_id).attributes["friendly_name"]
            for entity_id in (
                "sensor.my_cheapest",
                "sensor.ceny_paliv_n95_home",
                "sensor.ceny_paliv_n95_2",
                "sensor.ceny_paliv_cng_top5",
            )
        }
        assert names == {
            "sensor.my_cheapest": "Ceny paliv Praha Natural 95 · cheapest",
            "sensor.ceny_paliv_n95_home": "Ceny paliv Praha Natural 95 · favourite station",
            "sensor.ceny_paliv_n95_2": "Ceny paliv Praha Natural 95 · cheapest #2",
            "sensor.ceny_paliv_cng_top5": "Ceny paliv Praha CNG · cheapest",
        }
        assert hass.states.get("sensor.ceny_paliv_cng_top5").attributes["unit_of_measurement"] == "Kč/kg"
        # the station is no longer in the name: its readable title is in the attribute (no street: the town)
        assert hass.states.get("sensor.ceny_paliv_n95_2").attributes["station"] == "Oblibena · Praha"
        assert hass.states.get("sensor.ceny_paliv_n95_home").attributes["station"] == "Oblibena · Praha"
        assert await hass.config_entries.async_unload(entry.entry_id)


def test_entity_translations_and_icons_cover_every_sensor():
    from pathlib import Path

    from custom_components.ceny_paliv import sensor

    root = Path(sensor.__file__).parent
    keys = {"cheapest", "favourite", "archived_favourite", "position"}
    assert keys == set(re.findall(r'_attr_translation_key = "(\w+)"', (root / "sensor.py").read_text("utf-8")))
    for language in ("en", "cs"):
        names = json.loads((root / "translations" / f"{language}.json").read_text("utf-8"))["entity"]["sensor"]
        assert set(names) == keys
        assert all("{fuel}" in item["name"] for item in names.values())
        assert "{position}" in names["position"]["name"]
    icons = json.loads((root / "icons.json").read_text("utf-8"))["entity"]["sensor"]
    assert set(icons) == keys


async def test_upgrade_keeps_legacy_city_trend_history(
    hass, hass_storage, enable_custom_integrations, mock_frontend, marker
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Oblibena"}, "language": "cs"},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    yesterday = (dt_util.now().date() - timedelta(days=1)).isoformat()
    # history as written by 0.4.1: keyed by station slug
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {"n95": {"Oblibena": [[yesterday, 34]]}},
    }
    station = marker("Oblibena", 35)
    snapshot = MarkerSnapshot(markers=[station], fetched_at=dt_util.now())
    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        home = hass.states.get("sensor.ceny_paliv_n95_home")
        assert home.attributes["trends"]["1"]["ref_price"] == 34
        saved = await entry.runtime_data._store.async_load()
        assert "Oblibena" not in saved["n95"]
        assert saved["n95"][station["url"]][0] == [yesterday, 34]
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


async def test_reauth_and_reconfigure_replace_only_the_key(hass, enable_custom_integrations, mock_frontend, marker):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "old-key", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {}, "language": "cs"},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    entry_id = entry.entry_id
    with (
        patch(
            "custom_components.ceny_paliv.config_flow.async_fetch_markers",
            new=AsyncMock(return_value=[marker("Oblibena", 33)]),
        ) as fetch,
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await entry.start_reauth_flow(hass)
        assert result["step_id"] == "reauth_confirm"
        # a key with a line break can never be sent as a header: refused without a request
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "bad\nkey"})
        assert result["errors"] == {"base": "invalid_auth"}
        assert fetch.await_count == 0
        fetch.side_effect = InvalidAuth
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "still-wrong"})
        assert result["errors"] == {"base": "invalid_auth"}
        fetch.side_effect = None
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": " new-key "})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data == {"key": "new-key", "city": "Praha"}
        assert entry.entry_id == entry_id

        result = await entry.start_reconfigure_flow(hass)
        assert result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "third-key"})
        assert result["reason"] == "reconfigure_successful"
        assert entry.data["key"] == "third-key"
        assert entry.options["fuels"] == ["n95"]


@pytest.mark.parametrize(("definite", "refreshes_until_reauth"), [(True, 1), (False, 2)])
async def test_refused_key_starts_reauth(
    hass, enable_custom_integrations, mock_frontend, marker, definite, refreshes_until_reauth
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95", "diesel"], "homes": {}, "language": "cs"},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Levna", 33)], fetched_at=dt_util.now())

    def reauth_flows():
        return [
            flow for flow in hass.config_entries.flow.async_progress()
            if flow["context"]["source"] == "reauth"
        ]

    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)
    ) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # 401/403 is certain; an HTML page (definite=False) only counts when it repeats
        fetch.side_effect = InvalidAuth(definite=definite)
        for refresh in range(1, refreshes_until_reauth + 1):
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()
            assert bool(reauth_flows()) is (refresh == refreshes_until_reauth)
        assert hass.states.get("sensor.ceny_paliv_n95_top5").state == "unavailable"
        refused = entry.runtime_data.last_exception
        assert refused.translation_key == "invalid_auth"
        assert str(refused) == "mBenzin.cz no longer accepts the access key"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_one_refused_fuel_does_not_ask_for_a_new_key(hass, enable_custom_integrations, mock_frontend, marker):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95", "diesel"], "homes": {}, "language": "cs"},
        unique_id="Praha",
    )
    entry.add_to_hass(hass)

    async def fetch(session, key, fuel, *, cache=None, max_age=None):
        if fuel == "diesel":
            raise InvalidAuth(definite=True)
        return MarkerSnapshot(markers=[marker("Levna", 33)], fetched_at=dt_util.now())

    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=fetch):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert not [f for f in hass.config_entries.flow.async_progress() if f["context"]["source"] == "reauth"]
        assert hass.states.get("sensor.ceny_paliv_n95_top5").state == "33"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_area_change_frees_the_old_city_and_refuses_a_taken_one(
    hass, enable_custom_integrations, mock_frontend, marker
):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Ceny paliv Praha", data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {}}, unique_id="Praha",
    )
    brno = MockConfigEntry(
        domain=DOMAIN, title="Moje Brno", data={"key": "dummy", "city": "Brno"},
        options={"fuels": ["n95"], "homes": {}}, unique_id="Brno",
    )
    entry.add_to_hass(hass)
    brno.add_to_hass(hass)
    markers = [marker("Praha-A", 33), marker("Brno-A", 32, city="Brno"), marker("Ostrava-A", 31, city="Ostrava")]
    with (
        patch("custom_components.ceny_paliv.config_flow.async_fetch_markers", new=AsyncMock(return_value=markers)),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"area_mode": "city"})
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"city": "Brno"})
        assert result["errors"] == {"city": "already_configured"}
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"city": "Ostrava"})
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.unique_id == "Ostrava"
        assert entry.title == "Ceny paliv Ostrava"

        # Praha is free again for a new configuration
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"area_mode": "city"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"city": "Praha"})
        assert result["step_id"] == "fuels"

        # a title typed by the user is kept
        result = await hass.config_entries.options.async_init(brno.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"area_mode": "gps"})
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"location_method": "home"})
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"gps_radius_km": 20})
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
        assert brno.title == "Moje Brno"
        assert brno.unique_id.startswith("gps-")


async def test_archived_favourite_is_disabled_and_reenabled_when_chosen_again(
    hass, enable_custom_integrations, mock_frontend, marker
):
    old, new = marker("Oblibena", 33), marker("Nova", 32)
    entry = MockConfigEntry(
        domain=DOMAIN, data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {"n95": "Oblibena"}, "language": "en"}, unique_id="Praha",
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_n95_home", config_entry=entry)

    async def choose(station):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"area_mode": "city"})
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"city": "Praha"})
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"station": station})
        assert result["type"] is FlowResultType.CREATE_ENTRY

    with (
        patch("custom_components.ceny_paliv.config_flow.async_fetch_markers", new=AsyncMock(return_value=[old, new])),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=None)),
        patch("custom_components.ceny_paliv.async_setup_entry", new=AsyncMock(return_value=True)),
        patch("custom_components.ceny_paliv.async_unload_entry", new=AsyncMock(return_value=True)),
    ):
        await choose("Nova")
        assert registry.async_get(legacy.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION
        await choose("Oblibena")
        assert registry.async_get(legacy.entity_id).disabled_by is None


async def test_zone_occupancy_changes_do_not_refresh(hass, enable_custom_integrations, mock_frontend, marker):
    hass.states.async_set("zone.work", "0", {"latitude": 50.1, "longitude": 14.4, "radius": 100})
    entry = MockConfigEntry(
        domain=DOMAIN, data={"key": "dummy", "city": ""},
        options={"area_mode": "gps", "location_method": "zone", "zone_entity": "zone.work",
                 "gps_radius_km": 5, "fuels": ["n95"]},
        unique_id="gps-zone",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Nearby", 30)], fetched_at=dt_util.now())
    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)
    ) as fetch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.states.async_set("zone.work", "2", {"latitude": 50.1, "longitude": 14.4, "radius": 100})
        await hass.async_block_till_done()
        assert fetch.await_count == 1  # people arriving is not a new area
        hass.states.async_set("zone.work", "2", {"latitude": 50.1, "longitude": 14.4, "radius": 300})
        await hass.async_block_till_done()
        assert fetch.await_count == 2
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_remove_entry_deletes_history_and_last_unload_releases_cache(
    hass, hass_storage, enable_custom_integrations, mock_frontend, marker
):
    from custom_components.ceny_paliv.api import shared_marker_cache
    from custom_components.ceny_paliv.sensor import CenyPalivHomeSensor, CenyPalivTop5Sensor

    entry = MockConfigEntry(
        domain=DOMAIN, data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {}}, unique_id="Praha",
    )
    entry.add_to_hass(hass)
    snapshot = MarkerSnapshot(markers=[marker("Levna", 33)], fetched_at=dt_util.now())
    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        shared_marker_cache(hass)
        assert any(key.endswith("shared_marker_cache") for key in hass.data)
        assert f"{DOMAIN}.{entry.entry_id}" in hass_storage
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
    assert f"{DOMAIN}.{entry.entry_id}" not in hass_storage
    assert not any(key.endswith("shared_marker_cache") for key in hass.data)
    # big, display-only attributes stay out of the recorder
    assert {"stations", "labels", "logos", "gps_area"} <= CenyPalivTop5Sensor._unrecorded_attributes
    assert "trends" in CenyPalivHomeSensor._unrecorded_attributes


async def test_first_refresh_without_any_data_retries_setup(hass, enable_custom_integrations, mock_frontend):
    entry = MockConfigEntry(
        domain=DOMAIN, data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95", "diesel"], "homes": {}}, unique_id="Praha",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ceny_paliv.coordinator.async_fetch_snapshot",
        new=AsyncMock(side_effect=CannotConnect("HTTP 503")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get("sensor.ceny_paliv_n95_top5") is None


async def test_gps_logo_step_preselects_only_chains_inside_the_area(
    hass, enable_custom_integrations, mock_frontend, marker, tmp_path
):
    hass.config.config_dir = str(tmp_path)
    hass.config.latitude, hass.config.longitude = 50.1, 14.4
    near = marker("Blizko", 33, name="Orlen")
    far = {**marker("Daleko", 30, city="Brno", name="Shell"), "lat": 49.2, "lng": 16.6}
    index = [
        {"id": "orlen", "label": "Orlen", "match": ["orlen"]},
        {"id": "shell", "label": "Shell", "match": ["shell"]},
    ]
    with (
        patch("custom_components.ceny_paliv.config_flow.async_fetch_markers", new=AsyncMock(return_value=[near, far])),
        patch("custom_components.ceny_paliv.config_flow.async_fetch_index", new=AsyncMock(return_value=index)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"area_mode": "gps"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"location_method": "home"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"gps_radius_km": 10})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"fuels": ["n95"], "language": "en"}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["step_id"] == "logos"
        (logos_key,) = result["data_schema"].schema
        assert logos_key.default() == ["orlen"]
        hass.config_entries.flow.async_abort(result["flow_id"])


async def test_area_and_location_choices_are_translated_by_home_assistant(
    hass, enable_custom_integrations, mock_frontend, marker
):
    """Option labels come from translations/<language>.json, so they follow each user's own language."""
    from pathlib import Path

    with patch(
        "custom_components.ceny_paliv.config_flow.async_fetch_markers",
        new=AsyncMock(return_value=[marker("Oblibena", 33)]),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"key": "dummy"})
        (area_key,) = result["data_schema"].schema
        area_selector = result["data_schema"].schema[area_key]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"area_mode": "gps"})
        (method_key,) = result["data_schema"].schema
        method_selector = result["data_schema"].schema[method_key]
        hass.config_entries.flow.async_abort(result["flow_id"])
    root = Path(__file__).parent.parent / "custom_components" / DOMAIN / "translations"
    for language in ("en", "cs"):
        selectors = json.loads((root / f"{language}.json").read_text(encoding="utf-8"))["selector"]
        for selector in (area_selector, method_selector):
            key = selector.config["translation_key"]
            assert set(selectors[key]["options"]) == set(selector.config["options"]), (language, key)


def test_every_setting_field_has_a_description():
    """Quality scale config-flow: every field of setup, Configure, reauth and reconfigure is explained."""
    from pathlib import Path

    from custom_components.ceny_paliv import const

    folder = Path(const.__file__).parent / "translations"
    english = json.loads((folder / "en.json").read_text("utf-8"))
    for language in ("en", "cs"):
        strings = json.loads((folder / f"{language}.json").read_text("utf-8"))
        for section in ("config", "options"):
            steps = strings[section]["step"]
            assert set(steps) == set(english[section]["step"]), (language, section)
            for name, step in steps.items():
                assert set(step.get("data_description", {})) == set(step.get("data", {})), (language, section, name)
                assert all(text.strip() for text in step.get("data_description", {}).values())


async def test_removing_a_fuel_removes_its_sensors_but_not_another_areas(
    hass, enable_custom_integrations, mock_frontend, marker
):
    praha = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95", "diesel"], "homes": {"diesel": "Oblibena"}},
        unique_id="Praha",
    )
    brno = MockConfigEntry(
        domain=DOMAIN,
        data={"key": "dummy", "city": "Brno"},
        options={"fuels": ["diesel"], "homes": {}},
        unique_id="Brno",
    )
    praha.add_to_hass(hass)
    brno.add_to_hass(hass)
    registry = er.async_get(hass)
    snapshot = MarkerSnapshot(
        markers=[marker("Oblibena", 35), marker("Levna", 33, city="Brno")], fetched_at=dt_util.now()
    )

    def fuels_of(entry):
        return sorted(
            {e.unique_id.split("_")[1] for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
        )

    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(praha.entry_id)  # sets up every area of the integration
        await hass.async_block_till_done()
        assert brno.state is ConfigEntryState.LOADED
        assert fuels_of(praha) == ["diesel", "n95"]
        diesel_ids = [
            e.entity_id
            for e in er.async_entries_for_config_entry(registry, praha.entry_id)
            if "_diesel_" in e.unique_id
        ]
        assert len(diesel_ids) == 7  # top5, favourite and 5 positions

        hass.config_entries.async_update_entry(praha, options={"fuels": ["n95"], "homes": {}})
        await hass.async_block_till_done()

        # gone from the registry and the state machine, not left behind as "unavailable"
        assert fuels_of(praha) == ["n95"]
        assert all(hass.states.get(entity_id) is None for entity_id in diesel_ids)
        assert fuels_of(brno) == ["diesel"]
        assert len(er.async_entries_for_config_entry(registry, brno.entry_id)) == 6
    for entry in (praha, brno):
        assert await hass.config_entries.async_unload(entry.entry_id)
