# Changelog

## Unreleased

### New

- **Diagnostics show what mBenzin.cz sends**: the field names of its stations per fuel, their number, and one example
  station (the first of the nationwide list, never one of your area). This tells whether a field could give the
  streets and towns their accents.
- **Price history per station** in Home Assistant's long-term statistics: the favourite station's price is recorded
  under the station itself (`ceny_paliv:<fuel>_<station id>`), with the up to 35 days the integration already kept.
  Choosing another favourite, choosing a station again, or removing and adding the integration no longer loses or
  mixes its history. The favourite sensor has a new `statistic_id` attribute and the card's 30-day graph uses it.
- **Readable station names**: every station gets a `title` such as "VS Petrol · Obory" (the name and the street, or
  the town when it has no street), a `street` without the repeated station name (also when mBenzin writes the name
  without accents, as "Am oil Milicin parkoviste") and its `city`. The `station` attribute of the favourite and
  position sensors, and so the card's favourite station, shows the title; list rows show the town for stations
  without a street. Town names no longer keep a run of spaces ("Brandys nad Labem Stara Boleslav"). The
  favourite-station choices use "·" instead of "–".
- **Documentation** (quality scale: the Gold `docs-*` rules): the README, in English and Czech, now has use cases, how
  the data is updated, every attribute of every sensor, examples, known limitations and troubleshooting.
- **Repairs** (quality scale: repair-issues): Settings → Repairs shows when a fuel has had no prices from mBenzin.cz
  for more than 24 hours, when the zone of a GPS area was deleted, or when the GPS centre has no valid coordinates.
  Each message says what to do and disappears by itself once the cause is gone, or when the area is deleted.
- **Removing a fuel removes its sensors** (in Configure), archived favourites included, instead of leaving them
  behind as unavailable entities. Other areas are not touched.
- **Archived favourite sensors are diagnostic and off by default** (quality scale: entity-category,
  entity-disabled-by-default): they only keep the statistics of a former favourite. Choosing that station again
  switches its sensor back on.
- **Action `ceny_paliv.refresh`** (quality scale: action-setup, docs-actions, action-exceptions): loads the prices now,
  for one area or all of them. Prices downloaded less than 30 minutes ago are reused, so it cannot flood mBenzin.cz;
  if mBenzin.cz does not answer, prices still within their lifetime are kept. It reports what could not be refreshed.
- **Translated error messages** (quality scale: exception-translations): the refresh failure, a refused key and the
  action's errors are shown in English or Czech.
- **Diagnostics** (quality scale: diagnostics): Settings → Devices & services → Ceny paliv → ⋮ → Download diagnostics
  gives the settings and the state of the last refresh of each fuel, for bug reports. The access key, the GPS centre
  and the favourite stations are redacted, and the station lists are left out.

### Changed

- **Sensors are unavailable while mBenzin.cz cannot be reached** (quality scale: entity-unavailable,
  log-when-unavailable). When one fuel fails, only its sensors become unavailable; when every fuel fails, all of them.
  The failure and the recovery are logged once instead of a warning on every refresh. The card keeps showing the last
  known prices with the warning "mBenzin.cz cannot be reached — showing the last known prices"; it stores them in the
  browser, so they also survive a page reload. **Breaking:** automations that read the price of a failed fuel now see
  `unavailable` instead of the previous price, and the card's "Last refresh failed" note is replaced by that warning.
- **Each area is a device; sensors have translated names** (quality scale: devices, has-entity-name, entity-translations,
  icon-translations). Every configured area is a service device ("Ceny paliv Praha", manufacturer mBenzin.cz), and its
  sensors are named under it in the Home Assistant language, for example "Natural 95 · cheapest #1"
  ("Natural 95 · 1. nejlevnější"). **Breaking:** the position and favourite sensors are no longer named after the
  station they show; the station is in their `station` attribute. Entity IDs and history stay as they are.
- **This repository is now the project's home**: the documentation, issue tracker, HACS instructions and logo pack
  point to `Vituhlos/ha-ceny-paliv`, and the code owner is @Vituhlos. If you added the original repository to HACS,
  replace it with `https://github.com/Vituhlos/ha-ceny-paliv` to keep getting updates.
- Every setup and Configure field now has a short description, in English and Czech.
- The README describes every setting in a table and how to remove the integration.

## 0.5.3

### Changed

- **The card looks and behaves like a Home Assistant card** (#24, #25):
  - It takes its colours, fonts, sizes and corners from your theme instead of drawing its own dark surface. It follows light, dark and custom themes, and the map follows the theme too.
  - The favourite station and the list follow the tile card: a round icon, a name, a second line and the price on the right. Themes that restyle tiles, such as Fluvy, restyle these lines too.
  - Prices and times follow your Home Assistant profile: the number format (`38,50` in Czech), the 12/24 h clock and the time zone.
  - Less clutter: no all-caps label, tap hint or chevrons. A tap still opens the details or Google Maps.
  - Outdated prices are flagged by an icon as well as their colour. A row shows the price date before the address, and no longer repeats the station name.
  - A failed refresh shows as a warning in the card.

### Fixed

- In a GPS area the favourite-station card said "Cheapest in town"; it now says "Cheapest in the area" (#24).
- Czech hidden-stations note: "starší než včerejšek" instead of "starší než včera" (#25).

### Known limitations

- Validated with offline tests, CI and a demo page (default, custom and Fluvy themes, light and dark, phone and desktop widths) before release; checked on a live Home Assistant dashboard only after release.

## 0.5.2

### New

- **Show older prices too** (#22): small stations update their prices on mbenzin.cz less often, so with the
  one-day limit for petrol and diesel they often dropped out of the list (in a 20 km area around a small town, 15 of
  22 stations). A new setting in the integration's **Configure** → "Fuels and language" step keeps prices up to 3 or
  7 days old in the ranking. Their date is shown in amber. The default stays "today and yesterday", and LPG, CNG
  and AdBlue keep their longer limits.

### Fixed

- The map showed clipped prices such as „7,9 Kč“: the marker was too narrow for the price with its unit. It now
  shows just the price, for example „37,9“ (#21).

### Known limitations

- Validated with offline tests and CI before release; checked on a live Home Assistant only after release.

## 0.5.1

### Changed

- **Price source shown with the prices** (#19): mBenzin.cz gives the access key on condition that the prices are
  shown with the visible source „Ceny: mbenzin.cz“ (as a link on the web). The card now shows it as a link to
  mbenzin.cz in both footers, and under your station when the favourite card is shown alone. Tapping the link opens
  only the link. Every sensor also carries it as its `attribution`, so Home Assistant shows it in the entity details.

### Known limitations

- Not verified against a live Home Assistant instance or in a browser before release; validated with offline tests
  and CI only.

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
