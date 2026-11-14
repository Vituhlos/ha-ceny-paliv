"""The ceny_paliv.refresh action: load the prices now, without flooding mBenzin.cz."""
from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FORCED_REFRESH_MIN_AGE, FUELS
from .coordinator import CenyPalivConfigEntry

SERVICE_REFRESH = "refresh"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"  # not in homeassistant.const of 2025.1
REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions once, when the integration is set up (not per entry)."""

    async def async_refresh(call: ServiceCall) -> None:
        failed: list[str] = []
        kept: list[str] = []
        for entry in _loaded_entries(hass, call.data.get(ATTR_CONFIG_ENTRY_ID)):
            await entry.runtime_data.async_refresh_now()
            _collect_failures(entry, failed, kept)
        if failed or kept:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
                translation_placeholders={"failed": ", ".join(failed) or "—", "kept": ", ".join(kept) or "—"},
            )

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, async_refresh, schema=REFRESH_SCHEMA)


def _loaded_entries(hass: HomeAssistant, entry_id: str | None) -> list[CenyPalivConfigEntry]:
    if entry_id is None:
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
        ]
        if not entries:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_loaded_entries")
        return entries
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"title": entry.title},
        )
    return [entry]


def _collect_failures(entry: CenyPalivConfigEntry, failed: list[str], kept: list[str]) -> None:
    """Failed: no prices could be loaded. Kept: mBenzin.cz did not answer, so the cached prices stay."""
    coordinator = entry.runtime_data
    if not coordinator.last_update_success:
        failed.append(f"{entry.title} ({coordinator.last_exception})")
        return
    # one minute of slack: the cache counts on the event loop's clock, fetched_at on the wall clock
    oldest = dt_util.now() - FORCED_REFRESH_MIN_AGE - timedelta(minutes=1)
    for fuel in coordinator.fuels:
        label = f"{entry.title} · {FUELS.get(fuel, (fuel,))[0]}"
        if fuel in coordinator.failed_fuels:
            failed.append(f"{label} ({coordinator.failed_fuels[fuel]})")
            continue
        fetched_at = dt_util.parse_datetime(((coordinator.data or {}).get(fuel) or {}).get("fetched_at") or "")
        if fetched_at is not None and fetched_at < oldest:
            kept.append(label)
