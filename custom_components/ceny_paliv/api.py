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


def station_options(markers: list[dict[str, Any]], city: str) -> list[dict[str, str]]:
    """Stations of one city selling the fuel, for a select box."""
    out = []
    for m in markers:
        if city_of(m) != city:
            continue
        slug = station_slug(m)
        out.append({"value": slug, "label": station_title(m["name"], pretty(slug))})
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
    in_city = [m for m in markers if city_of(m) == city]

    cutoff = (today - dt.timedelta(days=HISTORY_DAYS)).isoformat()
    for m in in_city:
        slug = station_slug(m)
        log = [e for e in history.get(slug, []) if e[0] >= cutoff]
        sample_date = sample_day.isoformat()
        if not log or sample_date >= log[-1][0]:
            log = [e for e in log if e[0] != sample_date]
            log.append([sample_date, m["price"]])
        history[slug] = log

    def entry(m: dict[str, Any], d: dt.date | None, rank: int | None) -> dict[str, Any]:
        slug = station_slug(m)
        log = history.get(slug, [])
        return {
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
            "home": bool(home_slug) and slug == home_slug,
            "trends": {str(n): _trend(log, m["price"], today, n) for n in PERIODS},
        }

    kept: list[tuple[dict[str, Any], dt.date]] = []
    excluded = 0
    for m in in_city:
        d = parse_fresh(m.get("fresh"), sample_day)
        if d is None or (today - d).days > max_age:
            excluded += 1
            continue
        kept.append((m, d))
    kept.sort(key=lambda t: t[0]["price"])
    stations = [entry(m, d, i + 1) for i, (m, d) in enumerate(kept[:TOP])]

    home = None
    if home_slug:
        for m in in_city:
            if station_slug(m) != home_slug:
                continue
            d = parse_fresh(m.get("fresh"), sample_day)
            pos = next((i + 1 for i, (k, _) in enumerate(kept) if station_slug(k) == home_slug), None)
            home = entry(m, d, pos)
            home["age_days"] = (today - d).days if d else None
            home["fresh_count"] = len(kept)
            if kept:
                home["cheapest_name"] = kept[0][0]["name"]
                home["vs_cheapest"] = round(m["price"] - kept[0][0]["price"], 2)
            break

    stamp = fetched_stamp.isoformat(timespec="seconds")
    return {
        "stations": stations,
        "home": home,
        "fetched_at": stamp,
        "last_attempt": now.isoformat(timespec="seconds"),
        "fetch_error": None,
        "city_total": len(in_city),
        "excluded": excluded,
        "max_age_days": max_age,
        "fuel": fuel,
        "fuel_label": label,
        "unit": unit,
        "city_name": pretty(city),
        "language": language,
        "labels": LABELS.get(language, LABELS[DEFAULT_LANGUAGE]),
        "next_update": (now + UPDATE_INTERVAL).isoformat(timespec="seconds"),
    }
