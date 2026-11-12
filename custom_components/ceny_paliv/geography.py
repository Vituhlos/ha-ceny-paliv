"""Reusable geographic filtering for mBenzin station markers."""
from __future__ import annotations

import math
from numbers import Real
from typing import Any

EARTH_RADIUS_KM = 6371.0088
MIN_RADIUS_KM = 5
MAX_RADIUS_KM = 50
_BOUNDARY_TOLERANCE_KM = 1e-9


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


def _station_key(station: dict[str, Any]) -> tuple[str, ...]:
    """Stable tie-breakers without treating a slug as a station identifier."""
    return tuple(
        str(station.get(field) or "")
        for field in ("url", "city", "name", "address", "lat", "lng")
    )


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

    Invalid marker coordinates are skipped. The returned marker dictionaries are
    copies with an additional ``distance_km`` field; source freshness fields are
    left intact.
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
        distance = distance_km(center_lat, center_lng, *coordinates)
        if distance <= radius or math.isclose(
            distance, radius, rel_tol=0.0, abs_tol=_BOUNDARY_TOLERANCE_KM
        ):
            station = dict(marker)
            station["distance_km"] = distance
            stations.append(station)

    return sorted(stations, key=lambda station: (station["distance_km"], _station_key(station)))


def cheapest_stations_within_radius(
    markers: list[dict[str, Any]],
    latitude: Any,
    longitude: Any,
    radius_km: Any = 5,
) -> list[dict[str, Any]]:
    """Return area stations ordered by price, then distance and stable fields."""
    stations = [
        station
        for station in stations_within_radius(markers, latitude, longitude, radius_km)
        if _price(station) is not None
    ]
    return sorted(
        stations,
        key=lambda station: (
            _price(station),
            station["distance_km"],
            _station_key(station),
        ),
    )


def nearest_stations_within_radius(
    markers: list[dict[str, Any]],
    latitude: Any,
    longitude: Any,
    radius_km: Any = 5,
) -> list[dict[str, Any]]:
    """Return area stations ordered by distance, then price and stable fields."""
    stations = stations_within_radius(markers, latitude, longitude, radius_km)
    return sorted(
        stations,
        key=lambda station: (
            station["distance_km"],
            _price(station) if _price(station) is not None else math.inf,
            _station_key(station),
        ),
    )
