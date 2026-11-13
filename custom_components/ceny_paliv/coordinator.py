"""Data update coordinator for Ceny paliv."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .logos import logo_dir, scan_logos
from .api import (
    MBenzinError,
    async_fetch_snapshot,
    build_payload,
    next_update_at,
    shared_marker_cache,
)
from .const import (
    AREA_MODE_GPS,
    CONF_AREA_MODE,
    CONF_CITY,
    CONF_FUELS,
    CONF_GPS_RADIUS_KM,
    CONF_HOMES,
    CONF_HOME_HISTORY,
    CONF_HOME_IDENTITIES,
    CONF_KEY,
    CONF_LOCATION,
    CONF_LOCATION_METHOD,
    CONF_LANGUAGE,
    CONF_ZONE_ENTITY,
    DEFAULT_GPS_RADIUS_KM,
    DEFAULT_FUELS,
    DEFAULT_LANGUAGE,
    DOMAIN,
    LOCATION_HOME,
    LOCATION_ZONE,
    UPDATE_INTERVAL,
)
from .geography import distance_km

_LOGGER = logging.getLogger(__name__)

type CenyPalivConfigEntry = ConfigEntry[CenyPalivCoordinator]


class CenyPalivCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetch the prices of every selected fuel and keep the daily price history."""

    config_entry: CenyPalivConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CenyPalivConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=UPDATE_INTERVAL)
        self._store: Store[dict[str, dict]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._history: dict[str, dict[str, list[list]]] | None = None
        if (
            entry.options.get(CONF_AREA_MODE) == AREA_MODE_GPS
            and entry.options.get(CONF_LOCATION_METHOD) == LOCATION_ZONE
            and (zone_entity := entry.options.get(CONF_ZONE_ENTITY))
        ):
            entry.async_on_unload(
                async_track_state_change_event(
                    hass, [zone_entity], self._async_zone_state_changed
                )
            )

    @property
    def fuels(self) -> list[str]:
        return list(self.config_entry.options.get(CONF_FUELS, DEFAULT_FUELS))

    @property
    def homes(self) -> dict[str, str]:
        return dict(self.config_entry.options.get(CONF_HOMES, {}))

    @property
    def home_identities(self) -> dict[str, str]:
        return dict(self.config_entry.options.get(CONF_HOME_IDENTITIES, {}))

    @property
    def home_history(self) -> dict[str, list[dict[str, Any]]]:
        return {
            fuel: list(records)
            for fuel, records in self.config_entry.options.get(CONF_HOME_HISTORY, {}).items()
        }

    @property
    def language(self) -> str:
        return self.config_entry.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    async def _async_zone_state_changed(self, event: Event) -> None:
        """Refresh immediately when the configured zone changes or is removed."""
        await self.async_refresh()

    def _gps_location(self) -> tuple[tuple[float, float] | None, str | None]:
        options = self.config_entry.options
        method = options.get(CONF_LOCATION_METHOD, LOCATION_HOME)
        if method == LOCATION_HOME:
            latitude, longitude = self.hass.config.latitude, self.hass.config.longitude
        elif method == LOCATION_ZONE:
            entity_id = options.get(CONF_ZONE_ENTITY)
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is None:
                return None, "zone_unavailable"
            latitude = state.attributes.get("latitude")
            longitude = state.attributes.get("longitude")
        else:
            location = options.get(CONF_LOCATION) or {}
            latitude = location.get("latitude")
            longitude = location.get("longitude")
        try:
            distance_km(latitude, longitude, latitude, longitude)
            return (float(latitude), float(longitude)), None
        except (TypeError, ValueError, OverflowError):
            return None, "invalid_coordinates"

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        if self._history is None:
            self._history = await self._store.async_load() or {}
        session = async_get_clientsession(self.hass)
        key = self.config_entry.data[CONF_KEY]
        city = self.config_entry.options.get(
            CONF_CITY, self.config_entry.data.get(CONF_CITY, "")
        )
        gps_mode = self.config_entry.options.get(CONF_AREA_MODE) == AREA_MODE_GPS
        location_method = self.config_entry.options.get(
            CONF_LOCATION_METHOD, LOCATION_HOME
        )
        gps_center, gps_error = self._gps_location() if gps_mode else (None, None)
        gps_radius_km = self.config_entry.options.get(
            CONF_GPS_RADIUS_KM, DEFAULT_GPS_RADIUS_KM
        )
        zone_entity = (
            self.config_entry.options.get(CONF_ZONE_ENTITY)
            if location_method == LOCATION_ZONE
            else None
        )
        homes = self.homes
        result: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        for fuel in self.fuels:
            try:
                snapshot = await async_fetch_snapshot(
                    session, key, fuel, cache=shared_marker_cache(self.hass)
                )
            except MBenzinError as err:
                now = dt_util.now()
                err_name = type(err).__name__
                errors.append(f"{fuel}: {err_name}")
                previous = (self.data or {}).get(fuel)
                if previous is None:
                    continue
                # keep the last good data and flag the failure (the dashboard shows it)
                result[fuel] = {
                    **previous,
                    "fetch_error": err_name,
                    "last_attempt": now.isoformat(timespec="seconds"),
                    "next_update": next_update_at(now).isoformat(timespec="seconds"),
                }
                continue
            now = dt_util.now()
            result[fuel] = build_payload(
                snapshot.markers,
                fuel=fuel,
                city=city,
                home_slug=homes.get(fuel),
                history=self._history.setdefault(fuel, {}),
                now=now,
                language=self.language,
                fetched_at=snapshot.fetched_at,
                gps_method=location_method if gps_mode else None,
                gps_center=gps_center,
                gps_radius_km=gps_radius_km,
                gps_zone_entity=zone_entity,
                gps_error=gps_error,
                legacy_city=self.config_entry.data.get(CONF_CITY),
            )

        logos = await self.hass.async_add_executor_job(scan_logos, logo_dir(self.hass))
        for payload in result.values():
            payload["logos"] = logos

        if not result:
            raise UpdateFailed("Ceny paliv refresh failed (mBenzin.cz): " + ", ".join(errors))
        if errors:
            _LOGGER.warning("Ceny paliv partial refresh: %s", ", ".join(errors))
        await self._store.async_save(self._history)
        return result
