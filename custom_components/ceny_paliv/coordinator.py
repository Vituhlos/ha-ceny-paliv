"""Data update coordinator for Ceny paliv."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .logos import logo_dir, scan_logos
from .api import (
    InvalidAuth,
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
    CONF_MAX_AGE_DAYS,
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
    FORCED_REFRESH_MIN_AGE,
    FUELS,
    LOCATION_HOME,
    LOCATION_ZONE,
    SOURCE_URL,
    STALE_DATA_AFTER,
    UPDATE_INTERVAL,
)
from .geography import distance_km
from .statistics import async_import_station_statistics

_LOGGER = logging.getLogger(__name__)

type CenyPalivConfigEntry = ConfigEntry[CenyPalivCoordinator]


def no_data_issue_id(entry_id: str) -> str:
    return f"no_data_{entry_id}"


def location_issue_id(entry_id: str) -> str:
    return f"gps_location_{entry_id}"


class CenyPalivCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetch the prices of every selected fuel and keep the daily price history."""

    config_entry: CenyPalivConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CenyPalivConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=UPDATE_INTERVAL)
        self._store: Store[dict[str, dict]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._history: dict[str, dict[str, list[list]]] | None = None
        self._key_rejections = 0  # consecutive refreshes in which every fuel was refused for the key
        # fuels whose last refresh failed, with the error: their sensors are unavailable (entity.py)
        self.failed_fuels: dict[str, str] = {}
        self._snapshot_max_age: timedelta | None = None  # set while the refresh action runs
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
        """Refresh when the configured zone moves, is resized, appears or is removed.

        The state of a zone is the number of people in it: arrivals and departures alone are ignored.
        """
        old, new = event.data.get("old_state"), event.data.get("new_state")
        if old is not None and new is not None and all(
            old.attributes.get(attr) == new.attributes.get(attr) for attr in ("latitude", "longitude", "radius")
        ):
            return
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

    def _async_update_issues(self, payloads: dict[str, dict[str, Any]], gps_error: str | None) -> None:
        """Repairs: tell the user when something only they can fix keeps the prices from coming."""
        entry = self.config_entry
        now = dt_util.now()
        stale = sorted(
            (fetched_at, fuel)
            for fuel, payload in payloads.items()
            if (fetched_at := dt_util.parse_datetime(payload.get("fetched_at") or "")) is not None
            and now - fetched_at > STALE_DATA_AFTER
        )
        if stale:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                no_data_issue_id(entry.entry_id),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="no_data",
                translation_placeholders={
                    "title": entry.title,
                    "fuels": ", ".join(FUELS.get(fuel, (fuel,))[0] for _, fuel in stale),
                    "since": dt_util.as_local(stale[0][0]).strftime("%Y-%m-%d %H:%M"),
                    "url": SOURCE_URL,  # hassfest wants URLs as placeholders, not in the text
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, no_data_issue_id(entry.entry_id))
        if gps_error is None:
            ir.async_delete_issue(self.hass, DOMAIN, location_issue_id(entry.entry_id))
        elif gps_error == "zone_unavailable":
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                location_issue_id(entry.entry_id),
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="zone_missing",
                translation_placeholders={"title": entry.title, "zone": entry.options.get(CONF_ZONE_ENTITY, "")},
            )
        else:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                location_issue_id(entry.entry_id),
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="invalid_location",
                translation_placeholders={"title": entry.title},
            )

    async def async_refresh_now(self) -> None:
        """The refresh action: download again every fuel whose data is older than FORCED_REFRESH_MIN_AGE."""
        self._snapshot_max_age = FORCED_REFRESH_MIN_AGE
        try:
            await self.async_refresh()
        finally:
            self._snapshot_max_age = None

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
        errors: dict[str, str] = {}
        auth_errors: list[InvalidAuth] = []

        for fuel in self.fuels:
            try:
                snapshot = await async_fetch_snapshot(
                    session, key, fuel, cache=shared_marker_cache(self.hass), max_age=self._snapshot_max_age
                )
            except MBenzinError as err:
                now = dt_util.now()
                err_name = type(err).__name__
                errors[fuel] = err_name
                if isinstance(err, InvalidAuth):
                    auth_errors.append(err)
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
                max_age_days=self.config_entry.options.get(CONF_MAX_AGE_DAYS),
            )
            if (home := result[fuel].get("home")) is not None:
                # the favourite's price history, kept per station whatever happens to entities or entries
                home["statistic_id"] = async_import_station_statistics(
                    self.hass, fuel, home, self._history[fuel].get(home.get("url"), []), now
                )

        if self.fuels and len(auth_errors) == len(self.fuels):
            self._key_rejections += 1
            # 401/403 is certain; an HTML answer only after it repeats (6 h later), so an outage page cannot
            # ask for a new key. Home Assistant then shows the "Reauthenticate" prompt.
            if any(err.definite for err in auth_errors) or self._key_rejections >= 2:
                raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="invalid_auth")
        else:
            self._key_rejections = 0

        logos = await self.hass.async_add_executor_job(scan_logos, logo_dir(self.hass))
        for payload in result.values():
            payload["logos"] = logos

        self._async_update_issues(result, gps_error)
        if not result or set(errors) == set(self.fuels):
            # every fuel failed: the coordinator makes all sensors unavailable, logs it once and logs the recovery
            self.failed_fuels = errors
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"errors": ", ".join(f"{fuel}: {err}" for fuel, err in errors.items())},
            )
        # one fuel failing while the others refresh: log each change once, not on every refresh
        for fuel in sorted(errors.keys() - self.failed_fuels.keys()):
            _LOGGER.warning(
                "Ceny paliv: %s prices cannot be refreshed from mBenzin.cz (%s); its sensors are unavailable",
                fuel,
                errors[fuel],
            )
        if self.last_update_success:  # after a full outage the coordinator already logged the recovery
            for fuel in sorted(self.failed_fuels.keys() - errors.keys()):
                _LOGGER.info("Ceny paliv: %s prices are refreshed again", fuel)
        self.failed_fuels = errors
        await self._store.async_save(self._history)
        return result
