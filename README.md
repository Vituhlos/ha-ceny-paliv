<p align="center"><img src="https://raw.githubusercontent.com/Vituhlos/ha-ceny-paliv/main/docs/logo.png" alt="Ceny paliv" width="420"></p>

# ⛽ Ceny paliv – Czech fuel prices for Home Assistant

**English** · [Česky](README.cs.md)

A HACS integration that shows the cheapest stations in **your city** or a **5–50 km GPS area** for the fuel(s) you use — **Natural 95, Diesel, LPG, CNG** and more — plus **your favourite station** with price history and trends. Everything is configured from the Home Assistant UI.

![Dashboard](docs/screenshot.webp)

> **Ceny paliv** (Czech for “fuel prices”) is an independent project. The prices come from [mBenzin.cz](https://www.mbenzin.cz); this project is not made, endorsed or supported by mBenzin.cz.

## Features

- Pick your **city**, one or **several fuels** (e.g. Natural 95 + LPG for a dual-fuel car) and a **favourite station per fuel**
- Or choose a GPS area centred on Home Assistant's configured home location, **a person or device you follow** (the area moves with you), a saved `zone.*`, a point selected on Home Assistant's map, or (advanced) manually entered coordinates; choose a **5–50 km** radius (default **40 km**). A person's or a phone's location is used only if you choose it; no geocoder or extra mBenzin request is used
- Per fuel: the **top 5 cheapest** stations in the city (only that city, not the region), and a **map**; tap a station for its details and **navigation in Mapy.com, Google Maps or Waze**
- Favourite station: price, **trends vs 1/2/7/14/30 days ago**, rank in town, long-term statistics (the 30-day graph)
- **Average prices** in the whole country, in your region (kraj) and in your area, and how your area stands against them, with long-term statistics, from the same download
- A ready-made **dashboard card** (`ceny-paliv-card`) shipped with the integration — add it from the card picker, no YAML to copy — in **English or Czech** (your choice during setup). It is **flexible**: two columns on a wide dashboard, one on a phone, a compact version, and every part (favourite station, list, map, graph) can be placed as its own card
- Optional **station logos** (Orlen, MOL, Shell, Tesco…): tick the chains you want in the setup and they are downloaded for you. Chains without a logo get a colour badge with their initials
- Stale prices are hidden (older than yesterday for petrol/diesel, 3 days for CNG, 7 days for LPG/AdBlue). Small stations update their prices less often: the **Show older prices too** setting (up to 3 or 7 days) keeps them in the list, with the price date shown

## Use cases

- **Fill up where it is cheapest** on your way: the card lists the five cheapest stations in your city or around your home, with the price date; tap one to navigate there with Mapy.com, Google Maps or Waze.
- **Follow your usual station**: its price, its rank in town, how far it is from the cheapest one, and how its price moved over 1–30 days, with a 30-day graph.
- **Dual-fuel or several cars**: one card per fuel (for example Natural 95 and LPG), or one area per town you drive in.
- **Get told instead of looking**: a phone notification when your station gets cheaper, when a price drops under your limit, or about a cheap station near you on the road (see [Blueprints](#blueprints)).
- **Rural areas**: a GPS circle of 5–50 km collects the stations of several small towns, and "Show older prices too" keeps stations that update their prices rarely.

## 1. Get your access key (free)

mBenzin blocks plain scraping with a browser check, but they give a **personal access key** to Home Assistant users. E-mail **reklama@mbenzin.cz** and tell them what the prices are for, which city/stations, and how often you load them. (For me the answer came quickly and the key worked immediately.)

- The key is **personal — never share it or publish it**. Everyone requests their own.
- mBenzin.cz asks that the prices are shown with the visible source **„Ceny: mbenzin.cz“** (as a link on the web). The card shows it under the list (or under your station when shown alone) and every sensor carries it as its `attribution`; if you build your own cards, add it there too.
- To change the key, open the integration's ⋮ menu → **Reconfigure**. If mBenzin.cz stops accepting it (HTTP 401/403, or its HTML refusal page on two refreshes in a row), Home Assistant shows a **Reauthenticate** prompt. Either way, settings, price history and sensors stay.
- The provider has not confirmed a request limit for this integration. Automatic refreshes remain every **6 hours**, and requests for the same key and fuel are shared across configurations. This deduplication and the temporary HTTP 429 cooldown are not a per-key request quota; no persistent quota is enforced. A true quota would require a provider-confirmed limit and persistent tracking. After HTTP 429, all fuels for that key wait for a valid `Retry-After` value (capped at 24 hours) or just under 6 hours when none is provided; this in-memory cooldown is cleared by a Home Assistant restart.
- The key is sent in an HTTP header, not in the request URL.
- The download is done by the [aiombenzin](https://pypi.org/project/aiombenzin/) library (by the same author), which Home Assistant installs with the integration.
- It uses mBenzin's price-map data, which is not a documented public API: be gentle and respect their conditions.

## 2. Install with HACS

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/Vituhlos/ha-ceny-paliv`, category **Integration**.
2. Search for **Ceny paliv**, download it, **restart** Home Assistant.
3. Settings → Devices & services → **Add integration** → **Ceny paliv**, then:
   1. paste your **access key**
   2. choose **City** (the original behavior) or **GPS area**
   3. for GPS, choose Home Assistant's home location, a saved zone, a point on the built-in map, or advanced manual coordinates; set a 5–50 km radius (40 km by default)
   4. choose your **city** (City mode), **fuel(s)** and the **language** of the dashboard texts (English / Čeština)
   5. for each fuel, choose a **favourite station** (City mode lists the city; GPS mode lists stations in the selected circle first and retains an already-saved favourite outside it)
   6. optionally tick the **logos** of the chains to show (chains in the selected area are preselected; see [Station logos](#4-station-logos-optional))

You can change the area mode, location method or point, radius, fuels, language, favourite stations and logos later: the integration's **Configure** button. Existing entries without an area mode remain in City mode. Home Assistant home coordinates are read at refresh time; zone changes trigger a refresh, while a deleted zone produces an empty GPS result until it is restored or replaced.

> The setup screens follow Home Assistant's own language (English and Czech are provided). The language chosen in step 3 only sets the labels of the dashboard card.

### Settings

Everything except the access key is asked during setup and can be changed later with **Configure**. The access key is changed with **⋮ → Reconfigure** (or when Home Assistant asks for a new one).

| Setting | When | What it does |
|---|---|---|
| Access key | setup, Reconfigure | Your personal mBenzin.cz key; checked with a real download before it is saved. |
| Search area | always | **City**: the stations of one city. **GPS area**: the stations within a radius of a point. |
| Location source | GPS area | The centre: Home Assistant's home location, a person or device you follow, a saved zone, a point on the map, or manual coordinates. |
| Person or device | location source Person | A `person.*` or `device_tracker.*` (for example the Home Assistant app on your phone). The area moves with it once it is 1 km or more away, computed from the prices already downloaded; without a location it stays around home. |
| Zone | location source Zone | The zone whose centre is used; a moved zone triggers a refresh, a deleted one leaves the area empty. |
| GPS centre | location source Map | The point picked on the map. |
| Latitude, Longitude | location source Manual | Decimal degrees (−90 to 90, −180 to 180). |
| Radius (km) | GPS area | 5–50 km, 40 km by default. |
| City | City | Only that city's stations, not the surrounding region. |
| Fuels | always | One or more of Natural 95, Natural 98, Diesel, Diesel Plus, LPG, CNG, AdBlue; each gets its own sensors. |
| Language of the dashboard texts | always | English or Čeština for the card's labels; entity names and setup screens follow Home Assistant's language. |
| Show older prices too | always | Prices up to 1 (default), 3 or 7 days old count; LPG and AdBlue always allow 7 days, CNG 3. |
| Favourite station | per fuel | Optional (**—** for none); gets its own sensor with history, trends and rank. Choosing another station starts a new sensor. |
| Logos | always | Chains whose logos are downloaded from the logo pack; see [Station logos](#4-station-logos-optional). |

## Entities

For each fuel `<fuel>` (`n95`, `benzinplus`, `diesel`, `dieselplus`, `lpg`, `cng`, `adblue`):

| Entity | What |
|---|---|
| `sensor.ceny_paliv_<fuel>_top5` | price of the cheapest station, with long-term statistics (`state_class: measurement`, since 0.9); attributes: the 5 cheapest stations (name, address, price, coordinates, Google Maps link, trends…). GPS mode also provides `gps_area` metadata and at most 10 compact `gps_nearest_stations` summaries ordered by distance |
| `sensor.ceny_paliv_<fuel>_home` | price at your favourite station (only if you chose one); trends, rank, statistics |
| `sensor.ceny_paliv_<fuel>_1` … `_5` | the 5 cheapest stations, with latitude/longitude for the map card |
| `sensor.ceny_paliv_<fuel>_national_average` | average price of the up-to-date stations in the Czech Republic; the 14 regions in attributes |
| `sensor.ceny_paliv_<fuel>_region_average` | average price in the region (kraj) of your area |
| `sensor.ceny_paliv_<fuel>_area_average` | average price in your area (town or GPS area) and how it compares |
| `event.ceny_paliv_<fuel>_price_change` | events when your favourite station gets cheaper or dearer, or the area's cheapest price drops |

Each configured area is a service device (named after the entry, for example `Ceny paliv Praha`) and its sensors have translated names under it, for example `Ceny paliv Praha Natural 95 · cheapest #1`; the station a position or favourite sensor currently shows is in its `station` attribute. Existing entity IDs remain stable when upgrading or changing area mode. A former favourite station keeps an archived sensor for its statistics (diagnostic, disabled; see [section 5](#5-without-the-card-standard-cards)).

All sensors show the price in Kč/l (CNG in Kč/kg) and carry the attribution `Ceny: mbenzin.cz`. The card finds its sensors by the `cp_fuel`, `cp_role` (`top5`, `home`, `position`, `home_archive`, `national_average`, `region_average`, `area_average`), `cp_index` and `cp_config_id` attributes.

### Attributes

**`sensor.ceny_paliv_<fuel>_top5`** — state: the cheapest price.

| Attribute | Content |
|---|---|
| `stations` | the 5 cheapest stations with an up-to-date price (fields below) |
| `home` | your favourite station in the same form, with its rank and comparison (or `null`) |
| `fetched_at`, `last_attempt`, `next_update` | when the prices were downloaded, when the last refresh ran, when the next one is due |
| `fetch_error` | always `null` on an available sensor (a failed fuel makes its sensors unavailable) |
| `city_name`, `city_total`, `excluded` | the area's name; in City mode the number of the city's stations; how many stations were left out because their price is too old |
| `max_age_days` | how old a price may be to count (the setting, or the fuel's longer limit) |
| `fuel`, `fuel_label`, `unit` | fuel code, its name and the unit |
| `gps_area` | GPS mode: method, centre, radius, zone, location error, number of stations in the circle |
| `gps_nearest_stations` | GPS mode: up to 10 nearest stations, compact (name, city, address, price, coordinates, date, distance) |
| `language`, `labels`, `logos` | the card's language, its texts and the downloaded logos |

Each station in `stations` (and `home`) has `rank`, `name`, `title` (a readable label: the name and the street, or the town when the station has no street, for example `Benzina · Karlovarská`), `chain`, `street` (the address without the repeated station name; for a village without streets its name and number), `city` (the town, without a house number), `address` (mBenzin's address, for example `Selbská 15/2732, Aš`), `price`, `lat`, `lng`, `updated` (mBenzin's own wording, for example `Dnes`), `updated_date`, `maps` (a Google Maps link), `home` (whether it is your favourite) and `trends`; in GPS mode also `distance_km`. The street and the town come from mBenzin's address, with accents; for a station without one, from its link, without accents. `trends` has the keys `1`, `2`, `7`, `14` and `30` (days); each is `null` until there is an earlier price, otherwise `dir` (`up`, `down`, `flat`), `delta` (Kč), `ref_date` and `ref_price`.

**`sensor.ceny_paliv_<fuel>_home`** — state: the price at your favourite station; long-term statistics (`state_class: measurement`).

| Attribute | Content |
|---|---|
| `station`, `price`, `latitude`, `longitude`, `maps`, `distance_km` | the station's readable title (as `title` above) and where it is (`distance_km` in GPS mode) |
| `updated`, `updated_date`, `age_days` | when the station last updated its price |
| `rank`, `fresh_count`, `vs_cheapest`, `cheapest_name` | its rank among the up-to-date stations, how many there are, how much more it costs than the cheapest one and which that is |
| `trends` | as above |
| `statistic_id` | the station's own long-term statistics, for example `ceny_paliv:n95_3fa2b1c4d5e6` (see below) |

**`sensor.ceny_paliv_<fuel>_1` … `_5`** — state: the price of the n-th cheapest station; attributes `station` (the readable title), `price`, `latitude` and `longitude` for the map (no coordinates when that station is your favourite, which the favourite sensor draws). A position without a station is `unknown`.

**Average prices** — the three sensors below count only the up-to-date stations (the same age limit as the list, including **Show older prices too**) and keep long-term statistics (`state_class: measurement`). Each station's region comes from its coordinates and the region boundaries bundled with the integration (ČÚZK, simplified: a station within about 200 m of a regional border may count for the neighbouring region).

| Sensor | State | Attributes |
|---|---|---|
| `_national_average` | the average in the Czech Republic | `station_count`, `median`, `regions`: for each region `code` (NUTS 3, for example `CZ010`), `name`, `average`, `station_count`, `vs_national` and `rank` (1 = the cheapest region) |
| `_region_average` | the average in your area's region (a city's region, or the GPS centre's); unavailable when the centre lies outside the Czech Republic | `region`, `region_code`, `station_count`, `rank`, `vs_national` |
| `_area_average` | the average of the stations in your area | `station_count`, `region`, `region_rank`, `vs_national` and `vs_region` (Kč; below zero: your area is cheaper) |

When a followed person or a moved GPS area crosses into another region, the region sensor continues with that region's average.

**`event.ceny_paliv_<fuel>_price_change`** — an event entity that compares each refresh with the one before. Its event types:

| Event type | When |
|---|---|
| `favourite_cheaper` / `favourite_dearer` | the price at your favourite station went down / up (choosing another favourite is not a change) |
| `cheapest_cheaper` | the area's cheapest price went down (also when a moved GPS area finds a cheaper station) |

Each event carries `fuel`, `unit`, `area`, `station`, `address`, `price`, `previous_price`, `change` (Kč), `distance_km` (GPS mode) and `maps`. Its entity id stays the same when you choose another favourite station, so automations keep working. The prices at start-up are only the baseline: a restart, or a refresh that failed, reports nothing.

## How the data is updated

- **Every 6 hours** the integration downloads the nationwide prices of each fuel from mBenzin.cz (one request per fuel), and at setup or Home Assistant start. Areas with the same key share each download for just under 6 hours, so every scheduled refresh still gets new data and a second area costs no extra request.
- City and GPS filtering, the favourite station, the ranking and the trends are computed from that download; changing the area, a followed person moving, or reloading the integration reuses it. A Home Assistant restart clears it.
- The action [`ceny_paliv.refresh`](#actions) refreshes now; it downloads again only data older than 30 minutes.
- **HTTP 429** (too many requests): every fuel of that key waits for mBenzin's `Retry-After` (at most 24 hours), or just under 6 hours without it. The wait is kept in memory only.
- **When mBenzin.cz cannot be reached** for a fuel, its sensors are unavailable until the next successful refresh; the failure and the recovery are logged once, and after 24 hours without prices **Settings → Repairs** says so. The card keeps showing the last known prices with a warning.
- **Prices count only while fresh**: today and yesterday by default (CNG 3 days, LPG and AdBlue 7), or up to 3 or 7 days with "Show older prices too". mBenzin's relative dates ("Dnes", "Včera") are read against the time of the download in Czech time.
- **Trends**: once a day the prices are stored locally (`.storage/ceny_paliv.<entry id>`, kept 35 days): in City mode of every station of the city, in GPS mode of the five shown and the favourite. The trends compare with that log.
- **Long-term statistics per station**: at each refresh the favourite station's price is written to Home Assistant's long-term statistics under the station itself (`ceny_paliv:<fuel>_<station id>`, named for example "Natural 95 · Benzina · Karlovarská"), together with the up to 35 days of its daily log. They do not belong to a sensor or an area: choosing another favourite starts that station's own statistics, choosing a station again continues its history, and removing and adding the integration keeps it. The card's 30-day graph shows them; the favourite sensor still has its own statistics too.

## 3. The dashboard card (included, nothing else to install)

The integration ships its own card, **`ceny-paliv-card`**. After installing (and restarting) just:

1. Open a dashboard → **Edit** → **Add card** → search **Ceny paliv**.
2. Pick the **fuel** (the visual editor lists the fuels you set up). Done.

Or in YAML:

```yaml
type: custom:ceny-paliv-card
fuel: n95            # n95 | benzinplus | diesel | dieselplus | lpg | cng | adblue
```

One card per fuel, or several fuels in one card with a switch at the top (`fuels: [n95, lpg]`, for example for a dual-fuel car). The card has four parts: your favourite station (price, trends, rank), the top 5, a map and the 30-day graph. The graph draws your station against the area's cheapest price (its daily lowest) and the area's average, from Home Assistant's long-term statistics: hover or touch it for a day's values. The cheapest price is recorded from 0.9 and the average from 0.8, so their lines start then; without a favourite the graph shows the area only. Tap a station of the top 5 for its details (price, date, rank, distance, trends) and to navigate there with Mapy.com, Google Maps or Waze; long-press it for your favourite station's history. Above the list, sort the stations by price, by distance or by **worth it**: the price with the fuel burnt driving there and back (2 × distance × consumption, spread over your fill-up), so a cheap station far away loses to a slightly dearer one around the corner. Distances are straight lines from the GPS area's centre (or Home Assistant's home location in a town); in a GPS area the ten nearest stations join the five cheapest for these orders. Everything below is also in the card's visual editor. If the same fuel has multiple Ceny paliv configurations, select the intended configuration in the visual editor (or set `config_id` from the top5 sensor's `cp_config_id` in YAML); a card without an explicit configuration will not mix entities from different areas.

| Option | Default | |
|---|---|---|
| `fuel` | – | required (or `fuels`); with `fuels`, the one shown first |
| `fuels` | – | the fuels of a switch at the top of the card, for example `[n95, diesel]` (the switch remembers nothing: the card opens on `fuel`) |
| `sort` | `price` | the order of the list, also switchable in the card: `price`, `distance`, or `worth` (worth it: the price per litre with the fuel burnt driving there and back) |
| `tank_litres` | `40` | for `worth`: how much you fill up (CNG: kg) |
| `consumption` | `6.5` | for `worth`: your car's consumption in l/100 km (CNG: kg/100 km) |
| `config_id` | automatic when unambiguous | choose one configuration when the same fuel is configured more than once |
| `show` | `[home, list, map, graph]` | the parts to draw: `home` (favourite station), `list` (cheapest stations), `map`, `graph` (30 days) |
| `layout` | `auto` | `auto`: two columns (station and list on the left, map and graph on the right) when the card is wide, one column when it is narrow, as on a phone; `columns`: always two; `stack`: always one |
| `stations` | `5` | how many stations in the list (1–5, also on the map) |
| `compact` | `false` | dense version: one line per station, trends on one line, no legend |
| `show_footer` | `true` (`false` if `compact`) | update times and legend below the list |
| `map_height` | automatic | height of the map in pixels |
| `logo_path` | – | only to use your own PNG files instead of the logo pack (see below) |

Texts follow the language chosen in the setup. If the card does not show up after an update, reload the browser page (Ctrl+F5).

### Place the parts where you want

Use several cards with `show` to put each part anywhere in a dashboard, with other cards in between:

```yaml
type: custom:ceny-paliv-card
fuel: n95
show: [home]          # only my station
---
type: custom:ceny-paliv-card
fuel: n95
show: [list]
stations: 3
compact: true         # small tile with the 3 cheapest stations
---
type: custom:ceny-paliv-card
fuel: n95
show: [map, graph]
map_height: 260
```

(The three cards are separate; `---` only separates them here.) In a *sections* dashboard the card also resizes itself to its content.

### More cards for a dashboard

Besides the main card, the integration brings smaller cards, also in the card picker (search "Ceny paliv"). Each shows one area; with several areas choose one in its editor (`config_id`).

| Card | What it shows | Options |
|---|---|---|
| `custom:ceny-paliv-fuels-card` | every fuel of the area at a glance: the cheapest price and station, your station's price, the trend since yesterday | `fuels` (which and in what order; default all) |
| `custom:ceny-paliv-savings-card` | what a full tank costs at your station, at the cheapest one and at the area's average price, how much you save, and whether the longer drive to the cheapest pays off | `fuel` (required), `tank_litres` (40; kg for CNG), `consumption` (6.5 per 100 km) |
| `custom:ceny-paliv-compare-card` | your station, the area, your region and the Czech Republic side by side as bars, each against the country, and the 14 regions from the cheapest | `fuel` (required), `show_regions` (true) |
| `custom:ceny-paliv-regions-card` | a map of the 14 regions coloured from the cheapest (green) to the dearest (red), your region outlined; tap a region for its price and rank | `fuel` (required) |
| `custom:ceny-paliv-stations-map-card` | the area's up-to-date stations as dots coloured from the cheapest to the dearest, around the area's centre and circle (or the town's stations), with the regions' borders behind; the five cheapest and yours carry their price, and a tap opens the station's details and navigation. A drawn map, not map tiles: for streets use the main card's map | `fuel` (required) |

```yaml
type: custom:ceny-paliv-savings-card
fuel: n95
tank_litres: 45
consumption: 7.2
```

**A badge** for the top of a dashboard (Edit dashboard → Add badge → Ceny paliv): `custom:ceny-paliv-badge` with `fuel` and `price: cheapest` (default), `mine` or `area` (the area average). **A tile card feature**: under a tile card of a Ceny paliv sensor, add the feature "Ceny paliv: price details" (`type: custom:ceny-paliv-price-feature`); it shows in one line what that sensor says, with the trend since yesterday: the cheapest station for the top5 sensor, your station's rank and how much more it costs for the favourite, the region and the difference from the country for an average.

```yaml
type: tile
entity: sensor.ceny_paliv_n95_home
features:
  - type: custom:ceny-paliv-price-feature
```

The drive is counted only when the cheapest station is farther than yours: twice the extra distance (there and back, in a straight line) at your consumption and the cheapest price.

For a notification when your station's price changes, see `examples/price_alert.yaml`.

## 4. Station logos (optional)

The card shows a round logo for the chain of each station. Without a logo it draws a coloured badge with the initials of the chain (`OR`, `PR`…), so nothing has to be set up.

To have the real logos, open **Settings → Devices & services → Ceny paliv → Configure** and go to the **Station logos** step: tick the chains you want. They are downloaded (a few KB each) from the [logo pack](logos/) in this repository into the folder `ceny_paliv_logos` of your Home Assistant configuration and the card finds them by itself. Untick a chain to remove its logo. The chains of your city are preselected the first time. Nothing is downloaded unless you tick it, and the pack is not installed with the integration.

The pack is also published as **`ceny-paliv-logos.zip`** in each [release](https://github.com/Vituhlos/ha-ceny-paliv/releases): unzip it into `<config>/ceny_paliv_logos/` if you prefer to do it by hand (restart or reload the integration to pick up new files). You can drop your own square PNG there too, named after the chain in lower case, without accents, with dashes for spaces (`eurobit.png`, `robin-oil.png`): such files are used and never deleted. To use files from another folder, set `logo_path: /local/logos/` on the card (files named like the chain, for example `/local/logos/orlen.png`).

The logos are trademarks of their owners, used only to identify the stations; this project is not affiliated with them. The sources and the removal policy are in [logos/SOURCES.md](logos/SOURCES.md).

## 5. Without the card: standard cards

Every sensor has a fixed, translated name (for example `Natural 95 · cheapest #1`); the readable title of the station it currently shows (for example `Benzina · Karlovarská`) is in its `station` attribute and follows the ranking at each refresh, while the entity ids stay the same. The one exception is the favourite sensor: choosing a different favourite station creates a new one (for example `_home_2`), so the statistics of two stations are never mixed (see Notes).

An **Entities** card with the 5 cheapest stations (the sensor state is the price):

```yaml
type: entities
title: Natural 95
entities:
  - sensor.ceny_paliv_n95_1
  - sensor.ceny_paliv_n95_2
  - sensor.ceny_paliv_n95_3
  - sensor.ceny_paliv_n95_4
  - sensor.ceny_paliv_n95_5
```

A **Markdown** card with the address and a Google Maps link:

```yaml
type: markdown
title: Natural 95 – top 5
content: |-
  {% for s in (state_attr('sensor.ceny_paliv_n95_top5', 'stations') or []) %}
  {{ s.rank }}. **{{ s.name }}** – {{ s.street }}: **{{ '%.2f' | format(s.price) }} Kč/l** · [Maps]({{ s.maps }})
  {% endfor %}
```

Each station in `stations` has `rank`, `name`, `title`, `street`, `city`, `address`, `price`, `lat`, `lng`, `updated`, `maps`, `home` and `trends`; GPS entries also include `distance_km` (see [Attributes](#attributes)). The top5 sensor's `gps_area` attribute contains the method, centre, radius, selected zone (if any), any location error, and the total number of markers with valid coordinates in the circle. `gps_nearest_stations` is a separate, compact list of at most 10 nearby stations; it does not duplicate map links or trend histories. Provider-controlled text in GPS station attributes is capped to keep the complete state attributes below Home Assistant Recorder's 16 KiB limit. Use the `_home` sensor for your favourite station (its attributes include `rank`, `vs_cheapest`, `trends`, and—when inside the GPS area—`distance_km`).

Changing a favourite to a different station gives it a station-specific statistics identity. The previous home sensor remains registered as an archived entity so its Home Assistant long-term statistics are not combined with a different station; archived sensors are diagnostic entities, kept out of automatic dashboards and disabled (enable one in its entity settings to look at its history), and choosing that station again re-enables it; removing a fuel in **Configure** removes its sensors, archived ones included; returning to a previously selected station reuses only that station's verified identity. GPS trend history uses full marker URLs and records new samples only for the current five cheapest stations and selected favourite. Samples for stations that temporarily leave the displayed five are retained until the existing 35-day expiry and can be used again if the station returns; expired or empty URL-keyed logs are pruned on refresh. New City trend history is also keyed by full marker URL so equal slugs in different cities cannot share prices. Trend history from versions up to 0.4.x (keyed by station slug) moves to the station URL on the first refresh that shows the entry's original city, when exactly one station there has that slug, so upgrading keeps your trends; ambiguous legacy logs are never assigned to a station and expire after 35 days. If a saved favourite cannot be uniquely resolved in nationwide markers, it is retained until you explicitly choose a station.

After an explicit favourite change, Home Assistant may give the new home sensor a suffixed entity ID because the old ID remains attached to its archived statistics. The dashboard card resolves the current sensor automatically; standard YAML cards that refer directly to the old `_home` entity should be updated to the new home sensor entity ID.

## Actions

### `ceny_paliv.refresh` — refresh the prices now

Loads the prices from mBenzin.cz without waiting for the next six-hourly refresh, for example before a trip.

| Field | Required | What it does |
|---|---|---|
| `config_entry_id` | no | The area to refresh (pick it in the action editor). Without it, every area is refreshed. |

- Prices downloaded less than **30 minutes** ago are reused, so calling it often does not flood mBenzin.cz; during an HTTP 429 cooldown nothing is downloaded.
- If mBenzin.cz does not answer, prices still within their lifetime are kept and the action reports them as kept; a fuel with no prices left fails, and its sensors become unavailable.
- The action fails with a message when an area does not exist or is not running, or when some prices could not be refreshed (it names the area and fuel).

```yaml
action: ceny_paliv.refresh
data:
  config_entry_id: 01JC0EXAMPLE  # optional: the area picked in the action editor
```

## Blueprints

Ready-made automations: import one with its button (or **Settings → Automations & scenes → Blueprints → Import blueprint** with the file's link), then create an automation from it. Each one lets you choose the message language (English or Czech) and what to do, for example a notification to your phone with `{{ title }}` and `{{ message }}`; by default it creates a notification in Home Assistant.

| Blueprint | What it does | |
|---|---|---|
| [Favourite station price change](blueprints/automation/ceny_paliv/favourite_price_change.yaml) | your favourite station got cheaper (or dearer too), by at least your smallest change; uses the price-change events | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FVituhlos%2Fha-ceny-paliv%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fceny_paliv%2Ffavourite_price_change.yaml) |
| [Price under a limit](blueprints/automation/ceny_paliv/price_below_limit.yaml) | a price (the area's cheapest, your favourite or an average) dropped under your limit; once per crossing | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FVituhlos%2Fha-ceny-paliv%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fceny_paliv%2Fprice_below_limit.yaml) |
| [Cheap station nearby](blueprints/automation/ceny_paliv/cheap_station_nearby.yaml) | while you are away from home, the cheapest station of a GPS area within your price and distance, with a pause between messages; best with an area that follows you | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FVituhlos%2Fha-ceny-paliv%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fceny_paliv%2Fcheap_station_nearby.yaml) |

## Examples

**A notification when your station's price changes** — a complete automation is in [`examples/price_alert.yaml`](examples/price_alert.yaml).

**A notification when the cheapest Natural 95 drops below 35 Kč/l:**

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.ceny_paliv_n95_top5
    below: 35
actions:
  - action: notify.mobile_app_YOUR_PHONE
    data:
      title: "⛽ Natural 95 under 35 Kč"
      message: >-
        {% set s = state_attr('sensor.ceny_paliv_n95_top5', 'stations')[0] %}
        {{ s.title }}: {{ '%.2f' | format(s.price) }} Kč/l
```

**A notification when your favourite station is the cheapest:**

```yaml
triggers:
  - trigger: template
    value_template: "{{ state_attr('sensor.ceny_paliv_n95_home', 'vs_cheapest') | float(1) <= 0 }}"
actions:
  - action: notify.mobile_app_YOUR_PHONE
    data:
      message: "Your station is the cheapest today: {{ states('sensor.ceny_paliv_n95_home') }} Kč/l"
```

**Fresh prices before a trip** (a script; the refresh reports what it could not refresh, so it is allowed to fail):

```yaml
sequence:
  - action: ceny_paliv.refresh
    continue_on_error: true
  - action: notify.mobile_app_YOUR_PHONE
    data:
      message: >-
        Cheapest Diesel: {{ states('sensor.ceny_paliv_diesel_top5') }} Kč/l
        ({{ (state_attr('sensor.ceny_paliv_diesel_top5', 'stations') or [{'name': 'no data'}])[0].name }})
```

Replace `notify.mobile_app_YOUR_PHONE` with your notify action, and the entity ids with yours (Settings → Entities, search "Ceny paliv").

## Upgrading from 0.5

Nothing to do: update in HACS and restart Home Assistant. Entity ids, history, statistics, settings and dashboard cards
carry over. What happens on the first start:

- Each area becomes a device and its sensors move under it; their names come from the translations (for example
  `Natural 95 · cheapest #1` instead of the station's name, which is now in the `station` attribute).
- An automatic area title with a run of spaces is tidied ("Ceny paliv Brandys nad Labem Stara Boleslav").
- Archived favourite sensors become diagnostic entities.
- The favourite station's price history starts its station statistics, filled with up to 35 days already stored.
- From now on a fuel's sensors are **unavailable** while mBenzin.cz cannot be reached (they kept the last price
  before); automations that read them may need a condition. The card still shows the last known prices.
- If you added `donthedandy/ha-ceny-paliv` to HACS, replace it with `https://github.com/Vituhlos/ha-ceny-paliv`.

## Removing the integration

1. **Settings → Devices & services → Ceny paliv**, then **⋮ → Delete** for each configured area. Its sensors and its stored price history are deleted with it. The long-term statistics of your favourite stations stay in Home Assistant (to delete them: **Developer tools → Statistics**, search `ceny_paliv`).
2. Remove the `custom:ceny-paliv-card` cards from your dashboards. The card is served by the integration, so there is nothing else to uninstall.
3. **HACS → Ceny paliv → ⋮ → Remove**, then restart Home Assistant.
4. Optionally delete the folder `ceny_paliv_logos` in your Home Assistant configuration folder: downloaded logos are not removed automatically.

## Known limitations

- **Unofficial data source**: the prices come from mBenzin.cz's price map, not a documented public API, and need a personal key from mBenzin.cz. mBenzin.cz has not confirmed any request limit.
- **Prices are as fresh as the stations make them**: each station updates its price on mBenzin.cz itself, small ones rarely. Older prices are hidden (or shown with their date with "Show older prices too").
- **E10** is not distinguished: "Natural 95" is the price of 95-octane petrol.
- Czech Republic only; the seven fuels mBenzin.cz publishes; at most **5 stations** per fuel and area; GPS radius 5–50 km.
- Automatic refresh every **6 hours**; faster only by the refresh action, and not more often than every 30 minutes.
- After a Home Assistant restart while mBenzin.cz is down, the area cannot start until prices arrive (Home Assistant retries by itself), and the card shows its "unavailable" message.
- The card remembers the last known prices **per browser**: another device or a private window shows nothing during an outage.
- Trends need history: they start the day after setup and reach 30 days after a month (a `*` marks a shorter history).
- Sensor names are fixed (for example "Natural 95 · cheapest #1"); the station is in the `station` attribute.
- A station without an address at mBenzin.cz shows its street and town without accents (taken from its link).
- Texts in English and Czech only.

## Troubleshooting

| Problem | What to do |
|---|---|
| "mBenzin did not accept the key" or a **Reauthenticate** prompt | Paste the whole key, without spaces (⋮ → Reconfigure). If it still fails, ask reklama@mbenzin.cz whether the key is active. |
| "temporarily rate-limited (HTTP 429)" | Wait: the integration waits for mBenzin.cz by itself. Do not call `ceny_paliv.refresh` in a loop. |
| Sensors are **unavailable** | mBenzin.cz did not answer for that fuel. They come back with the next successful refresh; after 24 hours **Settings → Repairs** explains what to check. |
| **No stations** in a GPS area | Check **Settings → Repairs** (deleted zone, invalid location); a larger radius; "Show older prices too" for areas with rarely updated stations. |
| The favourite station shows **an old price** or is "not ranked" | The station has not updated its price on mBenzin.cz; it is ranked again once it does. |
| The card asks to **choose an area** | The same fuel is set up in more than one area: pick the area in the card editor (`config_id`). |
| The card is missing or looks old after an update | Reload the browser page (Ctrl+F5). |

To look deeper: **Settings → Devices & services → Ceny paliv → ⋮ → Enable debug logging**, reproduce the problem, then **Disable debug logging** to download the log. Attach it to an [issue](https://github.com/Vituhlos/ha-ceny-paliv/issues) together with the diagnostics (below). Neither contains your key.

## Notes

- **E10** is not distinguished by mBenzin: "Natural 95" is the price shown for 95-octane petrol.
- Entity ids are `sensor.ceny_paliv_<fuel>_…`; a second configuration for the same fuel receives distinct Home Assistant entity IDs. Use `config_id` to bind a dashboard card to one area.
- The daily price log used for the trends is stored by Home Assistant and fills up over time (a `*` next to a trend in the card marks a trend computed from a shorter history).
- **Settings → Repairs** tells you when something needs you: a fuel without prices from mBenzin.cz for more than 24 hours (check the website and your key), a deleted zone or person the GPS area was centred on, or a GPS centre without valid coordinates. The message disappears by itself once the cause is gone.
- To report a problem, attach the diagnostics: **Settings → Devices & services → Ceny paliv → ⋮ → Download diagnostics**. The file shows the settings and how the last refresh of each fuel went; the access key, the GPS centre and the favourite stations are replaced by `**REDACTED**`, and the station lists are left out. It also lists the fields mBenzin.cz sends for a station, with one example: the first station of the nationwide list, never one of your area.

## Development tests

Use Python 3.12 and install `requirements_test.txt`, then run `python -m pytest`.
The tests use simulated data and block network sockets; no mBenzin key is needed.
CI also tests Python 3.14 with `requirements_test_latest.txt`. These requirements pin
the test framework, which in turn pins Home Assistant 2025.1.0 and 2026.10.4 respectively.
The Home Assistant frontend and HTTP server are mocked in integration tests.
The card has its own tests without dependencies: `node --test tests/test_card.js` (Node 22+). To look at it without Home Assistant, serve the repository (`python -m http.server 8765`) and open `http://localhost:8765/tools/card-demo.html?theme=dark&lang=cs` (made-up data; `theme`, `lang`, `width`, `compact`, `show`).
The region boundaries in `custom_components/ceny_paliv/regions.json` are built by `python script/build_regions.py` from ČÚZK's download service.
CI additionally runs hassfest, the HACS validation, ruff, `mypy --strict custom_components/ceny_paliv` (with the Home Assistant 2026.10 pin) and a check that the manifest and card versions match.

## 🇨🇿 Česky

Úplný český popis (získání klíče, instalace přes HACS, senzory, dashboard) najdete v **[README.cs.md](README.cs.md)**. Stručně: klíč zdarma na reklama@mbenzin.cz, HACS → Vlastní repozitáře → `https://github.com/Vituhlos/ha-ceny-paliv` (Integrace) → restart → Přidat integraci **Ceny paliv**.

## License

MIT — see [LICENSE](LICENSE).

The region boundaries (`regions.json`) are derived from RÚIAN data by ČÚZK (Český úřad zeměměřický a katastrální), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); simplified.
