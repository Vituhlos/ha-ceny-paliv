"""The Czech region (kraj) of a point, from the simplified boundaries in regions.json (script/build_regions.py)."""
from __future__ import annotations

import json
import math
import pathlib
from functools import lru_cache
from typing import Any

# within this distance of a simplified border a point outside every region still belongs to the nearest one
_NEAR_BORDER_KM = 2.0

Ring = list[tuple[float, float]]


class _Region:
    __slots__ = ("code", "name", "polygons", "bbox")

    def __init__(self, data: dict[str, Any]) -> None:
        self.code: str = data["code"]
        self.name: str = data["name"]
        self.polygons: list[list[Ring]] = [
            [[(float(lat), float(lng)) for lat, lng in ring] for ring in polygon] for polygon in data["polygons"]
        ]
        points = [point for polygon in self.polygons for point in polygon[0]]
        self.bbox = (
            min(lat for lat, _ in points),
            max(lat for lat, _ in points),
            min(lng for _, lng in points),
            max(lng for _, lng in points),
        )

    def contains(self, lat: float, lng: float) -> bool:
        south, north, west, east = self.bbox
        if not (south <= lat <= north and west <= lng <= east):
            return False
        return any(
            _in_ring(polygon[0], lat, lng) and not any(_in_ring(hole, lat, lng) for hole in polygon[1:])
            for polygon in self.polygons
        )

    def distance_km(self, lat: float, lng: float) -> float:
        """Approximate distance to the nearest boundary point (enough for points a little outside)."""
        scale = math.cos(math.radians(lat))
        return 111.2 * min(
            math.hypot(lat - y, (lng - x) * scale) for polygon in self.polygons for ring in polygon for y, x in ring
        )


def _in_ring(ring: Ring, lat: float, lng: float) -> bool:
    inside = False
    y1, x1 = ring[-1]
    for y2, x2 in ring:
        if (y1 > lat) != (y2 > lat) and lng < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
        y1, x1 = y2, x2
    return inside


def _load() -> list[_Region]:
    data = json.loads((pathlib.Path(__file__).parent / "regions.json").read_text(encoding="utf-8"))
    return [_Region(region) for region in data["regions"]]


_REGIONS = _load()  # read once on import, which Home Assistant runs outside the event loop
REGION_NAMES = {region.code: region.name for region in _REGIONS}


@lru_cache(maxsize=8192)
def region_of(lat: float, lng: float) -> str | None:
    """The NUTS 3 code of the region (for example CZ010 for Prague), or None outside the Czech Republic."""
    for region in _REGIONS:
        if region.contains(lat, lng):
            return region.code
    # a point in a sliver between two simplified borders: the nearest region, if any is close
    margin = _NEAR_BORDER_KM / 70  # degrees, generous for both latitude and longitude
    distances = [
        (region.distance_km(lat, lng), region.code)
        for region in _REGIONS
        if region.bbox[0] - margin <= lat <= region.bbox[1] + margin
        and region.bbox[2] - margin <= lng <= region.bbox[3] + margin
    ]
    distance, code = min(distances, default=(math.inf, None))
    return code if distance <= _NEAR_BORDER_KM else None
