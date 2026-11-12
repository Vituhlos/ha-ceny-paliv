"""Regression tests for the mBenzin client and payload."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.ceny_paliv.geography import (
    EARTH_RADIUS_KM,
    cheapest_stations_within_radius,
    distance_km,
    nearest_stations_within_radius,
    stations_within_radius,
)
from custom_components.ceny_paliv.api import (
    CannotConnect,
    InvalidAuth,
    RateLimited,
    SharedMarkerCache,
    async_fetch_markers,
    build_payload,
    city_options,
    parse_fresh,
    shared_marker_cache,
    station_options,
)


def payload(markers, now, *, fuel="n95", home=None, history=None, city="Praha"):
    return build_payload(
        markers, fuel=fuel, city=city, home_slug=home,
        history=history if history is not None else {}, now=now, language="cs",
    )


def test_city_price_top_five_and_favourite_outside_top(marker, now):
    markers = [marker(f"Stanice-{i}", price) for i, price in enumerate([40, 35, 38, 34, 39, 36, 37])]
    markers.append(marker("Jine-mesto", 1, city="Brno"))
    result = payload(markers, now, home="Stanice-0")
    assert result["city_total"] == 7
    assert [s["price"] for s in result["stations"]] == [34, 35, 36, 37, 38]
    assert [s["rank"] for s in result["stations"]] == [1, 2, 3, 4, 5]
    assert result["home"]["rank"] == 7
    assert result["home"]["fresh_count"] == 7
    assert result["home"]["vs_cheapest"] == 6
    assert result["city_name"] == "Praha"
    assert result["labels"]["my_station"] == "Moje stanice"


def test_favourite_in_top_and_missing(marker, now):
    markers = [marker("Oblibena", 32), marker("Druha", 33)]
    result = payload(markers, now, home="Oblibena")
    assert result["stations"][0]["home"] is True
    assert result["home"]["rank"] == 1
    assert result["home"]["vs_cheapest"] == 0
    assert payload(markers, now, home="neznamy")["home"] is None
    assert payload([], now)["stations"] == []


@pytest.mark.parametrize(
    ("fuel", "fresh", "expected"),
    [
        ("n95", "Včera", True), ("n95", "před 2 dny", False),
        ("lpg", "před 7 dny", True), ("lpg", "před 8 dny", False),
        ("cng", "před 3 dny", True), ("cng", "před 4 dny", False),
        ("adblue", "před 7 dny", True), ("adblue", "před 8 dny", False),
        ("diesel", None, False),
    ],
)
def test_freshness_limits_and_stale_home(marker, now, fuel, fresh, expected):
    history = {}
    result = payload([marker("Oblibena", 35, fresh=fresh)], now, fuel=fuel, home="Oblibena", history=history)
    assert bool(result["stations"]) is expected
    assert result["excluded"] == int(not expected)
    assert result["home"]["rank"] == (1 if expected else None)
    assert history["Oblibena"] == [["2025-01-15", 35]]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Dnes", date(2025, 1, 15)), ("Včera", date(2025, 1, 14)),
        ("vcera", date(2025, 1, 14)), ("před 3 dny", date(2025, 1, 12)),
        ("2. 1. 2025", date(2025, 1, 2)), ("31. 2. 2025", None),
        ("neznámé", None), (None, None),
    ],
)
def test_parse_fresh(value, expected):
    assert parse_fresh(value, date(2025, 1, 15)) == expected


def test_history_pruning_replacement_and_trends(marker, now):
    history = {"Oblibena": [
        ["2024-12-10", 50], ["2024-12-11", 40], ["2025-01-08", 36],
        ["2025-01-14", 34], ["2025-01-15", 10],
    ]}
    result = payload([marker("Oblibena", 35)], now, home="Oblibena", history=history)
    assert history["Oblibena"] == [
        ["2024-12-11", 40], ["2025-01-08", 36], ["2025-01-14", 34], ["2025-01-15", 35],
    ]
    trends = result["home"]["trends"]
    assert trends["1"] == {"dir": "up", "delta": 1, "ref_date": "2025-01-14", "ref_price": 34}
    assert trends["7"]["dir"] == "down"
    assert trends["30"]["ref_date"] == "2024-12-11"
    payload([marker("Oblibena", 34)], now, history=history)
    assert history["Oblibena"][-1] == ["2025-01-15", 34]
    assert len(history["Oblibena"]) == 4
    assert payload([marker("Nova", 35)], now)["stations"][0]["trends"]["1"] is None


def test_options_filter_cities_and_stations(marker):
    markers = [marker("Shell-Jedna", 30, name="Shell"), marker("Orlen-Dva", 32, name="Orlen"), marker("Jina", 31, city="Brno")]
    assert city_options(markers) == [{"value": "Brno", "label": "Brno"}, {"value": "Praha", "label": "Praha"}]
    assert station_options(markers, "Praha") == [
        {"value": "Orlen-Dva", "label": "Orlen – Dva"},
        {"value": "Shell-Jedna", "label": "Shell – Jedna"},
    ]


def test_distance_km_zero_and_known_distance():
    assert distance_km(50.1, 14.4, 50.1, 14.4) == 0
    assert distance_km(0, 0, 0, 1) == pytest.approx(111.1950802335, abs=1e-9)
    assert distance_km(0, 179.9, 0, -179.9) == pytest.approx(22.2390160467, abs=1e-8)
    assert distance_km(90, 0, 0, 0) == pytest.approx(10007.55722101796, abs=1e-8)
    assert distance_km(-90, 0, 0, 0) == pytest.approx(10007.55722101796, abs=1e-8)
    assert distance_km(0, 0, 0, 180) == pytest.approx(20015.11444203592, abs=1e-8)
    assert distance_km(50.0755, 14.4378, 49.1951, 16.6068) == pytest.approx(184.3, abs=0.1)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ((90, -180), (90, 180)),
        ((-90, -180), (-90, 180)),
        ((0, -180), (0, 180)),
        ((89.999999, 179.999999), (89.999999, 179.999999)),
    ],
)
def test_distance_edge_coordinates_and_identity(first, second):
    assert distance_km(*first, *second) == pytest.approx(0, abs=1e-8)


def test_distance_symmetry_and_near_identical_coordinates():
    first = (50.0755, 14.4378)
    second = (49.1951, 16.6068)
    assert distance_km(*first, *second) == pytest.approx(distance_km(*second, *first), abs=1e-10)
    assert 0 < distance_km(50.1, 14.4, 50.1000000001, 14.4) < 0.0001


def test_stations_inside_outside_and_exactly_on_radius(marker):
    radius = 5
    boundary_lat = math.degrees(radius / EARTH_RADIUS_KM)
    markers = [
        {**marker("inside", 30), "lat": 0.01, "lng": 0},
        {**marker("boundary", 31), "lat": boundary_lat, "lng": 0},
        {**marker("outside", 32), "lat": 0.1, "lng": 0},
    ]

    result = stations_within_radius(markers, 0, 0, radius)

    assert [station["name"] for station in result] == ["inside", "boundary"]
    assert result[1]["distance_km"] == pytest.approx(radius)


@pytest.mark.parametrize("radius", [5, 50])
def test_radius_includes_exact_boundary_but_not_just_outside(marker, radius):
    boundary_lat = math.degrees(radius / EARTH_RADIUS_KM)
    inside_lat = math.degrees((radius - 1e-8) / EARTH_RADIUS_KM)
    outside_lat = math.degrees((radius + 1e-8) / EARTH_RADIUS_KM)
    markers = [
        {**marker("inside", 30), "lat": inside_lat, "lng": 0},
        {**marker("boundary", 31), "lat": boundary_lat, "lng": 0},
        {**marker("outside", 32), "lat": outside_lat, "lng": 0},
    ]

    assert [station["name"] for station in stations_within_radius(markers, 0, 0, radius)] == [
        "inside", "boundary",
    ]


def test_boundary_tolerance_does_not_admit_points_outside_by_a_fraction_of_a_micrometer(marker):
    outside_lat = math.degrees((5 + 1e-10) / EARTH_RADIUS_KM)

    assert stations_within_radius(
        [{**marker("just-outside", 30), "lat": outside_lat, "lng": 0}],
        0,
        0,
        5,
    ) == []


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (None, 0),
        (0, None),
        (float("nan"), 0),
        (0, float("nan")),
        (float("inf"), 0),
        (0, float("-inf")),
        (10**400, 0),
        ("50", 14.4),
        ("", 14.4),
        (91, 0),
        (-91, 0),
        (0, 181),
        (0, -181),
        (True, 0),
        (False, 0),
    ],
)
def test_invalid_center_coordinates_rejected(latitude, longitude):
    with pytest.raises(ValueError):
        stations_within_radius([], latitude, longitude)


@pytest.mark.parametrize(
    "radius",
    [None, -1, 0, 4.99, 50.01, 51, float("nan"), float("inf"), True, "10", 10**400],
)
def test_invalid_radius_rejected(radius):
    with pytest.raises(ValueError):
        stations_within_radius([], 0, 0, radius)


def test_invalid_station_coordinates_are_skipped(marker):
    missing_lat = marker("missing-lat", 30)
    del missing_lat["lat"]
    missing_lng = marker("missing-lng", 31)
    del missing_lng["lng"]
    markers = [
        missing_lat,
        missing_lng,
        {**marker("nan-lng", 32), "lng": float("nan")},
        {**marker("infinite-lat", 33), "lat": float("inf")},
        {**marker("out-of-range", 34), "lat": -91},
        marker("valid", 34),
    ]

    assert [station["name"] for station in stations_within_radius(markers, 50.1, 14.4)] == ["valid"]


def test_malformed_markers_are_skipped_without_affecting_valid_stations(marker):
    markers = [
        None,
        [],
        "not a marker",
        10,
        {"lat": None, "lng": 14.4},
        marker("valid", 34),
    ]

    assert [station["name"] for station in stations_within_radius(markers, 50.1, 14.4)] == ["valid"]


def test_cheapest_and_nearest_have_deterministic_order(marker):
    stations = [
        {**marker("far-cheap", 20), "lat": 50.12, "lng": 14.4, "fresh": "Včera"},
        {**marker("near-expensive", 30), "lat": 50.11, "lng": 14.4},
        {**marker("near-cheapest", 20), "lat": 50.11, "lng": 14.4},
    ]

    cheapest = cheapest_stations_within_radius(stations, 50.1, 14.4)
    nearest = nearest_stations_within_radius(stations, 50.1, 14.4)

    assert [station["name"] for station in cheapest] == [
        "near-cheapest", "far-cheap", "near-expensive",
    ]
    assert [station["name"] for station in nearest] == [
        "near-cheapest", "near-expensive", "far-cheap",
    ]
    assert cheapest[1]["fresh"] == "Včera"
    assert "distance_km" not in stations[0]


def test_equal_price_and_distance_uses_stable_url_order(marker):
    stations = [
        {**marker("Z", 20), "url": "/stations/z"},
        {**marker("A", 20), "url": "/stations/a"},
    ]

    assert [station["url"] for station in cheapest_stations_within_radius(stations, 50.1, 14.4)] == [
        "/stations/a", "/stations/z",
    ]
    assert [station["url"] for station in nearest_stations_within_radius(stations, 50.1, 14.4)] == [
        "/stations/a", "/stations/z",
    ]


def test_sort_order_is_invariant_to_input_permutation_even_when_tie_fields_match(marker):
    first = {**marker("Same", 20), "chain": "Chain B", "fresh": "Včera"}
    second = {**marker("Same", 20), "chain": "Chain A", "fresh": "Dnes"}
    stations = [first, second]

    for selector in (stations_within_radius, cheapest_stations_within_radius, nearest_stations_within_radius):
        forward = selector(stations, 50.1, 14.4)
        reverse = selector(list(reversed(stations)), 50.1, 14.4)
        assert forward == reverse


def test_same_slug_in_different_cities_are_distinct_markers(marker):
    stations = [
        {**marker("Same-slug", 30, city="Praha"), "lat": 50.1, "lng": 14.4},
        {**marker("Same-slug", 31, city="Brno"), "lat": 50.11, "lng": 14.4},
    ]

    result = cheapest_stations_within_radius(stations, 50.1, 14.4)

    assert [station["url"] for station in result] == [
        "/Ceny-benzinu-a-nafty/Praha/Same-slug/123",
        "/Ceny-benzinu-a-nafty/Brno/Same-slug/123",
    ]


def test_empty_geographic_results(marker):
    assert stations_within_radius([], 50.1, 14.4) == []
    assert stations_within_radius([], 0, 0, 50) == []
    assert stations_within_radius([marker("far", 30)], 0, 0) == []
    assert cheapest_stations_within_radius([], 50.1, 14.4) == []
    assert nearest_stations_within_radius([], 50.1, 14.4) == []


@pytest.mark.parametrize(
    "price",
    [None, float("nan"), float("inf"), float("-inf"), -1, True, "30", "", 10**400],
)
def test_invalid_station_prices_are_excluded_from_cheapest(marker, price):
    stations = [marker("invalid", price), marker("valid", 30)]

    assert [station["name"] for station in cheapest_stations_within_radius(stations, 50.1, 14.4)] == [
        "valid",
    ]


def test_zero_price_remains_valid_and_nearest_does_not_require_a_price(marker):
    stations = [
        {**marker("zero", 0), "lat": 50.101, "lng": 14.4},
        {**marker("missing-price", 20), "lat": 50.101, "lng": 14.4},
        {
            key: value
            for key, value in {**marker("no-price", 20), "lat": 50.101}.items()
            if key != "price"
        },
    ]

    assert [station["name"] for station in cheapest_stations_within_radius(stations, 50.1, 14.4)] == [
        "zero", "missing-price",
    ]
    assert [station["name"] for station in nearest_stations_within_radius(stations, 50.1, 14.4)] == [
        "zero", "missing-price", "no-price",
    ]


def test_non_json_marker_values_do_not_break_nearest_sorting(marker):
    stations = [marker("invalid-price", object()), marker("valid-price", 30)]

    assert [station["name"] for station in nearest_stations_within_radius(stations, 50.1, 14.4)] == [
        "valid-price", "invalid-price",
    ]


def test_geographic_ranking_preserves_but_does_not_filter_stale_price(marker):
    stale = {**marker("stale-cheapest", 10, fresh="před 30 dny"), "lat": 50.1, "lng": 14.4}
    fresh = {**marker("fresh", 20, fresh="Dnes"), "lat": 50.101, "lng": 14.4}

    result = cheapest_stations_within_radius([fresh, stale], 50.1, 14.4)

    assert [station["name"] for station in result] == ["stale-cheapest", "fresh"]
    assert result[0]["fresh"] == "před 30 dny"


def test_geographic_helpers_do_not_change_city_payload_or_history(marker, now):
    city_station = marker("Same-slug", 30, city="Praha")
    other_city_station = marker("Same-slug", 1, city="Brno")
    original_history = {}
    with_other_city = {}

    original = payload([city_station], now, history=original_history)
    result = payload([city_station, other_city_station], now, history=with_other_city)
    stations_within_radius([city_station, other_city_station], 50.1, 14.4)

    assert result == original
    assert with_other_city == original_history
    assert [station["price"] for station in result["stations"]] == [30]


def session_with_response(status=200, data=None, json_error=None, headers=None):
    response = MagicMock()
    response.status = status
    response.headers = headers or {}
    response.json = AsyncMock(return_value=data, side_effect=json_error)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get.return_value = context
    return session


async def test_fetch_success_and_request(marker):
    markers = [marker("Test", 33)]
    session = session_with_response(data={"markers": markers})
    assert await async_fetch_markers(session, "dummy", "n95") == markers
    assert session.get.call_count == 1
    request_url = session.get.call_args.args[0]
    request_kwargs = session.get.call_args.kwargs
    assert request_url == "https://www.mbenzin.cz/Mapa-cen/data"
    assert request_kwargs["params"] == {"fuel": "n95", "ccs": "0"}
    assert request_kwargs["headers"]["X-Mbenzin-Klic"] == "dummy"
    assert "dummy" not in request_url
    assert "klic" not in request_url


@pytest.mark.parametrize(("status", "error"), [(401, InvalidAuth), (403, InvalidAuth), (429, RateLimited), (500, CannotConnect)])
async def test_fetch_http_errors(status, error):
    with pytest.raises(error):
        await async_fetch_markers(session_with_response(status=status), "dummy", "n95")


@pytest.mark.parametrize("data", [None, [], {}, {"markers": None}, {"markers": {}}])
async def test_fetch_invalid_response(data):
    with pytest.raises(InvalidAuth):
        await async_fetch_markers(session_with_response(data=data), "dummy", "n95")


async def test_fetch_invalid_json():
    with pytest.raises(InvalidAuth):
        await async_fetch_markers(session_with_response(json_error=ValueError("not JSON")), "dummy", "n95")


@pytest.mark.parametrize("error", [aiohttp.ClientError(), TimeoutError()])
async def test_fetch_network_errors(error):
    session = MagicMock()
    session.get.side_effect = error
    with pytest.raises(CannotConnect):
        await async_fetch_markers(session, "dummy", "n95")


async def test_fetch_429_parses_retry_after():
    session = session_with_response(status=429, headers={"Retry-After": "120"})

    with pytest.raises(RateLimited) as err:
        await async_fetch_markers(session, "sensitive-key", "n95")

    assert err.value.retry_after == 120
    assert "sensitive-key" not in str(err.value)


async def test_fetch_429_parses_retry_after_http_date():
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=120)
    session = session_with_response(
        status=429, headers={"Retry-After": format_datetime(retry_at, usegmt=True)}
    )

    with pytest.raises(RateLimited) as err:
        await async_fetch_markers(session, "key", "n95")

    assert 0 < err.value.retry_after <= 120


async def test_shared_cache_hits_are_scoped_by_key_and_fuel(marker):
    cache = SharedMarkerCache(max_entries=20)
    original = [marker("Praha", 30, city="Praha"), marker("Brno", 20, city="Brno")]
    first_session = session_with_response(data={"markers": original})
    other_key_session = session_with_response(data={"markers": [marker("Other", 44)]})
    other_fuel_session = session_with_response(data={"markers": [marker("Diesel", 39)]})

    shared = await async_fetch_markers(first_session, "key-one", "n95", cache=cache)
    shared[0]["price"] = -1
    again = await async_fetch_markers(session_with_response(), "key-one", "n95", cache=cache)
    different_key = await async_fetch_markers(other_key_session, "key-two", "n95", cache=cache)
    different_fuel = await async_fetch_markers(other_fuel_session, "key-one", "diesel", cache=cache)

    assert again == original
    assert different_key == [marker("Other", 44)]
    assert different_fuel == [marker("Diesel", 39)]
    assert "key-one" not in repr(cache._entries)
    assert first_session.get.call_count == 1
    assert other_key_session.get.call_count == 1
    assert other_fuel_session.get.call_count == 1


async def test_shared_cache_data_remains_national_and_city_results_are_independent(marker, now):
    cache = SharedMarkerCache(max_entries=20)
    markers = [marker("Praha", 30, city="Praha"), marker("Brno", 20, city="Brno")]
    session = session_with_response(data={"markers": markers})

    nationwide = await async_fetch_markers(session, "key", "n95", cache=cache)
    prague = build_payload(
        nationwide, fuel="n95", city="Praha", home_slug=None, history={}, now=now, language="cs"
    )
    brno = build_payload(
        await async_fetch_markers(session_with_response(), "key", "n95", cache=cache),
        fuel="n95",
        city="Brno",
        home_slug=None,
        history={},
        now=now,
        language="cs",
    )

    assert prague["city_total"] == brno["city_total"] == 1
    assert prague["stations"][0]["price"] == 30
    assert brno["stations"][0]["price"] == 20
    assert session.get.call_count == 1


async def test_shared_cache_single_flight(marker):
    cache = SharedMarkerCache(max_entries=20)
    session = session_with_response(data={"markers": [marker("Shared", 31)]})
    context = session.get.return_value
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed_enter():
        entered.set()
        await release.wait()
        return context.__aenter__.return_value

    context.__aenter__.side_effect = delayed_enter
    first = asyncio.create_task(async_fetch_markers(session, "key", "n95", cache=cache))
    await entered.wait()
    second = asyncio.create_task(async_fetch_markers(session, "key", "n95", cache=cache))
    await asyncio.sleep(0)
    release.set()

    assert await first == await second == [marker("Shared", 31)]
    assert session.get.call_count == 1


async def test_shared_cache_expires_successful_markers(marker):
    cache = SharedMarkerCache(max_entries=20, ttl=timedelta(milliseconds=10))
    first = session_with_response(data={"markers": [marker("Old", 31)]})
    fresh = session_with_response(data={"markers": [marker("New", 30)]})

    assert await async_fetch_markers(first, "key", "n95", cache=cache) == [marker("Old", 31)]
    await asyncio.sleep(0.02)
    assert await async_fetch_markers(fresh, "key", "n95", cache=cache) == [marker("New", 30)]
    assert first.get.call_count == fresh.get.call_count == 1


async def test_shared_cache_failed_flight_clears_and_allows_later_request(marker):
    cache = SharedMarkerCache(max_entries=20)
    session = MagicMock()
    session.get.side_effect = aiohttp.ClientError("connection failed")

    first = asyncio.create_task(async_fetch_markers(session, "key", "n95", cache=cache))
    second = asyncio.create_task(async_fetch_markers(session, "key", "n95", cache=cache))
    results = await asyncio.gather(first, second, return_exceptions=True)
    assert all(isinstance(result, CannotConnect) for result in results)
    assert session.get.call_count == 1
    assert len(cache._inflight) == 0

    session.get.side_effect = None
    session.get.return_value = session_with_response(data={"markers": [marker("Recovered", 32)]}).get.return_value
    assert await async_fetch_markers(session, "key", "n95", cache=cache) == [marker("Recovered", 32)]
    assert session.get.call_count == 2


async def test_shared_cache_respects_retry_after_and_fallback_backoff():
    cache = SharedMarkerCache(max_entries=20, ttl=timedelta(seconds=30))
    limited = session_with_response(status=429, headers={"Retry-After": "60"})

    with pytest.raises(RateLimited) as err:
        await async_fetch_markers(limited, "key", "n95", cache=cache)
    assert err.value.retry_after == 60
    with pytest.raises(RateLimited):
        await async_fetch_markers(session_with_response(), "key", "n95", cache=cache)
    assert limited.get.call_count == 1

    fallback = session_with_response(status=429)
    with pytest.raises(RateLimited) as err:
        await async_fetch_markers(fallback, "key", "diesel", cache=cache)
    assert err.value.retry_after is None
    with pytest.raises(RateLimited):
        await async_fetch_markers(session_with_response(), "key", "diesel", cache=cache)
    assert fallback.get.call_count == 1


async def test_shared_cache_has_bounded_entry_count(marker):
    cache = SharedMarkerCache(max_entries=2)
    for key in ("key-one", "key-two", "key-three"):
        await async_fetch_markers(
            session_with_response(data={"markers": [marker(key, 30)]}),
            key,
            "n95",
            cache=cache,
        )

    assert len(cache._entries) == 2
    assert len(cache._inflight) == 0


async def test_shared_cache_survives_reload_but_starts_empty_after_restart(marker):
    def fake_hass():
        return SimpleNamespace(
            data={},
            config_entries=SimpleNamespace(async_entries=lambda domain: []),
        )

    hass = fake_hass()
    first_cache = shared_marker_cache(hass)
    response = session_with_response(data={"markers": [marker("Cached", 30)]})

    assert await async_fetch_markers(response, "key", "n95", cache=first_cache) == [marker("Cached", 30)]
    assert shared_marker_cache(hass) is first_cache
    assert await async_fetch_markers(session_with_response(), "key", "n95", cache=shared_marker_cache(hass)) == [
        marker("Cached", 30)
    ]

    restarted_hass = fake_hass()
    restarted_cache = shared_marker_cache(restarted_hass)
    fresh_response = session_with_response(data={"markers": [marker("Fresh", 29)]})
    assert restarted_cache is not first_cache
    assert await async_fetch_markers(fresh_response, "key", "n95", cache=restarted_cache) == [
        marker("Fresh", 29)
    ]
    assert response.get.call_count == fresh_response.get.call_count == 1
