"""Price-change events per fuel: the favourite station got cheaper or dearer, the area's cheapest price dropped.

One entity per fuel, `event.ceny_paliv_<fuel>_price_change`, compares each refresh with the one before; its entity id
stays the same when another favourite station is chosen, so automations and blueprints keep working.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import CenyPalivConfigEntry, CenyPalivCoordinator
from .entity import CenyPalivEntity

# the coordinator does all the fetching; entities only read its data
PARALLEL_UPDATES = 0

FAVOURITE_CHEAPER = "favourite_cheaper"
FAVOURITE_DEARER = "favourite_dearer"
CHEAPEST_CHEAPER = "cheapest_cheaper"


async def async_setup_entry(hass: HomeAssistant, entry: CenyPalivConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(CenyPalivPriceChangeEvent(coordinator, entry, fuel) for fuel in coordinator.fuels)


def _station(data: dict[str, Any] | None) -> tuple[str, float] | None:
    """Who and how much, to compare two refreshes: the station URL (or title) and the price."""
    if not data or data.get("price") is None:
        return None
    return str(data.get("url") or data.get("title")), float(data["price"])


class CenyPalivPriceChangeEvent(CenyPalivEntity, EventEntity):
    _attr_translation_key = "price_change"
    _attr_event_types = [FAVOURITE_CHEAPER, FAVOURITE_DEARER, CHEAPEST_CHEAPER]

    def __init__(self, coordinator: CenyPalivCoordinator, entry: CenyPalivConfigEntry, fuel: str) -> None:
        super().__init__(coordinator, entry, fuel, "price_change")
        self.entity_id = f"event.ceny_paliv_{fuel}_price_change"
        self._attr_extra_state_attributes = {"cp_config_id": entry.entry_id, "cp_fuel": fuel, "cp_role": "price_change"}
        self._favourite: tuple[str, float] | None = None
        self._cheapest: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # the prices at start-up are the baseline: a restart never reports a change by itself
        self._remember(self._payload)

    def _remember(self, payload: dict[str, Any]) -> None:
        self._favourite = _station(payload.get("home"))
        stations = payload.get("stations") or []
        self._cheapest = float(stations[0]["price"]) if stations else None

    @callback
    def _handle_coordinator_update(self) -> None:
        payload = self._payload
        if not payload or payload.get("fetch_error"):
            super()._handle_coordinator_update()  # last known prices: nothing new to compare
            return
        favourite, cheapest = self._favourite, self._cheapest
        self._remember(payload)
        common = {"fuel": payload.get("fuel_label"), "unit": payload.get("unit"), "area": payload.get("city_name")}

        home = payload.get("home")
        now = _station(home)
        # the same station as before (another favourite chosen in the meantime is not a price change)
        if home and now and favourite and now[0] == favourite[0] and now[1] != favourite[1]:
            self._fire(
                FAVOURITE_CHEAPER if now[1] < favourite[1] else FAVOURITE_DEARER,
                home,
                previous=favourite[1],
                common=common,
            )
        stations = payload.get("stations") or []
        if stations and cheapest is not None and float(stations[0]["price"]) < cheapest:
            self._fire(CHEAPEST_CHEAPER, stations[0], previous=cheapest, common=common)
        super()._handle_coordinator_update()

    def _fire(self, event_type: str, station: dict[str, Any], *, previous: float, common: dict[str, Any]) -> None:
        price = float(station["price"])
        self._trigger_event(
            event_type,
            {
                **common,
                "station": station.get("title"),
                "address": station.get("address"),
                "price": price,
                "previous_price": previous,
                "change": round(price - previous, 2),
                "distance_km": station.get("distance_km"),
                "maps": station.get("maps"),
            },
        )
        self.async_write_ha_state()  # one state per event: two events in one refresh are both seen
