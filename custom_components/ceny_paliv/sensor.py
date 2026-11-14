"""Sensors: top-5 summary, favourite station and 5 map positions, per fuel.

Entity ids are suggested for new installs (the dashboard card finds the sensors by their cp_* attributes):
  sensor.ceny_paliv_<fuel>_top5   cheapest price, all details in attributes
  sensor.ceny_paliv_<fuel>_home   price at your favourite station (if one is chosen)
  sensor.ceny_paliv_<fuel>_1 .. 5 the 5 cheapest stations, with latitude/longitude for the map card

Names come from the translations (entity.sensor.<translation_key>) under the area's device; the station a sensor
currently describes is in its `station` attribute.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FUELS, TOP
from .coordinator import CenyPalivConfigEntry
from .entity import CenyPalivEntity

# the coordinator does all the fetching; entities only read its data
PARALLEL_UPDATES = 0

TOP_ATTRIBUTES = (
    "stations",
    "home",
    "gps_area",
    "gps_nearest_stations",
    "fetched_at",
    "last_attempt",
    "fetch_error",
    "city_total",
    "excluded",
    "max_age_days",
    "fuel",
    "fuel_label",
    "unit",
    "city_name",
    "language",
    "labels",
    "next_update",
    "logos",
)
HOME_ATTRIBUTES = (
    "updated",
    "updated_date",
    "age_days",
    "rank",
    "fresh_count",
    "vs_cheapest",
    "cheapest_name",
    "trends",
    "maps",
    "distance_km",
)


async def async_setup_entry(hass: HomeAssistant, entry: CenyPalivConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    _async_remove_unconfigured_fuels(hass, entry, coordinator.fuels)
    entities: list[CenyPalivSensor] = []
    for fuel in coordinator.fuels:
        entities.append(CenyPalivTop5Sensor(coordinator, entry, fuel))
        if coordinator.homes.get(fuel):
            home = CenyPalivHomeSensor(coordinator, entry, fuel)
            _async_enable_active_favourite(hass, home.unique_id)
            entities.append(home)
        existing_ids = {entity.unique_id for entity in entities}
        for record in coordinator.home_history.get(fuel, []):
            archived = CenyPalivArchivedHomeSensor(
                coordinator,
                entry,
                fuel,
                str(record.get("identity", "unknown")),
                bool(record.get("legacy")),
            )
            if archived.unique_id not in existing_ids:
                entities.append(archived)
                existing_ids.add(archived.unique_id)
        entities.extend(CenyPalivPositionSensor(coordinator, entry, fuel, i) for i in range(TOP))
    async_add_entities(entities)


@callback
def _async_remove_unconfigured_fuels(hass: HomeAssistant, entry: CenyPalivConfigEntry, fuels: list[str]) -> None:
    """A fuel removed in Configure takes its sensors (archived favourites too) instead of leaving them unavailable."""
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        # unique ids are <entry id>_<fuel>_<suffix>[_<station digest>] (entity.py); fuel codes have no "_"
        if registered.unique_id.startswith(prefix) and registered.unique_id[len(prefix):].split("_")[0] not in fuels:
            registry.async_remove(registered.entity_id)


@callback
def _async_enable_active_favourite(hass: HomeAssistant, unique_id: str) -> None:
    """A favourite chosen again reuses its archived sensor, which the integration had switched off."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    registered = registry.async_get(entity_id) if entity_id else None
    if registered and registered.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
        registry.async_update_entity(entity_id, disabled_by=None)


class CenyPalivSensor(CenyPalivEntity, SensorEntity):
    """A price sensor: the unit follows the fuel (Kč/l, CNG in Kč/kg)."""

    def __init__(self, coordinator, entry, fuel, suffix, *, identity=None) -> None:
        super().__init__(coordinator, entry, fuel, suffix, identity=identity)
        self._attr_native_unit_of_measurement = FUELS.get(fuel, (fuel, "Kč/l"))[1]


class CenyPalivTop5Sensor(CenyPalivSensor):
    _attr_translation_key = "cheapest"
    # read by the card from the live state; recording them every refresh only fills the database
    _unrecorded_attributes = frozenset(
        {"stations", "home", "gps_area", "gps_nearest_stations", "labels", "logos"}
    )

    def __init__(self, coordinator, entry, fuel) -> None:
        super().__init__(coordinator, entry, fuel, "top5")

    @property
    def native_value(self) -> float | None:
        stations = self._payload.get("stations") or []
        return stations[0]["price"] if stations else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {k: self._payload.get(k) for k in TOP_ATTRIBUTES}
        attrs.update(cp_fuel=self._fuel, cp_role="top5", cp_config_id=self._entry_id)
        return attrs


class CenyPalivHomeSensor(CenyPalivSensor):
    """Favourite station. state_class=measurement -> long-term statistics (the 30-day graph)."""

    _attr_translation_key = "favourite"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"trends", "maps"})

    def __init__(self, coordinator, entry, fuel) -> None:
        super().__init__(
            coordinator,
            entry,
            fuel,
            "home",
            identity=coordinator.home_identities.get(fuel),
        )

    @property
    def _home(self) -> dict[str, Any] | None:
        return self._payload.get("home")

    @property
    def available(self) -> bool:
        return super().available and self._home is not None

    @property
    def native_value(self) -> float | None:
        return self._home["price"] if self._home else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        home = self._home or {}
        # price: the bare number for the map marker, which is too narrow for the state with its unit
        attrs = {"station": home.get("title"), "price": home.get("price"), "latitude": home.get("lat"), "longitude": home.get("lng")}
        attrs.update({k: home.get(k) for k in HOME_ATTRIBUTES})
        attrs.update(cp_fuel=self._fuel, cp_role="home", cp_config_id=self._entry_id)
        return attrs


class CenyPalivArchivedHomeSensor(CenyPalivSensor):
    """Keep retired favourite sensor identities registered without mixing station statistics."""

    _attr_translation_key = "archived_favourite"
    # it only keeps the statistics of a former favourite: out of the dashboards, and off when first registered
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, fuel: str, identity: str, legacy: bool) -> None:
        super().__init__(
            coordinator,
            entry,
            fuel,
            "home",
            identity=None if legacy else identity,
        )
        self._identity = identity

    @property
    def available(self) -> bool:
        return False

    @property
    def native_value(self) -> None:
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "cp_fuel": self._fuel,
            "cp_role": "home_archive",
            "cp_config_id": self._entry_id,
            "archived_station_identity": self._identity,
        }


class CenyPalivPositionSensor(CenyPalivSensor):
    """The n-th cheapest station. Has latitude/longitude so the map card can show it."""

    _attr_translation_key = "position"

    def __init__(self, coordinator, entry, fuel, index: int) -> None:
        super().__init__(coordinator, entry, fuel, str(index + 1))
        self._index = index
        self._attr_translation_placeholders = {**self._attr_translation_placeholders, "position": str(index + 1)}

    @property
    def _station(self) -> dict[str, Any] | None:
        stations = self._payload.get("stations") or []
        return stations[self._index] if len(stations) > self._index else None

    # No `available` override: a position without a station is "unknown", not "unavailable", because
    # Home Assistant drops the attributes of unavailable entities and the card needs cp_* to bind it.

    @property
    def native_value(self) -> float | None:
        return self._station["price"] if self._station else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._station
        attrs: dict[str, Any] = {
            "cp_fuel": self._fuel,
            "cp_role": "position",
            "cp_index": self._index + 1,
            "cp_config_id": self._entry_id,
        }
        if s:
            # the favourite station is drawn by its own sensor on the map: no coordinates here
            attrs.update(
                station=s["title"],  # 'VS Petrol · Obory'
                price=s["price"],  # the map marker label (the state with its unit does not fit)
                latitude=None if s["home"] else s["lat"],
                longitude=None if s["home"] else s["lng"],
            )
        return attrs

