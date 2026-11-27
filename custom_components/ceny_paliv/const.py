"""Constants for the Ceny paliv integration (data from mBenzin.cz)."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "ceny_paliv"

CARD_URL = "/ceny_paliv_static/ceny-paliv-card.js"
CARD_VERSION = "0.8.0"

# Optional station logos (pack in the GitHub repository, downloaded on request, see logos.py)
REGIONS_URL = "/ceny_paliv_static/regions.json"  # the region boundaries, for the regions card
LOGO_URL = "/ceny_paliv_static/logos"  # served from <config>/ceny_paliv_logos/
LOGO_DIR_NAME = "ceny_paliv_logos"
_PACK = "https://raw.githubusercontent.com/Vituhlos/ha-ceny-paliv/main/logos"
LOGO_INDEX_URL = f"{_PACK}/index.json"
LOGO_RAW_URL = _PACK + "/{id}.png"

CONF_KEY = "key"
CONF_CITY = "city"
CONF_AREA_MODE = "area_mode"
CONF_LOCATION_METHOD = "location_method"
CONF_LOCATION = "location"
CONF_ZONE_ENTITY = "zone_entity"
CONF_PERSON_ENTITY = "person_entity"  # person.* or device_tracker.* the GPS area follows
CONF_GPS_RADIUS_KM = "gps_radius_km"
AREA_MODE_CITY = "city"
AREA_MODE_GPS = "gps"
LOCATION_HOME = "home"
LOCATION_ZONE = "zone"
LOCATION_MAP = "map"
LOCATION_MANUAL = "manual"
LOCATION_PERSON = "person"
# a followed person must move this far before the area is computed again (from the shared download, no request)
PERSON_MOVE_KM = 1.0
DEFAULT_GPS_RADIUS_KM = 40
CONF_FUELS = "fuels"
CONF_HOMES = "homes"  # {fuel: station slug}
CONF_HOME_IDENTITIES = "home_identities"  # {fuel: exact station URL after an explicit favourite change}
CONF_HOME_HISTORY = "home_history"  # retired favourite sensor identities, retained to isolate HA statistics
CONF_LANGUAGE = "language"
CONF_STATION = "station"
CONF_LOGOS = "logos"  # logo ids ticked in the setup

NONE_VALUE = "__none__"

# sent with every request to mBenzin.cz (through aiombenzin) and to the logo pack
USER_AGENT = "HomeAssistant-ceny-paliv"

# fuel code -> (label, unit)
FUELS: dict[str, tuple[str, str]] = {
    "n95": ("Natural 95", "Kč/l"),
    "benzinplus": ("Natural 98", "Kč/l"),
    "diesel": ("Diesel", "Kč/l"),
    "dieselplus": ("Diesel Plus", "Kč/l"),
    "lpg": ("LPG", "Kč/l"),
    "cng": ("CNG", "Kč/kg"),
    "adblue": ("AdBlue", "Kč/l"),
}
DEFAULT_FUELS = ["n95"]

TOP = 5
# How old a price may be to be shown: 0 = today only, 1 = today + yesterday, ...
# LPG / CNG / AdBlue stations are updated less often, so they get a longer window.
MAX_AGE_DAYS_DEFAULT = 1
MAX_AGE_DAYS_BY_FUEL = {"lpg": 7, "cng": 3, "adblue": 7}
# The user may accept older prices (rural stations are updated less often); it never shortens a fuel's window.
CONF_MAX_AGE_DAYS = "max_age_days"
MAX_AGE_CHOICES = (1, 3, 7)
HISTORY_DAYS = 35
FLAT = 0.005  # |delta| below this = stable price
PERIODS = (1, 2, 7, 14, 30)  # trend windows in days

# Automatic refreshes remain six-hourly; no unconfirmed provider limit is assumed.
UPDATE_INTERVAL = timedelta(hours=6)
# Shared marker cache lifetime. It must expire before the next scheduled refresh: Home Assistant schedules
# that refresh from a whole-second loop time, so a cache living exactly UPDATE_INTERVAL would often serve the
# refresh its own six-hour-old snapshot and stretch the real refresh period to twelve hours.
MARKER_CACHE_TTL = UPDATE_INTERVAL - timedelta(minutes=10)
# A Repairs issue is raised when a fuel's prices have not been downloaded for this long (four missed refreshes).
STALE_DATA_AFTER = timedelta(hours=24)
# The refresh action downloads again only data older than this, so repeated calls cannot flood mBenzin.cz.
FORCED_REFRESH_MIN_AGE = timedelta(minutes=30)

MAPS = "https://www.google.com/maps/search/?api=1&query={lat},{lng}"

# Condition of the mBenzin.cz access key: show "Ceny: mbenzin.cz" visibly with the prices (as a link on the web).
SOURCE_URL = "https://www.mbenzin.cz"
ATTRIBUTION = "Ceny: mbenzin.cz"

LANGUAGES = {"en": "English", "cs": "Čeština"}
DEFAULT_LANGUAGE = "en"

# Texts used by the dashboard views (read from the `labels` attribute of sensor.ceny_paliv_<fuel>_top5).
# {placeholders} are filled in by the view.
LABELS: dict[str, dict[str, str]] = {
    "en": {
        "locale": "en-GB",
        "my_station": "My station",
        "updated_today": "Updated today",
        "updated_yesterday": "Updated yesterday",
        "price_from": "Price from {d} — may be outdated",
        "trends_start": "Trends start tomorrow (first daily record: today)",
        "since_partial": "* since {d} — history still filling",
        "not_ranked": "Not ranked — price too old",
        "cheapest_town": "Cheapest in town · #{rank} of {n} up-to-date stations",
        "cheapest_area": "Cheapest in the area · #{rank} of {n} up-to-date stations",
        "vs_cheapest": "+{d} vs cheapest ({name}) · #{rank} of {n}",
        "tap_history": "Tap for full history",
        "no_recent": "No recent prices",
        "cheapest_price": "Cheapest {p} {unit}",
        "stations_same": "{n} stations at this price",
        "today": "Today",
        "yesterday": "Yesterday",
        "today_l": "today",
        "yesterday_l": "yesterday",
        "days_l": "{n} days",
        "cheapest_badge": "Cheapest",
        "table_updated": "Table updated {t} · next refresh {n}",
        "stale": "mBenzin.cz cannot be reached — showing the last known prices",
        "hidden": "{h} of {t} stations hidden — price older than {age}",
        "arrows": "Arrows: price vs yesterday",
        "down": "down",
        "stable": "stable",
        "up": "up",
        "longpress": "long-press a row for your station history",
        "e10_note": "(E10 not distinguished)",
        "tap_station": "tap a station for details and navigation",
        "navigate": "Navigate",
        "close": "Close",
        "rank_of": "#{rank} of {n}",
        "more_than_cheapest": "+{d} vs the cheapest",
        "sort": "Order",
        "sort_price": "Price",
        "sort_distance": "Distance",
        "chains_limited": "Nationwide average · cheapest {n} of {total}",
        "sort_worth": "Worth it",
        "with_drive": "≈ {p} with the drive",
        "graph_title": "Prices over 30 days",
        "series_cheapest": "Cheapest in the area",
        "series_average": "Area average",
        "graph_empty": "No history yet: it fills up day by day.",
        "fuels_title": "Fuel prices",
        "mine_short": "mine {p}",
        "savings_title": "A full tank",
        "fill_up": "{n} {u} fill-up",
        "save_at": "At {name} you save {d} Kč",
        "mine_cheapest": "Your station is the cheapest",
        "save_vs_avg": "At {name} {d} Kč less than at the average price",
        "drive_extra": "{km} km more there and back ≈ {d} Kč",
        "worth_yes": "worth it: you still save {d} Kč",
        "worth_no": "not worth the drive",
        "compare_title": "Price comparison",
        "compare_sub": "average prices in {unit}, against the country",
        "compare_area": "Area",
        "compare_region": "Region",
        "compare_country": "Czech Republic",
        "compare_ranks": "The {n} regions, cheapest first",
        "regions_title": "Regions",
        "regions_sub": "average price by region; tap a region",
        "regions_loading": "Loading the map…",
        "regions_source": "Boundaries: ČÚZK",
        "map_title": "Stations",
        "map_sub": "{n} up-to-date prices; tap a station",
        "map_center": "Centre of the area",
        "areas_title": "Areas",
        "areas_sub": "the cheapest first",
        "road_title": "On the road",
        "road_gps_only": "Only a GPS area knows how far its stations are: choose one in the card editor.",
        "history_error": "Could not load history. Retrying…",
        "chains_title": "Chain ranking",
        "chains_sub": "Nationwide average price",
        "chain_count": "Stations: {n}",
        "chains_empty": "No current chain prices.",
        "chains_more": "Show {n} more",
        "changes_title": "What changed",
        "changes_empty": "No price changes in the last {n} days.",
        "ev_favourite_cheaper": "Your station got cheaper",
        "ev_favourite_dearer": "Your station got dearer",
        "ev_cheapest_cheaper": "A cheaper station in the area",
        "trend_title": "Price trend",
        "vs_yesterday": "vs yesterday",
        "source": "Ceny: mbenzin.cz",
    },
    "cs": {
        "locale": "cs-CZ",
        "my_station": "Moje stanice",
        "updated_today": "Aktualizováno dnes",
        "updated_yesterday": "Aktualizováno včera",
        "price_from": "Cena z {d} — může být zastaralá",
        "trends_start": "Trendy se objeví zítra (první denní záznam: dnes)",
        "since_partial": "* od {d} — historie se teprve plní",
        "not_ranked": "Mimo pořadí — příliš stará cena",
        "cheapest_town": "Nejlevnější ve městě · {rank}. z {n} aktuálních stanic",
        "cheapest_area": "Nejlevnější v okolí · {rank}. z {n} aktuálních stanic",
        "vs_cheapest": "+{d} oproti nejlevnější ({name}) · {rank}. z {n}",
        "tap_history": "Klepnutím zobrazíte celou historii",
        "no_recent": "Žádné aktuální ceny",
        "cheapest_price": "Nejlevnější {p} {unit}",
        "stations_same": "{n} stanic má tuto cenu",
        "today": "Dnes",
        "yesterday": "Včera",
        "today_l": "dnešek",
        "yesterday_l": "včerejšek",
        "days_l": "{n} dní",
        "cheapest_badge": "Nejlevnější",
        "table_updated": "Tabulka aktualizována {t} · další aktualizace {n}",
        "stale": "mBenzin.cz je nedostupný — zobrazeny poslední známé ceny",
        "hidden": "{h} z {t} stanic skryto — cena je starší než {age}",
        "arrows": "Šipky: cena oproti včerejšku",
        "down": "klesá",
        "stable": "beze změny",
        "up": "roste",
        "longpress": "dlouhým stisknutím řádku zobrazíte historii vaší stanice",
        "e10_note": "(E10 se nerozlišuje)",
        "tap_station": "klepnutím na stanici zobrazíte podrobnosti a navigaci",
        "navigate": "Navigovat",
        "close": "Zavřít",
        "rank_of": "{rank}. z {n}",
        "more_than_cheapest": "+{d} oproti nejlevnější",
        "sort": "Řazení",
        "sort_price": "Cena",
        "sort_distance": "Vzdálenost",
        "chains_limited": "Průměr v Česku · nejlevnějších {n} z {total}",
        "sort_worth": "Vyplatí se",
        "with_drive": "≈ {p} i s cestou",
        "graph_title": "Ceny za 30 dní",
        "series_cheapest": "Nejlevnější v oblasti",
        "series_average": "Průměr oblasti",
        "graph_empty": "Zatím bez historie: plní se den po dni.",
        "fuels_title": "Ceny paliv",
        "mine_short": "moje {p}",
        "savings_title": "Plná nádrž",
        "fill_up": "natankování {n} {u}",
        "save_at": "U {name} ušetříte {d} Kč",
        "mine_cheapest": "Vaše stanice je nejlevnější",
        "save_vs_avg": "U {name} o {d} Kč méně než za průměrnou cenu",
        "drive_extra": "o {km} km delší cesta tam a zpět ≈ {d} Kč",
        "worth_yes": "vyplatí se: i tak ušetříte {d} Kč",
        "worth_no": "nevyplatí se dojet",
        "compare_title": "Srovnání cen",
        "compare_sub": "průměrné ceny v {unit}, proti celé republice",
        "compare_area": "Oblast",
        "compare_region": "Kraj",
        "compare_country": "Česko",
        "compare_ranks": "{n} krajů od nejlevnějšího",
        "regions_title": "Kraje",
        "regions_sub": "průměrná cena podle krajů; klepněte na kraj",
        "regions_loading": "Načítám mapu…",
        "regions_source": "Hranice: ČÚZK",
        "map_title": "Stanice",
        "map_sub": "{n} aktuálních cen; klepněte na stanici",
        "map_center": "Střed oblasti",
        "areas_title": "Oblasti",
        "areas_sub": "od nejlevnější",
        "road_title": "Na cestě",
        "road_gps_only": "Vzdálenost stanic zná jen GPS oblast: vyberte ji v editoru karty.",
        "history_error": "Historii se nepodařilo načíst. Zkusím to znovu…",
        "chains_title": "Žebříček řetězců",
        "chains_sub": "Průměrná cena v Česku",
        "chain_count": "Počet stanic: {n}",
        "chains_empty": "Aktuální ceny řetězců nejsou k dispozici.",
        "chains_more": "Zobrazit další ({n})",
        "changes_title": "Co se změnilo",
        "changes_empty": "Za posledních {n} dní se ceny nezměnily.",
        "ev_favourite_cheaper": "Vaše stanice zlevnila",
        "ev_favourite_dearer": "Vaše stanice zdražila",
        "ev_cheapest_cheaper": "Levnější stanice v oblasti",
        "trend_title": "Vývoj ceny",
        "vs_yesterday": "oproti včerejšku",
        "source": "Ceny: mbenzin.cz",
    },
}
