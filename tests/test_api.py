"""Regression tests for the mBenzin client and payload."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.ceny_paliv.api import (
    CannotConnect,
    InvalidAuth,
    RateLimited,
    async_fetch_markers,
    build_payload,
    city_options,
    parse_fresh,
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


def session_with_response(status=200, data=None, json_error=None):
    response = MagicMock()
    response.status = status
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
    assert "fuel=n95" in session.get.call_args.args[0]


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
