# Changelog

## 0.5.0

### New

- **GPS search areas** (#5): instead of a city, follow the stations within 5–50 km of your home, a saved Home
  Assistant zone, a point on the map or manual coordinates. Several areas can show the same fuel; the card picks
  one with the new `config_id` option.
- **Shared mBenzin data** (#4): configurations with the same key and fuel share one nationwide download; requests
  are single-flight and HTTP 429 pauses the whole key.
- **New key without losing anything** (#13): if mBenzin.cz stops accepting the key, Home Assistant asks for
  a new one (Reauthenticate); the key can also be changed any time (⋮ → Reconfigure). Settings, price history and
  sensors stay.
- The card's rows and favourite card can be used with the keyboard; the card picker shows a preview.

### Fixed

- A new configuration without a favourite station for some fuel failed with "Unknown error" (#6).
- Prices were often refreshed only every ~12 hours: the scheduled refresh received its own six-hour-old cached
  snapshot (#7). `next_update` is now right across DST changes, and `Retry-After` is capped at 24 hours.
- After switching a configuration from City to GPS, the favourite sensor could start reporting a station with the
  same name in another city and mix its statistics (#8).
- One malformed station in the mBenzin data could make every sensor of a City configuration unavailable (#10).
- Card: map and graph no longer disappear after an outage or restart; positions that were empty when the page
  loaded appear on the map; a removed area cannot blank the card; the visual editor no longer saves its defaults
  (a `show_map: false` card kept its map hidden only until the first edit); a tap no longer opens Google Maps
  several times after editing (#11, #12).
- The entry follows its area: its unique ID and automatic title change with the city or GPS mode, so the old city
  can be added again (#14).
- A zone's occupancy changes no longer trigger refreshes; only moving or resizing the zone does (#14).
- Logo pack: stricter ids and manifest checks; GPS mode preselects only the chains inside the area
  (#15).

### Changed — please read before upgrading from 0.4.x

- **Trend history** is now keyed by station URL. On the first refresh after the upgrade, your 0.4.x history moves
  to the new keys when the station is unambiguous in your city, so trends continue (#9). Ambiguous old logs are
  not guessed and expire after 35 days.
- **Position sensors** (`sensor.ceny_paliv_<fuel>_1…5`) without a station are now `unknown` instead of
  `unavailable`, so the card can still identify them (#11).
- **Favourite station change**: the old favourite sensor stays registered with its history but is now **disabled**
  when you choose another station, and re-enabled if you choose it again (#14). The new favourite sensor
  gets a new entity id (for example `_home_2`); update automations that use `_home` (see
  `examples/price_alert.yaml`).
- Big display-only attributes (`stations`, `labels`, `logos`, GPS details, `trends`) are no longer written to the
  recorder; the card reads them from the live state (#14).
- Deleting a configuration now deletes its price-history storage (#14).
- Area and location choices in the setup are translated by Home Assistant (#16).

### Development

- CI runs hassfest, the HACS validation, ruff, a version-consistency check, the card tests on Node 22 and the
  Home Assistant matrix 2025.1.0 / Python 3.12 and 2026.10.4 / Python 3.14; actions are pinned and kept current by
  Dependabot (#17).
- Offline test suites: 190+ Python tests and 21 card tests.

### Known limitations

- Not verified against a live Home Assistant instance or live mBenzin.cz data before release.
- The integration icons in `brand/` are shown by Home Assistant 2026.3 and newer; older versions show a placeholder.
- The card uses its own dark colours and does not follow a light theme.
