"""Diagnostics download: the settings and refresh state of one area, without the key or where the user lives."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import CONF_HOME_HISTORY, CONF_HOME_IDENTITIES, CONF_HOMES, CONF_KEY, CONF_LOCATION
from .coordinator import CenyPalivConfigEntry

# the personal key, the GPS centre and the favourite stations (which point to where the user lives)
TO_REDACT = {
    CONF_KEY,
    CONF_LOCATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_HOMES,
    CONF_HOME_IDENTITIES,
    CONF_HOME_HISTORY,
}

# per fuel: how the last refresh went; the station lists themselves are left out
FUEL_KEYS = (
    "fetched_at",
    "last_attempt",
    "fetch_error",
    "next_update",
    "max_age_days",
    "city_name",
    "city_total",
    "excluded",
    "language",
    "gps_area",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CenyPalivConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    fuels = {}
    for fuel, payload in (coordinator.data or {}).items():
        home = payload.get("home")
        fuels[fuel] = {
            **{key: payload.get(key) for key in FUEL_KEYS if key in payload},
            "stations": len(payload.get("stations") or []),
            "gps_nearest_stations": len(payload.get("gps_nearest_stations") or []),
            "home_found": home is not None,
            "home_age_days": home.get("age_days") if home else None,
            "home_rank": home.get("rank") if home else None,
            "logos": len(payload.get("logos") or []),
        }
    return async_redact_data(
        {
            "entry": {"title": entry.title, "data": dict(entry.data), "options": dict(entry.options)},
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "last_exception": repr(coordinator.last_exception) if coordinator.last_exception else None,
                "update_interval": str(coordinator.update_interval),
                "failed_fuels": sorted(coordinator.failed_fuels),
            },
            "fuels": fuels,
            # what mBenzin sends, to see whether a field could improve the integration (for example accents)
            "mbenzin_markers": coordinator.marker_fields,
        },
        TO_REDACT,
    )
