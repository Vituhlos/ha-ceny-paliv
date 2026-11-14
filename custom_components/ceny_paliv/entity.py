"""Base entity of Ceny paliv: one fuel of one area, grouped under the area's service device."""
from __future__ import annotations

import hashlib
from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, FUELS, SOURCE_URL
from .coordinator import CenyPalivConfigEntry, CenyPalivCoordinator


class CenyPalivEntity(CoordinatorEntity[CenyPalivCoordinator]):
    """One fuel of one area (config entry)."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION  # shown by Home Assistant with the state (condition of the mBenzin key)

    def __init__(
        self,
        coordinator: CenyPalivCoordinator,
        entry: CenyPalivConfigEntry,
        fuel: str,
        suffix: str,
        *,
        identity: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._fuel = fuel
        self._entry_id = entry.entry_id
        self._attr_unique_id = _sensor_unique_id(entry.entry_id, fuel, suffix, identity)
        # suggestion for new installs; registered entities keep their ids (the unique id is unchanged)
        self.entity_id = f"sensor.ceny_paliv_{fuel}_{suffix}"
        self._attr_translation_placeholders = {"fuel": FUELS.get(fuel, (fuel,))[0]}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,  # "Ceny paliv Praha", "Ceny paliv GPS area" or the user's own title
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="mBenzin.cz",
            configuration_url=SOURCE_URL,
        )

    @property
    def available(self) -> bool:
        """Unavailable while mBenzin.cz cannot refresh this fuel (all fuels: the coordinator's own failure)."""
        return super().available and self._fuel not in self.coordinator.failed_fuels

    @property
    def _payload(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self._fuel) or {}


def _sensor_unique_id(
    entry_id: str, fuel: str, suffix: str, identity: str | None = None
) -> str:
    """Keep the original home ID until a station is explicitly changed."""
    unique_id = f"{entry_id}_{fuel}_{suffix}"
    if identity is not None and suffix == "home":
        digest = hashlib.sha256(identity.encode()).hexdigest()[:12]
        unique_id += f"_{digest}"
    return unique_id
