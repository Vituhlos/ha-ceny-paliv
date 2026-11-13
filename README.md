<p align="center"><img src="https://raw.githubusercontent.com/donthedandy/ha-ceny-paliv/main/docs/logo.png" alt="Ceny paliv" width="420"></p>

# ⛽ Ceny paliv – Czech fuel prices for Home Assistant

**English** · [Česky](README.cs.md)

A HACS integration that shows the cheapest stations in **your city** or a **5–50 km GPS area** for the fuel(s) you use — **Natural 95, Diesel, LPG, CNG** and more — plus **your favourite station** with price history and trends. Everything is configured from the Home Assistant UI.

![Dashboard](docs/screenshot.webp)

> **Ceny paliv** (Czech for “fuel prices”) is an independent project. The prices come from [mBenzin.cz](https://www.mbenzin.cz); this project is not made, endorsed or supported by mBenzin.cz.

## Features

- Pick your **city**, one or **several fuels** (e.g. Natural 95 + LPG for a dual-fuel car) and a **favourite station per fuel**
- Or choose a GPS area centred on Home Assistant's configured home location, a saved `zone.*`, a point selected on Home Assistant's map, or (advanced) manually entered coordinates; choose a **5–50 km** radius (default **40 km**). No phone location, GPS tracker, geocoder, or extra mBenzin request is used
- Per fuel: the **top 5 cheapest** stations in the city (only that city, not the region), with a Google Maps link, and a **map**
- Favourite station: price, **trends vs 1/2/7/14/30 days ago**, rank in town, long-term statistics (the 30-day graph)
- A ready-made **dashboard card** (`ceny-paliv-card`) shipped with the integration — add it from the card picker, no YAML to copy — in **English or Czech** (your choice during setup). It is **flexible**: two columns on a wide dashboard, one on a phone, a compact version, and every part (favourite station, list, map, graph) can be placed as its own card
- Optional **station logos** (Orlen, MOL, Shell, Tesco…): tick the chains you want in the setup and they are downloaded for you. Chains without a logo get a colour badge with their initials
- Stale prices are hidden (older than yesterday for petrol/diesel, 3 days for CNG, 7 days for LPG/AdBlue)

## 1. Get your access key (free)

mBenzin blocks plain scraping with a browser check, but they give a **personal access key** to Home Assistant users. E-mail **reklama@mbenzin.cz** and tell them what the prices are for, which city/stations, and how often you load them. (For me the answer came quickly and the key worked immediately.)

- The key is **personal — never share it or publish it**. Everyone requests their own.
- To change the key, open the integration's ⋮ menu → **Reconfigure**. If mBenzin.cz stops accepting it (HTTP 401/403, or its HTML refusal page on two refreshes in a row), Home Assistant shows a **Reauthenticate** prompt. Either way, settings, price history and sensors stay.
- The provider has not confirmed a request limit for this integration. Automatic refreshes remain every **6 hours**, and requests for the same key and fuel are shared across configurations. This deduplication and the temporary HTTP 429 cooldown are not a per-key request quota; no persistent quota is enforced. A true quota would require a provider-confirmed limit and persistent tracking. After HTTP 429, all fuels for that key wait for a valid `Retry-After` value (capped at 24 hours) or just under 6 hours when none is provided; this in-memory cooldown is cleared by a Home Assistant restart.
- The key is sent in an HTTP header, not in the request URL.
- It uses mBenzin's price-map data, which is not a documented public API: be gentle and respect their conditions.

## 2. Install with HACS

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/donthedandy/ha-ceny-paliv`, category **Integration**.
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

## Entities

For each fuel `<fuel>` (`n95`, `benzinplus`, `diesel`, `dieselplus`, `lpg`, `cng`, `adblue`):

| Entity | What |
|---|---|
| `sensor.ceny_paliv_<fuel>_top5` | price of the cheapest station; attributes: the 5 cheapest stations (name, address, price, coordinates, Google Maps link, trends…). GPS mode also provides `gps_area` metadata and at most 10 compact `gps_nearest_stations` summaries ordered by distance |
| `sensor.ceny_paliv_<fuel>_home` | price at your favourite station (only if you chose one); trends, rank, statistics |
| `sensor.ceny_paliv_<fuel>_1` … `_5` | the 5 cheapest stations, with latitude/longitude for the map card |

The position sensors are named after the station they currently show (for example `1 · Orlen – Bratri Stefanu 69`); existing entity IDs remain stable when changing area mode. Prices refresh every 6 hours. If a refresh fails (for example HTTP 429) the last data is kept and the attribute `fetch_error` says why. Nationwide data is shared between configurations with the same key and fuel for just under 6 hours, so every scheduled refresh downloads fresh data. GPS filtering and the in-area favourite selector use that same snapshot; changing the area does not create another mBenzin request. Manual refreshes and integration reloads reuse this in-memory cache; restarting Home Assistant clears it. Cached relative freshness labels are interpreted against the original response time in the Czech timezone, not the later cache-use time.

## 3. The dashboard card (included, nothing else to install)

The integration ships its own card, **`ceny-paliv-card`**. After installing (and restarting) just:

1. Open a dashboard → **Edit** → **Add card** → search **Ceny paliv**.
2. Pick the **fuel** (the visual editor lists the fuels you set up). Done.

Or in YAML:

```yaml
type: custom:ceny-paliv-card
fuel: n95            # n95 | benzinplus | diesel | dieselplus | lpg | cng | adblue
```

One card per fuel: for a dual-fuel car add a second card with `fuel: lpg`. The card has four parts: your favourite station (price, trends, rank), the top 5 with a Google Maps link on tap, a map and the 30-day graph. Everything below is also in the card's visual editor. If the same fuel has multiple Ceny paliv configurations, select the intended configuration in the visual editor (or set `config_id` from the top5 sensor's `cp_config_id` in YAML); a card without an explicit configuration will not mix entities from different areas.

| Option | Default | |
|---|---|---|
| `fuel` | – | required |
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

For a notification when your station's price changes, see `examples/price_alert.yaml`.

## 4. Station logos (optional)

The card shows a round logo for the chain of each station. Without a logo it draws a coloured badge with the initials of the chain (`OR`, `PR`…), so nothing has to be set up.

To have the real logos, open **Settings → Devices & services → Ceny paliv → Configure** and go to the **Station logos** step: tick the chains you want. They are downloaded (a few KB each) from the [logo pack](logos/) in this repository into the folder `ceny_paliv_logos` of your Home Assistant configuration and the card finds them by itself. Untick a chain to remove its logo. The chains of your city are preselected the first time. Nothing is downloaded unless you tick it, and the pack is not installed with the integration.

The pack is also published as **`ceny-paliv-logos.zip`** in each [release](https://github.com/donthedandy/ha-ceny-paliv/releases): unzip it into `<config>/ceny_paliv_logos/` if you prefer to do it by hand (restart or reload the integration to pick up new files). You can drop your own square PNG there too, named after the chain in lower case, without accents, with dashes for spaces (`eurobit.png`, `robin-oil.png`): such files are used and never deleted. To use files from another folder, set `logo_path: /local/logos/` on the card (files named like the chain, for example `/local/logos/orlen.png`).

The logos are trademarks of their owners, used only to identify the stations; this project is not affiliated with them. The sources and the removal policy are in [logos/SOURCES.md](logos/SOURCES.md).

## 5. Without the card: standard cards

Every sensor is named after what it currently shows (for example `1 · Orlen – Bratri Stefanu 69`), so any standard card displays the station without a template. The names follow the ranking and update at each refresh; the entity ids never change.

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

Each station in `stations` has `rank`, `name`, `street`, `address`, `price`, `lat`, `lng`, `updated`, `maps`, `home` and `trends`; GPS entries also include `distance_km`. The top5 sensor's `gps_area` attribute contains the method, centre, radius, selected zone (if any), any location error, and the total number of markers with valid coordinates in the circle. `gps_nearest_stations` is a separate, compact list of at most 10 nearby stations; it does not duplicate map links or trend histories. Provider-controlled text in GPS station attributes is capped to keep the complete state attributes below Home Assistant Recorder's 16 KiB limit. Use the `_home` sensor for your favourite station (its attributes include `rank`, `vs_cheapest`, `trends`, and—when inside the GPS area—`distance_km`).

Changing a favourite to a different station gives it a station-specific statistics identity. The previous home sensor remains registered as an archived entity so its Home Assistant long-term statistics are not combined with a different station; newly archived sensors are disabled (enable one in its entity settings to look at its history), and choosing that station again re-enables it; returning to a previously selected station reuses only that station's verified identity. GPS trend history uses full marker URLs and records new samples only for the current five cheapest stations and selected favourite. Samples for stations that temporarily leave the displayed five are retained until the existing 35-day expiry and can be used again if the station returns; expired or empty URL-keyed logs are pruned on refresh. New City trend history is also keyed by full marker URL so equal slugs in different cities cannot share prices. Trend history from versions up to 0.4.x (keyed by station slug) moves to the station URL on the first refresh that shows the entry's original city, when exactly one station there has that slug, so upgrading keeps your trends; ambiguous legacy logs are never assigned to a station and expire after 35 days. If a saved favourite cannot be uniquely resolved in nationwide markers, it is retained until you explicitly choose a station.

After an explicit favourite change, Home Assistant may give the new home sensor a suffixed entity ID because the old ID remains attached to its archived statistics. The dashboard card resolves the current sensor automatically; standard YAML cards that refer directly to the old `_home` entity should be updated to the new home sensor entity ID.

## Notes

- **E10** is not distinguished by mBenzin: "Natural 95" is the price shown for 95-octane petrol.
- Entity ids are `sensor.ceny_paliv_<fuel>_…`; a second configuration for the same fuel receives distinct Home Assistant entity IDs. Use `config_id` to bind a dashboard card to one area.
- The daily price log used for the trends is stored by Home Assistant and fills up over time (a `*` next to a trend in the card marks a trend computed from a shorter history).

## Development tests

Use Python 3.12 and install `requirements_test.txt`, then run `python -m pytest`.
The tests use simulated data and block network sockets; no mBenzin key is needed.
CI also tests Python 3.14 with `requirements_test_latest.txt`. These requirements pin
the test framework, which in turn pins Home Assistant 2025.1.0 and 2026.10.4 respectively.
The Home Assistant frontend and HTTP server are mocked in integration tests.

## 🇨🇿 Česky

Úplný český popis (získání klíče, instalace přes HACS, senzory, dashboard) najdete v **[README.cs.md](README.cs.md)**. Stručně: klíč zdarma na reklama@mbenzin.cz, HACS → Vlastní repozitáře → `https://github.com/donthedandy/ha-ceny-paliv` (Integrace) → restart → Přidat integraci **Ceny paliv**.

## License

MIT — see [LICENSE](LICENSE).
