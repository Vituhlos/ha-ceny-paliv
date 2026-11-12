"""Reusable geographic filtering for mBenzin station markers."""
from __future__ import annotations

import json
import math
from numbers import Real
from typing import Any

EARTH_RADIUS_KM = 6371.0088
MIN_RADIUS_KM = 5
MAX_RADIUS_KM = 50


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as err:
        raise ValueError(f"{name} must be a finite number") from err
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _coordinates(latitude: Any, longitude: Any, name: str) -> tuple[float, float]:
    lat = _finite_number(latitude, f"{name} latitude")
    lng = _finite_number(longitude, f"{name} longitude")
    if not -90 <= lat <= 90:
        raise ValueError(f"{name} latitude must be between -90 and 90")
    if not -180 <= lng <= 180:
        raise ValueError(f"{name} longitude must be between -180 and 180")
    return lat, lng


def distance_km(latitude1: Any, longitude1: Any, latitude2: Any, longitude2: Any) -> float:
    """Return great-circle distance between two GPS coordinates using Haversine."""
    lat1, lng1 = _coordinates(latitude1, longitude1, "first")
    lat2, lng2 = _coordinates(latitude2, longitude2, "second")
    return _distance_km_validated(lat1, lng1, lat2, lng2)


def _distance_km_validated(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = lat2_rad - lat1_rad
    delta_lng = math.radians(lng2 - lng1)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, haversine)))


def _marker_coordinates(marker: dict[str, Any]) -> tuple[float, float] | None:
    try:
        return _coordinates(marker.get("lat"), marker.get("lng"), "station")
    except ValueError:
        return None


def _station_key(station: dict[str, Any]) -> str:
    """Canonical sort-only key for JSON markers; never an identity or dedupe key."""
    try:
        return json.dumps(
            station,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    except (TypeError, ValueError, RecursionError):
        # A non-JSON value in an otherwise usable marker must not break sorting.
        sortable_fields = ("url", "name", "chain", "price", "fresh", "lat", "lng")
        scalar_types = (type(None), bool, int, float, str)
        sortable = {
            key: station[key]
            for key in sortable_fields
            if key in station and isinstance(station[key], scalar_types)
        }
        return json.dumps(sortable, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _price(station: dict[str, Any]) -> float | None:
    try:
        price = _finite_number(station.get("price"), "station price")
    except ValueError:
        return None
    return price if price >= 0 else None


def stations_within_radius(
    markers: list[dict[str, Any]],
    latitude: Any,
    longitude: Any,
    radius_km: Any = 5,
) -> list[dict[str, Any]]:
    """Return valid station markers within the inclusive 5–50 km radius.

    Invalid marker coordinates and non-object entries are skipped. This function
    does not filter price age; callers must apply the integration's fuel-specific
    freshness policy before using its results for price decisions. Returned marker
    dictionaries are copies with ``distance_km`` added and source fields retained.
    """
    stations = _stations_within_radius(markers, latitude, longitude, radius_km)
    return sorted(stations, key=lambda station: (station["distance_km"], _station_key(station)))


def _stations_within_radius(
    markers: list[dict[str, Any]],
    latitude: Any,
    longitude: Any,
    radius_km: Any,
) -> list[dict[str, Any]]:
    """Validate inputs and return eligible station copies without sorting.

    The eight-ULP allowance only absorbs floating-point round-off at the boundary.
    """
    center_lat, center_lng = _coordinates(latitude, longitude, "center")
    radius = _finite_number(radius_km, "radius")
    if not MIN_RADIUS_KM <= radius <= MAX_RADIUS_KM:
        raise ValueError(f"radius must be between {MIN_RADIUS_KM} and {MAX_RADIUS_KM} km")

    stations: list[dict[str, Any]] = []
    for marker in markers:
        if not isinstance(marker, dict):
            continue
        coordinates = _marker_coordinates(marker)
        if coordinates is None:
            continue
        distance = _distance_km_validated(center_lat, center_lng, *coordinates)
        if distance <= radius or distance - radius <= 8 * math.ulp(radius):
            station = dict(marker)
            station["distance_km"] = distance
            stations.append(station)

    return stations


def cheapest_stations_within_radius(
    markers: list[dict[str, Any]],
    latitude: Any,
    longitude: Any,
    radius_km: Any = 5,
) -> list[dict[str, Any]]:
    """Return priced stations ordered by price, then distance and marker data.

    Invalid, negative, or non-finite prices are excluded. Zero remains valid to
    match the existing city payload's non-validating numeric price sort. Price
    freshness is not checked here; callers must apply the fuel-specific policy.
    """
    priced = [
        (price, station)
        for station in _stations_within_radius(markers, latitude, longitude, radius_km)
        if (price := _price(station)) is not None
    ]
    priced.sort(key=lambda item: (item[0], item[1]["distance_km"], _station_key(item[1])))
    return [station for _, station in priced]


def nearest_stations_within_radius(
    markers: list[dict[str, Any]],
    latitude: Any,
    longitude: Any,
    radius_km: Any = 5,
) -> list[dict[str, Any]]:
    """Return area stations by distance; invalid/missing prices sort last at ties.

    Stations are not excluded for missing prices because this is a proximity
    result. Price freshness is retained but not filtered by this spatial helper.
    """
    ordered: list[tuple[dict[str, Any], float | None]] = []
    for station in _stations_within_radius(markers, latitude, longitude, radius_km):
        price = _price(station)
        ordered.append((station, price))
    ordered.sort(
        key=lambda item: (
            item[0]["distance_km"],
            item[1] if item[1] is not None else math.inf,
            _station_key(item[0]),
        )
    )
    return [station for station, _ in ordered]
