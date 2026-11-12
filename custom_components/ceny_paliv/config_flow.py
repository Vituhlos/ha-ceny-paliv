"""Config flow: key -> city -> fuels -> favourite station for each fuel."""
from __future__ import annotations

import math
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
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
    CannotConnect,
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
    CONF_KEY,
    CONF_LOCATION,
    CONF_LOCATION_METHOD,
    CONF_LANGUAGE,
    CONF_LOGOS,
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
    NONE_VALUE,
)
from .geography import MAX_RADIUS_KM, MIN_RADIUS_KM
from .logos import async_fetch_index, async_sync, chains_in, installed_ids, logo_dir


def _error_key(err: MBenzinError) -> str:
    if isinstance(err, InvalidAuth):
        return "invalid_auth"
    if isinstance(err, RateLimited):
        return "rate_limited"
    return "cannot_connect"


def _valid_coordinates(latitude: Any, longitude: Any) -> bool:
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        return False
    try:
        lat, lng = float(latitude), float(longitude)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180


class _FuelStationSteps:
    """Shared by the config flow and the options flow: choose fuels, then a favourite station per fuel."""

    _key: str
    _city: str
    _fuels: list[str]
    _language: str
    _queue: list[str]
    _homes: dict[str, str]
    _stations: dict[str, list[dict[str, str]]]
    _defaults_fuels: list[str] = DEFAULT_FUELS
    _defaults_language: str | None = None
    _defaults_homes: dict[str, str] = {}
    _defaults_logos: list[str] | None = None
    _area_mode: str
    _location_method: str
    _gps_location: dict[str, float] | None
    _gps_zone_entity: str | None
    _gps_radius_km: float
    _cities: list[dict[str, str]]
    _chains: set[str]
    _logos: list[str] | None = None

    async def async_step_fuels(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            fuels = user_input[CONF_FUELS]
            if not fuels:
                errors[CONF_FUELS] = "no_fuel"
            else:
                session = async_get_clientsession(self.hass)
                stations: dict[str, list[dict[str, str]]] = {}
                chains: set[str] = set()
                try:
                    for fuel in fuels:
                        markers = await async_fetch_markers(
                            session, self._key, fuel, cache=shared_marker_cache(self.hass)
                        )
                        gps = self._area_mode == AREA_MODE_GPS
                        stations[fuel] = station_options(
                            markers,
                            None if gps else self._city,
                            use_url=gps,
                        )
                        chains |= {
                            m.get("chain") or m["name"]
                            for m in markers
                            if gps or city_of(m) == self._city
                        }
                except MBenzinError as err:
                    errors["base"] = _error_key(err)
                else:
                    self._fuels, self._stations, self._chains = fuels, stations, chains
                    self._language = user_input[CONF_LANGUAGE]
                    self._queue, self._homes = list(fuels), {}
                    return await self.async_step_station()
        schema = vol.Schema(
            {
                vol.Required(CONF_FUELS, default=self._defaults_fuels): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": k, "label": v[0]} for k, v in FUELS.items()],
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_LANGUAGE, default=self._default_language()): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": k, "label": v} for k, v in LANGUAGES.items()],
                        mode=SelectSelectorMode.DROPDOWN,
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

    def _localized_options(self, values: dict[str, tuple[str, str]]) -> list[dict[str, str]]:
        language = (self.hass.config.language or DEFAULT_LANGUAGE).split("-")[0]
        return [
            {"value": value, "label": labels[1 if language == "cs" else 0]}
            for value, labels in values.items()
        ]

    async def async_step_area_mode(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._area_mode = user_input[CONF_AREA_MODE]
            if self._area_mode == AREA_MODE_CITY:
                if not getattr(self, "_cities", None):
                    self._cities = city_options(
                        await async_fetch_markers(
                            async_get_clientsession(self.hass),
                            self._key,
                            "n95",
                            cache=shared_marker_cache(self.hass),
                        )
                    )
                return await self.async_step_city()
            self._gps_config_unique_id = f"gps-{uuid4()}"
            return await self.async_step_location_method()

        schema = vol.Schema(
            {
                vol.Required(CONF_AREA_MODE, default=getattr(self, "_defaults_area_mode", AREA_MODE_CITY)):
                    SelectSelector(
                        SelectSelectorConfig(
                            options=self._localized_options(
                                {
                                    AREA_MODE_CITY: ("City", "Město"),
                                    AREA_MODE_GPS: ("GPS area", "GPS okolí"),
                                }
                            ),
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
            }
        )
        return self.async_show_form(step_id="area_mode", data_schema=schema)

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
                        options=self._localized_options(
                            {
                                LOCATION_HOME: ("Home location", "Poloha domácnosti"),
                                LOCATION_ZONE: ("Saved Home Assistant zone", "Uložená zóna Home Assistantu"),
                                LOCATION_MAP: ("Choose a point on the map", "Vybrat bod na mapě"),
                                LOCATION_MANUAL: ("Manual coordinates (advanced)", "Ruční souřadnice (pokročilé)"),
                            }
                        ),
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
                        min=-90, max=90, step=0.000001, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_LONGITUDE,
                    default=default_location[CONF_LONGITUDE],
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=-180, max=180, step=0.000001, mode=NumberSelectorMode.BOX
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
            if choice != NONE_VALUE:
                self._homes[fuel] = choice
            self._queue.pop(0)
            if self._queue:
                return await self.async_step_station()
            return await self.async_step_logos()
        options = [{"value": NONE_VALUE, "label": "—"}] + self._stations[fuel]
        valid = {o["value"] for o in options}
        default = self._defaults_homes.get(fuel, NONE_VALUE)
        if default not in valid and default != NONE_VALUE:
            options.append(
                {
                    "value": default,
                    "label": (
                        "Saved station (not resolved)"
                        if self._default_language() != "cs"
                        else "Uložená stanice (neověřená)"
                    ),
                }
            )
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


class CenyPalivConfigFlow(_FuelStationSteps, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _cities: list[dict[str, str]]

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_KEY].strip()
            try:
                markers = await async_fetch_markers(
                    async_get_clientsession(self.hass),
                    key,
                    "n95",
                    cache=shared_marker_cache(self.hass),
                )
            except MBenzinError as err:
                errors["base"] = _error_key(err)
            else:
                self._key = key
                self._cities = city_options(markers)
                return await self.async_step_area_mode()
        schema = vol.Schema(
            {vol.Required(CONF_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_city(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._city = user_input[CONF_CITY]
            if not getattr(self, "_options_flow", False):
                await self.async_set_unique_id(self._city)
                self._abort_if_unique_id_configured()
            return await self.async_step_fuels()
        schema = vol.Schema(
            {
                vol.Required(CONF_CITY): SelectSelector(
                    SelectSelectorConfig(options=self._cities, mode=SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="city", data_schema=schema)

    async def _async_finish(self) -> ConfigFlowResult:
        if self._area_mode == AREA_MODE_GPS:
            await self.async_set_unique_id(self._gps_config_unique_id)
        return self.async_create_entry(
            title=(
                f"Ceny paliv {pretty(self._city)}"
                if self._area_mode == AREA_MODE_CITY
                else "Ceny paliv GPS area"
            ),
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
        self._defaults_fuels = list(entry.options.get(CONF_FUELS, DEFAULT_FUELS))
        self._defaults_homes = dict(entry.options.get(CONF_HOMES, {}))
        self._defaults_language = entry.options.get(CONF_LANGUAGE)
        self._defaults_logos = entry.options.get(CONF_LOGOS)
        self._defaults_area_mode = entry.options.get(CONF_AREA_MODE, AREA_MODE_CITY)
        self._defaults_location_method = entry.options.get(CONF_LOCATION_METHOD, LOCATION_HOME)
        self._defaults_gps_location = entry.options.get(CONF_LOCATION)
        self._defaults_zone_entity = entry.options.get(CONF_ZONE_ENTITY)
        self._defaults_gps_radius_km = entry.options.get(
            CONF_GPS_RADIUS_KM, DEFAULT_GPS_RADIUS_KM
        )
        self._cities = city_options(
            await async_fetch_markers(
                async_get_clientsession(self.hass),
                self._key,
                "n95",
                cache=shared_marker_cache(self.hass),
            )
        )
        return await self.async_step_area_mode()

    def _own_entry_id(self) -> str | None:
        return self.config_entry.entry_id

    async def _async_finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._options(self.config_entry.options))
