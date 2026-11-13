"""Config flow: key -> city -> fuels -> favourite station for each fuel."""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    InvalidAuth,
    MBenzinError,
    RateLimited,
    async_fetch_markers,
    city_of,
    city_options,
    pretty,
    shared_marker_cache,
    station_options,
)
from .const import (
    CONF_CITY,
    CONF_AREA_MODE,
    CONF_FUELS,
    CONF_GPS_RADIUS_KM,
    CONF_HOMES,
    CONF_HOME_HISTORY,
    CONF_HOME_IDENTITIES,
    CONF_KEY,
    CONF_LOCATION,
    CONF_LOCATION_METHOD,
    CONF_LANGUAGE,
    CONF_LOGOS,
    CONF_MAX_AGE_DAYS,
    CONF_STATION,
    CONF_ZONE_ENTITY,
    AREA_MODE_CITY,
    AREA_MODE_GPS,
    DEFAULT_GPS_RADIUS_KM,
    DEFAULT_FUELS,
    DEFAULT_LANGUAGE,
    DOMAIN,
    FUELS,
    LANGUAGES,
    LOCATION_HOME,
    LOCATION_MANUAL,
    LOCATION_MAP,
    LOCATION_ZONE,
    MAX_AGE_CHOICES,
    MAX_AGE_DAYS_DEFAULT,
    NONE_VALUE,
)
from .geography import MAX_RADIUS_KM, MIN_RADIUS_KM, stations_within_radius
from .logos import async_fetch_index, async_sync, chains_in, installed_ids, logo_dir


def _error_key(err: MBenzinError) -> str:
    if isinstance(err, InvalidAuth):
        return "invalid_auth"
    if isinstance(err, RateLimited):
        return "rate_limited"
    return "cannot_connect"


def _clean_key(value: Any) -> str | None:
    """The pasted key without surrounding spaces, or None when it cannot be a key (empty, control characters)."""
    key = str(value or "").strip()
    return key if key and key.isprintable() else None


async def _async_check_key(hass, key: str | None) -> tuple[list[dict[str, Any]] | None, dict[str, str]]:
    """Validate a key with one n95 download (shared cache): (markers, errors)."""
    if key is None:
        return None, {"base": "invalid_auth"}
    try:
        markers = await async_fetch_markers(
            async_get_clientsession(hass), key, "n95", cache=shared_marker_cache(hass)
        )
    except MBenzinError as err:
        return None, {"base": _error_key(err)}
    return markers, {}


def _valid_coordinates(latitude: Any, longitude: Any) -> bool:
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        return False
    try:
        lat, lng = float(latitude), float(longitude)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180


def _station_slug(marker: dict[str, Any]) -> str | None:
    if not isinstance(marker, dict) or not isinstance(marker.get("url"), str):
        return None
    try:
        parts = marker["url"].split("/")
        if (
            len(parts) < 5
            or parts[1] != "Ceny-benzinu-a-nafty"
            or not parts[2]
            or not parts[3]
            or not parts[4]
        ):
            return None
        return parts[3]
    except (KeyError, IndexError, AttributeError, TypeError):
        return None


class _FuelStationSteps:
    """Shared by the config flow and the options flow: choose fuels, then a favourite station per fuel."""

    _key: str
    _city: str
    _fuels: list[str]
    _language: str
    _queue: list[str]
    _homes: dict[str, str]
    _home_identities: dict[str, str]
    _home_history: dict[str, list[dict[str, Any]]]
    _stations: dict[str, list[dict[str, str]]]
    _station_markers: dict[str, list[dict[str, Any]]]
    _defaults_fuels: list[str] = DEFAULT_FUELS
    _defaults_language: str | None = None
    _defaults_homes: dict[str, str] = {}
    _defaults_logos: list[str] | None = None
    _defaults_max_age_days: int = MAX_AGE_DAYS_DEFAULT
    _max_age_days: int = MAX_AGE_DAYS_DEFAULT
    _area_mode: str
    _location_method: str
    _gps_location: dict[str, float] | None
    _gps_zone_entity: str | None
    _gps_radius_km: float
    _cities: list[dict[str, str]]
    _chains: set[str]
    _logos: list[str] | None = None

    async def async_step_city(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._city = user_input[CONF_CITY]
            if not getattr(self, "_options_flow", False):
                await self.async_set_unique_id(self._city)
                self._abort_if_unique_id_configured()
            elif any(
                other.unique_id == self._city and other.entry_id != self._own_entry_id()
                for other in self.hass.config_entries.async_entries(DOMAIN)
            ):
                # another configuration already covers this city
                return self.async_show_form(
                    step_id="city", data_schema=self._city_schema(), errors={CONF_CITY: "already_configured"}
                )
            return await self.async_step_fuels()
        return self.async_show_form(step_id="city", data_schema=self._city_schema())

    def _city_schema(self) -> vol.Schema:
        city_key = vol.Required(CONF_CITY)
        if (
            getattr(self, "_defaults_city", None)
            in {city["value"] for city in self._cities}
        ):
            city_key = vol.Required(CONF_CITY, default=self._defaults_city)
        return vol.Schema(
            {
                city_key: SelectSelector(
                    SelectSelectorConfig(options=self._cities, mode=SelectSelectorMode.DROPDOWN)
                )
            }
        )

    async def async_step_fuels(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            fuels = user_input[CONF_FUELS]
            self._pending_fuels = list(fuels)
            self._pending_language = user_input[CONF_LANGUAGE]
            self._pending_max_age_days = int(user_input.get(CONF_MAX_AGE_DAYS, MAX_AGE_DAYS_DEFAULT))
            if not fuels:
                errors[CONF_FUELS] = "no_fuel"
            else:
                session = async_get_clientsession(self.hass)
                stations: dict[str, list[dict[str, str]]] = {}
                station_markers: dict[str, list[dict[str, Any]]] = {}
                chains: set[str] = set()
                try:
                    for fuel in fuels:
                        markers = await async_fetch_markers(
                            session, self._key, fuel, cache=shared_marker_cache(self.hass)
                        )
                        gps = self._area_mode == AREA_MODE_GPS
                        gps_center = self._gps_center_for_flow() if gps else None
                        stations[fuel] = (
                            station_options(
                                markers,
                                None,
                                use_url=True,
                                center=gps_center,
                                radius_km=getattr(
                                    self, "_gps_radius_km", DEFAULT_GPS_RADIUS_KM
                                ),
                            )
                            if gps and gps_center is not None
                            else []
                            if gps
                            else station_options(markers, self._city)
                        )
                        station_markers[fuel] = [
                            marker for marker in markers if isinstance(marker, dict)
                        ]
                        # chains of the chosen area only, so the logo step preselects what the area needs
                        if not gps:
                            area_markers = [m for m in markers if city_of(m) == self._city]
                        elif gps_center is None:
                            area_markers = []
                        else:
                            try:
                                area_markers = stations_within_radius(
                                    markers, *gps_center,
                                    getattr(self, "_gps_radius_km", DEFAULT_GPS_RADIUS_KM),
                                )
                            except (TypeError, ValueError, OverflowError):
                                area_markers = []
                        chains |= {
                            m.get("chain")
                            if isinstance(m.get("chain"), str)
                            else m.get("name")
                            for m in area_markers
                            if isinstance(m, dict)
                            and isinstance(m.get("name"), str)
                        }
                except MBenzinError as err:
                    errors["base"] = _error_key(err)
                else:
                    self._fuels, self._stations, self._chains = fuels, stations, chains
                    self._station_markers = station_markers
                    self._language = user_input[CONF_LANGUAGE]
                    self._max_age_days = self._pending_max_age_days
                    self._queue, self._homes = list(fuels), {}
                    self._pending_fuels = None
                    self._pending_language = None
                    return await self.async_step_station()
        pending_fuels = getattr(self, "_pending_fuels", None)
        default_fuels = (
            pending_fuels if pending_fuels is not None else self._defaults_fuels
        )
        default_language = (
            getattr(self, "_pending_language", None) or self._default_language()
        )
        default_max_age = getattr(self, "_pending_max_age_days", None) or self._defaults_max_age_days
        if default_max_age not in MAX_AGE_CHOICES:
            default_max_age = MAX_AGE_DAYS_DEFAULT
        schema = vol.Schema(
            {
                vol.Required(CONF_FUELS, default=default_fuels): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": k, "label": v[0]} for k, v in FUELS.items()],
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_LANGUAGE, default=default_language): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": k, "label": v} for k, v in LANGUAGES.items()],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_MAX_AGE_DAYS, default=str(default_max_age)): SelectSelector(
                    SelectSelectorConfig(
                        options=[str(days) for days in MAX_AGE_CHOICES],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="max_age_days",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="fuels", data_schema=schema, errors=errors)

    def _default_language(self) -> str:
        """Language of the dashboard texts: the saved one, else Home Assistant's own language."""
        if self._defaults_language in LANGUAGES:
            return self._defaults_language
        ha_language = (self.hass.config.language or DEFAULT_LANGUAGE).split("-")[0]
        return ha_language if ha_language in LANGUAGES else DEFAULT_LANGUAGE

    def _gps_center_for_flow(self) -> tuple[float, float] | None:
        method = getattr(self, "_location_method", LOCATION_HOME)
        if method == LOCATION_HOME:
            latitude, longitude = self.hass.config.latitude, self.hass.config.longitude
        elif method == LOCATION_ZONE:
            entity_id = getattr(self, "_gps_zone_entity", None)
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is None:
                return None
            latitude = state.attributes.get(CONF_LATITUDE)
            longitude = state.attributes.get(CONF_LONGITUDE)
        else:
            location = getattr(self, "_gps_location", None) or {}
            latitude = location.get(CONF_LATITUDE)
            longitude = location.get(CONF_LONGITUDE)
        if not _valid_coordinates(latitude, longitude):
            return None
        return float(latitude), float(longitude)

    async def _async_load_cities(self) -> str | None:
        """Load city choices on demand using a fuel already configured for this entry."""
        fuel = next(
            (item for item in self._defaults_fuels if item in FUELS),
            DEFAULT_FUELS[0],
        )
        try:
            markers = await async_fetch_markers(
                async_get_clientsession(self.hass),
                self._key,
                fuel,
                cache=shared_marker_cache(self.hass),
            )
        except MBenzinError as err:
            return _error_key(err)
        self._cities = city_options(markers)
        return None if self._cities else "no_cities"

    async def async_step_area_mode(
        self,
        user_input: dict[str, Any] | None = None,
        *,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._area_mode = user_input[CONF_AREA_MODE]
            self._pending_area_mode = self._area_mode
            if self._area_mode == AREA_MODE_CITY:
                if not getattr(self, "_cities", None):
                    error = await self._async_load_cities()
                    if error:
                        return await self.async_step_area_mode(
                            errors={"base": error}
                        )
                self._pending_area_mode = None
                return await self.async_step_city()
            if not hasattr(self, "_city"):
                self._city = ""
            self._gps_config_unique_id = f"gps-{uuid4()}"
            self._pending_area_mode = None
            return await self.async_step_location_method()

        default_area_mode = getattr(
            self, "_pending_area_mode", getattr(self, "_defaults_area_mode", AREA_MODE_CITY)
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_AREA_MODE, default=default_area_mode):
                    SelectSelector(
                        SelectSelectorConfig(
                            options=[AREA_MODE_CITY, AREA_MODE_GPS],
                            translation_key="area_mode",  # labels in translations/<language>.json
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
            }
        )
        return self.async_show_form(
            step_id="area_mode", data_schema=schema, errors=errors or {}
        )

    async def async_step_location_method(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._location_method = user_input[CONF_LOCATION_METHOD]
            if self._location_method == LOCATION_HOME:
                self._gps_location = None
                self._gps_zone_entity = None
                return await self.async_step_gps_radius()
            if self._location_method == LOCATION_ZONE:
                return await self.async_step_location_zone()
            if self._location_method == LOCATION_MAP:
                return await self.async_step_location_map()
            return await self.async_step_location_manual()

        default = getattr(self, "_defaults_location_method", LOCATION_HOME)
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION_METHOD, default=default): SelectSelector(
                    SelectSelectorConfig(
                        options=[LOCATION_HOME, LOCATION_ZONE, LOCATION_MAP, LOCATION_MANUAL],
                        translation_key="location_method",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="location_method", data_schema=schema)

    async def async_step_location_zone(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input[CONF_ZONE_ENTITY]
            state = self.hass.states.get(entity_id)
            if not entity_id.startswith("zone.") or state is None or not _valid_coordinates(
                state.attributes.get(CONF_LATITUDE), state.attributes.get(CONF_LONGITUDE)
            ):
                errors[CONF_ZONE_ENTITY] = "invalid_zone"
            else:
                self._gps_zone_entity = entity_id
                self._gps_location = None
                return await self.async_step_gps_radius()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ZONE_ENTITY,
                    default=getattr(self, "_defaults_zone_entity", None),
                ): EntitySelector(EntitySelectorConfig(domain="zone"))
            }
        )
        return self.async_show_form(step_id="location_zone", data_schema=schema, errors=errors)

    async def async_step_location_map(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            if not _valid_coordinates(location.get(CONF_LATITUDE), location.get(CONF_LONGITUDE)):
                errors[CONF_LOCATION] = "invalid_coordinates"
            else:
                self._gps_location = {
                    CONF_LATITUDE: float(location[CONF_LATITUDE]),
                    CONF_LONGITUDE: float(location[CONF_LONGITUDE]),
                }
                self._gps_zone_entity = None
                return await self.async_step_gps_radius()
        default_location = getattr(self, "_defaults_gps_location", None) or {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCATION, default=default_location): LocationSelector(
                    LocationSelectorConfig(radius=False)
                )
            }
        )
        return self.async_show_form(step_id="location_map", data_schema=schema, errors=errors)

    async def async_step_location_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            latitude, longitude = user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
            if not _valid_coordinates(latitude, longitude):
                errors["base"] = "invalid_coordinates"
            else:
                self._gps_location = {
                    CONF_LATITUDE: float(latitude),
                    CONF_LONGITUDE: float(longitude),
                }
                self._gps_zone_entity = None
                return await self.async_step_gps_radius()
        default_location = getattr(self, "_defaults_gps_location", None) or {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE,
                    default=default_location[CONF_LATITUDE],
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=-90, max=90, step="any", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_LONGITUDE,
                    default=default_location[CONF_LONGITUDE],
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=-180, max=180, step="any", mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="location_manual", data_schema=schema, errors=errors)

    async def async_step_gps_radius(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                radius = float(user_input[CONF_GPS_RADIUS_KM])
            except (TypeError, ValueError):
                radius = 0
            if not math.isfinite(radius) or not MIN_RADIUS_KM <= radius <= MAX_RADIUS_KM:
                errors[CONF_GPS_RADIUS_KM] = "invalid_radius"
            else:
                self._gps_radius_km = radius
                return await self.async_step_fuels()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GPS_RADIUS_KM,
                    default=getattr(self, "_defaults_gps_radius_km", DEFAULT_GPS_RADIUS_KM),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_RADIUS_KM,
                        max=MAX_RADIUS_KM,
                        step=1,
                        unit_of_measurement="km",
                        mode=NumberSelectorMode.SLIDER,
                    )
                )
            }
        )
        return self.async_show_form(step_id="gps_radius", data_schema=schema, errors=errors)

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        fuel = self._queue[0]
        if user_input is not None:
            choice = user_input.get(CONF_STATION, NONE_VALUE)
            previous_choice = self._defaults_homes.get(fuel, NONE_VALUE)
            previous_identity = getattr(self, "_home_identities", {}).get(fuel) or (
                # a saved slug always belongs to the city it was chosen in
                self._canonical_station_identity(
                    fuel, previous_choice, city=getattr(self, "_original_city", None) or None
                )
                if previous_choice != NONE_VALUE
                else None
            )
            selected_identity = self._canonical_station_identity(
                fuel,
                choice,
                city=self._city if self._area_mode == AREA_MODE_CITY else None,
            )
            area_changed = (
                self._area_mode
                != getattr(self, "_defaults_area_mode", AREA_MODE_CITY)
                or (
                    self._area_mode == AREA_MODE_CITY
                    and self._city != getattr(self, "_original_city", self._city)
                )
                or (
                    self._area_mode == AREA_MODE_GPS
                    and (
                        self._location_method
                        != getattr(self, "_defaults_location_method", LOCATION_HOME)
                        or self._gps_location
                        != getattr(self, "_defaults_gps_location", None)
                        or self._gps_zone_entity
                        != getattr(self, "_defaults_zone_entity", None)
                        or self._gps_radius_km
                        != getattr(
                            self, "_defaults_gps_radius_km", DEFAULT_GPS_RADIUS_KM
                        )
                    )
                )
            )
            if (
                choice != NONE_VALUE
                and selected_identity is None
                and (
                    choice != previous_choice
                    or area_changed
                    or previous_identity is not None
                )
            ):
                selected_identity = (
                    f"unresolved:{self._area_mode}:"
                    f"{self._city if self._area_mode == AREA_MODE_CITY else self._location_method}:"
                    f"{choice}"
                )
            if (
                getattr(self, "_options_flow", False)
                and previous_identity != selected_identity
                and (previous_choice != choice or previous_identity is not None or selected_identity is not None)
            ):
                if previous_choice != NONE_VALUE:
                    identity = previous_identity or previous_choice
                    legacy = fuel not in self._home_identities
                    records = self._home_history.setdefault(fuel, [])
                    record = {"identity": identity, "legacy": legacy}
                    if record not in records:
                        records.append(record)
                if choice != NONE_VALUE and selected_identity is not None:
                    if any(
                        record.get("identity") == selected_identity
                        and record.get("legacy")
                        for record in self._home_history.get(fuel, [])
                    ):
                        self._home_identities.pop(fuel, None)
                    else:
                        self._home_identities[fuel] = selected_identity
                elif choice == NONE_VALUE:
                    self._home_identities.pop(fuel, None)
            if choice != NONE_VALUE:
                self._homes[fuel] = choice
            else:
                self._homes.pop(fuel, None)
                self._home_identities.pop(fuel, None)
            self._queue.pop(0)
            if self._queue:
                return await self.async_step_station()
            return await self.async_step_logos()
        options = [{"value": NONE_VALUE, "label": "—"}] + self._stations[fuel]
        default = self._defaults_homes.get(fuel, NONE_VALUE)
        if default not in {option["value"] for option in options} and default != NONE_VALUE:
            language = (self.hass.config.language or DEFAULT_LANGUAGE).split("-")[0]
            # A saved slug (from City mode) is only meaningful in the city it was chosen in: never match
            # another city's station that happens to share the slug.
            slug_city = getattr(self, "_original_city", None)
            candidates = [
                marker
                for marker in self._station_markers.get(fuel, [])
                if marker.get("url") == default
                or (
                    "/" not in default
                    and bool(slug_city)
                    and city_of(marker) == slug_city
                    and _station_slug(marker) == default
                )
            ]
            if len(candidates) == 1 and self._area_mode == AREA_MODE_GPS:
                marker = candidates[0]
                # keep the favourite as its exact station URL, so GPS mode never resolves a bare slug
                default = marker["url"]
                pretty_options = station_options([marker], None, use_url=True)
                if default in {option["value"] for option in options}:
                    pass  # the station is inside the area and already listed
                elif pretty_options:
                    prefix = (
                        "Outside selected GPS area · "
                        if language != "cs"
                        else "Mimo zvolenou GPS oblast · "
                    )
                    options.append(
                        {"value": default, "label": prefix + pretty_options[0]["label"]}
                    )
                else:
                    options.append(
                        {
                            "value": default,
                            "label": (
                                "Saved station (not resolved)"
                                if language != "cs"
                                else "Uložená stanice (neověřená)"
                            ),
                        }
                    )
            else:
                options.append(
                    {
                        "value": default,
                        "label": (
                            "Saved station (not resolved)"
                            if language != "cs"
                            else "Uložená stanice (neověřená)"
                        ),
                    }
                )
        valid = {option["value"] for option in options}
        schema = vol.Schema(
            {
                vol.Optional(CONF_STATION, default=default if default in valid else NONE_VALUE): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(
            step_id="station",
            data_schema=schema,
            description_placeholders={"fuel": FUELS[fuel][0], "city": pretty(self._city)},
        )

    def _canonical_station_identity(
        self, fuel: str, choice: str, *, city: str | None = None
    ) -> str | None:
        if choice == NONE_VALUE:
            return None
        markers = self._station_markers.get(fuel, [])
        if "/" in choice:
            matching = [
                marker for marker in markers
                if marker.get("url") == choice and _station_slug(marker) is not None
            ]
        else:
            matching = [
                marker
                for marker in markers
                if (city is None or city_of(marker) == city)
                and _station_slug(marker) == choice
            ]
        if len(matching) != 1:
            return None
        url = matching[0].get("url")
        return url if isinstance(url, str) else None

    async def async_step_logos(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Optional: tick the chains whose logos should be downloaded from the pack on GitHub."""
        session = async_get_clientsession(self.hass)
        if user_input is None:
            index = await async_fetch_index(session)
            if not index:  # offline or pack not published: carry on without logos
                self._logos = None
                return await self._async_finish()
            self._index = index
            in_city = chains_in(sorted(self._chains), index)
            folder = logo_dir(self.hass)
            default = self._defaults_logos
            if default is None:
                default = await self.hass.async_add_executor_job(installed_ids, folder) or sorted(in_city)
            options = sorted(index, key=lambda i: (i["id"] not in in_city, i["label"].casefold()))
            known = {i["id"] for i in index}
            schema = vol.Schema(
                {
                    vol.Optional(CONF_LOGOS, default=[d for d in default if d in known]): SelectSelector(
                        SelectSelectorConfig(
                            options=[{"value": i["id"], "label": i["label"]} for i in options],
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            )
            return self.async_show_form(step_id="logos", data_schema=schema)
        self._logos = list(user_input.get(CONF_LOGOS, []))
        others: set[str] = set()
        for other in self.hass.config_entries.async_entries(DOMAIN):
            if other.entry_id != self._own_entry_id():
                others |= set(other.options.get(CONF_LOGOS, []))
        await async_sync(self.hass, session, self._index, others | set(self._logos))
        return await self._async_finish()

    def _own_entry_id(self) -> str | None:
        return None

    async def _async_finish(self) -> ConfigFlowResult:  # pragma: no cover - implemented by the flows
        raise NotImplementedError

    def _options(self, previous: dict[str, Any] | None = None) -> dict[str, Any]:
        options = {
            **(previous or {}),
            CONF_FUELS: self._fuels,
            CONF_HOMES: self._homes,
            CONF_LANGUAGE: self._language,
            CONF_AREA_MODE: self._area_mode,
            CONF_MAX_AGE_DAYS: self._max_age_days,
        }
        home_identities = getattr(self, "_home_identities", {})
        home_history = getattr(self, "_home_history", {})
        options.pop(CONF_HOME_IDENTITIES, None)
        options.pop(CONF_HOME_HISTORY, None)
        if home_identities:
            options[CONF_HOME_IDENTITIES] = dict(home_identities)
        if home_history:
            options[CONF_HOME_HISTORY] = {
                fuel: list(records) for fuel, records in home_history.items()
            }
        if self._area_mode == AREA_MODE_CITY:
            options[CONF_CITY] = self._city
        else:
            options[CONF_LOCATION_METHOD] = self._location_method
            options[CONF_GPS_RADIUS_KM] = self._gps_radius_km
            if self._gps_location is not None:
                options[CONF_LOCATION] = self._gps_location
            if self._gps_zone_entity is not None:
                options[CONF_ZONE_ENTITY] = self._gps_zone_entity
        logos = self._logos if self._logos is not None else (previous or {}).get(CONF_LOGOS)
        if logos is not None:
            options[CONF_LOGOS] = logos
        return options


def _entry_title(area_mode: str, city: str) -> str:
    return f"Ceny paliv {pretty(city)}" if area_mode == AREA_MODE_CITY else "Ceny paliv GPS area"


_KEY_SCHEMA = vol.Schema(
    {vol.Required(CONF_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


class CenyPalivConfigFlow(_FuelStationSteps, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _cities: list[dict[str, str]]

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        # A new entry has no favourite identities yet; the shared station step updates them.
        self._home_identities = {}
        self._home_history = {}
        if user_input is not None:
            key = _clean_key(user_input[CONF_KEY])
            markers, errors = await _async_check_key(self.hass, key)
            if markers is not None:
                self._key = key
                self._cities = city_options(markers)
                return await self.async_step_area_mode()
        return self.async_show_form(step_id="user", data_schema=_KEY_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """mBenzin.cz refused the key: ask for a new one (the entry, its history and entities stay)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_replace_key("reauth_confirm", self._get_reauth_entry(), user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Replace the access key of an existing entry."""
        return await self._async_replace_key("reconfigure", self._get_reconfigure_entry(), user_input)

    async def _async_replace_key(self, step_id: str, entry, user_input: dict[str, Any] | None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            key = _clean_key(user_input[CONF_KEY])
            markers, errors = await _async_check_key(self.hass, key)
            if markers is not None:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_KEY: key})
        return self.async_show_form(step_id=step_id, data_schema=_KEY_SCHEMA, errors=errors)

    async def _async_finish(self) -> ConfigFlowResult:
        if self._area_mode == AREA_MODE_GPS:
            await self.async_set_unique_id(self._gps_config_unique_id)
        return self.async_create_entry(
            title=_entry_title(self._area_mode, self._city),
            data={CONF_KEY: self._key, CONF_CITY: self._city or ""},
            options=self._options(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> CenyPalivOptionsFlow:
        return CenyPalivOptionsFlow()


class CenyPalivOptionsFlow(_FuelStationSteps, OptionsFlow):
    """Change the fuels and the favourite stations later."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        self._options_flow = True
        self._key = entry.data[CONF_KEY]
        self._city = entry.options.get(CONF_CITY, entry.data.get(CONF_CITY, ""))
        self._original_city = self._city
        self._defaults_city = self._city
        self._defaults_fuels = list(entry.options.get(CONF_FUELS, DEFAULT_FUELS))
        self._defaults_homes = dict(entry.options.get(CONF_HOMES, {}))
        self._home_identities = dict(entry.options.get(CONF_HOME_IDENTITIES, {}))
        self._home_history = {
            fuel: list(records)
            for fuel, records in entry.options.get(CONF_HOME_HISTORY, {}).items()
        }
        self._defaults_language = entry.options.get(CONF_LANGUAGE)
        self._defaults_logos = entry.options.get(CONF_LOGOS)
        self._defaults_max_age_days = entry.options.get(CONF_MAX_AGE_DAYS, MAX_AGE_DAYS_DEFAULT)
        self._max_age_days = self._defaults_max_age_days
        self._defaults_area_mode = entry.options.get(CONF_AREA_MODE, AREA_MODE_CITY)
        self._defaults_location_method = entry.options.get(CONF_LOCATION_METHOD, LOCATION_HOME)
        self._defaults_gps_location = entry.options.get(CONF_LOCATION)
        self._defaults_zone_entity = entry.options.get(CONF_ZONE_ENTITY)
        self._defaults_gps_radius_km = entry.options.get(
            CONF_GPS_RADIUS_KM, DEFAULT_GPS_RADIUS_KM
        )
        self._cities = []
        self._pending_area_mode = None
        self._pending_fuels = None
        self._pending_language = None
        self._pending_max_age_days = None
        return await self.async_step_area_mode()

    def _own_entry_id(self) -> str | None:
        return self.config_entry.entry_id

    async def _async_finish(self) -> ConfigFlowResult:
        entry = self.config_entry
        # the entry's identity follows its area, so the old city can be added again and the title stays true
        if self._area_mode == AREA_MODE_CITY:
            unique_id = self._city
        else:
            unique_id = entry.unique_id if (entry.unique_id or "").startswith("gps-") else f"gps-{uuid4()}"
        updates: dict[str, Any] = {"unique_id": unique_id}
        if entry.title == _entry_title(
            entry.options.get(CONF_AREA_MODE, AREA_MODE_CITY), entry.options.get(CONF_CITY, entry.data.get(CONF_CITY, ""))
        ):  # only an automatic title; a title the user typed is theirs
            updates["title"] = _entry_title(self._area_mode, self._city)
        self.hass.config_entries.async_update_entry(entry, **updates)
        self._update_favourite_registry(entry)
        return self.async_create_entry(data=self._options(entry.options))

    @callback
    def _update_favourite_registry(self, entry) -> None:
        """Disable favourite sensors archived by this change; re-enable a favourite that becomes active again."""
        from .sensor import _sensor_unique_id  # noqa: PLC0415 - sensor imports the coordinator stack

        registry = er.async_get(self.hass)
        before = {
            (fuel, record.get("identity"), bool(record.get("legacy")))
            for fuel, records in entry.options.get(CONF_HOME_HISTORY, {}).items()
            for record in records
        }

        def entity_id(fuel: str, identity: str | None) -> str | None:
            unique_id = _sensor_unique_id(entry.entry_id, fuel, "home", identity)
            return registry.async_get_entity_id("sensor", DOMAIN, unique_id)

        active = {
            entity_id(fuel, self._home_identities.get(fuel))
            for fuel in self._homes
            if fuel in self._fuels
        }
        for fuel, records in self._home_history.items():
            for record in records:
                identity, legacy = record.get("identity"), bool(record.get("legacy"))
                if (fuel, identity, legacy) in before:
                    continue
                archived = entity_id(fuel, None if legacy else identity)
                if archived and archived not in active:
                    registry.async_update_entity(archived, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
        for entity in filter(None, active):
            registry_entry = registry.async_get(entity)
            if registry_entry and registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
                registry.async_update_entity(entity, disabled_by=None)
