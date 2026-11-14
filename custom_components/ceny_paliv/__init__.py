"""Ceny paliv: Czech fuel prices (data from mBenzin.cz)."""
from __future__ import annotations

from pathlib import Path

from aiohttp import web

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .api import release_shared_marker_cache
from .const import AREA_MODE_CITY, CARD_URL, CARD_VERSION, CONF_AREA_MODE, CONF_CITY, DOMAIN, LOGO_URL
from .coordinator import CenyPalivConfigEntry, CenyPalivCoordinator, location_issue_id, no_data_issue_id
from .logos import ID_RE, logo_dir
from .services import async_setup_services

PLATFORMS = ["sensor"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)  # set up in the UI only


class CenyPalivCardView(HomeAssistantView):
    """Serves the card with `Cache-Control: no-cache`: the browser always revalidates, so it never keeps a stale
    copy (Home Assistant's own pages carry no cache headers, so an old page may still point to an old URL)."""

    url = CARD_URL
    name = "ceny_paliv:card"
    requires_auth = False

    def __init__(self, path: Path) -> None:
        self._path = path

    async def get(self, request: web.Request) -> web.StreamResponse:
        return web.FileResponse(self._path, headers={"Cache-Control": "no-cache"})


class CenyPalivLogoView(HomeAssistantView):
    """Serves the downloaded chain logos (<config>/ceny_paliv_logos/<id>.png). No auth: the browser loads them in <img>."""

    url = LOGO_URL + "/{logo_id}.png"
    name = "ceny_paliv:logo"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request, logo_id: str) -> web.StreamResponse:
        path = logo_dir(self._hass) / f"{logo_id}.png"
        if not ID_RE.match(logo_id) or not await self._hass.async_add_executor_job(path.is_file):
            return web.Response(status=404)
        return web.FileResponse(path, headers={"Cache-Control": "no-cache"})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card (custom:ceny-paliv-card) and load it in the frontend."""
    card = Path(__file__).parent / "frontend" / "ceny-paliv-card.js"
    hass.http.register_view(CenyPalivCardView(card))
    hass.http.register_view(CenyPalivLogoView(hass))
    add_extra_js_url(hass, f"{CARD_URL}?v={CARD_VERSION}")
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: CenyPalivConfigEntry) -> bool:
    """Upgrade an entry written by an older version; Home Assistant updates the entities and the device itself."""
    if entry.version > 1:
        return False  # written by a newer version of the integration: do not guess
    if entry.minor_version < 2:
        # 0.5 kept every dash of a town as a space ("Ceny paliv Brandys nad Labem   Stara Boleslav"); since 0.6 the
        # area's device is named after the entry. A title the user typed is left as it is.
        from .config_flow import _entry_title  # noqa: PLC0415 - the flow imports the coordinator stack

        automatic = _entry_title(
            entry.options.get(CONF_AREA_MODE, AREA_MODE_CITY),
            entry.options.get(CONF_CITY, entry.data.get(CONF_CITY, "")),
        )
        title = automatic if " ".join(entry.title.split()) == automatic else entry.title
        hass.config_entries.async_update_entry(entry, title=title, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CenyPalivConfigEntry) -> bool:
    coordinator = CenyPalivCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: CenyPalivConfigEntry) -> None:
    """Options changed (fuels / favourite stations): reload."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: CenyPalivConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not any(
        other.entry_id != entry.entry_id and other.state is ConfigEntryState.LOADED
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        release_shared_marker_cache(hass)  # no entry uses the nationwide snapshots any more
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: CenyPalivConfigEntry) -> None:
    """The entry is deleted: its price history and its Repairs issues go with it."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
    for issue_id in (no_data_issue_id(entry.entry_id), location_issue_id(entry.entry_id)):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
