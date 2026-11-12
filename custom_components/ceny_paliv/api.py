"""mBenzin.cz price-map client and data processing."""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import math
import re
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from numbers import Real
from typing import Any, Callable
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_LANGUAGE,
    DOMAIN,
    FLAT,
    FUELS,
    HISTORY_DAYS,
    LABELS,
    MAPS,
    MAX_AGE_DAYS_BY_FUEL,
    MAX_AGE_DAYS_DEFAULT,
    PERIODS,
    TOP,
    UPDATE_INTERVAL,
    URL,
    USER_AGENT,
)
from .geography import (
    cheapest_stations_within_radius,
    distance_km,
    nearest_stations_within_radius,
)

_CZECH_TIMEZONE = ZoneInfo("Europe/Prague")


class MBenzinError(Exception):
    """Base error."""


class CannotConnect(MBenzinError):
    """The site cannot be reached."""


class InvalidAuth(MBenzinError):
    """The access key is missing, wrong or not accepted."""


class RateLimited(MBenzinError):
    """HTTP 429: the provider is temporarily limiting requests."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__()
        self.retry_after = retry_after


def _now_prague() -> dt.datetime:
    return dt.datetime.now(_CZECH_TIMEZONE)


def _retry_after_seconds(value: str | None, now: dt.datetime | None = None) -> float | None:
    """Parse a valid Retry-After header as a non-negative delay."""
    if not value:
        return None
    value = value.strip()
    if value.isdecimal():
        try:
            delay = float(int(value))
        except (OverflowError, ValueError):
            return None
        return delay if math.isfinite(delay) else None
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=dt.timezone.utc)
        current = now or dt.datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - current.astimezone(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


async def _async_fetch_markers(
    session: aiohttp.ClientSession,
    key: str,
    fuel: str,
    clock: Callable[[], dt.datetime] = _now_prague,
) -> list[dict[str, Any]]:
    """Download the price-map markers of one fuel (all of the Czech Republic)."""
    try:
        async with session.get(
            URL,
            params={"fuel": fuel, "ccs": "0"},
            headers={"User-Agent": USER_AGENT, "X-Mbenzin-Klic": key},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 429:
                now = clock()
                if now.tzinfo is None:
                    now = now.replace(tzinfo=_CZECH_TIMEZONE)
                raise RateLimited(_retry_after_seconds(resp.headers.get("Retry-After"), now))
            if resp.status in (401, 403):
                raise InvalidAuth
            if resp.status != 200:
                raise CannotConnect(f"HTTP {resp.status}")
            try:
                data = await resp.json(content_type=None)
            except ValueError:  # an HTML "browser check" page = key not accepted
                data = None
    except (aiohttp.ClientError, TimeoutError) as err:
        error_name = type(err).__name__
    else:
        error_name = None
    if error_name is not None:
        raise CannotConnect(error_name)
    markers = data.get("markers") if isinstance(data, dict) else None
    if not isinstance(markers, list):
        raise InvalidAuth
    return markers


@dataclass
class MarkerSnapshot:
    """Unmodified nationwide markers and the instant the response was received."""

    markers: list[dict[str, Any]]
    fetched_at: dt.datetime


@dataclass
class _MarkerCacheEntry:
    expires_at: float
    snapshot: MarkerSnapshot | None = None


def _consume_task_exception(task: asyncio.Task[Any]) -> None:
    """Prevent abandoned single-flight tasks from emitting unhandled exceptions."""
    if not task.cancelled():
        task.exception()


class SharedMarkerCache:
    """Short-lived, bounded cache shared across this HA instance's config entries."""

    def __init__(
        self,
        max_entries: int,
        ttl: dt.timedelta = UPDATE_INTERVAL,
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
        self, session: aiohttp.ClientSession, key: str, fuel: str
    ) -> MarkerSnapshot:
        """Return cached data or join the single flight, enforcing key-wide 429 cooldowns."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        cache_key = (key_hash, fuel)
        async with self._lock:
            now = self._monotonic()
            self._prune(now)
            entry = self._entries.get(cache_key)
            if entry is not None:
                self._entries.move_to_end(cache_key)
                assert entry.snapshot is not None
                return deepcopy(entry.snapshot)

            backoff_until = self._key_backoffs.get(key_hash)
            if backoff_until is not None and backoff_until > now:
                raise RateLimited(backoff_until - now)

            task = self._inflight.get(cache_key)
            if task is None:
                task = asyncio.create_task(self._async_load(key_hash, cache_key, session, key, fuel))
                task.add_done_callback(_consume_task_exception)
                self._inflight[cache_key] = task

        return deepcopy(await asyncio.shield(task))

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
                raise RateLimited(err.retry_after)
            raise type(err)(*err.args)
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
) -> MarkerSnapshot:
    """Fetch markers with their actual response time for date-safe processing."""
    if cache is not None:
        return await cache.async_get_snapshot(session, key, fuel)
    markers = await _async_fetch_markers(session, key, fuel)
    return MarkerSnapshot(markers=markers, fetched_at=_now_prague())


def city_of(marker: dict[str, Any]) -> str | None:
    """City slug of a marker: /Ceny-benzinu-a-nafty/<City>/<Station>/<id>."""
    parts = marker.get("url", "").split("/")
    return parts[2] if len(parts) >= 5 else None


def station_slug(marker: dict[str, Any]) -> str:
    return marker["url"].split("/")[3]


def _safe_station_slug(marker: dict[str, Any]) -> str | None:
    try:
        return station_slug(marker)
    except (KeyError, IndexError, AttributeError):
        return None


def _usable_gps_marker(marker: dict[str, Any]) -> bool:
    if _safe_station_slug(marker) is None or not isinstance(marker.get("name"), str):
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
    return slug.replace("-", " ")


def street_of(name: str, address: str) -> str:
    """The address text without the leading station name ('Bratri Stefanu 69')."""
    if address.lower().startswith(name.lower()):
        return address[len(name):].strip()
    return address


def station_title(name: str, address: str) -> str:
    """'Orlen – Bratri Stefanu 69' from the station name and its address text."""
    street = street_of(name, address)
    return f"{name} – {street}" if street else name


def city_options(markers: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Cities that have at least one station, for a select box."""
    slugs = {c for m in markers if (c := city_of(m))}
    return [{"value": s, "label": pretty(s)} for s in sorted(slugs, key=str.casefold)]


def station_options(
    markers: list[dict[str, Any]],
    city: str | None,
    *,
    use_url: bool = False,
) -> list[dict[str, str]]:
    """Stations of one city selling the fuel, for a select box."""
    out = []
    for m in markers:
        if city is not None and city_of(m) != city:
            continue
        slug = station_slug(m)
        out.append(
            {
                "value": m["url"] if use_url else slug,
                "label": station_title(m["name"], pretty(slug)),
            }
        )
    return sorted(out, key=lambda o: o["label"].casefold())


def parse_fresh(value: str | None, today: dt.date) -> dt.date | None:
    """mBenzin 'fresh' field -> date. Returns None when the format is unknown."""
    raw = (value or "").strip()
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
    if m:
        return today - dt.timedelta(days=int(m.group(1)))
    return None


def _trend(log: list[list], price: float, today: dt.date, days: int) -> dict[str, Any] | None:
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


def build_payload(
    markers: list[dict[str, Any]],
    *,
    fuel: str,
    city: str,
    home_slug: str | None,
    history: dict[str, list[list]],
    now: dt.datetime,
    language: str = DEFAULT_LANGUAGE,
    fetched_at: dt.datetime | None = None,
    gps_method: str | None = None,
    gps_center: tuple[float, float] | None = None,
    gps_radius_km: float = 40,
    gps_zone_entity: str | None = None,
    gps_error: str | None = None,
) -> dict[str, Any]:
    """Top stations of the city + the favourite station, with trends.

    `history` ({station slug: [[date, price], ...]}) is updated in place with today's prices.
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
    max_age = MAX_AGE_DAYS_BY_FUEL.get(fuel, MAX_AGE_DAYS_DEFAULT)
    gps_mode = gps_method is not None
    in_city = [m for m in markers if city_of(m) == city] if not gps_mode else []
    in_region = (
        cheapest_stations_within_radius(markers, *gps_center, gps_radius_km)
        if gps_mode and gps_center is not None
        else []
    )
    region_markers = (
        [marker for marker in in_region if _usable_gps_marker(marker)]
        if gps_mode
        else []
    )
    candidate_markers = region_markers if gps_mode else in_city

    def history_key(marker: dict[str, Any]) -> str:
        return str(marker.get("url") or station_slug(marker)) if gps_mode else station_slug(marker)

    home_matches: list[dict[str, Any]] = []
    if home_slug:
        if gps_mode and "/" in home_slug:
            home_matches = [
                m for m in markers
                if isinstance(m, dict) and m.get("url") == home_slug and _usable_gps_marker(m)
            ]
        elif gps_mode:
            home_matches = [
                m for m in markers
                if isinstance(m, dict)
                and _safe_station_slug(m) == home_slug
                and _usable_gps_marker(m)
            ]
            if len(home_matches) != 1:
                home_matches = []
        else:
            home_matches = [
                m for m in markers
                if isinstance(m, dict)
                and city_of(m) == city
                and (m.get("url") == home_slug or _safe_station_slug(m) == home_slug)
            ]
        if len(home_matches) > 1:
            home_matches = []
    home_marker = home_matches[0] if home_matches else None

    cutoff = (today - dt.timedelta(days=HISTORY_DAYS)).isoformat()
    history_markers = list(candidate_markers)
    if gps_mode and home_marker is not None and home_marker not in history_markers:
        history_markers.append(home_marker)
    for m in history_markers:
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
        data = {
            "rank": rank,
            "name": m["name"],
            "chain": m.get("chain") or m["name"],
            "address": pretty(slug),
            "street": street_of(m["name"], pretty(slug)),
            "price": m["price"],
            "lat": m["lat"],
            "lng": m["lng"],
            "updated": m.get("fresh"),
            "updated_date": d.isoformat() if d else None,
            "maps": MAPS.format(lat=m["lat"], lng=m["lng"]),
            "home": (
                bool(home_marker) and m.get("url") == home_marker.get("url")
                if gps_mode
                else bool(home_slug)
                and (station_slug(m) == home_slug or m.get("url") == home_slug)
            ),
            "trends": {str(n): _trend(log, m["price"], today, n) for n in PERIODS},
        }
        if "distance_km" in m:
            data["distance_km"] = m["distance_km"]
        return data

    kept: list[tuple[dict[str, Any], dt.date]] = []
    excluded = 0
    for m in candidate_markers:
        d = parse_fresh(m.get("fresh"), sample_day)
        age_days = max(0, (today - d).days) if d is not None else None
        if age_days is None or age_days > max_age:
            excluded += 1
            continue
        kept.append((m, d))
    kept.sort(
        key=lambda t: (
            t[0]["price"],
            t[0].get("distance_km", 0),
        )
    )
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
                home["cheapest_name"] = kept[0][0]["name"]
                home["vs_cheapest"] = round(m["price"] - kept[0][0]["price"], 2)
        elif gps_mode:
            d = parse_fresh(m.get("fresh"), sample_day)
            home = entry(m, d, None)
            home["age_days"] = max(0, (today - d).days) if d else None
            home["fresh_count"] = len(kept)
            if kept:
                home["cheapest_name"] = kept[0][0]["name"]
                home["vs_cheapest"] = round(m["price"] - kept[0][0]["price"], 2)

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
        "next_update": (now + UPDATE_INTERVAL).isoformat(timespec="seconds"),
    }
    if not gps_mode:
        result["city_total"] = len(in_city)
    else:
        nearest = nearest_stations_within_radius(
            [m for m, _ in kept], *gps_center, gps_radius_km
        ) if gps_center is not None else []
        nearest_dates = {history_key(m): d for m, d in kept}
        result["gps_nearest_stations"] = [
            entry(m, nearest_dates.get(history_key(m)), index)
            for index, m in enumerate(nearest, start=1)
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
