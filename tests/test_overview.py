"""Average prices in the country, in the regions (kraje) and in the area, and the area's standing."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ceny_paliv.api import MarkerSnapshot, build_payload, price_overview, warm_regions
from custom_components.ceny_paliv.const import DOMAIN
from custom_components.ceny_paliv.regions import REGION_NAMES, region_of

PRAHA = (50.08, 14.42)
KLADNO = (50.147, 14.103)  # Středočeský kraj, around Prague (a hole in its boundary)
BRNO = (49.19, 16.61)
OSTRAVA = (49.82, 18.26)
BERLIN = (52.52, 13.40)


def _at(marker, slug, price, city, where, **kwargs):
    return {**marker(slug, price, city=city, **kwargs), "lat": where[0], "lng": where[1]}


def test_the_bundled_boundaries_hold_the_14_regions():
    data = json.loads((Path(__file__).parents[1] / "custom_components/ceny_paliv/regions.json").read_text("utf-8"))
    assert "CC BY 4.0" in data["source"]
    assert len(REGION_NAMES) == 14
    assert REGION_NAMES["CZ010"] == "Hlavní město Praha"
    assert REGION_NAMES["CZ063"] == "Kraj Vysočina"


def test_a_point_gets_its_region():
    assert region_of(*PRAHA) == "CZ010"
    assert region_of(*KLADNO) == "CZ020"
    assert region_of(*BRNO) == "CZ064"
    assert region_of(*OSTRAVA) == "CZ080"
    assert region_of(*BERLIN) is None


def test_a_point_just_past_a_simplified_border_belongs_to_the_nearest_region():
    data = json.loads((Path(__file__).parents[1] / "custom_components/ceny_paliv/regions.json").read_text("utf-8"))
    # the westernmost boundary point of the country: everything west of it lies outside every region
    lat, lng, code = min(
        ((lat, lng, region["code"]) for region in data["regions"] for polygon in region["polygons"] for lat, lng in polygon[0]),
        key=lambda point: point[1],
    )
    assert region_of(lat, lng - 0.005) == code  # about 350 m
    assert region_of(lat, lng - 0.1) is None  # about 7 km


def test_price_overview_ranks_the_regions_and_places_the_area(marker):
    stations = [
        _at(marker, "P1", 34, "Praha", PRAHA),
        _at(marker, "P2", 36, "Praha", PRAHA),
        _at(marker, "B1", 32, "Brno", BRNO),
        _at(marker, "O1", 33, "Ostrava", OSTRAVA),
        _at(marker, "D1", 30, "Berlin", BERLIN),  # in no region, still in the country's average
    ]
    warm_regions(stations + [{"broken": True}])
    overview = price_overview(stations, [34, 36], "CZ010")
    assert overview["national"] == {"average": 33.0, "median": 33, "station_count": 5}
    assert [(r["code"], r["average"], r["rank"], r["vs_national"]) for r in overview["regions"]] == [
        ("CZ064", 32.0, 1, -1.0),
        ("CZ080", 33.0, 2, 0.0),
        ("CZ010", 35.0, 3, 2.0),
    ]
    assert overview["region"]["name"] == "Hlavní město Praha"
    assert overview["area"] == {"average": 35.0, "station_count": 2, "vs_national": 2.0, "vs_region": 0.0}

    empty = price_overview([], [], None)
    assert empty["national"] == {"average": None, "median": None, "station_count": 0}
    assert empty["region"] is None
    assert empty["area"] == {"average": None, "station_count": 0, "vs_national": None, "vs_region": None}


def test_the_payload_compares_only_up_to_date_prices(marker, now):
    markers = [
        _at(marker, "P1", 34, "Praha", PRAHA),
        _at(marker, "P2", 20, "Praha", PRAHA, fresh="01.11.2024"),  # too old for the averages too
        _at(marker, "B1", 32, "Brno", BRNO),
    ]
    city = build_payload(markers, fuel="n95", city="Praha", home_slug=None, history={}, now=now)["overview"]
    assert city["national"]["average"] == 33.0
    assert city["region"]["code"] == "CZ010"
    assert city["area"] == {"average": 34.0, "station_count": 1, "vs_national": 1.0, "vs_region": 0.0}

    def gps(center):
        return build_payload(
            markers, fuel="n95", city="", home_slug=None, history={}, now=now,
            gps_method="map", gps_center=center, gps_radius_km=20,
        )["overview"]

    assert gps(BRNO)["region"]["code"] == "CZ064"
    assert gps(BRNO)["area"]["vs_region"] == 0.0
    abroad = gps(BERLIN)
    assert abroad["region"] is None
    assert abroad["area"] == {"average": None, "station_count": 0, "vs_national": None, "vs_region": None}


async def test_average_sensors(hass, enable_custom_integrations, mock_frontend, marker):
    hass.config.latitude, hass.config.longitude = BERLIN
    city = MockConfigEntry(
        domain=DOMAIN, title="Ceny paliv Praha", data={"key": "dummy", "city": "Praha"},
        options={"fuels": ["n95"], "homes": {}}, unique_id="Praha",
    )
    abroad = MockConfigEntry(
        domain=DOMAIN, title="Ceny paliv GPS area", data={"key": "dummy", "city": ""},
        options={"fuels": ["diesel"], "homes": {}, "area_mode": "gps", "location_method": "home", "gps_radius_km": 10},
        unique_id="gps-abroad",
    )
    city.add_to_hass(hass)
    abroad.add_to_hass(hass)
    markers = [
        _at(marker, "P1", 34, "Praha", PRAHA),
        _at(marker, "P2", 36, "Praha", PRAHA),
        _at(marker, "B1", 32, "Brno", BRNO),
    ]
    snapshot = MarkerSnapshot(markers=markers, fetched_at=dt_util.now())
    with patch("custom_components.ceny_paliv.coordinator.async_fetch_snapshot", new=AsyncMock(return_value=snapshot)):
        assert await hass.config_entries.async_setup(city.entry_id)
        await hass.async_block_till_done()

    national = hass.states.get("sensor.ceny_paliv_n95_national_average")
    assert national.state == "34.0"
    assert national.attributes["station_count"] == 3
    assert national.attributes["median"] == 34
    assert [region["code"] for region in national.attributes["regions"]] == ["CZ064", "CZ010"]
    assert national.attributes["unit_of_measurement"] == "Kč/l"
    assert national.attributes["state_class"] == "measurement"
    assert national.attributes["cp_role"] == "national_average"

    region = hass.states.get("sensor.ceny_paliv_n95_region_average")
    assert region.state == "35.0"
    assert region.attributes["region"] == "Hlavní město Praha"
    assert (region.attributes["region_code"], region.attributes["rank"], region.attributes["vs_national"]) == ("CZ010", 2, 1.0)

    area = hass.states.get("sensor.ceny_paliv_n95_area_average")
    assert area.state == "35.0"
    assert (area.attributes["vs_national"], area.attributes["vs_region"], area.attributes["region_rank"]) == (1.0, 0.0, 2)
    assert area.attributes["friendly_name"] == "Ceny paliv Praha Natural 95 · area average"

    # a GPS area centred abroad: the country's average stays, the region is unknown
    assert hass.states.get("sensor.ceny_paliv_diesel_national_average").state == "34.0"
    assert hass.states.get("sensor.ceny_paliv_diesel_region_average").state == "unavailable"
    assert hass.states.get("sensor.ceny_paliv_diesel_area_average").state == "unknown"
    for entry in (city, abroad):
        assert await hass.config_entries.async_unload(entry.entry_id)
