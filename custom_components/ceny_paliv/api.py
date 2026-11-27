"""Processing of the mBenzin.cz price map; the download itself is the aiombenzin library."""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import math
import re
from collections import Counter, OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import timezone
from numbers import Real
from statistics import median
from typing import Any, Callable
import unicodedata
from zoneinfo import ZoneInfo

import aiohttp
import aiombenzin
from aiombenzin import CannotConnect, InvalidAuth, MBenzinError, RateLimited

from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_LANGUAGE,
    DOMAIN,
    FLAT,
    FUELS,
    HISTORY_DAYS,
    LABELS,
    MAPS,
    MARKER_CACHE_TTL,
    MAX_AGE_DAYS_BY_FUEL,
    MAX_AGE_DAYS_DEFAULT,
    PERIODS,
    TOP,
    UPDATE_INTERVAL,
    USER_AGENT,
)
from .geography import (
    distance_km,
    nearest_stations_within_radius,
    stations_within_radius,
)
from .regions import REGION_NAMES, region_of

_CZECH_TIMEZONE = ZoneInfo("Europe/Prague")
_GPS_NEAREST_LIMIT = 10
_MAX_ATTRIBUTE_TEXT = 120
_MAX_RANKED_CHAINS = 100  # cap the live sensor attribute even when each station reports a distinct name


def _now_prague() -> dt.datetime:
    return dt.datetime.now(_CZECH_TIMEZONE)


def next_update_at(now: dt.datetime) -> dt.datetime:
    """`now` + the refresh interval in elapsed time (correct across DST changes), in now's timezone."""
    if now.tzinfo is None:
        return now + UPDATE_INTERVAL
    return (now.astimezone(timezone.utc) + UPDATE_INTERVAL).astimezone(now.tzinfo)


async def _async_fetch_markers(
    session: aiohttp.ClientSession,
    key: str,
    fuel: str,
    clock: Callable[[], dt.datetime] = _now_prague,
) -> list[dict[str, Any]]:
    """Download the price-map markers of one fuel (all of the Czech Republic) through aiombenzin."""
    return await aiombenzin.async_fetch_markers(session, key, fuel, user_agent=USER_AGENT, clock=clock)


@dataclass
class MarkerSnapshot:
    """Unmodified nationwide markers and the instant the response was received."""

    markers: list[dict[str, Any]]
    fetched_at: dt.datetime


@dataclass
class _MarkerCacheEntry:
    expires_at: float
    snapshot: MarkerSnapshot
    loaded_at: float = 0.0


def _consume_task_exception(task: asyncio.Task[Any]) -> None:
    """Prevent abandoned single-flight tasks from emitting unhandled exceptions."""
    if not task.cancelled():
        task.exception()


class SharedMarkerCache:
    """Short-lived, bounded cache shared across this HA instance's config entries."""

    def __init__(
        self,
        max_entries: int,
        ttl: dt.timedelta = MARKER_CACHE_TTL,
        clock: Callable[[], dt.datetime] = _now_prague,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.max_entries = max(1, max_entries)
        self.ttl = ttl.total_seconds()
        self._entries: OrderedDict[tuple[str, str], _MarkerCacheEntry] = OrderedDict()
        self._inflight: dict[tuple[str, str], asyncio.Task[MarkerSnapshot]] = {}
        self._key_backoffs: dict[str, float] = {}
        self._clock = clock
        self._monotonic = monotonic or (lambda: asyncio.get_running_loop().time())
        self._lock = asyncio.Lock()

    async def async_get_snapshot(
        self,
        session: aiohttp.ClientSession,
        key: str,
        fuel: str,
        *,
        max_age: dt.timedelta | None = None,
    ) -> MarkerSnapshot:
        """Return cached data or join the single flight, enforcing key-wide 429 cooldowns.

        With max_age, cached data older than that is downloaded again (the refresh action). If that download
        cannot be made (no connection, 429 cooldown), the cached data is returned: it is still within its lifetime.
        """
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        cache_key = (key_hash, fuel)
        async with self._lock:
            now = self._monotonic()
            self._prune(now)
            entry = self._entries.get(cache_key)
            if entry is not None and (max_age is None or now - entry.loaded_at <= max_age.total_seconds()):
                self._entries.move_to_end(cache_key)
                assert entry.snapshot is not None
                return deepcopy(entry.snapshot)

            backoff_until = self._key_backoffs.get(key_hash)
            if backoff_until is not None and backoff_until > now:
                if entry is not None:
                    return deepcopy(entry.snapshot)
                raise RateLimited(backoff_until - now)

            task = self._inflight.get(cache_key)
            if task is None:
                task = asyncio.create_task(self._async_load(key_hash, cache_key, session, key, fuel))
                task.add_done_callback(_consume_task_exception)
                self._inflight[cache_key] = task

        try:
            return deepcopy(await asyncio.shield(task))
        except (CannotConnect, RateLimited):
            if entry is None:  # entry is only kept here for a download forced by max_age
                raise
            return deepcopy(entry.snapshot)

    async def async_get(
        self, session: aiohttp.ClientSession, key: str, fuel: str
    ) -> list[dict[str, Any]]:
        """Compatibility API returning a copy of the marker list."""
        return (await self.async_get_snapshot(session, key, fuel)).markers

    async def _async_load(
        self,
        key_hash: str,
        cache_key: tuple[str, str],
        session: aiohttp.ClientSession,
        key: str,
        fuel: str,
    ) -> MarkerSnapshot:
        try:
            markers = await _async_fetch_markers(session, key, fuel, self._clock)
        except MBenzinError as err:
            if isinstance(err, RateLimited):
                delay = err.retry_after if err.retry_after is not None else self.ttl
                async with self._lock:
                    proposed_until = self._monotonic() + delay
                    self._key_backoffs[key_hash] = max(
                        proposed_until, self._key_backoffs.get(key_hash, proposed_until)
                    )
                # fresh errors for every waiter, deliberately not chained to the shared one
                raise RateLimited(err.retry_after) from None
            if isinstance(err, InvalidAuth):
                raise InvalidAuth(*err.args, definite=err.definite) from None
            raise type(err)(*err.args) from None
        else:
            fetched_at = self._clock()
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=_CZECH_TIMEZONE)
            else:
                fetched_at = fetched_at.astimezone(_CZECH_TIMEZONE)
            snapshot = MarkerSnapshot(markers=deepcopy(markers), fetched_at=fetched_at)
            async with self._lock:
                backoff_until = self._key_backoffs.get(key_hash)
                now = self._monotonic()
                if backoff_until is not None and backoff_until > now:
                    raise RateLimited(backoff_until - now)
                self._entries[cache_key] = _MarkerCacheEntry(
                    now + self.ttl,
                    snapshot=snapshot,
                    loaded_at=now,
                )
                self._entries.move_to_end(cache_key)
                self._trim()
            return snapshot
        finally:
            async with self._lock:
                self._inflight.pop(cache_key, None)

    def _prune(self, now: float) -> None:
        for cache_key, entry in tuple(self._entries.items()):
            if entry.expires_at <= now:
                self._entries.pop(cache_key, None)
        for key_hash, backoff_until in tuple(self._key_backoffs.items()):
            if backoff_until <= now:
                self._key_backoffs.pop(key_hash, None)

    def _trim(self) -> None:
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)


_SHARED_CACHE_KEY = f"{DOMAIN}_shared_marker_cache"


def shared_marker_cache(hass: HomeAssistant) -> SharedMarkerCache:
    """Return the cache shared by this HA instance; a restart naturally starts empty."""
    cache = hass.data.get(_SHARED_CACHE_KEY)
    if cache is None:
        cache = SharedMarkerCache(max_entries=len(FUELS))
        hass.data[_SHARED_CACHE_KEY] = cache
    entry_count = len(hass.config_entries.async_entries(DOMAIN))
    cache.max_entries = max(1, (entry_count + 1) * len(FUELS))
    cache._trim()
    return cache


def release_shared_marker_cache(hass: HomeAssistant) -> None:
    """Drop the shared snapshots (and any cooldown) once no entry is loaded."""
    hass.data.pop(_SHARED_CACHE_KEY, None)


async def async_fetch_markers(
    session: aiohttp.ClientSession,
    key: str,
    fuel: str,
    *,
    cache: SharedMarkerCache | None = None,
) -> list[dict[str, Any]]:
    """Fetch markers, optionally sharing cached and in-flight results."""
    if cache is not None:
        return await cache.async_get(session, key, fuel)
    return await _async_fetch_markers(session, key, fuel)


async def async_fetch_snapshot(
    session: aiohttp.ClientSession,
    key: str,
    fuel: str,
    *,
    cache: SharedMarkerCache | None = None,
    max_age: dt.timedelta | None = None,
) -> MarkerSnapshot:
    """Fetch markers with their actual response time for date-safe processing."""
    if cache is not None:
        return await cache.async_get_snapshot(session, key, fuel, max_age=max_age)
    markers = await _async_fetch_markers(session, key, fuel)
    return MarkerSnapshot(markers=markers, fetched_at=_now_prague())


def city_of(marker: dict[str, Any]) -> str | None:
    """City slug of a marker: /Ceny-benzinu-a-nafty/<City>/<Station>/<id>."""
    if not isinstance(marker, dict):
        return None
    url = marker.get("url")
    if not isinstance(url, str):
        return None
    parts = url.split("/")
    return parts[2] if len(parts) >= 5 and parts[1] == "Ceny-benzinu-a-nafty" and parts[2] else None


def station_slug(marker: dict[str, Any]) -> str:
    url = marker.get("url")
    if not isinstance(url, str):
        raise ValueError("marker URL is missing")
    parts = url.split("/")
    if (
        len(parts) < 5
        or parts[1] != "Ceny-benzinu-a-nafty"
        or not parts[2]
        or not parts[3]
        or not parts[4]
    ):
        raise ValueError("marker URL is invalid")
    return parts[3]


def _safe_station_slug(marker: dict[str, Any]) -> str | None:
    try:
        return station_slug(marker)
    except (KeyError, IndexError, AttributeError, ValueError):
        return None


def _usable_marker(marker: dict[str, Any]) -> bool:
    """A marker with a station URL, a name, a finite non-negative price and valid coordinates.

    One malformed marker must never abort the refresh of every fuel, so City and GPS mode both skip it.
    """
    if (
        not isinstance(marker, dict)
        or _safe_station_slug(marker) is None
        or not isinstance(marker.get("name"), str)
        or not marker["name"].strip()
    ):
        return False
    try:
        price = marker["price"]
        if (
            isinstance(price, bool)
            or not isinstance(price, Real)
            or not math.isfinite(float(price))
            or float(price) < 0
        ):
            return False
        distance_km(marker.get("lat"), marker.get("lng"), marker.get("lat"), marker.get("lng"))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return True


def pretty(slug: str) -> str:
    """Dashes are spaces, and a run of them is one: 'Brandys-nad-Labem---Stara-Boleslav' -> one space each."""
    return " ".join(slug.replace("-", " ").split())


def _fold(text: str) -> str:
    """Compare text the way mBenzin's URLs spell it: no accents, no case ('Miličín' == 'Milicin')."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()


def street_of(name: str, address: str) -> str:
    """The address without the station name in front of it: mBenzin's URLs repeat the name, without accents.

    'Am oil Miličín' + 'Am oil Milicin parkoviste' -> 'parkoviste'; 'Davo-oil' + 'Davo oil' -> ''.
    """
    words = address.split()
    name_words = re.findall(r"[^\W_]+", name)
    if name_words and len(words) >= len(name_words) and all(
        _fold(word.strip(".,-")) == _fold(part) for word, part in zip(words[: len(name_words)], name_words, strict=True)
    ):
        return " ".join(words[len(name_words):])
    return " ".join(words)


def _without_house_number(town: str) -> str:
    """'Bochov 213' -> 'Bochov': mBenzin puts the house number after the town.

    Word by word on purpose: the text comes from mBenzin, and a regular expression for this backtracks badly on a
    long run of numbers.
    """
    words = town.split()
    while len(words) > 1 and words[-1][:1].isdigit():
        words.pop()
    return " ".join(words) or town


def street_and_town(marker: dict[str, Any]) -> tuple[str, str]:
    """The station's street and town, with accents from mBenzin's `addr` ('Selbská 15/2732, Aš') when it has one.

    Without `addr` both come from the station's link, which has no accents ('Selbska 15/2732', 'As'). The town
    never carries a house number. A village without streets is addressed by its name and number ('Lhota 12'):
    that is its street, and the village its town.
    """
    name = marker["name"] if isinstance(marker.get("name"), str) else ""
    slug_town = pretty(city_of(marker) or "")
    town = _without_house_number(slug_town)
    addr = marker.get("addr")
    if not isinstance(addr, str) or not " ".join(addr.split()):
        return street_of(name, pretty(_safe_station_slug(marker) or "")), town
    parts = [" ".join(part.split()) for part in addr.split(",") if part.strip()]
    town_words = _fold(town).split()

    def is_town(part: str) -> bool:
        # whole words: 'Táborská 5' in Tábor is a street, 'Lhota 12' in Lhota is the village itself
        return bool(town_words) and _fold(part).split()[: len(town_words)] == town_words

    if len(parts) == 1:
        if is_town(parts[0]):
            village = _without_house_number(parts[0])
            # 'Lhota 12' is the address line of a village; 'Lhota' alone has no street at all
            return ("" if village == parts[0] else parts[0]), village
        return street_of(name, parts[0]), town
    # the town is the part that matches the town of the link, else the last one ('Pražská 310, Neveklov')
    index = next((i for i in range(1, len(parts)) if is_town(parts[i])), len(parts) - 1)
    return street_of(name, ", ".join(parts[:index])), _without_house_number(parts[index])


def station_title(name: str, street: str, city: str | None = None) -> str:
    """'Benzina · Karlovarská': the name, then the street, or the town when the station has no street."""
    place = street or city
    return f"{name} · {place}" if place else name


def city_options(markers: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Cities that have at least one station, for a select box."""
    slugs = {c for m in markers if (c := city_of(m))}
    return [{"value": s, "label": pretty(s)} for s in sorted(slugs, key=str.casefold)]


def station_options(
    markers: list[dict[str, Any]],
    city: str | None,
    *,
    use_url: bool = False,
    center: tuple[float, float] | None = None,
    radius_km: float = 40,
) -> list[dict[str, str]]:
    """Stations selling the fuel, optionally limited to a GPS circle."""
    out = []
    valid_markers = [
        marker
        for marker in markers
        if isinstance(marker, dict)
        and _safe_station_slug(marker) is not None
        and isinstance(marker.get("name"), str)
        and marker["name"].strip()
        and (use_url is False or _usable_marker(marker))
    ]
    if center is not None:
        try:
            valid_markers = stations_within_radius(
                valid_markers, *center, radius_km
            )
        except (TypeError, ValueError, OverflowError):
            valid_markers = []
    if city is not None:
        valid_markers = [m for m in valid_markers if city_of(m) == city]
    value_counts: dict[str, int] = {}
    for marker in valid_markers:
        value = marker["url"] if use_url else station_slug(marker)
        value_counts[value] = value_counts.get(value, 0) + 1
    for m in valid_markers:
        value = m["url"] if use_url else station_slug(m)
        if value_counts[value] != 1:
            continue
        street, town = street_and_town(m)
        label = station_title(m["name"], street, town)
        if use_url:
            station_id = m["url"].rstrip("/").rsplit("/", 1)[-1]
            label = (
                f"{_bounded_text(station_title(m['name'], street), 100)}"
                f" · {_bounded_text(town, 30)}"
                f" · {_bounded_text(station_id, 32)}"
            )
        out.append({"value": value, "label": label})
    return sorted(out, key=lambda o: o["label"].casefold())


def _bounded_text(value: Any, limit: int = _MAX_ATTRIBUTE_TEXT) -> str:
    """Keep provider-controlled text from dominating recorded sensor attributes."""
    text = value if isinstance(value, str) else str(value or "")
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def parse_fresh(value: str | None, today: dt.date) -> dt.date | None:
    """mBenzin 'fresh' field -> date. Returns None when the format is unknown."""
    raw = value.strip() if isinstance(value, str) else ""
    if len(raw) > 40:  # "před 3 dny" is short; a long text would make the search below slow, not right
        return None
    low = raw.lower()
    if low == "dnes":
        return today
    if low in ("včera", "vcera"):
        return today - dt.timedelta(days=1)
    m = re.match(r"^(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})$", raw)
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"(\d+)\s*d", low)  # e.g. "před 3 dny"
    if m and len(m.group(1)) <= 4:  # a longer number is not a real age (and would overflow the date)
        return today - dt.timedelta(days=int(m.group(1)))
    return None


def _trend(log: list[list[Any]], price: float, today: dt.date, days: int) -> dict[str, Any] | None:
    """Compare with the price `days` ago (or the oldest earlier record). None when no earlier record."""
    earlier = [(d, p) for d, p in log if d < today.isoformat()]
    if not earlier:
        return None
    target = (today - dt.timedelta(days=days)).isoformat()
    older = [e for e in earlier if e[0] <= target]
    ref_date, ref_price = older[-1] if older else earlier[0]
    delta = round(price - ref_price, 2)
    return {
        "dir": "flat" if abs(delta) < FLAT else ("up" if delta > 0 else "down"),
        "delta": delta,
        "ref_date": ref_date,
        "ref_price": ref_price,
    }


def warm_regions(markers: list[dict[str, Any]]) -> None:
    """Find every station's region once, in an executor job; build_payload then reads them from the cache."""
    for marker in markers:
        if _usable_marker(marker):
            region_of(marker["lat"], marker["lng"])


def _average(prices: list[float]) -> float | None:
    return round(sum(prices) / len(prices), 2) if prices else None


def _difference(value: float | None, reference: float | None) -> float | None:
    return round(value - reference, 2) if value is not None and reference is not None else None


def price_overview(
    fresh_markers: list[dict[str, Any]], area_prices: list[float], area_region: str | None
) -> dict[str, Any]:
    """The average price in the country and in each region, and how the area stands against them."""
    national = [marker["price"] for marker in fresh_markers]
    national_average = _average(national)
    by_region: dict[str, list[float]] = {}
    by_chain: dict[str, list[float]] = {}
    chain_names: dict[str, str] = {}
    for marker in fresh_markers:
        raw = marker.get("chain")
        name = " ".join((raw if isinstance(raw, str) and raw.strip() else marker["name"]).split())
        key = name.casefold()
        by_chain.setdefault(key, []).append(marker["price"])
        chain_names[key] = min(name, chain_names.get(key, name))
        if (code := region_of(marker["lat"], marker["lng"])) is not None:
            by_region.setdefault(code, []).append(marker["price"])
    regions: list[dict[str, Any]] = sorted(
        (
            {
                "code": code,
                "name": REGION_NAMES[code],
                "average": _average(prices),
                "station_count": len(prices),
                "vs_national": _difference(_average(prices), national_average),
            }
            for code, prices in by_region.items()
        ),
        key=lambda region: (region["average"], region["code"]),
    )
    for rank, region in enumerate(regions, start=1):
        region["rank"] = rank  # 1 = the cheapest region
    area_region_data: dict[str, Any] | None = next((region for region in regions if region["code"] == area_region), None)
    area_average = _average(area_prices)
    ranked_chains = sorted((sum(prices) / len(prices), key) for key, prices in by_chain.items())
    return {
        "national": {
            "average": national_average,
            "median": round(median(national), 2) if national else None,
            "station_count": len(national),
        },
        "chain_count": len(ranked_chains),
        "chains": [
            {"name": _bounded_text(chain_names[key], 64), "average": round(average, 2), "station_count": len(by_chain[key])}
            for average, key in ranked_chains[:_MAX_RANKED_CHAINS]
        ],
        "regions": regions,
        "region": area_region_data,
        "area": {
            "average": area_average,
            "station_count": len(area_prices),
            "vs_national": _difference(area_average, national_average),
            "vs_region": _difference(area_average, area_region_data["average"] if area_region_data else None),
        },
    }


def build_payload(
    markers: list[dict[str, Any]],
    *,
    fuel: str,
    city: str,
    home_slug: str | None,
    history: dict[str, list[list[Any]]],
    now: dt.datetime,
    language: str = DEFAULT_LANGUAGE,
    fetched_at: dt.datetime | None = None,
    gps_method: str | None = None,
    gps_center: tuple[float, float] | None = None,
    gps_radius_km: float = 40,
    gps_zone_entity: str | None = None,
    gps_error: str | None = None,
    legacy_city: str | None = None,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    """Top stations of the city + the favourite station, with trends.

    `history` ({station URL: [[date, price], ...]}) is updated in place. Versions up to 0.4.x keyed it by
    station slug; those logs were always written for `legacy_city` (the entry's original city), so while
    showing that city a slug log moves to the URL of the one station there with that slug. Ambiguous or
    unmatched slug logs are never assigned and expire with the 35-day window like any other log.
    """
    today = (
        now.astimezone(_CZECH_TIMEZONE).date()
        if now.tzinfo is not None
        else now.date()
    )
    if fetched_at is None:
        sample_day = today
        fetched_stamp = now
    else:
        source_time = fetched_at
        if source_time.tzinfo is None:
            source_time = source_time.replace(tzinfo=_CZECH_TIMEZONE)
        sample_day = source_time.astimezone(_CZECH_TIMEZONE).date()
        fetched_stamp = source_time
    label, unit = FUELS.get(fuel, (fuel, "Kč/l"))
    # the user's choice only widens the window: a fuel updated less often keeps its longer default
    max_age = max(MAX_AGE_DAYS_BY_FUEL.get(fuel, MAX_AGE_DAYS_DEFAULT), max_age_days or 0)
    gps_mode = gps_method is not None
    in_city = [m for m in markers if city_of(m) == city and _usable_marker(m)] if not gps_mode else []
    in_region = (
        stations_within_radius(markers, *gps_center, gps_radius_km)
        if gps_mode and gps_center is not None
        else []
    )
    region_markers = (
        [marker for marker in in_region if _usable_marker(marker)]
        if gps_mode
        else []
    )
    candidate_markers = region_markers if gps_mode else in_city

    def history_key(marker: dict[str, Any]) -> str:
        url = marker.get("url")
        return url if isinstance(url, str) else station_slug(marker)

    home_matches: list[dict[str, Any]] = []
    if home_slug:
        if gps_mode and "/" in home_slug:
            home_matches = [
                m for m in markers
                if isinstance(m, dict) and m.get("url") == home_slug and _usable_marker(m)
            ]
        elif gps_mode:
            # A bare slug is a favourite saved in City mode: it only identifies a station in that city.
            home_matches = [
                m for m in markers
                if isinstance(m, dict)
                and bool(city)
                and city_of(m) == city
                and _safe_station_slug(m) == home_slug
                and _usable_marker(m)
            ]
            if len(home_matches) != 1:
                home_matches = []
        else:
            home_matches = [
                m for m in markers
                if isinstance(m, dict)
                and city_of(m) == city
                and (m.get("url") == home_slug or _safe_station_slug(m) == home_slug)
                and _usable_marker(m)
            ]
        if len(home_matches) > 1:
            home_matches = []
    home_marker = home_matches[0] if home_matches else None

    cutoff = (today - dt.timedelta(days=HISTORY_DAYS)).isoformat()
    if not gps_mode and legacy_city and city == legacy_city:
        slug_counts: dict[str, int] = {}
        for m in in_city:
            if (slug := _safe_station_slug(m)) is not None:
                slug_counts[slug] = slug_counts.get(slug, 0) + 1
        for m in in_city:
            slug, url = _safe_station_slug(m), m.get("url")
            if slug is None or slug_counts[slug] != 1 or slug not in history or not isinstance(url, str):
                continue
            merged = {item[0]: item for item in history.pop(slug) if isinstance(item, (list, tuple)) and len(item) == 2}
            merged.update({item[0]: item for item in history.get(url, [])})
            history[url] = [list(merged[day]) for day in sorted(merged)]
    # Prune expired histories regardless of current area; retain inactive station samples until their
    # 35-day window expires (legacy slug logs included, so unassignable ones disappear in time).
    for key in list(history):
        if not isinstance(key, str):
            continue
        log = [
            item
            for item in history.get(key, [])
            if isinstance(item, (list, tuple))
            and len(item) == 2
            and isinstance(item[0], str)
            and item[0] >= cutoff
        ]
        if log:
            history[key] = log
        else:
            history.pop(key, None)
    if not gps_mode:
        for m in candidate_markers:
            key = history_key(m)
            log = [e for e in history.get(key, []) if e[0] >= cutoff]
            sample_date = sample_day.isoformat()
            if not log or sample_date >= log[-1][0]:
                log = [e for e in log if e[0] != sample_date]
                log.append([sample_date, m["price"]])
            history[key] = log

    def entry(m: dict[str, Any], d: dt.date | None, rank: int | None) -> dict[str, Any]:
        slug = _safe_station_slug(m) or ""
        log = history.get(history_key(m), [])
        display_text = _bounded_text if gps_mode else lambda value: value
        street, town = street_and_town(m)
        addr = m.get("addr")
        data = {
            "rank": rank,
            "name": display_text(m["name"]),
            "title": display_text(station_title(m["name"], street, town)),
            "chain": display_text(m.get("chain") or m["name"]),
            "address": display_text(" ".join(addr.split()) if isinstance(addr, str) and addr.strip() else pretty(slug)),
            "street": display_text(street),
            "city": display_text(town),
            "price": m["price"],
            "lat": m["lat"],
            "lng": m["lng"],
            "updated": (
                display_text(m["fresh"])
                if isinstance(m.get("fresh"), str)
                else m.get("fresh")
            ),
            "updated_date": d.isoformat() if d else None,
            "maps": MAPS.format(lat=m["lat"], lng=m["lng"]),
            "home": (
                home_marker is not None and m.get("url") == home_marker.get("url")
                if gps_mode
                else bool(home_slug)
                and (_safe_station_slug(m) == home_slug or m.get("url") == home_slug)
            ),
            "trends": {str(n): _trend(log, m["price"], today, n) for n in PERIODS},
        }
        if "distance_km" in m:
            data["distance_km"] = m["distance_km"]
        return data

    def fresh_date(m: dict[str, Any]) -> dt.date | None:
        """The day of the price, or None when it is unknown or older than the window."""
        d = parse_fresh(m.get("fresh"), sample_day)
        return d if d is not None and max(0, (today - d).days) <= max_age else None

    kept: list[tuple[dict[str, Any], dt.date]] = []
    excluded = 0
    for m in candidate_markers:
        if (d := fresh_date(m)) is None:
            excluded += 1
            continue
        kept.append((m, d))
    kept.sort(
        key=lambda t: (
            t[0]["price"],
            t[0].get("distance_km", 0),
        )
    )
    if gps_mode:
        retained: list[tuple[dict[str, Any], dt.date | None]] = list(kept[:TOP])
        if home_marker is not None and all(
            history_key(marker) != history_key(home_marker) for marker, _ in retained
        ):
            home_date = parse_fresh(home_marker.get("fresh"), sample_day)
            retained.append((home_marker, home_date))
        sample_date = sample_day.isoformat()
        for m, _ in retained:
            key = history_key(m)
            log = [e for e in history.get(key, []) if e[0] >= cutoff]
            if not log or sample_date >= log[-1][0]:
                log = [e for e in log if e[0] != sample_date]
                log.append([sample_date, m["price"]])
            history[key] = log
    stations = [entry(m, d, i + 1) for i, (m, d) in enumerate(kept[:TOP])]

    home = None
    if home_marker is not None:
        m = dict(home_marker)
        if gps_mode and gps_center is not None:
            m["distance_km"] = distance_km(
                *gps_center, m["lat"], m["lng"]
            )
        if not gps_mode or gps_center is None or any(
            candidate.get("url") == m.get("url") for candidate in in_region
        ):
            d = parse_fresh(m.get("fresh"), sample_day)
            pos = next(
                (i + 1 for i, (k, _) in enumerate(kept) if history_key(k) == history_key(m)),
                None,
            )
            home = entry(m, d, pos)
            home["age_days"] = max(0, (today - d).days) if d else None
            home["fresh_count"] = len(kept)
            if kept:
                home["cheapest_name"] = _bounded_text(kept[0][0]["name"]) if gps_mode else kept[0][0]["name"]
                home["vs_cheapest"] = round(m["price"] - kept[0][0]["price"], 2)
        elif gps_mode:
            d = parse_fresh(m.get("fresh"), sample_day)
            home = entry(m, d, None)
            home["age_days"] = max(0, (today - d).days) if d else None
            home["fresh_count"] = len(kept)
            if kept:
                home["cheapest_name"] = _bounded_text(kept[0][0]["name"]) if gps_mode else kept[0][0]["name"]
                home["vs_cheapest"] = round(m["price"] - kept[0][0]["price"], 2)
        if home is not None:
            home["url"] = m["url"]  # the station's identity, for its long-term statistics (statistics.py)

    if gps_mode:
        area_region = region_of(*gps_center) if gps_center is not None else None
    else:
        # a town lies in one region; the most common one only guards against a station placed across the border
        found = Counter(code for m in in_city if (code := region_of(m["lat"], m["lng"])) is not None)
        area_region = found.most_common(1)[0][0] if found else None
    overview = price_overview(
        [m for m in markers if _usable_marker(m) and fresh_date(m) is not None],
        [m["price"] for m, _ in kept],
        area_region,
    )

    stamp = fetched_stamp.isoformat(timespec="seconds")
    result = {
        "stations": stations,
        "home": home,
        "fetched_at": stamp,
        "last_attempt": now.isoformat(timespec="seconds"),
        "fetch_error": None,
        "excluded": excluded,
        "max_age_days": max_age,
        "fuel": fuel,
        "fuel_label": label,
        "unit": unit,
        "city_name": pretty(city) if not gps_mode else ("GPS area" if language != "cs" else "GPS okolí"),
        "language": language,
        "labels": LABELS.get(language, LABELS[DEFAULT_LANGUAGE]),
        "next_update": next_update_at(now).isoformat(timespec="seconds"),
        "overview": overview,
    }
    if not gps_mode:
        result["city_total"] = len(in_city)
    else:
        nearest = nearest_stations_within_radius(
            [m for m, _ in kept], *gps_center, gps_radius_km
        ) if gps_center is not None else []
        nearest_dates = {history_key(m): d for m, d in kept}
        result["gps_nearest_stations"] = [
            {
                "rank": index,
                "name": _bounded_text(m["name"]),
                "city": _bounded_text(street_and_town(m)[1]),
                "address": _bounded_text(
                    " ".join(m["addr"].split())
                    if isinstance(m.get("addr"), str) and m["addr"].strip()
                    else pretty(_safe_station_slug(m) or "")
                ),
                "price": m["price"],
                "lat": m["lat"],
                "lng": m["lng"],
                "updated": _bounded_text(m.get("fresh")),
                "updated_date": (
                    nearest_dates[history_key(m)].isoformat()
                    if history_key(m) in nearest_dates
                    else None
                ),
                "distance_km": m["distance_km"],
            }
            for index, m in enumerate(nearest[:_GPS_NEAREST_LIMIT], start=1)
        ]
        result["gps_area"] = {
            "method": gps_method,
            "latitude": gps_center[0] if gps_center is not None else None,
            "longitude": gps_center[1] if gps_center is not None else None,
            "radius_km": gps_radius_km,
            "zone_entity": gps_zone_entity,
            "error": gps_error,
            "station_count": len(region_markers),
        }
    return result
