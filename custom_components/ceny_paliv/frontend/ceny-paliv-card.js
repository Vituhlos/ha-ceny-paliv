/*
 * Ceny paliv cards — shipped with the Ceny paliv integration, nothing to install separately.
 *
 *   custom:ceny-paliv-card          one fuel: your station, the cheapest stations, map and graph (below)
 *   custom:ceny-paliv-fuels-card    every fuel of an area at a glance (config_id, fuels)
 *   custom:ceny-paliv-savings-card  what a full tank costs and how much you save (fuel, config_id, tank_litres, consumption)
 *   custom:ceny-paliv-compare-card  your station, the area, the region and the country, and the 14 regions (fuel, config_id)
 *   custom:ceny-paliv-regions-card  a map of the 14 regions coloured by their average price (fuel, config_id)
 *   custom:ceny-paliv-stations-map-card  the area's stations as coloured prices around its centre (fuel, config_id)
 *   custom:ceny-paliv-areas-card    one fuel in every area: where it is cheapest (fuel)
 *   custom:ceny-paliv-road-card     the nearest stations, large, with a navigate button (fuel, config_id, stations, navigator)
 *   custom:ceny-paliv-big-card      one price, large, for a wall tablet (fuel, config_id, price: cheapest | mine | area)
 *   custom:ceny-paliv-changes-card  the last price changes from the price-change events (fuel, config_id, days)
 *   custom:ceny-paliv-trend-card    the change over 7 and 14 days: the area average, your station, the cheapest (fuel, config_id)
 *   custom:ceny-paliv-badge         a dashboard badge with a price (fuel, price: cheapest | mine | area, config_id)
 *   custom:ceny-paliv-price-feature a tile card feature for a Ceny paliv sensor: the station, rank or comparison, the trend
 *
 * Prices come from mBenzin.cz; this project is independent and not affiliated with mBenzin.
 *
 *   type: custom:ceny-paliv-card
 *   fuel: n95            # n95 | benzinplus | diesel | dieselplus | lpg | cng | adblue
 *
 * Optional (all of them are also in the visual editor: Add card > Ceny paliv):
 *   fuels: [n95, diesel] # a switch between these fuels at the top of the card (fuel: the one shown first)
 *   sort: price          # price | distance | worth (the price with the fuel burnt driving there and back)
 *   tank_litres: 40      # for "worth": how much you fill up (CNG: kg)
 *   consumption: 6.5     # for "worth": your car's consumption in l/100 km (CNG: kg/100 km)
 *   show: [home, list, map, graph]   # which parts to draw; use several cards to place them freely
 *   layout: auto         # auto = 2 columns when the card is wide | columns | stack
 *   stations: 5          # 1-5 stations in the list
 *   compact: false       # dense version: one line per station, short footer
 *   show_footer: true    # update times, legend (default: false when compact)
 *   map_height: 300      # px, default: the map card's own height
 *   logo_path: /local/   # only to use your own PNG files instead of the downloaded logo pack
 *
 * Tap a station for its details and navigation (Mapy.com, Google Maps, Waze); long-press for your station's history.
 *
 * Station logos: tick the chains in the integration's setup (Configure > Station logos); the card finds them by
 * itself. Chains without a logo get a coloured badge with their initials.
 *
 * Texts come from the language chosen in the integration setup (attribute `labels` of the top5 sensor).
 */
const CARD_VERSION = '0.8.0';

const PARTS = ['home', 'list', 'map', 'graph'];

// Parts a config shows. show_map / show_graph: options of the first versions, still honoured when `show` is not set.
function shownParts(config) {
  const legacy = PARTS.filter((p) => !(p === 'map' && config.show_map === false) && !(p === 'graph' && config.show_graph === false));
  const show = (Array.isArray(config.show) ? config.show : config.show ? [config.show] : legacy).filter((p) => PARTS.includes(p));
  return show.length ? show : PARTS;
}

// What the card uses for an option the config does not set (the editor shows these, but never saves them).
function editorDefaults(config) {
  return {
    fuels: [], show: shownParts(config), layout: 'auto', stations: 5, compact: false, show_footer: !config.compact, map_height: 0,
    sort: 'price', tank_litres: 40, consumption: 6.5,
  };
}

// Fuels a config can switch between: `fuels`, with `fuel` first when it is not in the list. One fuel: no switch.
function switchFuels(config) {
  const list = (Array.isArray(config.fuels) ? config.fuels : []).map(String).filter(Boolean);
  if (config.fuel && !list.includes(config.fuel)) list.unshift(config.fuel);
  return list.filter((f, i) => list.indexOf(f) === i);
}

// Orders of the station list. "worth" is the price per litre with the fuel burnt driving there and back included:
// price + 2 × km × consumption / 100 × price / tank. Plain arithmetic, no route: the distance is a straight line.
const SORTS = ['price', 'distance', 'worth'];
const withDrive = (price, km, tank, consumption) => price + (2 * km * consumption / 100) * price / tank;

// Kilometres in a straight line (haversine), for stations the integration gives no distance for.
function kmBetween(lat1, lng1, lat2, lng2) {
  const rad = Math.PI / 180;
  const a = Math.sin((lat2 - lat1) * rad / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin((lng2 - lng1) * rad / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.min(1, Math.sqrt(a)));
}

// ------------------------------------------------------------------ the 30-day graph
const GRAPH_DAYS = 30;
const GRAPH_HEIGHT = 160;
const GRAPH_PAD = { left: 40, right: 8, top: 8, bottom: 20 };

const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

// The days of the graph, oldest first, ending with `today` (local days, as the recorder's daily rows).
function graphDays(today, count) {
  const out = [];
  for (let i = count - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    out.push(isoDay(d));
  }
  return out;
}

// One value per local day from the recorder's daily statistics (`start` in ms, or ISO on older versions).
function calendarDay(date, timeZone) {
  return timeZone ? date.toLocaleDateString('sv-SE', { timeZone }) : isoDay(date);
}

function dailyValues(rows, type, timeZone) {
  const out = {};
  for (const r of Array.isArray(rows) ? rows : []) {
    const v = Number(r && r[type]);
    const start = typeof r.start === 'number' ? r.start : Date.parse(r.start);
    if (r[type] == null || !isFinite(v) || !isFinite(start)) continue;
    out[calendarDay(new Date(start), timeZone)] = v;
  }
  return out;
}

// The chart's geometry: a path per series (broken where a day has no value), dots for days with no neighbour,
// and a y range in half-crowns with three labels. Null when there is nothing to draw.
function chartModel(series, days, width) {
  const values = [];
  for (const s of series) for (const d of days) if (s.values[d] != null) values.push(s.values[d]);
  if (!values.length) return null;
  let lo = Math.floor(Math.min(...values) * 2) / 2;
  let hi = Math.ceil(Math.max(...values) * 2) / 2;
  if (hi - lo < 1) { const mid = (lo + hi) / 2; lo = mid - 0.5; hi = mid + 0.5; }
  hi = lo + Math.ceil(hi - lo);  // a whole number of crowns: the middle label falls on a half crown, never on 39.25
  const p = GRAPH_PAD;
  const step = days.length > 1 ? (width - p.left - p.right) / (days.length - 1) : 0;
  const x = (i) => p.left + i * step;
  const y = (v) => p.top + (hi - v) * (GRAPH_HEIGHT - p.top - p.bottom) / (hi - lo);
  const lines = series.map((s) => {
    let path = '';
    const dots = [];
    days.forEach((day, i) => {
      const v = s.values[day];
      if (v == null) return;
      const before = i > 0 && s.values[days[i - 1]] != null;
      const after = i < days.length - 1 && s.values[days[i + 1]] != null;
      path += `${before ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      if (!before && !after) dots.push([x(i), y(v)]);
    });
    return { path, dots };
  });
  return { lo, hi, ticks: [hi, (lo + hi) / 2, lo].map((v) => ({ v, y: y(v) })), lines, x, step };
}

// Navigation to a station. Mapy.com takes "lon,lat", Waze and Google Maps "lat,lng" (their URL documentation).
function navigationLinks(s) {
  const lat = Number(s && s.lat);
  const lng = Number(s && s.lng);
  if (!isFinite(lat) || !isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return [];
  return [
    { label: 'Mapy.com', icon: 'mdi:map-legend', url: `https://mapy.com/fnc/v1/route?end=${lng},${lat}&routeType=car_fast` },
    { label: 'Google Maps', icon: 'mdi:google-maps', url: `https://www.google.com/maps/dir/?api=1&destination=${lat}%2C${lng}&travelmode=driving` },
    { label: 'Waze', icon: 'mdi:waze', url: `https://waze.com/ul?ll=${lat}%2C${lng}&navigate=yes` },
  ];
}

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const norm = (s) => String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();

const STYLE = `
  :host {
    display: block;
    /* every colour comes from the Home Assistant theme, so light, dark and custom themes all work */
    --cp-text: var(--primary-text-color, #212121);
    --cp-muted: var(--secondary-text-color, #727272);
    --cp-line: var(--divider-color, rgba(0, 0, 0, 0.12));
    --cp-surface: var(--ha-card-background, var(--card-background-color, #fff));
    --cp-neutral: var(--disabled-color, #bdbdbd);
    --cp-home: var(--primary-color, #03a9f4);
    --cp-fuel: var(--orange-color, #ff9800);
    --cp-good-base: var(--success-color, #43a047);
    --cp-warn-base: var(--warning-color, #ffa600);
    --cp-bad-base: var(--error-color, #db4437);
    /* status text mixed with the text colour: darker on a light card, lighter on a dark one, readable on both */
    --cp-good: color-mix(in srgb, var(--cp-good-base) 80%, var(--cp-text));
    --cp-warn: color-mix(in srgb, var(--cp-warn-base) 70%, var(--cp-text));
    --cp-bad: color-mix(in srgb, var(--cp-bad-base) 80%, var(--cp-text));
    --cp-radius: var(--ha-card-features-border-radius, var(--ha-border-radius-lg, 12px));
  }
  .grid, .col { display: flex; flex-direction: column; gap: var(--ha-space-4, 16px); }
  .col { min-width: 0; }
  .grid.columns { flex-direction: row; align-items: flex-start; }
  .grid.columns > .col { flex: 1 1 0; }
  .grid.auto.wide { flex-direction: row; align-items: flex-start; }
  .grid.auto.wide > .col { flex: 1 1 0; }
  .card {
    display: flex; flex-direction: column; gap: var(--ha-space-3, 12px);
    padding: var(--ha-space-4, 16px); box-sizing: border-box;
    font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif); color: var(--cp-text);
    -webkit-font-smoothing: antialiased;
  }
  .card.compact { gap: var(--ha-space-2, 8px); padding: var(--ha-space-3, 12px); }
  .card.home { cursor: pointer; outline: none; }
  .card.home:focus-visible { box-shadow: inset 0 0 0 2px var(--cp-home); }
  .muted { color: var(--cp-muted); }
  .good { color: var(--cp-good); }
  .warn { color: var(--cp-warn); }
  .bad { color: var(--cp-bad); }
  .num { font-variant-numeric: tabular-nums; }
  a { color: inherit; }
  ha-icon { display: inline-flex; }

  /* header: the tile card's icon and two lines, with the price on the right */
  .head { display: flex; align-items: center; gap: var(--ha-space-3, 12px); min-width: 0; }
  .icon {
    position: relative; flex: none; width: 40px; height: 40px; overflow: hidden;
    display: flex; align-items: center; justify-content: center;
    border-radius: var(--ha-tile-icon-border-radius, var(--ha-border-radius-pill, 9999px));
    color: var(--tint); --mdc-icon-size: 24px;
  }
  .icon::before { content: ""; position: absolute; inset: 0; background: var(--tint); opacity: 0.2; }
  .icon > * { position: relative; }
  .icon.home { --tint: var(--cp-home); }
  .icon.fuel { --tint: var(--cp-fuel); }
  .compact .icon { width: 36px; height: 36px; --mdc-icon-size: 20px; }
  .info { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; }
  .primary, .secondary { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* the tile card's text tokens, so a theme that restyles tiles (Fluvy and others) restyles these lines too */
  .primary {
    font-size: var(--ha-tile-info-primary-font-size, var(--ha-font-size-m, 14px));
    font-weight: var(--ha-tile-info-primary-font-weight, var(--ha-font-weight-medium, 500));
    letter-spacing: var(--ha-tile-info-primary-letter-spacing, 0.1px); line-height: 20px;
  }
  .secondary {
    font-size: var(--ha-tile-info-secondary-font-size, var(--ha-font-size-s, 12px));
    font-weight: var(--ha-tile-info-secondary-font-weight, var(--ha-font-weight-normal, 400));
    letter-spacing: var(--ha-tile-info-secondary-letter-spacing, 0.4px); line-height: 16px;
    color: var(--ha-tile-info-secondary-color, var(--cp-muted));
  }
  /* header texts wrap instead of cutting "GPS area", "price from … — may be outdated" or "5 stations at this price" */
  .head > .info .primary, .head > .info .secondary { white-space: normal; }
  /* an outdated price is flagged by an icon too: some themes (Fluvy dark) use status colours close to the text */
  .secondary .flag { --mdc-icon-size: 14px; vertical-align: -2px; margin-inline-end: 4px; }
  .value { flex: none; display: flex; align-items: baseline; gap: var(--ha-space-1, 4px); line-height: var(--ha-line-height-condensed, 1.2); }
  .value .number { font-size: var(--ha-font-size-3xl, 28px); font-weight: var(--ha-font-weight-normal, 400); font-variant-numeric: tabular-nums; }
  .compact .value .number { font-size: var(--ha-font-size-2xl, 24px); }
  .value .unit { font-size: var(--ha-font-size-s, 12px); color: var(--cp-muted); }
  .value.stale .number { color: var(--cp-muted); }

  /* trends: five neutral tiles, like card features */
  .trends { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: var(--ha-space-2, 8px); }
  .trend {
    position: relative; overflow: hidden; display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 2px; min-height: 52px; padding: var(--ha-space-1, 4px) 2px; box-sizing: border-box; border-radius: var(--cp-radius);
  }
  .trend::before { content: ""; position: absolute; inset: 0; background: var(--cp-neutral); opacity: 0.2; }
  .trend > * { position: relative; }
  .trend .label { font-size: var(--ha-font-size-xs, 10px); line-height: 12px; letter-spacing: 0.4px; color: var(--cp-muted); }
  .trend .delta {
    display: inline-flex; align-items: center; gap: 2px; white-space: nowrap;
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums;
    --mdc-icon-size: 14px;
  }
  .trends-inline { display: flex; flex-wrap: wrap; gap: 2px var(--ha-space-3, 12px); font-size: var(--ha-font-size-s, 12px); }
  .trends-inline .delta { font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; }
  .note { font-size: var(--ha-font-size-xs, 10px); line-height: 14px; color: var(--cp-muted); }
  .status { display: flex; align-items: flex-start; gap: var(--ha-space-2, 8px); font-size: var(--ha-font-size-s, 12px); line-height: 16px; --mdc-icon-size: 16px; }
  .status ha-icon { flex: none; }

  /* station rows */
  .rows { display: flex; flex-direction: column; margin: 0 calc(-1 * var(--ha-space-2, 8px)); }
  .row {
    position: relative; display: flex; align-items: center; gap: var(--ha-space-3, 12px); min-height: 52px;
    padding: var(--ha-space-2, 8px); box-sizing: border-box; border-radius: var(--cp-radius);
    cursor: pointer; user-select: none; outline: none;
  }
  .row + .row::after { content: ""; position: absolute; top: 0; left: var(--ha-space-2, 8px); right: var(--ha-space-2, 8px); border-top: 1px solid var(--cp-line); }
  .row::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--cp-neutral); opacity: 0; transition: opacity 180ms ease-in-out; }
  .row:hover::before { opacity: 0.12; }
  .row:focus-visible { box-shadow: inset 0 0 0 2px var(--cp-home); }
  .row > * { position: relative; }
  .compact .row { min-height: 40px; padding: var(--ha-space-1, 4px) var(--ha-space-2, 8px); gap: 10px; }
  .row .info .primary ha-icon { --mdc-icon-size: 14px; color: var(--cp-home); vertical-align: -2px; margin-inline-start: 4px; }
  .row .change { flex: none; display: flex; align-items: center; gap: 2px; justify-content: flex-end;
    font-size: var(--ha-font-size-xs, 10px); font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; --mdc-icon-size: 14px; }
  .row .price { flex: none; display: flex; flex-direction: column; align-items: flex-end; min-width: 52px; }
  .row .price .number { font-size: var(--ha-font-size-l, 16px); font-weight: var(--ha-font-weight-medium, 500); line-height: 20px; font-variant-numeric: tabular-nums; }
  .row .price .diff { font-size: var(--ha-font-size-xs, 10px); line-height: 14px; color: var(--cp-muted); font-variant-numeric: tabular-nums; }
  .row .price.best .number, .row .price.best .diff { color: var(--cp-good); }

  /* station badge: the chain's logo or its initials, with the rank */
  .avatar { position: relative; flex: none; width: 36px; height: 36px; }
  .compact .avatar { width: 28px; height: 28px; }
  .disc {
    position: absolute; inset: 0; overflow: hidden; display: flex; align-items: center; justify-content: center;
    border-radius: var(--ha-border-radius-pill, 9999px);
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500); letter-spacing: 0.2px;
    background: color-mix(in srgb, hsl(var(--hue) 55% 50%) 22%, transparent);
    color: color-mix(in srgb, hsl(var(--hue) 60% 45%) 65%, var(--cp-text));
  }
  .compact .disc { font-size: var(--ha-font-size-xs, 10px); }
  .disc img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; background: #fff; }
  .avatar .rank {
    position: absolute; right: -4px; bottom: -4px; min-width: 16px; height: 16px; padding: 0 4px; box-sizing: border-box;
    display: flex; align-items: center; justify-content: center; border-radius: var(--ha-border-radius-pill, 9999px);
    background: var(--cp-surface); box-shadow: 0 0 0 1px var(--cp-line);
    font-size: var(--ha-font-size-xs, 10px); font-weight: var(--ha-font-weight-medium, 500); color: var(--cp-muted);
  }
  .avatar.best .rank { color: var(--cp-good); box-shadow: 0 0 0 1px currentColor; }

  /* footer and messages */
  .foot { display: flex; flex-direction: column; gap: 2px; padding-top: var(--ha-space-3, 12px); border-top: 1px solid var(--cp-line);
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--cp-muted); }
  .compact .foot { padding-top: var(--ha-space-2, 8px); }
  .foot .legend ha-icon { --mdc-icon-size: 12px; vertical-align: -1px; }
  .source { font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--cp-muted); }
  .alert { position: relative; display: flex; gap: var(--ha-space-2, 8px); padding: var(--ha-space-2, 8px) var(--ha-space-3, 12px);
    border-radius: var(--cp-radius); overflow: hidden; font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--cp-text); --mdc-icon-size: 18px; }
  .alert::before { content: ""; position: absolute; inset: 0; background: var(--alert-color); opacity: 0.12; }
  .alert > * { position: relative; }
  .alert ha-icon { flex: none; color: var(--alert-color); }
  .alert.warning { --alert-color: var(--cp-warn-base); }
  .alert.info { --alert-color: var(--info-color, #039be5); }
  .message { flex-direction: row; align-items: flex-start; font-size: var(--ha-font-size-m, 14px); line-height: 20px; color: var(--cp-muted); --mdc-icon-size: 20px; }
  .message ha-icon { flex: none; color: var(--cp-muted); }

  /* fuel switch and sort order: the segmented control of core cards (ha-control-select), in the theme's primary colour */
  .seg { position: relative; display: flex; gap: 4px; padding: 4px; height: 40px; box-sizing: border-box;
    border-radius: var(--ha-border-radius-lg, 12px); }
  .seg::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--cp-neutral); opacity: 0.2; }
  .seg .option { position: relative; flex: 1 1 0; min-width: 0; padding: 0 var(--ha-space-2, 8px); border: none; background: none;
    border-radius: calc(var(--ha-border-radius-lg, 12px) - 4px); cursor: pointer; outline: none;
    font: inherit; font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); color: var(--cp-text); }
  .seg .option::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--cp-home); opacity: 0;
    transition: opacity 80ms ease-in-out; }
  .seg .option:hover::before { opacity: 0.2; }
  .seg .option:focus-visible { box-shadow: 0 0 0 2px var(--cp-home); }
  .seg .option.selected { color: var(--text-primary-color, #fff); }
  .seg .option.selected::before { opacity: 1; }
  .seg .option span { position: relative; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* the sort order is secondary to the fuel switch: smaller, its choice a tint instead of a fill */
  .seg.small { height: 36px; }
  .seg.small .option { font-size: var(--ha-font-size-s, 12px); }
  .seg.small .option.selected { color: var(--cp-text); }
  .seg.small .option.selected::before { opacity: 0.24; }

  /* station details: Home Assistant's dialog, a bottom sheet on phones (ha-adaptive-dialog) */
  dialog.sheet {
    width: min(580px, 95vw); max-height: min(80vh, 720px); padding: 0; border: none; overflow: hidden;
    border-radius: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
    background: var(--ha-dialog-surface-background, var(--card-background-color, var(--cp-surface)));
    color: var(--cp-text); box-shadow: var(--ha-box-shadow-l, 0 16px 32px -6px rgba(0, 0, 0, 0.2));
    font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif);
  }
  dialog.sheet[open] { display: flex; flex-direction: column; }
  dialog.sheet::backdrop { background: rgba(0, 0, 0, 0.32); }
  .sheet-head { display: flex; align-items: center; gap: var(--ha-space-3, 12px); padding: var(--ha-space-6, 24px) var(--ha-space-6, 24px) var(--ha-space-3, 12px); }
  .sheet-head .primary { font-size: var(--ha-font-size-xl, 20px); font-weight: var(--ha-font-weight-normal, 400); line-height: 1.2; white-space: normal; }
  .sheet-head .secondary { white-space: normal; }
  .sheet-body { display: flex; flex-direction: column; gap: var(--ha-space-4, 16px); padding: 0 var(--ha-space-6, 24px) var(--ha-space-6, 24px); overflow: auto; }
  .sheet-body > * { flex: none; }  /* the body scrolls; its parts never shrink */
  .close { position: relative; flex: none; width: 40px; height: 40px; margin: -8px -8px -8px 0; padding: 0; border: none; background: none;
    border-radius: var(--ha-border-radius-pill, 9999px); color: var(--cp-text); cursor: pointer; outline: none; --mdc-icon-size: 24px;
    display: flex; align-items: center; justify-content: center; }
  .close::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--cp-neutral); opacity: 0; transition: opacity 180ms ease-in-out; }
  .close:hover::before { opacity: 0.2; }
  .close:focus-visible { box-shadow: 0 0 0 2px var(--cp-home); }
  .facts { display: flex; flex-wrap: wrap; gap: 2px var(--ha-space-3, 12px); font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--cp-muted); }
  /* navigation: card feature buttons */
  .nav { display: flex; gap: var(--ha-space-3, 12px); }
  .nav a {
    position: relative; overflow: hidden; flex: 1 1 0; min-width: 0; height: 42px; box-sizing: border-box;
    display: flex; align-items: center; justify-content: center; gap: var(--ha-space-2, 8px); padding: 0 var(--ha-space-2, 8px);
    border-radius: var(--cp-radius); text-decoration: none; outline: none; color: var(--cp-text);
    font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); --mdc-icon-size: 20px;
  }
  .nav a::before { content: ""; position: absolute; inset: 0; background: var(--cp-neutral); opacity: 0.2; transition: opacity 180ms ease-in-out; }
  .nav a:hover::before { opacity: 0.3; }
  .nav a:focus-visible { box-shadow: 0 0 0 2px var(--cp-home); }
  .nav a > * { position: relative; }
  .nav a span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  @media (max-width: 870px), (max-height: 500px) {
    dialog.sheet { width: 100vw; max-width: 100vw; margin: auto 0 0; max-height: 90vh;
      border-radius: var(--ha-border-radius-2xl, 20px) var(--ha-border-radius-2xl, 20px) 0 0;
      padding-bottom: var(--safe-area-inset-bottom, 0px); }
  }
  /* stacked on a narrow phone: each button keeps its height instead of sharing the row's width */
  @media (max-width: 420px) { .nav { flex-direction: column; } .nav a { flex: none; } }

  /* the 30-day graph: lines in the theme's colours, a tooltip like the energy cards' */
  .chart { position: relative; }
  .chart svg { display: block; width: 100%; height: auto; overflow: visible; touch-action: pan-y; }
  .chart svg * { pointer-events: none; }
  .chart .grid-line { stroke: var(--cp-line); stroke-width: 1; }
  .chart text { fill: var(--cp-muted); font-size: var(--ha-font-size-xs, 10px); font-family: inherit; font-variant-numeric: tabular-nums; }
  .chart .line { fill: none; stroke: currentColor; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
  .chart .line.average { stroke-dasharray: 4 3; stroke-width: 1.5; }
  .chart .dot { fill: currentColor; }
  .chart .cursor { stroke: var(--cp-muted); stroke-width: 1; }
  .mine { color: var(--cp-home); }
  .cheapest { color: var(--cp-good-base); }
  .average { color: var(--cp-muted); }
  .tip {
    position: absolute; top: 0; transform: translateX(-50%); pointer-events: none; z-index: 1;
    display: flex; flex-direction: column; gap: 2px; padding: 8px 10px; white-space: nowrap;
    background: var(--cp-surface); color: var(--cp-text); border: 1px solid var(--cp-line); border-radius: 4px;
    box-shadow: rgba(0, 0, 0, 0.2) 1px 2px 10px; font-size: var(--ha-font-size-s, 12px); line-height: 16px;
  }
  .tip[hidden] { display: none; }
  .tip b, .series .value { font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; color: var(--cp-text); }
  .series { display: flex; flex-wrap: wrap; gap: 4px var(--ha-space-4, 16px); font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--cp-muted); }
  .swatch { display: inline-block; width: 12px; height: 3px; margin-inline-end: 6px; border-radius: 2px; background: currentColor; vertical-align: middle; }
  .average .swatch { background: repeating-linear-gradient(90deg, currentColor 0 4px, transparent 4px 7px); }
  .series .name { color: var(--cp-muted); }

  .map, .graph { border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px)); overflow: hidden; }
  .map.fixed { position: relative; min-width: 200px; }
  .map.fixed > * { position: absolute; inset: 0; display: block; }
  @media (prefers-reduced-motion: reduce) { .row::before, .seg .option::before, .nav a::before, .close::before { transition: none; } }
`;

// A state Home Assistant restored for an entity no integration provides (yet): it carries no data or attributes.
const restored = (state) => !!(state && state.attributes && state.attributes.restored);

// Home Assistant drops the attributes of an unavailable entity, and the sensors of a fuel are unavailable while
// mBenzin.cz cannot refresh it. The card therefore keeps the last known state of each sensor (in this browser, so
// also across reloads) and shows it with a warning instead of an empty card.
const LAST_KNOWN_KEY = 'ceny-paliv-last-known';
const lastKnown = new Map();
let lastKnownLoaded = false;

function browserStorage() {
  try { return window.localStorage || null; } catch (e) { return null; }
}

function withLastKnown(hass) {
  const store = browserStorage();
  if (!lastKnownLoaded) {
    lastKnownLoaded = true;
    try {
      const saved = JSON.parse((store && store.getItem(LAST_KNOWN_KEY)) || '{}');
      for (const id of Object.keys(saved)) lastKnown.set(id, saved[id]);
    } catch (e) { /* no or broken storage: start empty */ }
  }
  const area = (a) => `${a.cp_config_id}|${a.cp_fuel}`;
  const live = new Set();  // areas and fuels whose top5 sensor is available: nothing of theirs is revived
  const gone = [];
  let changed = false;
  for (const id in hass.states) {
    if (!id.startsWith('sensor.ceny_paliv_')) continue;
    const s = hass.states[id];
    const a = s.attributes || {};
    if (s.state === 'unavailable') {
      // a restored state belongs to an entity no integration provides (a removed area): never revive it
      if (!a.restored) gone.push(id);
      continue;
    }
    if (!a.cp_role || a.cp_role === 'home_archive') continue;
    if (a.cp_role === 'top5') live.add(area(a));
    const known = lastKnown.get(id);
    if (!known || known.last_updated !== s.last_updated) {
      lastKnown.set(id, { state: s.state, last_updated: s.last_updated, attributes: a });
      changed = true;
    }
  }
  if (changed && store) {
    const keep = {};
    lastKnown.forEach((v, id) => { if (id in hass.states) keep[id] = v; });
    try { store.setItem(LAST_KNOWN_KEY, JSON.stringify(keep)); } catch (e) { /* full or blocked: memory only */ }
  }
  let states = null;
  for (const id of gone) {
    const known = lastKnown.get(id);
    // with its top5 available, an unavailable sensor is an archived favourite, not an outage
    if (!known || live.has(area(known.attributes))) continue;
    states = states || Object.assign({}, hass.states);
    states[id] = Object.assign({}, known, { entity_id: id, attributes: Object.assign({}, known.attributes, { cp_stale: true }) });
  }
  return states ? Object.assign({}, hass, { states }) : hass;
}

// TOP 5 sensors of one fuel (legacy entities are matched by entity id).
function topCandidates(hass, fuel) {
  const tops = [];
  for (const id in hass.states) {
    if (!id.startsWith('sensor.ceny_paliv_') || restored(hass.states[id])) continue;
    const a = hass.states[id].attributes || {};
    if (a.cp_fuel) {
      if (a.cp_fuel === fuel && a.cp_role === 'top5') tops.push({ id, attributes: a });
    } else {
      const m = id.match(/_([a-z0-9]+)_(top5|home|[1-5])$/);
      if (m && m[1] === fuel && m[2] === 'top5') tops.push({ id, attributes: a });
    }
  }
  return tops;
}

class CenyPalivCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._sig = '';
    this._children = null;
    this._timer = null;
    // registered once: the shadow root outlives every setConfig
    const root = this.shadowRoot;
    root.addEventListener('click', (e) => this._click(e));
    root.addEventListener('keydown', (e) => this._key(e));
    root.addEventListener('pointerdown', (e) => this._down(e));
    root.addEventListener('pointermove', (e) => { this._move(e); this._hover(e); });
    root.addEventListener('pointerout', (e) => { if (e.target && e.target.tagName === 'svg') this._hover(null); });
    // pointerleave does not bubble to the root: moving away is caught by pointermove / pointercancel
    ['pointerup', 'pointercancel'].forEach((n) => root.addEventListener(n, () => clearTimeout(this._timer)));
  }

  setConfig(config) {
    if (!config || !(config.fuel || switchFuels(config).length)) throw new Error('ceny-paliv-card: set "fuel", for example "n95"');
    this._fuels = switchFuels(config);
    this._config = Object.assign({ layout: 'auto', stations: 5, compact: false, logo_path: '' }, config, { fuel: config.fuel || this._fuels[0] });
    this._show = shownParts(config);
    this._layout = ['auto', 'columns', 'stack'].includes(this._config.layout) ? this._config.layout : 'auto';
    this._n = Math.min(5, Math.max(1, Math.round(Number(this._config.stations) || 5)));
    this._compact = !!this._config.compact;
    this._footer = this._config.show_footer != null ? !!this._config.show_footer : !this._compact;
    this._mapHeight = Number(this._config.map_height) > 0 ? Number(this._config.map_height) : 0;
    this._sort = SORTS.includes(this._config.sort) ? this._config.sort : 'price';
    const positive = (v, d) => (Number(v) > 0 ? Number(v) : d);
    this._tank = positive(this._config.tank_litres, 40);
    this._consumption = positive(this._config.consumption, 6.5);
    this._ids = null;
    this._scanAt = 0;
    this._sig = '';
    this._children = null;
    this._build();
    if (this._hass) this.hass = this._hass;  // a new config (e.g. the editor preview) renders at once
  }

  set hass(hass) {
    hass = withLastKnown(hass);
    this._hass = hass;
    if (!this._config) return;
    const previousIds = this._ids;
    this._ids = this._resolve(hass);
    if (previousIds && JSON.stringify(previousIds) !== JSON.stringify(this._ids)) {
      for (const id of ['map', 'graph']) {
        const container = this.shadowRoot.getElementById(id);
        if (container) container.replaceChildren();
      }
      this._resetExtra();
    }
    const top = hass.states[this._ids.top5];
    const home = hass.states[this._ids.home];
    // the date is part of the signature: "today"/"yesterday" labels and the freshness filter change at midnight
    const where = hass.config ? `${hass.config.latitude},${hass.config.longitude}` : '';  // distances in a town
    const sig = [JSON.stringify(this._ids), top && top.last_updated, home && home.last_updated, top && top.state, home && home.state, new Date().toDateString(), where].join('|');
    if (sig !== this._sig) {
      this._sig = sig;
      this._renderTexts();
    }
    if (this._children) this._children.forEach((c) => { c.hass = hass; });
  }

  // Find one configuration's sensors by their attributes, not by entity-id suffix alone.
  _resolve(hass) {
    const c = this._ids;
    const matches = (state, role, fuel, configId) => {
      if (!state) return false;
      const a = state.attributes || {};
      if (a.cp_role) {
        return a.cp_role === role
          && a.cp_fuel === fuel
          && typeof a.cp_config_id === 'string'
          && a.cp_config_id === configId
          && (role !== 'home' || !['unavailable', 'unknown'].includes(state.state));
      }
      return !configId && role !== 'home_archive'
        && (role !== 'home' || !['unavailable', 'unknown'].includes(state.state));
    };
    const topState = c && c.top5 && hass.states[c.top5];
    const cachedTopConfig = topState && (topState.attributes || {}).cp_config_id;
    const expectedTopConfig = this._config.config_id || cachedTopConfig;
    const cachedHome = c && c.home && hass.states[c.home];
    const valid = c && matches(topState, 'top5', this._config.fuel, expectedTopConfig)
      && (!c.home || matches(cachedHome, 'home', this._config.fuel, expectedTopConfig))
      && c.pos.every((id, index) => {
        if (!id) return true;
        const state = hass.states[id];
        const attributes = state && state.attributes || {};
        return matches(state, 'position', this._config.fuel, cachedTopConfig)
          && (!attributes.cp_index || attributes.cp_index === index + 1);
      });
    // Without an explicit config_id the binding is only safe while exactly one area offers this fuel. Checking that
    // walks every state, so it is repeated only when the entity registry changed (a new or removed area always
    // changes it) or every 10 s; without the registry (older frontends) it is checked on every update.
    const now = Date.now();
    const registry = hass.entities;
    const recheck = !registry || registry !== this._registry || now - this._scanAt >= 10000;
    let sole = null;
    if (!this._config.config_id && valid) {
      if (recheck || !this._sole) this._sole = topCandidates(hass, this._config.fuel).map((top) => top.id);
      sole = this._sole;
    }
    this._ambiguous = !!(sole && sole.length > 1);
    if (sole && sole.length !== 1) return { top5: null, home: null, pos: [] };
    // a favourite announced by the top5 sensor but not bound yet is looked for on the same schedule
    if (valid && (!sole || sole[0] === c.top5) && (c.home || !topState.attributes.home || !recheck)) return c;
    this._scanAt = now;
    this._registry = registry;
    this._sole = null;
    const fuel = this._config.fuel;
    const ids = { top5: null, home: null, pos: [] };
    const tops = topCandidates(hass, this._config.fuel);
    const candidates = this._config.config_id
      ? tops.filter((top) => top.attributes.cp_config_id === this._config.config_id)
      : tops;
    this._ambiguous = candidates.length > 1;
    if (candidates.length !== 1) return ids;
    const selected = candidates[0];
    const selectedConfig = selected.attributes.cp_config_id;
    ids.top5 = selected.id;
    const homes = [];
    for (const id of Object.keys(hass.states)) {
      if (!id.startsWith('sensor.ceny_paliv_') || restored(hass.states[id])) continue;
      const a = hass.states[id].attributes || {};
      if (a.cp_role === 'home_archive') continue;
      if (a.cp_role && (
        typeof a.cp_config_id !== 'string'
        || a.cp_config_id !== selectedConfig
      )) continue;
      if (selectedConfig && a.cp_config_id !== selectedConfig) continue;
      let role = null; let idx = 0;
      if (a.cp_fuel) {
        if (a.cp_fuel !== fuel || (selectedConfig && a.cp_config_id !== selectedConfig)) continue;
        role = a.cp_role; idx = a.cp_index || 0;
      } else {
        const m = id.match(/_([a-z0-9]+)_(top5|home|[1-5])$/);
        if (!m || m[1] !== fuel) continue;
        role = m[2] === 'top5' ? 'top5' : m[2] === 'home' ? 'home' : 'position';
        idx = /^\d$/.test(m[2]) ? Number(m[2]) : 0;
      }
      if (
        role === 'home'
        && !['unavailable', 'unknown'].includes(hass.states[id].state)
        && (!selectedConfig || a.cp_config_id === selectedConfig)
      ) homes.push(id);
      else if (role === 'position' && idx >= 1 && idx <= 5) ids.pos[idx - 1] = id;
    }
    ids.home = homes.length === 1 ? homes[0] : null;
    return ids;
  }

  _sides() {
    const a = this._show.some((p) => p === 'home' || p === 'list');
    const b = this._show.some((p) => p === 'map' || p === 'graph');
    return { a, b, wide: a && b && this._layout !== 'stack' };
  }

  getCardSize() {
    const h = { home: this._compact ? 2 : 4, list: this._compact ? 1 + this._n : 2 + 2 * this._n, map: this._mapHeight ? Math.ceil(this._mapHeight / 50) : 6, graph: 4 };
    const sizes = this._show.map((p) => h[p]);
    const sd = this._sides();
    const switcher = this._fuels && this._fuels.length > 1 ? 1 : 0;
    if (!sd.wide) return sizes.reduce((x, y) => x + y, 0) + switcher;
    const left = ['home', 'list'].filter((p) => this._show.includes(p)).reduce((x, p) => x + h[p], 0);
    const right = ['map', 'graph'].filter((p) => this._show.includes(p)).reduce((x, p) => x + h[p], 0);
    return Math.max(left, right) + switcher;
  }

  getGridOptions() {
    const wide = this._config ? this._sides().wide : true;
    return { columns: wide ? 12 : 6, min_columns: wide ? 8 : 3, rows: 'auto' };
  }
  static getConfigElement() { return document.createElement('ceny-paliv-card-editor'); }
  static fuels(hass) {
    const out = [];
    for (const [id, st] of Object.entries((hass && hass.states) || {})) {
      if (!id.startsWith('sensor.ceny_paliv_')) continue;
      const a = st.attributes || {};
      const isTop = a.cp_role === 'top5' || (!a.cp_role && /_top5$/.test(id) && a.fuel);
      if (isTop && a.fuel && !out.some((o) => o.value === a.fuel)) out.push({ value: a.fuel, label: a.fuel_label || a.fuel });
    }
    return out;
  }
  static configurations(hass, fuel) {
    const configs = [];
    for (const [id, state] of Object.entries((hass && hass.states) || {})) {
      const a = state.attributes || {};
      if (!id.startsWith('sensor.ceny_paliv_') || a.cp_fuel !== fuel || a.cp_role !== 'top5' || !a.cp_config_id) continue;
      if (!configs.some((item) => item.value === a.cp_config_id)) {
        const area = a.gps_area || null;
        const where = area
          ? [a.city_name || 'GPS area', area.radius_km ? `${area.radius_km} km` : '', area.zone_entity || area.method || ''].filter(Boolean).join(' · ')
          : (a.city_name || 'GPS area');
        configs.push({
          value: a.cp_config_id,
          label: `${where} (${a.cp_config_id.slice(0, 8)})`,
        });
      }
    }
    return configs.sort((a, b) => a.label.localeCompare(b.label));
  }
  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-card', fuel: found ? found.value : 'n95' };
  }

  // ---------------------------------------------------------------- skeleton
  _build() {
    const root = this.shadowRoot;
    const sd = this._sides();
    const col = (id, ids) => (ids.some((p) => this._show.includes(p))
      ? `<div class="col" id="${id}">${ids.filter((p) => this._show.includes(p)).map((p) => `<div id="${p}"></div>`).join('')}</div>` : '');
    const mode = sd.wide ? this._layout : 'stack';
    root.innerHTML = `<style>${STYLE}</style><div class="wrap"><div class="grid ${mode}">${col('colA', ['home', 'list'])}${col('colB', ['map', 'graph'])}</div></div>`;
    this._extraReady = false;
    this._gen = (this._gen || 0) + 1;
    this._fit();
  }

  // layout "auto": two columns from 640 px (back to one below 600 px, so it never flip-flops)
  _fit() {
    const grid = this.shadowRoot.querySelector('.grid');
    if (!grid || !grid.classList.contains('auto') || !this.getBoundingClientRect) return;
    const w = this.getBoundingClientRect().width;
    if (w >= 640) grid.classList.add('wide');
    else if (w < 600) grid.classList.remove('wide');
  }

  // the chart is drawn for its width: draw it again when the card's width changes
  _refit() {
    this._fit();
    if (!this._hass || !this._ids || !this._show || !this._show.includes('graph')) return;
    const width = this._measureGraph();
    if (Math.abs(width - (this._graphWidth || 0)) < 16) return;
    this._graphWidth = width;
    const el = this.shadowRoot.getElementById('graph');
    if (el && this._hass.states[this._ids.top5]) el.innerHTML = this._graphHtml();
  }

  connectedCallback() {
    if (!this._ro && window.ResizeObserver) this._ro = new ResizeObserver(() => this._refit());
    if (this._ro) this._ro.observe(this);
    this._fit();
  }

  disconnectedCallback() {
    if (this._ro) this._ro.disconnect();
  }

  // Map and graph are built once per binding; they are rebuilt after this reset.
  _resetExtra() {
    this._children = null;
    this._extraReady = false;
    this._gen = (this._gen || 0) + 1;
  }

  async _buildExtra() {
    if (this._extraReady || !this._hass) return;
    this._extraReady = true;
    const gen = this._gen;
    const helpers = window.loadCardHelpers ? await window.loadCardHelpers() : null;
    // setConfig or a new binding happened while the helpers loaded: that newer build owns the containers
    if (!helpers || gen !== this._gen) return;
    const hasHome = !!this._hass.states[this._ids.home];
    const kids = [];
    if (this._show.includes('map')) {
      // The marker is too narrow for the state with its unit ("37,9 Kč/l" showed as "7,9 Kč"): show the bare price.
      const marker = (id) => ({ entity: id, label_mode: 'attribute', attribute: 'price', focus: true });
      const entities = this._ids.pos.slice(0, this._n).filter(Boolean).map(marker);
      if (hasHome) entities.push(marker(this._ids.home));
      kids.push({ id: 'map', cls: this._mapHeight ? 'map fixed' : 'map', config: { type: 'map', theme_mode: 'auto', auto_fit: true, default_zoom: 12, hours_to_show: 0, entities } });
    }
    this._children = [];
    for (const k of kids) {
      const el = helpers.createCardElement(k.config);
      el.hass = this._hass;
      const wrap = document.createElement('div');
      wrap.className = k.cls;
      if (k.id === 'map' && this._mapHeight) wrap.style.height = `${this._mapHeight}px`;
      wrap.appendChild(el);
      const container = this.shadowRoot.getElementById(k.id);
      if (!container) continue;
      container.replaceChildren(wrap);
      this._children.push(el);
    }
  }

  // ---------------------------------------------------------------- helpers
  _labels() {
    const top = this._hass.states[this._ids.top5];
    return (top && top.attributes && top.attributes.labels) || {};
  }

  _T(k, v) {
    const lb = this._labels();
    return String(lb[k] !== undefined ? lb[k] : k).replace(/\{(\w+)\}/g, (m, x) => (v && v[x] !== undefined ? v[x] : m));
  }

  _arrow(t) {
    if (!t) return { icon: 'mdi:minus', cls: 'muted', txt: '—' };
    if (t.dir === 'down') return { icon: 'mdi:arrow-down', cls: 'good', txt: '−' + this._num(Math.abs(t.delta)) };
    if (t.dir === 'up') return { icon: 'mdi:arrow-up', cls: 'bad', txt: '+' + this._num(Math.abs(t.delta)) };
    return { icon: 'mdi:equal', cls: 'warn', txt: this._num(0) };
  }

  _age(s, today) {
    if (!s.updated_date) return s.updated === 'Dnes' ? 0 : 99;
    return Math.round((today - new Date(s.updated_date + 'T00:00:00')) / 86400000);
  }

  // ---------------------------------------------------------------- formatting, the Home Assistant way
  // Texts follow the language chosen in the integration (labels); the number and time format follow the user's
  // Home Assistant profile (decimal separator, 12/24 h clock, local or server time zone).
  _numberLocale() {
    const lang = this._labels().locale || (this._hass && this._hass.language) || 'en';
    const format = this._hass && this._hass.locale && this._hass.locale.number_format;
    const fixed = { comma_decimal: 'en-US', decimal_comma: 'de-DE', space_comma: 'fr-FR' };
    if (format in fixed) return fixed[format];
    return format === 'system' ? undefined : lang;
  }

  _num(value, digits = 2) {
    const n = Number(value);
    if (!isFinite(n)) return '—';
    try {
      return new Intl.NumberFormat(this._numberLocale(), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
    } catch (err) {
      return n.toFixed(digits);
    }
  }

  _dateTime(date, options) {
    const locale = (this._hass && this._hass.locale) || {};
    const opts = Object.assign({}, options);
    if (opts.hour) {
      if (locale.time_format === '12') opts.hour12 = true;
      else if (locale.time_format === '24') opts.hour12 = false;
    }
    const zone = locale.time_zone === 'server' && this._hass.config && this._hass.config.time_zone;
    if (zone) opts.timeZone = zone;
    const lang = locale.time_format === 'system' ? undefined : (this._labels().locale || 'en-GB');
    try {
      return new Intl.DateTimeFormat(lang, opts).format(date);
    } catch (err) {
      return date.toLocaleString();
    }
  }

  // A calendar date ("2026-11-10") as written, never shifted by a time zone: it is a day, not an instant.
  _day(iso, options) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    if (!m) return null;
    const locale = (this._hass && this._hass.locale) || {};
    const lang = locale.time_format === 'system' ? undefined : (this._labels().locale || 'en-GB');
    try {
      return new Intl.DateTimeFormat(lang, Object.assign({}, options, { timeZone: 'UTC' })).format(Date.UTC(+m[1], m[2] - 1, +m[3]));
    } catch (err) {
      return iso;
    }
  }

  // a station's price date: "today", "yesterday" or the day itself
  _when(s, age) {
    if (age <= 0) return { text: this._T('today'), old: false };
    if (age === 1) return { text: this._T('yesterday'), old: true };
    return { text: this._day(s.updated_date, { day: 'numeric', month: 'numeric' }) || s.updated || '—', old: true };
  }

  // URL of the logo of a station's chain, or '' when there is none. Logos come from the downloaded pack (list in the
  // `logos` attribute of the top5 sensor, matched on the chain name) or, with `logo_path`, from your own PNG files.
  _logoUrl(s) {
    const key = norm(s.chain || s.name);
    if (!key) return '';
    const path = this._config.logo_path;
    if (path) return `${path}${key.replace(/ /g, '-')}.png`;
    const top = this._hass.states[this._ids.top5];
    const list = (top && top.attributes && top.attributes.logos) || [];
    let best = null; let len = 0;
    for (const l of list) {
      for (const m of l.match || []) {
        if ((key === m || key.startsWith(m + ' ')) && m.length > len) { best = l.id; len = m.length; }
      }
    }
    return best ? `/ceny_paliv_static/logos/${encodeURIComponent(best)}.png` : '';
  }

  // Condition of the mBenzin.cz access key: "Ceny: mbenzin.cz" shown visibly with the prices, as a link on the web.
  _source() {
    const text = this._labels().source || 'Ceny: mbenzin.cz';
    return `<a href="https://www.mbenzin.cz" target="_blank" rel="noopener noreferrer">${esc(text)}</a>`;
  }

  _initials(name) {
    const w = String(name || '?').trim();
    return (w.length <= 3 ? w : w.replace(/[^\p{L}\p{N}]/gu, '').slice(0, 2)).toUpperCase();
  }

  // Round badge: the chain's logo when there is one, else its initials on a tint of a hue taken from the name.
  _disc(s) {
    const name = s.chain || s.name || '?';
    let h = 0; for (const ch of norm(name)) h = (h * 31 + ch.charCodeAt(0)) % 360;
    const url = this._logoUrl(s);
    const img = url ? `<img src="${esc(url)}" alt="" onerror="this.remove()">` : '';
    return `<span class="disc" style="--hue:${h}" aria-hidden="true">${esc(this._initials(name))}${img}</span>`;
  }

  _avatar(s, rank, best) {
    const badge = rank != null && rank !== '' ? `<span class="rank">${esc(rank)}</span>` : '';
    return `<span class="avatar${best ? ' best' : ''}">${this._disc(s)}${badge}</span>`;
  }

  // ---------------------------------------------------------------- rendering
  _renderTexts() {
    const hass = this._hass;
    const top = hass.states[this._ids.top5];
    const root = this.shadowRoot;
    const first = this._show.find((p) => p === 'home' || p === 'list') || this._show[0];
    // the fuel switch is the first row of the first card, so it stays with the prices it switches
    const sw = this._switchHtml();
    const slot = (p, html) => {
      const el = root.getElementById(p);
      if (el) el.innerHTML = sw && p === first ? html.replace(/^(\s*<ha-card[^>]*>)/, `$1${sw}`) : html;
    };
    if (!top || top.state === 'unavailable') {
      // the message replaces the map and graph containers' content: rebuild them once the data is back
      this._resetExtra();
      const why = !top ? (this._ambiguous ? 'ambiguous' : 'missing') : 'unavailable';
      this._show.forEach((p) => slot(p, p === first ? this._message(why) : ''));
      return;
    }
    slot('home', this._show.includes('home') ? this._homeHtml() : '');
    slot('list', this._show.includes('list') ? this._listHtml() : '');
    if (this._show.includes('graph')) {
      this._graphWidth = this._measureGraph();
      slot('graph', this._graphHtml());
      this._loadStats();
    }
    // only "my station" was asked for, but no favourite is set: say so instead of an empty card (the graph shows the
    // area's prices without one)
    if (!hass.states[this._ids.home] && this._show.every((p) => p === 'home')) slot(first, this._message('no_home'));
    // only the list was asked for and it is the first card: the switch sits there; without home or list, above the map
    if (sw && !['home', 'list'].includes(first)) slot(first, `<ha-card class="card">${sw}</ha-card>`);
    this._buildExtra();
  }

  _switchHtml() {
    if (!this._fuels || this._fuels.length < 2) return '';
    const labels = {};
    for (const f of CenyPalivCard.fuels(this._hass)) labels[f.value] = f.label;
    const options = this._fuels.map((f) => {
      const on = f === this._config.fuel;
      return `<button class="option${on ? ' selected' : ''}" role="tab" aria-selected="${on}" data-fuel="${esc(f)}"><span>${esc(labels[f] || f.toUpperCase())}</span></button>`;
    }).join('');
    return `<div class="seg" role="tablist">${options}</div>`;
  }

  // Another fuel of the switch: bind its sensors and rebuild the map and graph for them.
  _switchFuel(fuel) {
    if (!fuel || fuel === this._config.fuel || !this._fuels.includes(fuel)) return;
    this._config = Object.assign({}, this._config, { fuel });
    this._ids = null;
    this._sig = '';
    this._scanAt = 0;
    for (const id of ['map', 'graph']) {
      const container = this.shadowRoot.getElementById(id);
      if (container) container.replaceChildren();
    }
    this._resetExtra();
    if (this._hass) this.hass = this._hass;
  }

  _message(why) {
    const lang = ((this._hass && this._hass.language) || 'en').split('-')[0] === 'cs' ? 'cs' : 'en';
    const fuel = esc(this._config.fuel);
    const text = {
      en: {
        missing: `no sensors found for "${fuel}"${this._config.config_id ? ' in the chosen configuration — pick it again in the card editor' : ''}.`,
        ambiguous: `several configurations provide "${fuel}" — choose one in the card editor.`,
        unavailable: 'the sensors are unavailable right now (Home Assistant is starting or mBenzin.cz cannot be reached).',
        no_home: 'no favourite station is set for this fuel (Configure the integration).',
      },
      cs: {
        missing: `pro „${fuel}“ nebyly nalezeny senzory${this._config.config_id ? ' ve zvolené konfiguraci — vyberte ji znovu v editoru karty' : ''}.`,
        ambiguous: `„${fuel}“ nabízí více konfigurací — vyberte jednu v editoru karty.`,
        unavailable: 'senzory jsou teď nedostupné (Home Assistant startuje nebo mBenzin.cz neodpovídá).',
        no_home: 'pro toto palivo není nastavena oblíbená stanice (nastavení integrace).',
      },
    }[lang][why];
    return `<ha-card class="card message"><ha-icon icon="mdi:gas-station-off-outline"></ha-icon><span>Ceny paliv: ${text}</span></ha-card>`;
  }

  _homeHtml() {
    const e = this._hass.states[this._ids.home];
    if (!e) return '';
    const T = (k, v) => this._T(k, v);
    const a = e.attributes;
    const cp = this._compact;
    const topAttrs = this._hass.states[this._ids.top5].attributes || {};
    const stationName = String(a.station || '').trim() || T('my_station');
    const ok = !['unavailable', 'unknown'].includes(e.state);
    const stale = a.cp_stale || a.age_days == null || Number(a.age_days) > 1;
    const updated = a.cp_stale ? T('stale') : a.age_days == 0 ? T('updated_today') : (a.age_days == 1 ? T('updated_yesterday')
      : T('price_from', { d: this._day(a.updated_date, { day: 'numeric', month: 'numeric', year: 'numeric' }) || a.updated || '—' }));
    const tr = a.trends || {};
    const tiles = this._trendTiles(tr);
    const trends = cp
      ? `<div class="trends-inline">${[1, 7, 30].map((n) => { const r = this._arrow(tr[String(n)]); return `<span class="muted">${n} d <span class="delta ${r.cls}">${esc(r.txt)}</span></span>`; }).join('')}</div>`
      : tiles.html;
    const note = cp ? '' : tiles.note;
    let status;
    if (a.rank == null) status = { icon: 'mdi:clock-alert-outline', cls: 'warn', text: T('not_ranked') };
    else if (Number(a.vs_cheapest) <= 0) status = { icon: 'mdi:trophy-outline', cls: 'good', text: T(topAttrs.gps_area ? 'cheapest_area' : 'cheapest_town', { rank: a.rank, n: a.fresh_count }) };
    else status = { icon: 'mdi:information-outline', cls: 'muted', text: T('vs_cheapest', { d: this._num(a.vs_cheapest), name: a.cheapest_name, rank: a.rank, n: a.fresh_count }) };
    const homeStation = topAttrs.home || { name: stationName };
    const icon = this._logoUrl(homeStation)
      ? `<span class="avatar">${this._disc(homeStation)}</span>`
      : '<span class="icon home"><ha-icon icon="mdi:gas-station-in-use"></ha-icon></span>';
    return `<ha-card class="card home${cp ? ' compact' : ''}" role="button" tabindex="0" data-more-info="${esc(this._ids.home)}" aria-label="${esc(T('my_station'))}: ${esc(stationName)}">
      <div class="head">${icon}
        <div class="info"><span class="primary">${esc(stationName)}</span>
          <span class="secondary${stale ? ' warn' : ''}">${stale ? '<ha-icon class="flag" icon="mdi:clock-alert-outline"></ha-icon>' : ''}${esc(cp ? updated : `${T('my_station')} · ${updated}`)}</span></div>
        <div class="value${stale ? ' stale' : ''}"><span class="number">${ok ? this._num(e.state) : '—'}</span><span class="unit">${esc(a.unit_of_measurement || 'Kč/l')}</span></div>
      </div>
      ${trends}
      ${note ? `<span class="note">${esc(note)}</span>` : ''}
      <div class="status ${status.cls}"><ha-icon icon="${status.icon}"></ha-icon><span>${esc(status.text)}</span></div>
      ${this._show.includes('list') ? '' : `<span class="source">${this._source()}</span>`}
    </ha-card>`;
  }

  // The five trend tiles (1, 2, 7, 14, 30 days) and the note under them: no history yet, or a shorter one (*).
  _trendTiles(tr) {
    const T = (k, v) => this._T(k, v);
    const today = new Date(); today.setHours(0, 0, 0, 0);
    let partial = null;
    const tile = (n) => {
      const t = tr[String(n)]; const r = this._arrow(t);
      let covered = true;
      if (t) {
        const target = new Date(today); target.setDate(target.getDate() - n);
        covered = new Date(t.ref_date + 'T00:00:00') <= target; if (!covered) partial = t.ref_date;
      }
      return `<div class="trend"><span class="label">${n} d${t && !covered ? '*' : ''}</span>
        <span class="delta ${r.cls}">${t ? `<ha-icon icon="${r.icon}"></ha-icon>` : ''}${esc(r.txt)}</span></div>`;
    };
    const html = `<div class="trends">${[1, 2, 7, 14, 30].map(tile).join('')}</div>`;
    const anyTrend = Object.values(tr).some(Boolean);
    const note = !anyTrend ? T('trends_start')
      : (partial ? T('since_partial', { d: this._day(partial, { day: 'numeric', month: 'short' }) || partial }) : '');
    return { html, note };
  }

  _listHtml() {
    const S = this._hass.states[this._ids.top5];
    const at = S.attributes;
    const T = (k, v) => this._T(k, v);
    const all = Array.isArray(at.stations) ? at.stations : [];
    const maxAge = at.max_age_days != null ? Number(at.max_age_days) : 1;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const fresh = all.filter((s) => this._age(s, today) <= maxAge);
    const center = this._center(at);
    const sort = center ? this._sort : 'price';
    const pool = sort === 'price' ? fresh : this._pool(at, fresh, center, today, maxAge);
    const key = sort === 'distance' ? (x) => x._km : (x) => x._worth;
    const list = sort === 'price' ? fresh.slice(0, this._n) : pool.slice().sort((x, y) => key(x) - key(y) || x.price - y.price).slice(0, this._n);
    // for the station details; the area's up-to-date stations: all stations of the town or circle minus the outdated ones
    const total = at.city_total != null ? at.city_total : (at.gps_area && at.gps_area.station_count);
    const upToDate = total != null && isFinite(Number(total)) ? Number(total) - Number(at.excluded || 0) : fresh.length;
    const cp = this._compact;
    // the cheapest of the area, whatever the order (in price order the first row, as before)
    const prices = (sort === 'price' ? list : fresh).map((s) => Number(s.price)).filter((p) => !isNaN(p));
    const min = prices.length ? Math.min(...prices) : null;
    this._rows = { list, fresh: Math.max(upToDate, fresh.length), unit: at.unit_of_measurement || 'Kč/l', min };
    const unit = at.unit_of_measurement || 'Kč/l';
    const n = min === null ? 0 : fresh.filter((s) => Number(s.price) === min).length;
    const sub = min === null ? T('no_recent') : T('cheapest_price', { p: this._num(min), unit }) + (n > 1 ? ' · ' + T('stations_same', { n }) : '');
    const head = `<div class="head"><span class="icon fuel"><ha-icon icon="mdi:gas-station"></ha-icon></span>
      <div class="info"><span class="primary">${esc(at.fuel_label || this._config.fuel)} · ${esc(at.city_name || '')}</span>
        <span class="secondary">${esc(sub)}</span></div>
      <div class="value"><span class="number${min === null ? ' muted' : ''}">${min === null ? '—' : this._num(min)}</span><span class="unit">${esc(unit)}</span></div></div>`;
    const sorter = center && !cp && fresh.length ? `<div class="seg small" role="tablist" aria-label="${esc(T('sort'))}">${SORTS.map((o) => {
      const on = o === sort;
      return `<button class="option${on ? ' selected' : ''}" role="tab" aria-selected="${on}" data-sort="${o}"><span>${esc(T('sort_' + o))}</span></button>`;
    }).join('')}</div>` : '';
    const rows = list.map((s, i) => {
      const best = Number(s.price) === min;
      const name = s.name || '—';
      const a0 = s.address || '';
      // the integration gives the street without the repeated name, or the town when there is no street;
      // before 0.6 only the address, which often repeats the name without its accents ("Am oil Milicin parkoviste")
      const addr = s.street !== undefined ? (s.street || s.city || '')
        : (norm(a0).startsWith(norm(name)) ? a0.slice(name.length).trim() : a0);
      const tr = this._arrow((s.trends || {})['1']);
      const when = this._when(s, this._age(s, today));
      const home = s.home ? `<ha-icon icon="mdi:home" title="${esc(T('my_station'))}"></ha-icon>` : '';
      // the price date first: a long address is what gets cut
      const where = [`<span class="${when.old ? 'warn' : ''}">${esc(when.text)}</span>`, esc(addr)].filter((w) => w !== '');
      return `<div class="row" role="button" tabindex="0" aria-haspopup="dialog" data-station="${i}" aria-label="${esc(name)} ${esc(addr)}: ${this._num(s.price)} ${esc(unit)}">
        ${this._avatar(s, sort === 'price' ? i + 1 : s.rank, best)}
        <div class="info"><span class="primary">${esc(name)}${cp && addr ? ` <span class="muted">${esc(addr)}</span>` : ''}${home}</span>
          ${cp ? '' : `<span class="secondary">${where.join(' · ')}</span>`}</div>
        <span class="change ${tr.cls}" title="${esc(T('vs_yesterday'))}">${s.trends && s.trends['1'] ? `<ha-icon icon="${tr.icon}"></ha-icon>` : ''}${esc(tr.txt)}</span>
        <span class="price${best ? ' best' : ''}"><span class="number">${this._num(s.price)}</span>${cp ? '' : `<span class="diff">${esc(this._diff(s, sort, best, min, unit))}</span>`}</span>
      </div>`;
    }).join('');
    // footer
    const now = new Date();
    const time = (d) => (d.toDateString() === now.toDateString()
      ? this._dateTime(d, { hour: 'numeric', minute: '2-digit' })
      : this._dateTime(d, { weekday: 'short', hour: 'numeric', minute: '2-digit' }));
    const fa = at.fetched_at ? new Date(at.fetched_at) : null;
    const nu = at.next_update ? new Date(at.next_update) : null;
    const hidden = (at.excluded || 0) + (all.length - fresh.length);
    // a failed refresh makes the sensors unavailable; the card then shows their last known state (withLastKnown)
    const alert = at.cp_stale
      ? `<div class="alert warning" role="status"><ha-icon icon="mdi:alert-outline"></ha-icon><span>${esc(T('stale'))}</span></div>`
      : '';
    const lines = [`<span>${esc(T('table_updated', { t: fa ? time(fa) : '—', n: nu ? time(nu) : '—' }))}</span>`];
    if (at.city_total) lines.push(`<span>${esc(T('hidden', { h: hidden, t: at.city_total, age: maxAge > 1 ? T('days_l', { n: maxAge }) : (maxAge === 1 ? T('yesterday_l') : T('today_l')) }))}</span>`);
    lines.push(`<span class="legend">${esc(T('arrows'))}: <span class="good"><ha-icon icon="mdi:arrow-down"></ha-icon> ${esc(T('down'))}</span> · <span class="warn"><ha-icon icon="mdi:equal"></ha-icon> ${esc(T('stable'))}</span> · <span class="bad"><ha-icon icon="mdi:arrow-up"></ha-icon> ${esc(T('up'))}</span> · ${esc(T('longpress'))}</span>`);
    lines.push(`<span>${this._source()} · ${esc(at.fuel_label || '')}${at.fuel === 'n95' ? ' ' + esc(T('e10_note')) : ''} · ${esc(T('tap_station'))}</span>`);
    const foot = this._footer ? `<div class="foot">${lines.join('')}</div>` : `<div class="foot"><span>${this._source()}</span></div>`;
    return `<ha-card class="card list${cp ? ' compact' : ''}" data-more-info="${esc(this._ids.home || this._ids.top5)}">${head}${alert}${sorter}<div class="rows">${rows}</div>${foot}</ha-card>`;
  }

  // The second line of a row's price: the cheapest, how much more, the distance or the price with the drive.
  _diff(s, sort, best, min, unit) {
    if (sort === 'distance') return `${this._num(s._km, 1)} km`;
    if (sort === 'worth') return this._T('with_drive', { p: this._num(s._worth), unit });
    return best ? this._T('cheapest_badge') : '+' + this._num(Number(s.price) - min);
  }

  // Where distances are measured from: the GPS area's centre, or in a town Home Assistant's home location.
  _center(at) {
    const config = (this._hass && this._hass.config) || {};
    const pick = (lat, lng) => (isFinite(Number(lat)) && isFinite(Number(lng)) && lat !== null && lng !== null ? [Number(lat), Number(lng)] : null);
    // a GPS area measures from its own centre only: without one (a location error) there are no distances
    if (at.gps_area) return pick(at.gps_area.latitude, at.gps_area.longitude);
    return pick(config.latitude, config.longitude);
  }

  // The stations to sort by distance or "worth": the cheapest ones and, in a GPS area, the nearest ones, once each.
  _pool(at, fresh, center, today, maxAge) {
    const near = (Array.isArray(at.gps_nearest_stations) ? at.gps_nearest_stations : []).filter((s) => this._age(s, today) <= maxAge);
    const seen = new Set();
    const out = [];
    const cheapest = new Set(fresh);
    for (const s of fresh.concat(near)) {
      const id = `${s.name}|${s.lat}|${s.lng}|${s.price}`;
      const price = Number(s.price);
      if (seen.has(id) || !isFinite(price)) continue;
      seen.add(id);
      const km = s.distance_km != null && isFinite(Number(s.distance_km)) ? Number(s.distance_km)
        : (isFinite(Number(s.lat)) && isFinite(Number(s.lng)) ? kmBetween(center[0], center[1], Number(s.lat), Number(s.lng)) : Infinity);
      const rank = cheapest.has(s) ? s.rank : null;  // gps_nearest_stations ranks by distance, not by price
      out.push(Object.assign({}, s, { rank, _km: km, _worth: withDrive(price, km, this._tank, this._consumption) }));
    }
    return out;
  }

  _setSort(sort) {
    if (!SORTS.includes(sort) || sort === this._sort) return;
    this._sort = sort;
    this._sig = '';
    if (this._hass) this.hass = this._hass;
  }

  // ---------------------------------------------------------------- the 30-day graph
  // Your station (its own statistics, kept per station since 0.6), the area's cheapest price (the top5 sensor's daily
  // minimum, recorded since 0.9) and the area's average (since 0.8), as far as each has history.
  _graphSeries() {
    const states = this._hass.states;
    const top = states[this._ids.top5];
    const home = states[this._ids.home];
    const configId = top && top.attributes && top.attributes.cp_config_id;
    const average = Object.keys(states).find((id) => {
      const a = states[id].attributes || {};
      return id.startsWith('sensor.ceny_paliv_') && a.cp_role === 'area_average' && a.cp_fuel === this._config.fuel && a.cp_config_id === configId;
    });
    const out = [];
    if (home) out.push({ key: 'mine', id: (home.attributes && home.attributes.statistic_id) || this._ids.home, type: 'mean', label: this._T('my_station') });
    if (top) out.push({ key: 'cheapest', id: this._ids.top5, type: 'min', label: this._T('series_cheapest') });
    if (average) out.push({ key: 'average', id: average, type: 'mean', label: this._T('series_average') });
    return out;
  }

  // Daily statistics from the recorder, loaded again for other sensors, on a new day and every hour.
  async _loadStats() {
    if (!this._hass || typeof this._hass.callWS !== 'function') return;
    const series = this._graphSeries();
    const ids = series.map((x) => x.id);
    const key = `${ids.join('|')}|${new Date().toDateString()}|${Math.floor(Date.now() / 3600000)}`;
    if (!ids.length || key === this._statsKey) return;
    this._statsKey = key;
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - GRAPH_DAYS);
    start.setHours(0, 0, 0, 0);
    let rows = {};
    try {
      rows = (await this._hass.callWS({
        type: 'recorder/statistics_during_period', start_time: start.toISOString(), end_time: end.toISOString(),
        statistic_ids: ids, period: 'day', types: ['mean', 'min'],
      })) || {};
    } catch (err) {
      rows = {};  // no recorder or no history yet: the graph says so
    }
    if (key !== this._statsKey) return;  // a newer load (another fuel, area or favourite) owns the graph
    const values = {};
    for (const x of series) values[x.id] = dailyValues(rows[x.id], x.type);
    this._stats = { key, values };
    const el = this.shadowRoot.getElementById('graph');
    if (el && this._hass.states[this._ids.top5]) el.innerHTML = this._graphHtml();
  }

  _measureGraph() {
    const el = this.shadowRoot.getElementById('graph');
    const w = el && el.getBoundingClientRect ? el.getBoundingClientRect().width : 0;
    return w > 0 ? Math.max(240, Math.round(w - 32)) : 360;  // the card's 16 px padding on both sides
  }

  _graphHtml() {
    const T = (k, v) => this._T(k, v);
    const top = this._hass.states[this._ids.top5];
    const at = (top && top.attributes) || {};
    const loaded = (this._stats && this._stats.values) || {};
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const days = graphDays(today, GRAPH_DAYS + 1);
    const series = this._graphSeries().map((x) => Object.assign({}, x, { values: loaded[x.id] || {} }));
    const width = this._graphWidth || 360;
    const model = chartModel(series, days, width);
    this._chart = model ? { model, days, series, width } : null;
    const unit = at.unit_of_measurement || 'Kč/l';
    const head = `<div class="head"><span class="icon home"><ha-icon icon="mdi:chart-line"></ha-icon></span>
      <div class="info"><span class="primary">${esc(T('graph_title'))}</span><span class="secondary">${esc(at.fuel_label || this._config.fuel)} · ${esc(at.city_name || '')}</span></div></div>`;
    if (!model) return `<ha-card class="card graph-card">${head}<span class="note">${esc(T('graph_empty'))}</span></ha-card>`;
    const p = GRAPH_PAD;
    const day = (iso) => this._day(iso, { day: 'numeric', month: 'numeric' }) || iso;
    const ticks = model.ticks.map((t) => `<line class="grid-line" x1="${p.left}" x2="${width - p.right}" y1="${t.y.toFixed(1)}" y2="${t.y.toFixed(1)}"></line>`
      + `<text x="${p.left - 6}" y="${(t.y + 3).toFixed(1)}" text-anchor="end">${esc(this._num(t.v, 1))}</text>`).join('');
    const xs = [0, Math.floor((days.length - 1) / 2), days.length - 1].map((i, n) => `<text x="${model.x(i).toFixed(1)}" y="${GRAPH_HEIGHT - 4}" text-anchor="${['start', 'middle', 'end'][n]}">${esc(day(days[i]))}</text>`).join('');
    const lines = series.map((x, i) => `<g class="${x.key}"><path class="line ${x.key}" d="${model.lines[i].path}"></path>${model.lines[i].dots.map(([cx, cy]) => `<circle class="dot" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="2.5"></circle>`).join('')}</g>`).join('');
    const last = (x) => { for (let i = days.length - 1; i >= 0; i -= 1) if (x.values[days[i]] != null) return x.values[days[i]]; return null; };
    const legend = series.map((x) => {
      const v = last(x);
      return `<span class="${x.key}"><span class="swatch"></span><span class="name">${esc(x.label)}</span>${v == null ? '' : ` <span class="value">${esc(this._num(v))}</span>`}</span>`;
    }).join('');
    const summary = series.map((x) => `${x.label}: ${last(x) == null ? '—' : `${this._num(last(x))} ${unit}`}`).join(', ');
    return `<ha-card class="card graph-card">${head}
      <div class="chart"><svg viewBox="0 0 ${width} ${GRAPH_HEIGHT}" role="img" aria-label="${esc(T('graph_title'))}: ${esc(summary)}" data-graph>
        ${ticks}${xs}${lines}<line class="cursor" x1="0" x2="0" y1="${p.top}" y2="${GRAPH_HEIGHT - p.bottom}" visibility="hidden"></line></svg>
        <div class="tip" hidden></div></div>
      <div class="series">${legend}</div></ha-card>`;
  }

  // the values of the day under the pointer, like the tooltip of Home Assistant's charts
  _hover(e) {
    const graph = this.shadowRoot.getElementById && this.shadowRoot.getElementById('graph');
    const svg = graph && graph.querySelector && graph.querySelector('svg');
    const tip = graph && graph.querySelector && graph.querySelector('.tip');
    const cursor = svg && svg.querySelector('.cursor');
    if (!svg || !tip || !cursor || !this._chart) return;
    const path = e && e.composedPath ? e.composedPath() : [];
    if (!e || !path.includes(svg)) { tip.hidden = true; cursor.setAttribute('visibility', 'hidden'); return; }
    const { model, days, series, width } = this._chart;
    const rect = svg.getBoundingClientRect();
    const at = ((e.clientX - rect.left) / rect.width) * width;
    const i = Math.max(0, Math.min(days.length - 1, Math.round((at - GRAPH_PAD.left) / (model.step || 1))));
    const rows = series.filter((x) => x.values[days[i]] != null)
      .map((x) => `<span class="${x.key}"><span class="swatch"></span><span class="name">${esc(x.label)}</span> <b>${esc(this._num(x.values[days[i]]))}</b></span>`);
    if (!rows.length) { tip.hidden = true; cursor.setAttribute('visibility', 'hidden'); return; }
    const px = model.x(i);
    cursor.setAttribute('x1', px.toFixed(1));
    cursor.setAttribute('x2', px.toFixed(1));
    cursor.setAttribute('visibility', 'visible');
    tip.innerHTML = `<span>${esc(this._day(days[i], { weekday: 'short', day: 'numeric', month: 'numeric' }) || days[i])}</span>${rows.join('')}`;
    tip.hidden = false;
    // kept inside the card: the tooltip's centre follows the day, its edges stay within the chart
    const half = tip.offsetWidth / 2;
    const left = Math.max(half, Math.min(rect.width - half, (px / width) * rect.width));
    tip.style.left = `${left}px`;
  }

  // ---------------------------------------------------------------- station details
  _stationHtml(s, rank) {
    const T = (k, v) => this._T(k, v);
    const rows = this._rows || { list: [], fresh: 0, unit: 'Kč/l', min: null };
    const shown = rows.list.map((x) => Number(x.price)).filter((p) => !isNaN(p));
    const min = rows.min != null ? rows.min : (shown.length ? Math.min(...shown) : Number(s.price));
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const when = this._when(s, this._age(s, today));
    const best = Number(s.price) === min;
    const addr = s.street !== undefined ? [s.street, s.city].filter(Boolean).join(', ') : (s.address || '');
    const facts = [
      `<span class="${when.old ? 'warn' : ''}">${esc(when.text)}</span>`,
      rank ? esc(T('rank_of', { rank, n: rows.fresh })) : '',
      best ? `<span class="good">${esc(T('cheapest_badge'))}</span>` : esc(T('more_than_cheapest', { d: this._num(Number(s.price) - min) })),
    ];
    const km = s.distance_km != null ? Number(s.distance_km) : s._km;
    if (km != null && isFinite(km)) facts.push(`${this._num(km, 1)} km`);
    const tiles = this._trendTiles(s.trends || {});
    const nav = navigationLinks(s).map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer"><ha-icon icon="${l.icon}"></ha-icon><span>${esc(l.label)}</span></a>`).join('');
    return `<div class="sheet-head">${this._avatar(s, rank, best)}
        <div class="info"><span class="primary" id="sheet-title">${esc(s.name || '—')}</span><span class="secondary">${esc(addr)}</span></div>
        <button class="close" data-close aria-label="${esc(T('close'))}"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>
      <div class="sheet-body">
        <div class="head"><div class="info"><div class="facts">${facts.filter(Boolean).join('<span aria-hidden="true">·</span>')}</div></div>
          <div class="value"><span class="number">${this._num(s.price)}</span><span class="unit">${esc(rows.unit)}</span></div></div>
        ${tiles.html}
        ${tiles.note ? `<span class="note">${esc(tiles.note)}</span>` : ''}
        ${nav ? `<div class="nav" role="group" aria-label="${esc(T('navigate'))}">${nav}</div>` : ''}
        <span class="source">${this._source()}</span>
      </div>`;
  }

  _openStation(index) {
    const s = this._rows && this._rows.list[index];
    if (!s) return;
    let dialog = this._sheet;
    if (!dialog || !dialog.isConnected) {
      dialog = document.createElement('dialog');
      dialog.className = 'sheet';
      dialog.setAttribute('aria-labelledby', 'sheet-title');
      // a tap on the dimmed page around it closes it, like Home Assistant's dialogs
      dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
      this.shadowRoot.appendChild(dialog);
      this._sheet = dialog;
    }
    dialog.innerHTML = this._stationHtml(s, s.rank != null ? s.rank : (this._sort === 'price' ? index + 1 : null));
    if (!dialog.open) dialog.showModal();
  }

  // ---------------------------------------------------------------- interaction
  _entityId(e) {
    const t = e.composedPath ? e.composedPath().find((n) => n.dataset && (n.dataset.station !== undefined || n.dataset.fuel || n.dataset.sort || n.dataset.close !== undefined || n.dataset.moreInfo)) : null;
    return t || null;
  }

  _down(e) {
    const t = this._entityId(e);
    this._long = false;
    clearTimeout(this._timer);
    this._start = { x: e.clientX, y: e.clientY };
    if (t && t.dataset.station !== undefined) {
      this._timer = setTimeout(() => {
        this._long = true;
        this._moreInfo(this._ids.home || this._ids.top5);
      }, 550);
    }
  }

  _move(e) {
    const s = this._start;
    if (s && Math.hypot((e.clientX || 0) - (s.x || 0), (e.clientY || 0) - (s.y || 0)) > 10) clearTimeout(this._timer);
  }

  // Enter / Space on a focused row or the favourite card acts like a tap
  _key(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    if (!this._entityId(e)) return;
    e.preventDefault();
    this._long = false;
    this._click(e);
  }

  _click(e) {
    if (e.composedPath && e.composedPath().some((n) => n.tagName === 'A')) return;
    const t = this._entityId(e);
    if (!t) return;
    if (this._long) { this._long = false; return; }
    if (t.dataset.fuel) this._switchFuel(t.dataset.fuel);
    else if (t.dataset.sort) this._setSort(t.dataset.sort);
    else if (t.dataset.close !== undefined) { if (this._sheet) this._sheet.close(); }
    else if (t.dataset.station !== undefined) this._openStation(Number(t.dataset.station));
    else if (t.dataset.moreInfo) this._moreInfo(t.dataset.moreInfo);
  }

  _moreInfo(entityId) {
    this.dispatchEvent(new CustomEvent('hass-more-info', { bubbles: true, composed: true, detail: { entityId } }));
  }
}


// ------------------------------------------------------------------ visual editor
const EDITOR_TEXT = {
  en: {
    fuel: 'Fuel', fuels: 'Fuels (switch, or the fuels shown)', config_id: 'Configuration / area', show: 'Parts to show', layout: 'Layout', stations: 'Stations in the list', compact: 'Compact', show_footer: 'Show update times and legend',
    map_height: 'Map height in px (0 = automatic)', logo_path: 'Folder of your own logos (leave empty for the logo pack)',
    show_regions: 'Show the 14 regions', days: 'Days back', navigator: 'Navigation app', badge_cheapest: 'The cheapest in the area', badge_mine: 'My station', badge_area: 'The area average', sort: 'Order of the stations', tank_litres: 'Fill-up in litres, kg for CNG (for "worth it")',
    consumption_n95: 'Petrol consumption', consumption_diesel: 'Diesel consumption', consumption_lpg: 'LPG consumption', consumption_cng: 'CNG consumption',
    consumption: 'Consumption per 100 km in litres, kg for CNG (for "worth it")', price: 'Price', distance: 'Distance', worth: 'Worth the drive',
    home: 'My station', list: 'Cheapest stations', map: 'Map', graph: '30-day graph: my station, the cheapest, the average',
    auto: 'Automatic: 2 columns when the card is wide', columns: 'Always 2 columns', stack: 'Always 1 column',
  },
  cs: {
    fuel: 'Palivo', fuels: 'Paliva (přepínač, nebo zobrazená paliva)', config_id: 'Konfigurace / oblast', show: 'Zobrazené části', layout: 'Rozvržení', stations: 'Počet stanic v seznamu', compact: 'Kompaktní', show_footer: 'Zobrazit časy aktualizace a legendu',
    map_height: 'Výška mapy v px (0 = automaticky)', logo_path: 'Složka s vlastními logy (prázdné = balíček log)',
    show_regions: 'Zobrazit 14 krajů', days: 'Kolik dní zpět', navigator: 'Navigační aplikace', badge_cheapest: 'Nejlevnější v oblasti', badge_mine: 'Moje stanice', badge_area: 'Průměr oblasti', sort: 'Řazení stanic', tank_litres: 'Kolik natankujete v litrech, u CNG v kg (pro „vyplatí se“)',
    consumption_n95: 'Spotřeba benzínu', consumption_diesel: 'Spotřeba nafty', consumption_lpg: 'Spotřeba LPG', consumption_cng: 'Spotřeba CNG',
    consumption: 'Spotřeba na 100 km v litrech, u CNG v kg (pro „vyplatí se“)', price: 'Cena', distance: 'Vzdálenost', worth: 'Vyplatí se dojet',
    home: 'Moje stanice', list: 'Nejlevnější stanice', map: 'Mapa', graph: 'Graf za 30 dní: moje stanice, nejlevnější, průměr',
    auto: 'Automaticky: 2 sloupce, je-li karta široká', columns: 'Vždy 2 sloupce', stack: 'Vždy 1 sloupec',
  },
};

class CenyPalivCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._render(); }
  set hass(hass) { this._hass = hass; this._render(); }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement('ha-form');
      this._form.addEventListener('value-changed', (e) => {
        // ha-form sends all of its data, including the defaults it was given for display: keep only what the
        // user set, so a legacy show_map/show_graph or the compact-dependent footer default survive an edit
        const defaults = editorDefaults(this._config);
        const config = Object.assign({}, this._config);
        for (const [k, v] of Object.entries(e.detail.value || {})) {
          if (!(k in this._config) && JSON.stringify(v) === JSON.stringify(defaults[k])) continue;
          config[k] = v;
        }
        if ('show' in config && JSON.stringify(config.show) !== JSON.stringify(defaults.show)) {
          delete config.show_map;  // an explicit `show` replaces the legacy options
          delete config.show_graph;
        }
        // config_id pins one configuration; it is only needed while several offer the fuel
        const availableConfigurations = CenyPalivCard.configurations(this._hass, config.fuel);
        const selectedConfigIsValid = availableConfigurations.some((item) => item.value === config.config_id);
        if (config.config_id && !selectedConfigIsValid) {
          if (availableConfigurations.length === 1) config.config_id = availableConfigurations[0].value;
          else delete config.config_id;
        }
        for (const k of Object.keys(config)) {
          const v = config[k];
          if (v === undefined || v === null || v === '' || (Array.isArray(v) && !v.length) || (k === 'map_height' && !v)) delete config[k];
        }
        this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    const code = (this._hass.language || 'en').split('-')[0];
    const lang = code in EDITOR_TEXT ? code : 'en';
    const L = EDITOR_TEXT[lang];
    const options = CenyPalivCard.fuels(this._hass);
    const configurations = CenyPalivCard.configurations(this._hass, this._config.fuel);
    this._form.hass = this._hass;
    // the editor gets every state change: rebuild the form only when what it shows has changed
    const stale = !!this._config.config_id && !configurations.some((item) => item.value === this._config.config_id);
    const key = JSON.stringify([lang, options, configurations, stale, this._config]);
    if (key === this._key) return;
    this._key = key;
    this._form.data = Object.assign(editorDefaults(this._config), this._config);
    this._form.schema = [
      { name: 'fuel', required: true, selector: { select: { options, mode: 'dropdown' } } },
      ...(options.length > 1 ? [{ name: 'fuels', selector: { select: { multiple: true, mode: 'list', options } } }] : []),
      // shown while several configurations offer the fuel, or to repair a pinned one that no longer exists
      ...(configurations.length > 1 || (stale && configurations.length)
        ? [{ name: 'config_id', selector: { select: { options: configurations, mode: 'dropdown' } } }]
        : []),
      { name: 'show', selector: { select: { multiple: true, mode: 'list', options: PARTS.map((p) => ({ value: p, label: L[p] })) } } },
      { name: 'layout', selector: { select: { mode: 'dropdown', options: ['auto', 'columns', 'stack'].map((p) => ({ value: p, label: L[p] })) } } },
      { name: 'stations', selector: { number: { min: 1, max: 5, step: 1, mode: 'slider' } } },
      { name: 'sort', selector: { select: { mode: 'dropdown', options: SORTS.map((p) => ({ value: p, label: L[p] })) } } },
      // litres, or kilograms for CNG: the formula only needs the fill-up and the consumption in the same unit
      { name: 'tank_litres', selector: { number: { min: 5, max: 150, step: 1, mode: 'box' } } },
      { name: 'consumption', selector: { number: { min: 1, max: 30, step: 0.1, mode: 'box' } } },
      { name: 'compact', selector: { boolean: {} } },
      { name: 'show_footer', selector: { boolean: {} } },
      { name: 'map_height', selector: { number: { min: 0, max: 800, step: 10, mode: 'box', unit_of_measurement: 'px' } } },
      { name: 'logo_path', selector: { text: {} } },
    ];
    this._form.computeLabel = (schema) => L[schema.name] || schema.name;
  }
}
if (!customElements.get('ceny-paliv-card-editor')) customElements.define('ceny-paliv-card-editor', CenyPalivCardEditor);

if (!customElements.get('ceny-paliv-card')) customElements.define('ceny-paliv-card', CenyPalivCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === 'ceny-paliv-card')) {
  window.customCards.push({
    type: 'ceny-paliv-card',
    name: 'Ceny paliv',
    preview: true,
    description: 'Czech fuel prices: cheapest stations of your city, your favourite station, map and a 30-day graph against the cheapest and the average, with navigation to a station (data from mBenzin.cz).',
  });
}
// ================================================================== the other cards
// Small cards for a dashboard: each shows one thing of one area (config entry), from the same sensors.

const FUEL_ORDER = ['n95', 'benzinplus', 'diesel', 'dieselplus', 'lpg', 'cng', 'adblue'];
const AREA_ROLES = ['top5', 'home', 'national_average', 'region_average', 'area_average'];

// The areas (config entries) with sensors, by their top5 sensors.
function areaIds(hass) {
  const out = [];
  for (const [id, st] of Object.entries((hass && hass.states) || {})) {
    const a = st.attributes || {};
    if (id.startsWith('sensor.ceny_paliv_') && a.cp_role === 'top5' && a.cp_config_id && !restored(st) && !out.includes(a.cp_config_id)) out.push(a.cp_config_id);
  }
  return out.sort();
}

// The sensors of one area by fuel and role (the active favourite only).
function areaSensors(hass, configId) {
  const out = {};
  for (const [id, st] of Object.entries((hass && hass.states) || {})) {
    const a = st.attributes || {};
    if (!id.startsWith('sensor.ceny_paliv_') || a.cp_config_id !== configId || !AREA_ROLES.includes(a.cp_role) || !a.cp_fuel || restored(st)) continue;
    if (a.cp_role === 'home' && ['unavailable', 'unknown'].includes(st.state)) continue;
    (out[a.cp_fuel] = out[a.cp_fuel] || {})[a.cp_role] = id;
  }
  return out;
}

// The areas for an editor's dropdown: their name and the start of their id.
function areaOptions(hass) {
  const seen = {};
  for (const [id, st] of Object.entries((hass && hass.states) || {})) {
    const a = st.attributes || {};
    if (id.startsWith('sensor.ceny_paliv_') && a.cp_role === 'top5' && a.cp_config_id && !(a.cp_config_id in seen)) {
      seen[a.cp_config_id] = `${a.city_name || 'GPS area'} (${a.cp_config_id.slice(0, 8)})`;
    }
  }
  return Object.entries(seen).map(([value, label]) => ({ value, label })).sort((x, y) => x.label.localeCompare(y.label));
}

const MINI_STYLE = `
  .tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--ha-space-2, 8px); }
  .tiles .trend { min-height: 56px; }
  .tiles .delta { font-size: var(--ha-font-size-m, 14px); }
  .tiles .trend.best .delta { color: var(--cp-good); }
  .row .icon { width: 36px; height: 36px; --mdc-icon-size: 20px; }
  .row .price .diff.mine { color: var(--cp-home); }
`;

class CenyPalivMiniCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._sig = '';
    this.shadowRoot.addEventListener('click', (e) => this._open(e));
    this.shadowRoot.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this._open(e); } });
  }

  static get defaults() { return {}; }

  setConfig(config) {
    if (!config) throw new Error('ceny-paliv: missing configuration');
    this._config = Object.assign({}, this.constructor.defaults, config);
    this._sig = '';
    if (this._hass) this.hass = this._hass;
  }

  set hass(hass) {
    hass = withLastKnown(hass);
    this._hass = hass;
    if (!this._config) return;
    const areas = areaIds(hass);
    const area = this._config.config_id && areas.includes(this._config.config_id) ? this._config.config_id : (areas.length === 1 ? areas[0] : null);
    this._area = area;
    this._why = area ? null : (this._config.config_id ? 'gone' : (areas.length ? 'ambiguous' : 'missing'));
    this._sensors = area ? areaSensors(hass, area) : {};
    const ids = [];
    for (const f of Object.values(this._sensors)) ids.push(...Object.values(f));
    const sig = [JSON.stringify(this._config), area, new Date().toDateString(), hass.language,
      this._historySignature?.() || '', ...ids.sort().map((id) => `${id}:${hass.states[id].state}:${hass.states[id].last_updated}`)].join('|');
    if (sig === this._sig || (this._sheet && this._sheet.open)) return;
    this._sig = sig;
    this.shadowRoot.innerHTML = `<style>${STYLE}${MINI_STYLE}</style>${this._area ? this._render() : this._message()}`;
  }

  getCardSize() { return 3; }
  getGridOptions() { return { columns: 6, min_columns: 3, rows: 'auto' }; }

  // the texts of the integration's language, from any top5 sensor of the area
  _labels() {
    for (const f of Object.values(this._sensors || {})) {
      const top = f.top5 && this._hass.states[f.top5];
      if (top && top.attributes && top.attributes.labels) return top.attributes.labels;
    }
    return {};
  }

  _state(fuel, role) {
    const id = ((this._sensors || {})[fuel] || {})[role];
    return id ? this._hass.states[id] : null;
  }

  _fuels() {
    const have = Object.keys(this._sensors || {}).filter((f) => this._sensors[f].top5);
    const wanted = Array.isArray(this._config.fuels) && this._config.fuels.length ? this._config.fuels : FUEL_ORDER.concat(have);
    return wanted.filter((f, i) => have.includes(f) && wanted.indexOf(f) === i);
  }

  _message() {
    const cs = ((this._hass && this._hass.language) || 'en').split('-')[0] === 'cs';
    const text = {
      missing: cs ? 'nebyly nalezeny žádné senzory Ceny paliv.' : 'no Ceny paliv sensors found.',
      ambiguous: cs ? 'máte více oblastí — vyberte jednu v editoru karty.' : 'there are several areas — choose one in the card editor.',
      gone: cs ? 'zvolená oblast už neexistuje — vyberte ji znovu v editoru karty.' : 'the chosen area no longer exists — choose it again in the card editor.',
    }[this._why];
    return `<ha-card class="card message"><ha-icon icon="mdi:gas-station-off-outline"></ha-icon><span>Ceny paliv: ${esc(text)}</span></ha-card>`;
  }

  _money(value) { return `${this._num(value, 0)} Kč`; }

  _open(e) {
    const t = e.composedPath ? e.composedPath().find((n) => n.dataset && n.dataset.moreInfo) : null;
    if (t) this.dispatchEvent(new CustomEvent('hass-more-info', { bubbles: true, composed: true, detail: { entityId: t.dataset.moreInfo } }));
  }

  static getConfigElement() {
    const editor = document.createElement('ceny-paliv-mini-editor');
    editor.card = this;
    return editor;
  }
}
// the formatting of the main card: numbers, days and texts as there
for (const m of ['_T', '_numberLocale', '_num', '_day', '_arrow', '_source']) CenyPalivMiniCard.prototype[m] = CenyPalivCard.prototype[m];

// ------------------------------------------------------------------ 1. every fuel at a glance
class CenyPalivFuelsCard extends CenyPalivMiniCard {
  static getStubConfig() { return { type: 'custom:ceny-paliv-fuels-card' }; }

  static editorSchema(hass) {
    return [{ name: 'fuels', selector: { select: { multiple: true, mode: 'list', options: CenyPalivCard.fuels(hass) } } }];
  }

  getCardSize() { return 1 + this._fuels().length; }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuels = this._fuels();
    const first = this._state(fuels[0], 'top5');
    const rows = fuels.map((fuel) => {
      const top = this._state(fuel, 'top5');
      const home = this._state(fuel, 'home');
      const a = top.attributes || {};
      const cheapest = (a.stations || [])[0];
      const ok = !['unavailable', 'unknown'].includes(top.state);
      const unit = a.unit_of_measurement || 'Kč/l';
      // the price's direction since yesterday: your station's, else the cheapest station's
      const trend = (home && home.attributes.trends && home.attributes.trends['1']) || (cheapest && cheapest.trends && cheapest.trends['1']);
      const r = this._arrow(trend);
      const mine = home && !['unavailable', 'unknown'].includes(home.state) ? T('mine_short', { p: this._num(home.state) }) : '';
      const where = cheapest ? (cheapest.title || cheapest.name || '') : T('no_recent');
      return `<div class="row" role="button" tabindex="0" data-more-info="${esc(top.entity_id || this._sensors[fuel].top5)}" aria-label="${esc(a.fuel_label || fuel)}: ${ok ? this._num(top.state) : '—'} ${esc(unit)}">
        <span class="icon fuel"><ha-icon icon="mdi:gas-station"></ha-icon></span>
        <div class="info"><span class="primary">${esc(a.fuel_label || fuel)}</span><span class="secondary">${esc(where)}</span></div>
        <span class="change ${r.cls}" title="${esc(T('vs_yesterday'))}">${trend ? `<ha-icon icon="${r.icon}"></ha-icon>` : ''}${esc(r.txt)}</span>
        <span class="price"><span class="number">${ok ? this._num(top.state) : '—'}</span>${mine ? `<span class="diff mine">${esc(mine)}</span>` : ''}</span>
      </div>`;
    }).join('');
    const area = first ? first.attributes.city_name || '' : '';
    return `<ha-card class="card">
      <div class="head"><span class="icon fuel"><ha-icon icon="mdi:gas-station-outline"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T('fuels_title'))}</span><span class="secondary">${esc(area)}</span></div></div>
      <div class="rows">${rows}</div>
      <span class="source">${this._source()}</span>
    </ha-card>`;
  }
}

// ------------------------------------------------------------------ 2. what a full tank costs, and the saving
// Your station against the cheapest and the area average; the extra drive to the cheapest is counted as in the main
// card's "worth it" order (there and back, in a straight line, at your consumption).
function fillUpSaving({ mine, cheapest, tank, consumption, kmMine, kmCheapest }) {
  if (cheapest == null || mine == null || mine <= cheapest) return null;
  const save = (mine - cheapest) * tank;
  if (kmMine == null || kmCheapest == null) return { save, extraKm: null, driveCost: null, net: null };
  const extraKm = Math.max(0, 2 * (kmCheapest - kmMine));
  const driveCost = (extraKm * consumption / 100) * cheapest;
  return { save, extraKm, driveCost, net: save - driveCost };
}

class CenyPalivSavingsCard extends CenyPalivMiniCard {
  static get defaults() { return { tank_litres: 40, consumption: 6.5 }; }

  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-savings-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass) {
    return [
      { name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } },
      { name: 'tank_litres', selector: { number: { min: 5, max: 150, step: 1, mode: 'box' } } },
      { name: 'consumption', selector: { number: { min: 1, max: 30, step: 0.1, mode: 'box' } } },
    ];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-savings-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  _km(station, at) {
    if (!station) return null;
    if (station.distance_km != null && isFinite(Number(station.distance_km))) return Number(station.distance_km);
    const lat = Number(station.lat != null ? station.lat : station.latitude);
    const lng = Number(station.lng != null ? station.lng : station.longitude);
    const center = CenyPalivCard.prototype._center.call(this, at);
    return center && isFinite(lat) && isFinite(lng) && (station.lat != null || station.latitude != null) ? kmBetween(center[0], center[1], lat, lng) : null;
  }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const top = this._state(fuel, 'top5');
    if (!top) { this._why = 'missing'; return this._message(); }
    const home = this._state(fuel, 'home');
    const avg = this._state(fuel, 'area_average');
    const at = top.attributes || {};
    const positive = (v, d) => (Number(v) > 0 ? Number(v) : d);
    const tank = positive(this._config.tank_litres, 40);
    const consumption = positive(this._config.consumption, 6.5);
    const amount = /kg/.test(at.unit_of_measurement || '') ? 'kg' : 'l';
    const number = (st) => (st && !['unavailable', 'unknown'].includes(st.state) && isFinite(Number(st.state)) ? Number(st.state) : null);
    const cheapestStation = (at.stations || [])[0];
    const cheapest = number(top);
    const mine = number(home);
    const average = number(avg);
    const name = (cheapestStation && cheapestStation.name) || '';
    const tile = (label, price, best) => `<div class="trend${best ? ' best' : ''}"><span class="label">${esc(label)}</span>
      <span class="delta">${price == null ? '—' : esc(this._money(price * tank))}</span></div>`;
    const tiles = [
      home ? tile(T('my_station'), mine, mine != null && mine <= cheapest) : '',
      tile(T('cheapest_badge'), cheapest, true),
      avg ? tile(T('series_average'), average, false) : '',
    ].filter(Boolean);
    const saving = fillUpSaving({ mine, cheapest, tank, consumption, kmMine: this._km(home && home.attributes, at), kmCheapest: this._km(cheapestStation, at) });
    let status;
    if (saving) status = { cls: 'good', icon: 'mdi:piggy-bank-outline', text: T('save_at', { name, d: this._num(saving.save, 0) }) };
    else if (mine != null && cheapest != null) status = { cls: 'good', icon: 'mdi:trophy-outline', text: T('mine_cheapest') };
    else if (average != null && cheapest != null && average > cheapest) status = { cls: 'good', icon: 'mdi:piggy-bank-outline', text: T('save_vs_avg', { name, d: this._num((average - cheapest) * tank, 0) }) };
    else status = null;
    let drive = '';
    if (saving && saving.extraKm != null && saving.extraKm > 0) {
      const worth = saving.net > 0;
      drive = `<div class="status ${worth ? 'muted' : 'warn'}"><ha-icon icon="mdi:car-arrow-right"></ha-icon><span>${esc(T('drive_extra', { km: this._num(saving.extraKm, 1), d: this._num(saving.driveCost, 0) }))} · ${esc(worth ? T('worth_yes', { d: this._num(saving.net, 0) }) : T('worth_no'))}</span></div>`;
    }
    return `<ha-card class="card" role="button" tabindex="0" data-more-info="${esc(this._sensors[fuel].home || this._sensors[fuel].top5)}">
      <div class="head"><span class="icon home"><ha-icon icon="mdi:fuel"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T('savings_title'))} · ${esc(at.fuel_label || fuel)}</span>
          <span class="secondary">${esc(T('fill_up', { n: this._num(tank, 0), u: amount }))} · ${esc(at.city_name || '')}</span></div></div>
      <div class="tiles" style="grid-template-columns: repeat(${tiles.length}, minmax(0, 1fr))">${tiles.join('')}</div>
      ${status ? `<div class="status ${status.cls}"><ha-icon icon="${status.icon}"></ha-icon><span>${esc(status.text)}</span></div>` : ''}
      ${drive}
      <span class="source">${this._source()}</span>
    </ha-card>`;
  }
}

// ------------------------------------------------------------------ 3. the area against the region and the country
// "Hlavní město Praha" -> "Praha", "Jihomoravský kraj" -> "Jihomoravský", "Kraj Vysočina" -> "Vysočina"
const shortRegion = (name) => String(name || '').replace(/^Hlavní město /, '').replace(/^Kraj /, '').replace(/ kraj$/, '');

const COMPARE_STYLE = `
  .bars { display: flex; flex-direction: column; gap: var(--ha-space-2, 8px); }
  .bar-row { color: var(--cp-text); display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px var(--ha-space-3, 12px); align-items: baseline; }
  .bar-row .label { font-size: var(--ha-font-size-m, 14px); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bar-row .value { font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; }
  .bar-row .vs { font-size: var(--ha-font-size-xs, 10px); color: var(--cp-muted); margin-inline-start: 4px; font-weight: var(--ha-font-weight-normal, 400); }
  .bar { grid-column: 1 / -1; position: relative; height: 8px; border-radius: var(--ha-border-radius-pill, 9999px); overflow: hidden; }
  .bar::before { content: ""; position: absolute; inset: 0; background: var(--cp-neutral); opacity: 0.2; }
  .bar span { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background: var(--bar, var(--cp-muted)); }
  .bar-row.mine { --bar: var(--cp-home); }
  .bar-row.best { --bar: var(--cp-good-base); }
  .ranks { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2px var(--ha-space-4, 16px); font-size: var(--ha-font-size-s, 12px); line-height: 18px; }
  .ranks span { display: flex; gap: var(--ha-space-2, 8px); color: var(--cp-muted); min-width: 0; }
  .ranks .n { flex: none; width: 18px; text-align: end; font-variant-numeric: tabular-nums; }
  .ranks .r { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ranks b { font-weight: var(--ha-font-weight-normal, 400); font-variant-numeric: tabular-nums; }
  .ranks .own { color: var(--cp-text); font-weight: var(--ha-font-weight-medium, 500); }
  .ranks .own b { font-weight: var(--ha-font-weight-medium, 500); color: var(--cp-home); }
  .section { font-size: var(--ha-font-size-s, 12px); color: var(--cp-muted); letter-spacing: 0.4px; }
`;

class CenyPalivCompareCard extends CenyPalivMiniCard {
  static get defaults() { return { show_regions: true }; }

  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-compare-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass) {
    return [
      { name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } },
      { name: 'show_regions', selector: { boolean: {} } },
    ];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-compare-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  getCardSize() { return this._config && this._config.show_regions !== false ? 7 : 4; }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const top = this._state(fuel, 'top5');
    const national = this._state(fuel, 'national_average');
    if (!top || !national) { this._why = 'missing'; return this._message(); }
    const value = (st) => (st && !['unavailable', 'unknown'].includes(st.state) && isFinite(Number(st.state)) ? Number(st.state) : null);
    const home = this._state(fuel, 'home');
    const region = this._state(fuel, 'region_average');
    const area = this._state(fuel, 'area_average');
    const country = value(national);
    const regionName = region && region.attributes.region;
    const rows = [
      home && { cls: 'mine', label: T('my_station'), v: value(home), id: this._sensors[fuel].home },
      { cls: '', label: `${T('compare_area')} · ${top.attributes.city_name || ''}`, v: value(area), id: this._sensors[fuel].area_average },
      region && { cls: '', label: `${T('compare_region')} · ${shortRegion(regionName)}`, v: value(region), id: this._sensors[fuel].region_average },
      { cls: '', label: T('compare_country'), v: country, id: this._sensors[fuel].national_average, country: true },
    ].filter((r) => r && r.v != null);
    const values = rows.map((r) => r.v);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const bars = rows.map((r) => {
      // the shortest bar is a quarter: the differences are a few crowns of some forty
      const width = hi > lo ? 25 + 75 * (r.v - lo) / (hi - lo) : 100;
      const vs = r.country ? '' : `<span class="vs">${esc(this._signed(r.v - country))}</span>`;
      return `<div class="bar-row ${r.cls}${r.v === lo && rows.length > 1 ? ' best' : ''}" role="button" tabindex="0" data-more-info="${esc(r.id)}">
        <span class="label">${esc(r.label)}</span><span class="value">${esc(this._num(r.v))}${vs}</span>
        <span class="bar" aria-hidden="true"><span style="width:${width.toFixed(1)}%"></span></span></div>`;
    }).join('');
    let ranks = '';
    const list = Array.isArray(national.attributes.regions) ? national.attributes.regions : [];
    if (this._config.show_regions !== false && list.length) {
      const own = region && region.attributes.region_code;
      const half = Math.ceil(list.length / 2);
      // column by column: 1-7 on the left, 8-14 on the right
      const ordered = [];
      for (let i = 0; i < half; i += 1) { ordered.push(list[i]); if (list[i + half]) ordered.push(list[i + half]); }
      ranks = `<span class="section">${esc(T('compare_ranks', { n: list.length }))}</span>
        <div class="ranks">${ordered.map((r) => `<span class="${r.code === own ? 'own' : ''}"><span class="n">${esc(r.rank)}.</span><span class="r">${esc(shortRegion(r.name))}</span><b>${esc(this._num(r.average))}</b></span>`).join('')}</div>`;
    }
    return `<ha-card class="card"><style>${COMPARE_STYLE}</style>
      <div class="head"><span class="icon fuel"><ha-icon icon="mdi:scale-balance"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T('compare_title'))} · ${esc(top.attributes.fuel_label || fuel)}</span>
          <span class="secondary">${esc(T('compare_sub', { unit: top.attributes.unit_of_measurement || 'Kč/l' }))}</span></div></div>
      <div class="bars">${bars}</div>
      ${ranks}
      <span class="source">${this._source()}</span>
    </ha-card>`;
  }

  _signed(d) { return `${d > 0 ? '+' : d < 0 ? '−' : '±'}${this._num(Math.abs(d))}`; }
}

// ------------------------------------------------------------------ 4. a map of the regions
// The boundaries come from the integration (regions.json, ČÚZK RÚIAN, CC BY 4.0), loaded once per page.
const REGIONS_URL = '/ceny_paliv_static/regions.json';
let regionGeometry = null;
let regionGeometryLoad = null;

function loadRegionGeometry() {
  if (regionGeometry || regionGeometryLoad || typeof fetch !== 'function') return regionGeometryLoad;
  regionGeometryLoad = fetch(`${REGIONS_URL}?v=${CARD_VERSION}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => { regionGeometry = data; return data; })
    .catch(() => null)
    .finally(() => { regionGeometryLoad = null; });
  return regionGeometryLoad;
}

// The regions as SVG paths: longitude shrunk by the cosine of the country's latitude, so the map is not stretched.
function regionPaths(data, width) {
  const regions = (data && data.regions) || [];
  let south = 90; let north = -90; let west = 180; let east = -180;
  for (const r of regions) for (const p of r.polygons) for (const [lat, lng] of p[0]) {
    south = Math.min(south, lat); north = Math.max(north, lat); west = Math.min(west, lng); east = Math.max(east, lng);
  }
  const k = Math.cos(((south + north) / 2) * Math.PI / 180);
  const scale = width / ((east - west) * k || 1);
  const height = (north - south) * scale;
  const pt = ([lat, lng]) => `${((lng - west) * k * scale).toFixed(1)},${((north - lat) * scale).toFixed(1)}`;
  const paths = regions.map((r) => ({
    code: r.code,
    name: r.name,
    holes: r.polygons.reduce((n, p) => n + p.length - 1, 0),
    d: r.polygons.map((p) => p.map((ring) => `M${ring.map(pt).join('L')}Z`).join('')).join(''),
  }));
  // a region with a hole (Středočeský around Prague) goes first, so the region inside it is drawn on top
  paths.sort((x, y) => y.holes - x.holes);
  return { paths, width, height: Math.ceil(height) };
}

const REGIONS_STYLE = `
  .regions svg { display: block; width: 100%; height: auto; }
  .regions path { stroke: var(--cp-surface); stroke-width: 1; stroke-linejoin: round; fill-rule: evenodd; cursor: pointer; outline: none; }
  .regions path.none { fill: var(--cp-neutral); fill-opacity: 0.4; }
  .regions path.own { stroke: var(--cp-text); stroke-width: 2.5; }
  .regions path.picked { stroke: var(--cp-home); stroke-width: 2.5; }
  .regions path:focus-visible { stroke: var(--cp-home); stroke-width: 3; }
  .scale { display: flex; align-items: center; gap: var(--ha-space-2, 8px); font-size: var(--ha-font-size-s, 12px); color: var(--cp-muted); font-variant-numeric: tabular-nums; }
  .scale .ramp { flex: 1 1 auto; height: 8px; border-radius: var(--ha-border-radius-pill, 9999px);
    background: linear-gradient(90deg, var(--cp-good-base), color-mix(in srgb, var(--cp-good-base), var(--cp-bad-base)), var(--cp-bad-base)); opacity: 0.85; }
  .picked-info { font-size: var(--ha-font-size-m, 14px); min-height: 20px; }
  .picked-info b { font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; }
`;

class CenyPalivRegionsCard extends CenyPalivMiniCard {
  constructor() {
    super();
    // a tap (or Enter) on a region shows its price and rank under the map
    this.shadowRoot.addEventListener('click', (e) => this._pick(e));
    this.shadowRoot.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') this._pick(e); });
  }

  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-regions-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass) {
    return [{ name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } }];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-regions-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  getCardSize() { return 5; }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const national = this._state(fuel, 'national_average');
    const top = this._state(fuel, 'top5');
    if (!national || !top) { this._why = 'missing'; return this._message(); }
    if (!regionGeometry) {
      const loading = loadRegionGeometry();
      if (loading) loading.then(() => { this._sig = ''; if (this._hass) this.hass = this._hass; });
    }
    const list = Array.isArray(national.attributes.regions) ? national.attributes.regions : [];
    const byCode = {};
    for (const r of list) byCode[r.code] = r;
    const prices = list.map((r) => Number(r.average)).filter((v) => isFinite(v));
    const lo = prices.length ? Math.min(...prices) : 0;
    const hi = prices.length ? Math.max(...prices) : 0;
    const region = this._state(fuel, 'region_average');
    const own = region && region.attributes.region_code;
    this._regions = byCode;
    let map = `<span class="note">${esc(T('regions_loading'))}</span>`;
    if (regionGeometry) {
      const shape = regionPaths(regionGeometry, 400);
      map = `<svg viewBox="0 0 ${shape.width} ${shape.height}" role="group" aria-label="${esc(T('regions_title'))}">${shape.paths.map((p) => {
        const r = byCode[p.code];
        const v = r ? Number(r.average) : NaN;
        // cheapest green, dearest red, mixed in between: both theme colours, so it works in light and dark
        const t = isFinite(v) && hi > lo ? Math.round(100 * (v - lo) / (hi - lo)) : 50;
        const fill = isFinite(v) ? `fill: color-mix(in srgb, var(--cp-bad-base) ${t}%, var(--cp-good-base)); fill-opacity: 0.85` : '';
        const label = r ? `${p.name}: ${this._num(v)} (${r.rank}.)` : p.name;
        const cls = [isFinite(v) ? '' : 'none', p.code === own ? 'own' : '', p.code === this._picked ? 'picked' : ''].filter(Boolean).join(' ');
        return `<path class="${cls}" d="${p.d}" style="${fill}" tabindex="0" role="button" data-region="${esc(p.code)}" aria-label="${esc(label)}"><title>${esc(label)}</title></path>`;
      }).join('')}</svg>`;
    }
    const pickedCode = this._picked || own;
    const picked = pickedCode && byCode[pickedCode];
    const info = picked
      ? `${esc(picked.name)}: <b>${esc(this._num(picked.average))} ${esc(top.attributes.unit_of_measurement || 'Kč/l')}</b> · ${esc(T('rank_of', { rank: picked.rank, n: list.length }))}`
      : '';
    return `<ha-card class="card"><style>${REGIONS_STYLE}</style>
      <div class="head"><span class="icon fuel"><ha-icon icon="mdi:map-outline"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T('regions_title'))} · ${esc(top.attributes.fuel_label || fuel)}</span>
          <span class="secondary">${esc(T('regions_sub'))}</span></div></div>
      <div class="regions">${map}</div>
      <div class="picked-info" aria-live="polite">${info}</div>
      ${prices.length ? `<div class="scale"><span>${esc(this._num(lo))}</span><span class="ramp" aria-hidden="true"></span><span>${esc(this._num(hi))}</span></div>` : ''}
      <span class="source">${this._source()} · ${esc(T('regions_source'))}</span>
    </ha-card>`;
  }

  _pick(e) {
    const t = e.composedPath ? e.composedPath().find((n) => n.dataset && n.dataset.region) : null;
    if (!t) return;
    if (e.preventDefault) e.preventDefault();
    this._picked = t.dataset.region;
    this._sig = '';
    if (this._hass) this.hass = this._hass;
  }
}

// ------------------------------------------------------------------ 5. the stations on a map
// A schematic map drawn by the card: the region borders, the area's circle and centre, and the stations as dots
// coloured from the cheapest to the dearest, the cheapest ones and yours labelled with their price. No map tiles:
// it works offline and in any theme. A tap opens the station's details and navigation, as in the main card.
const MAP_W = 400;
const MAP_H = 300;

// Kilometres east and south of a point, for a small area (a plane is exact enough within 50 km).
function toKm(lat, lng, lat0, lng0) {
  return [(lng - lng0) * Math.cos(lat0 * Math.PI / 180) * 111.32, (lat0 - lat) * 110.574];
}

const STATIONS_MAP_STYLE = `
  .smap svg { display: block; width: 100%; height: auto; border-radius: var(--cp-radius); overflow: hidden; }
  .smap .land { fill: var(--cp-neutral); fill-opacity: 0.12; }
  .smap .border { fill: none; stroke: var(--cp-line); stroke-width: 1; }
  .smap .area { fill: var(--cp-home); fill-opacity: 0.06; stroke: var(--cp-home); stroke-opacity: 0.5; stroke-width: 1.5; stroke-dasharray: 5 4; }
  .smap .center { fill: var(--cp-home); stroke: var(--cp-surface); stroke-width: 2; }
  .smap .st { cursor: pointer; outline: none; }
  .smap .st circle { stroke: var(--cp-surface); stroke-width: 1.5; }
  .smap .st.home circle { stroke: var(--cp-home); stroke-width: 3; }
  .smap .st:focus-visible circle { stroke: var(--cp-text); stroke-width: 3; }
  .smap .chip rect { fill: var(--cp-surface); stroke: currentColor; stroke-width: 1.5; }
  .smap .chip text { fill: var(--cp-text); font-size: 11px; font-weight: 500; font-family: inherit; font-variant-numeric: tabular-nums; }
`;

class CenyPalivStationsMapCard extends CenyPalivMiniCard {
  constructor() {
    super();
    this._sort = 'map';  // a station from the nearest list has no price rank in its details
    this.shadowRoot.addEventListener('click', (e) => this._tap(e));
    this.shadowRoot.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') this._tap(e); });
  }

  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-stations-map-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass) {
    return [{ name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } }];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-stations-map-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  getCardSize() { return 6; }

  // the up-to-date stations: the cheapest ones and, in a GPS area, the nearest ones, each once
  _stations(at) {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const maxAge = at.max_age_days != null ? Number(at.max_age_days) : 1;
    const fresh = (list) => (Array.isArray(list) ? list : []).filter((x) => this._age(x, today) <= maxAge);
    const seen = new Set();
    const out = [];
    const cheapest = new Set(fresh(at.stations));
    for (const x of fresh(at.stations).concat(fresh(at.gps_nearest_stations))) {
      const id = `${x.name}|${x.lat}|${x.lng}|${x.price}`;
      if (seen.has(id) || !isFinite(Number(x.lat)) || !isFinite(Number(x.lng)) || !isFinite(Number(x.price))) continue;
      seen.add(id);
      out.push(Object.assign({}, x, { rank: cheapest.has(x) ? x.rank : null }));
    }
    return out;
  }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const top = this._state(fuel, 'top5');
    if (!top) { this._why = 'missing'; return this._message(); }
    if (!regionGeometry) {
      const loading = loadRegionGeometry();
      if (loading) loading.then(() => { this._sig = ''; if (this._hass) this.hass = this._hass; });
    }
    const at = top.attributes || {};
    this._ids = { top5: this._sensors[fuel].top5 };  // the borrowed details use the area's logos
    const stations = this._stations(at);
    const prices = stations.map((x) => Number(x.price));
    const min = prices.length ? Math.min(...prices) : null;
    const max = prices.length ? Math.max(...prices) : null;
    const unit = at.unit_of_measurement || 'Kč/l';
    // the details rank a station among all the area's up-to-date stations, as the main card does
    const total = at.city_total != null ? at.city_total : (at.gps_area && at.gps_area.station_count);
    const upToDate = total != null && isFinite(Number(total)) ? Number(total) - Number(at.excluded || 0) : stations.length;
    this._rows = { list: stations, fresh: Math.max(upToDate, stations.length), unit, min };
    const area = at.gps_area || null;
    const center = CenyPalivCard.prototype._center.call(this, at);
    // the frame: the circle of a GPS area, else the stations with a kilometre around them
    let lat0; let lng0; let half;
    if (area && center && Number(area.radius_km) > 0) {
      [lat0, lng0] = center;
      half = Number(area.radius_km) * 1.08;
    } else if (stations.length) {
      const lats = stations.map((x) => Number(x.lat));
      const lngs = stations.map((x) => Number(x.lng));
      lat0 = (Math.min(...lats) + Math.max(...lats)) / 2;
      lng0 = (Math.min(...lngs) + Math.max(...lngs)) / 2;
      const [w, h] = toKm(Math.min(...lats), Math.max(...lngs), lat0, lng0).map(Math.abs);
      half = Math.max(2, w * MAP_H / MAP_W, h) + 1;
    } else {
      return `<ha-card class="card"><span class="note">${esc(T('no_recent'))}</span></ha-card>`;
    }
    const scale = (Math.min(MAP_W, MAP_H) / 2) / half;  // view units per kilometre: the frame fits the shorter side
    const view = (lat, lng) => { const [x, y] = toKm(lat, lng, lat0, lng0); return [MAP_W / 2 + x * scale, MAP_H / 2 + y * scale]; };
    const pts = (ring) => ring.map(([lat, lng]) => view(lat, lng).map((v) => v.toFixed(1)).join(',')).join('L');
    let land = '';
    if (regionGeometry && regionGeometry.regions) {
      const d = regionGeometry.regions.map((r) => r.polygons.map((p) => `M${pts(p[0])}Z`).join('')).join('');
      land = `<path class="land" d="${d}"></path><path class="border" d="${d}"></path>`;
    }
    const circle = area && center && Number(area.radius_km) > 0
      ? `<circle class="area" cx="${MAP_W / 2}" cy="${MAP_H / 2}" r="${(Number(area.radius_km) * scale).toFixed(1)}"></circle>` : '';
    const mark = center ? (() => { const [cx, cy] = view(center[0], center[1]); return `<circle class="center" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="5"><title>${esc(T('map_center'))}</title></circle>`; })() : '';
    const colour = (price) => {
      const t = max > min ? Math.round(100 * (price - min) / (max - min)) : 0;
      return `color-mix(in srgb, var(--cp-bad-base) ${t}%, var(--cp-good-base))`;
    };
    // labels for the five cheapest and your station, the cheapest first; one that would cover another is left out
    const placed = [];
    const order = stations.map((x, i) => i).sort((a, b) => stations[a].price - stations[b].price);
    const labelled = new Set(order.filter((i) => stations[i].rank != null || stations[i].home).slice(0, 6));
    const dots = [];  // the dearest first, so the cheapest dots lie on top
    const chips = [];
    for (const i of order) {
      const x = stations[i];
      const [px, py] = view(Number(x.lat), Number(x.lng));
      const label = `${x.name}: ${this._num(x.price)} ${unit}`;
      dots.unshift(`<g class="st${x.home ? ' home' : ''}" role="button" tabindex="0" data-station="${i}" aria-label="${esc(label)}" style="color: ${colour(Number(x.price))}">
        <circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="6" fill="currentColor"></circle><title>${esc(label)}</title></g>`);
      if (!labelled.has(i)) continue;
      const text = this._num(x.price);
      const w = 8 + text.length * 6.2;
      const box = [px - w / 2, py - 27, w, 18];
      if (placed.some((b) => box[0] < b[0] + b[2] && b[0] < box[0] + box[2] && box[1] < b[1] + b[3] && b[1] < box[1] + box[3])) continue;
      placed.push(box);
      chips.push(`<g class="chip st" data-station="${i}" style="color: ${colour(Number(x.price))}"><rect x="${box[0].toFixed(1)}" y="${box[1].toFixed(1)}" width="${w.toFixed(1)}" height="18" rx="9"></rect>
        <text x="${px.toFixed(1)}" y="${(py - 14.5).toFixed(1)}" text-anchor="middle">${esc(text)}</text></g>`);
    }
    const where = area ? `${at.city_name || ''} · ${this._num(area.radius_km, 0)} km` : (at.city_name || '');
    return `<ha-card class="card"><style>${STATIONS_MAP_STYLE}${REGIONS_STYLE}</style>
      <div class="head"><span class="icon fuel"><ha-icon icon="mdi:map-marker-multiple-outline"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T('map_title'))} · ${esc(at.fuel_label || fuel)}</span>
          <span class="secondary">${esc(where)} · ${esc(T('map_sub', { n: stations.length }))}</span></div></div>
      <div class="smap"><svg viewBox="0 0 ${MAP_W} ${MAP_H}" role="group" aria-label="${esc(T('map_title'))}">${land}${circle}${mark}${dots.join('')}${chips.join('')}</svg></div>
      ${min != null ? `<div class="scale"><span>${esc(this._num(min))}</span><span class="ramp" aria-hidden="true"></span><span>${esc(this._num(max))}</span></div>` : ''}
      <span class="source">${this._source()} · ${esc(T('regions_source'))}</span>
    </ha-card>`;
  }

  _tap(e) {
    const path = e.composedPath ? e.composedPath() : [];
    if (path.some((n) => n.dataset && n.dataset.close !== undefined)) { if (this._sheet) this._sheet.close(); return; }
    const t = path.find((n) => n.dataset && n.dataset.station !== undefined);
    if (!t) return;
    if (e.preventDefault) e.preventDefault();
    const fresh = !this._sheet;
    this._openStation(Number(t.dataset.station));
    // the map is drawn again once the details close (it waits while they are open)
    if (fresh && this._sheet) this._sheet.addEventListener('close', () => { this._sig = ''; if (this._hass) this.hass = this._hass; });
  }
}
// the station details of the main card: the same panel, the same navigation
for (const m of ['_stationHtml', '_openStation', '_trendTiles', '_when', '_age', '_avatar', '_disc', '_logoUrl', '_initials']) {
  CenyPalivStationsMapCard.prototype[m] = CenyPalivCard.prototype[m];
}

// ------------------------------------------------------------------ 6. one fuel in every area
// An area is named as its device in Home Assistant (the entry's title, or the name the user gave the device).
function areaName(hass, entityId, fallback) {
  const entity = hass.entities && hass.entities[entityId];
  const device = entity && entity.device_id && hass.devices && hass.devices[entity.device_id];
  return (device && (device.name_by_user || device.name)) || fallback || '';
}

class CenyPalivAreasCard extends CenyPalivMiniCard {
  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-areas-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass) {
    return [{ name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } }];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-areas-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  // every area, not one: the base's choice of an area does not apply
  set hass(hass) {
    hass = withLastKnown(hass);
    this._hass = hass;
    if (!this._config) return;
    const fuel = this._config.fuel;
    this._areas = areaIds(hass).map((id) => ({ id, sensors: areaSensors(hass, id)[fuel] || {} })).filter((a) => a.sensors.top5);
    this._sensors = this._areas.length ? { [fuel]: this._areas[0].sensors } : {};  // the texts of the first area
    const ids = this._areas.flatMap((a) => Object.values(a.sensors)).sort();
    const sig = [JSON.stringify(this._config), new Date().toDateString(), hass.language,
      ...ids.map((id) => `${id}:${hass.states[id].state}:${hass.states[id].last_updated}`)].join('|');
    if (sig === this._sig) return;
    this._sig = sig;
    this._why = 'missing';
    this.shadowRoot.innerHTML = `<style>${STYLE}${MINI_STYLE}</style>${this._areas.length ? this._render() : this._message()}`;
  }

  getCardSize() { return 2 + (this._areas ? this._areas.length : 1); }

  _render() {
    const T = (k, v) => this._T(k, v);
    const value = (id) => { const st = id && this._hass.states[id]; return st && isFinite(Number(st.state)) && !['unavailable', 'unknown'].includes(st.state) ? Number(st.state) : null; };
    const rows = this._areas.map((a) => {
      const top = this._hass.states[a.sensors.top5];
      return { a, top, cheapest: value(a.sensors.top5), average: value(a.sensors.area_average), mine: value(a.sensors.home),
        name: areaName(this._hass, a.sensors.top5, top.attributes.city_name) };
    }).sort((x, y) => (x.cheapest == null) - (y.cheapest == null) || x.cheapest - y.cheapest);
    const best = rows.length && rows[0].cheapest != null ? rows[0].cheapest : null;
    const first = rows[0] && rows[0].top.attributes;
    const html = rows.map((r) => {
      const station = ((r.top.attributes.stations || [])[0] || {});
      const extra = [station.title || station.name || '', r.average != null ? `${T('series_average')} ${this._num(r.average)}` : ''].filter(Boolean).join(' · ');
      const diff = r.cheapest == null ? '' : (r.cheapest === best ? T('cheapest_badge') : `+${this._num(r.cheapest - best)}`);
      return `<div class="row" role="button" tabindex="0" data-more-info="${esc(r.a.sensors.top5)}">
        <span class="icon fuel"><ha-icon icon="mdi:map-marker-radius-outline"></ha-icon></span>
        <div class="info"><span class="primary">${esc(r.name)}</span><span class="secondary">${esc(extra)}</span></div>
        <span class="price${r.cheapest === best ? ' best' : ''}"><span class="number">${r.cheapest == null ? '—' : this._num(r.cheapest)}</span>${diff ? `<span class="diff">${esc(diff)}</span>` : ''}</span>
      </div>`;
    }).join('');
    return `<ha-card class="card">
      <div class="head"><span class="icon fuel"><ha-icon icon="mdi:map-search-outline"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T('areas_title'))} · ${esc(first.fuel_label || this._config.fuel)}</span>
          <span class="secondary">${esc(T('areas_sub', { n: rows.length }))}</span></div></div>
      <div class="rows">${html}</div>
      <span class="source">${this._source()}</span>
    </ha-card>`;
  }
}

// ------------------------------------------------------------------ 7. on the road: the nearest stations, large
const ROAD_STYLE = `
  .road { display: flex; flex-direction: column; gap: var(--ha-space-3, 12px); }
  .stop { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--ha-space-1, 4px) var(--ha-space-3, 12px); align-items: center; }
  .stop .name { font-size: var(--ha-font-size-l, 16px); font-weight: var(--ha-font-weight-medium, 500); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .stop .where { grid-column: 1; font-size: var(--ha-font-size-m, 14px); color: var(--cp-muted); }
  .stop .big { grid-row: 1 / span 2; grid-column: 2; font-size: var(--ha-font-size-2xl, 24px); font-variant-numeric: tabular-nums; text-align: end; }
  .stop .big.best { color: var(--cp-good); }
  .stop .nav { grid-column: 1 / -1; }
  .stop .nav a { height: 48px; font-size: var(--ha-font-size-l, 16px); --mdc-icon-size: 22px; }
  .stop + .stop { padding-top: var(--ha-space-3, 12px); border-top: 1px solid var(--cp-line); }
`;
const NAVIGATORS = { mapy: 0, google: 1, waze: 2 };

class CenyPalivRoadCard extends CenyPalivMiniCard {
  static get defaults() { return { stations: 3, navigator: 'google' }; }

  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-road-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass, L) {
    return [
      { name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } },
      { name: 'stations', selector: { number: { min: 1, max: 5, step: 1, mode: 'slider' } } },
      { name: 'navigator', selector: { select: { mode: 'dropdown', options: [['mapy', 'Mapy.com'], ['google', 'Google Maps'], ['waze', 'Waze']].map(([value, label]) => ({ value, label })) } } },
    ];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-road-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  getCardSize() { return 2 + 3 * (Number(this._config && this._config.stations) || 3); }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const top = this._state(fuel, 'top5');
    if (!top) { this._why = 'missing'; return this._message(); }
    const at = top.attributes || {};
    const head = (sub) => `<div class="head"><span class="icon home"><ha-icon icon="mdi:car-arrow-right"></ha-icon></span>
      <div class="info"><span class="primary">${esc(T('road_title'))} · ${esc(at.fuel_label || fuel)}</span><span class="secondary">${esc(sub)}</span></div></div>`;
    if (!at.gps_area) return `<ha-card class="card">${head(at.city_name || '')}<div class="status muted"><ha-icon icon="mdi:information-outline"></ha-icon><span>${esc(T('road_gps_only'))}</span></div></ha-card>`;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const maxAge = at.max_age_days != null ? Number(at.max_age_days) : 1;
    const n = Math.min(5, Math.max(1, Math.round(Number(this._config.stations) || 3)));
    const near = (Array.isArray(at.gps_nearest_stations) ? at.gps_nearest_stations : [])
      .filter((x) => this._age(x, today) <= maxAge && isFinite(Number(x.distance_km)))
      .sort((x, y) => x.distance_km - y.distance_km).slice(0, n);
    const cheapest = near.length ? Math.min(...near.map((x) => Number(x.price))) : null;
    const pick = NAVIGATORS[this._config.navigator] != null ? NAVIGATORS[this._config.navigator] : 1;
    const stops = near.map((x) => {
      const link = navigationLinks(x)[pick];
      const best = Number(x.price) === cheapest;
      return `<div class="stop">
        <span class="name">${esc(x.name)}</span>
        <span class="big${best ? ' best' : ''}">${esc(this._num(x.price))}</span>
        <span class="where">${esc(this._num(x.distance_km, 1))} km · ${esc(x.city || '')}</span>
        ${link ? `<div class="nav"><a href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"><ha-icon icon="${link.icon}"></ha-icon><span>${esc(T('navigate'))} · ${esc(link.label)}</span></a></div>` : ''}
      </div>`;
    }).join('');
    return `<ha-card class="card"><style>${ROAD_STYLE}</style>
      ${head(`${at.city_name || ''} · ${at.unit_of_measurement || 'Kč/l'}`)}
      <div class="road">${stops || `<span class="note">${esc(T('no_recent'))}</span>`}</div>
      <span class="source">${this._source()}</span>
    </ha-card>`;
  }
}
for (const m of ['_age']) CenyPalivRoadCard.prototype[m] = CenyPalivCard.prototype[m];

// ------------------------------------------------------------------ 10. one price, large, for a wall tablet
const BIG_STYLE = `
  .big-card { container-type: inline-size; align-items: center; text-align: center; gap: var(--ha-space-2, 8px); }
  .big-card .what { font-size: clamp(14px, 6cqi, 28px); color: var(--cp-muted); }
  .big-card .price { font-size: clamp(40px, 24cqi, 160px); line-height: 1; font-weight: var(--ha-font-weight-normal, 400); font-variant-numeric: tabular-nums; }
  .big-card .price small { font-size: 0.25em; color: var(--cp-muted); margin-inline-start: 0.2em; }
  .big-card .where { font-size: clamp(12px, 4.5cqi, 22px); }
  .big-card .change { display: inline-flex; align-items: center; gap: 4px; font-size: clamp(12px, 4cqi, 20px); --mdc-icon-size: 1.2em; }
`;

class CenyPalivBigCard extends CenyPalivMiniCard {
  static get defaults() { return { price: 'cheapest' }; }

  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-big-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass, L) { return CenyPalivBadge.editorSchema(hass, L); }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-big-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  getCardSize() { return 4; }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const show = BADGE_SHOWS[this._config.price] ? this._config.price : 'cheapest';
    const top = this._state(fuel, 'top5');
    if (!top) { this._why = 'missing'; return this._message(); }
    const st = this._state(fuel, BADGE_SHOWS[show]);
    const at = top.attributes || {};
    const ok = st && !['unavailable', 'unknown'].includes(st.state) && isFinite(Number(st.state));
    const first = (at.stations || [])[0] || {};
    const where = { cheapest: first.title || first.name || '', mine: st ? st.attributes.station || '' : '', area: at.city_name || '' }[show];
    const trend = show === 'cheapest' ? first.trends && first.trends['1'] : (show === 'mine' && st ? st.attributes.trends && st.attributes.trends['1'] : null);
    const r = this._arrow(trend);
    const what = { cheapest: T('cheapest_badge'), mine: T('my_station'), area: T('series_average') }[show];
    return `<ha-card class="card big-card" role="button" tabindex="0" data-more-info="${esc((this._sensors[fuel] || {})[BADGE_SHOWS[show]] || this._sensors[fuel].top5)}"><style>${BIG_STYLE}</style>
      <span class="what">${esc(at.fuel_label || fuel)} · ${esc(what)}</span>
      <span class="price">${ok ? esc(this._num(st.state)) : '—'}<small>${esc(at.unit_of_measurement || 'Kč/l')}</small></span>
      ${where ? `<span class="where">${esc(where)}</span>` : ''}
      ${trend ? `<span class="change ${r.cls}"><ha-icon icon="${r.icon}"></ha-icon>${esc(r.txt)} · ${esc(T('vs_yesterday'))}</span>` : ''}
    </ha-card>`;
  }
}

// ------------------------------------------------------------------ 8. what changed: the price-change events
// State attributes identify the fuel and area even after an entity-registry rename.
function eventEntity(hass, fuel, top5Id) {
  const top = hass.states[top5Id];
  const area = top?.attributes?.cp_config_id;
  const device = hass.entities?.[top5Id]?.device_id;
  for (const [id, state] of Object.entries(hass.states)) {
    if (!id.startsWith('event.')) continue;
    const a = state.attributes || {};
    if (a.cp_role === 'price_change' && a.cp_fuel === fuel && area && area === a.cp_config_id) return id;
    // Older installs have device ownership and the suggested entity ID.
    const suggested = `event.ceny_paliv_${fuel}_price_change`;
    if (!a.cp_role && device && hass.entities[id]?.device_id === device &&
        (id === suggested || (id.startsWith(suggested + '_') && /^\d+$/.test(id.slice(suggested.length + 1))))) return id;
    // Older installs have device ownership and the suggested entity ID.
    if (!a.cp_role && device && hass.entities[id]?.device_id === device &&
        new RegExp(`^event\\.ceny_paliv_${fuel}_price_change(?:_\\d+)?$`).test(id)) return id;
  }
  return null;
}

// Recorder-backed cards refresh on the hour, including when Home Assistant is idle.
class CenyPalivHistoryCard extends CenyPalivMiniCard {
  connectedCallback() {
    this._scheduleRefresh();
    if (this._hass) this.hass = this._hass;
  }

  disconnectedCallback() {
    clearTimeout(this._refreshTimer);
  }

  _scheduleRefresh() {
    clearTimeout(this._refreshTimer);
    const hour = 3600000;
    const delay = this._failedKey ? 60000 : hour - Date.now() % hour;
    this._refreshTimer = setTimeout(() => {
      this._failedKey = null;
      this._sig = '';
      if (this._hass) this.hass = this._hass;
      this._scheduleRefresh();
    }, delay);
  }

  _historySignature() {
    return Math.floor(Date.now() / 3600000);
  }

  _requestFailed(key) {
    if (key !== this._loadKey) return;
    this._failedKey = key;
    this._loadKey = null;
    this._sig = '';
    this.hass = this._hass;
    if (this.isConnected) this._scheduleRefresh();
  }
}

// The events from the recorder's history: one state per event (the full or the compressed answer), newest first.
function eventHistory(answer, entityId) {
  const rows = Array.isArray(answer) ? (answer.find((group) => group[0]?.entity_id === entityId) || []) : (answer?.[entityId] || []);
  return rows.map((r) => {
    const state = r.s !== undefined ? r.s : r.state;
    const a = r.a !== undefined ? r.a : r.attributes;
    const when = r.lu !== undefined ? r.lu * 1000 : Date.parse(r.last_updated || r.last_changed);
    return { state, a: a || {}, when };
  }).filter((e) => e.a.event_type && !['unknown', 'unavailable'].includes(e.state) && isFinite(e.when)).sort((x, y) => y.when - x.when);
}

const CHANGE_LOOK = {
  favourite_cheaper: { icon: 'mdi:arrow-down', cls: 'good' },
  favourite_dearer: { icon: 'mdi:arrow-up', cls: 'bad' },
  cheapest_cheaper: { icon: 'mdi:trophy-outline', cls: 'good' },
};

class CenyPalivChangesCard extends CenyPalivHistoryCard {
  static get defaults() { return { days: 14 }; }

  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-changes-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass) {
    return [
      { name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } },
      { name: 'days', selector: { number: { min: 1, max: 30, step: 1, mode: 'slider' } } },
    ];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-changes-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  getCardSize() { return 5; }

  _days() { return Math.min(30, Math.max(1, Math.round(Number(this._config.days) || 14))); }

  _historySignature() {
    const fuel = this._config.fuel;
    const id = eventEntity(this._hass, fuel, this._sensors[fuel]?.top5);
    const state = this._hass.states[id];
    return `${super._historySignature()}|${id}|${state?.last_updated || state?.last_changed}`;
  }

  // the history again for another entity, after a new event, and every hour
  async _load(entityId) {
    const key = `${this._days()}|${this._historySignature()}`;
    if (key === this._loadKey || key === this._failedKey || typeof this._hass.callWS !== 'function') return;
    this._failedKey = null;
    this._loadKey = key;
    const end = new Date();
    const start = new Date(end.getTime() - this._days() * 86400000);
    let answer = {};
    try {
      answer = (await this._hass.callWS({
        type: 'history/history_during_period', start_time: start.toISOString(), end_time: end.toISOString(),
        entity_ids: [entityId], include_start_time_state: false, minimal_response: false, no_attributes: false, significant_changes_only: false,
      })) || {};
    } catch (err) {
      this._requestFailed(key);
      return;
    }
    if (key !== this._loadKey) return;
    this._events = { key: entityId, list: eventHistory(answer, entityId) };
    this._sig = '';
    this.hass = this._hass;
  }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const top = this._state(fuel, 'top5');
    if (!top) { this._why = 'missing'; return this._message(); }
    const at = top.attributes || {};
    const entityId = eventEntity(this._hass, fuel, this._sensors[fuel].top5);
    if (entityId) this._load(entityId);
    else { this._loadKey = null; this._failedKey = null; this._events = null; }
    const list = !this._failedKey && this._events && this._events.key === entityId ? this._events.list.slice(0, 10) : [];
    const rows = list.map((e) => {
      const look = CHANGE_LOOK[e.a.event_type] || { icon: 'mdi:swap-vertical', cls: 'muted' };
      const change = Number(e.a.change);
      const when = this._dateTime(new Date(e.when), { weekday: 'short', day: 'numeric', month: 'numeric', hour: 'numeric', minute: '2-digit' });
      return `<div class="row">
        <span class="icon ${look.cls === 'bad' ? 'fuel' : 'home'}"><ha-icon icon="${look.icon}"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T(`ev_${e.a.event_type}`))}</span><span class="secondary">${esc(when)} · ${esc(e.a.station || '')}</span></div>
        <span class="price"><span class="number">${esc(this._num(e.a.price))}</span>${isFinite(change) ? `<span class="diff ${look.cls}">${change > 0 ? '+' : '−'}${esc(this._num(Math.abs(change)))}</span>` : ''}</span>
      </div>`;
    }).join('');
    return `<ha-card class="card">
      <div class="head"><span class="icon home"><ha-icon icon="mdi:history"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T('changes_title'))} · ${esc(at.fuel_label || fuel)}</span>
          <span class="secondary">${esc(at.city_name || '')}</span></div></div>
      ${rows ? `<div class="rows">${rows}</div>` : `<span class="note">${esc(this._failedKey ? T('history_error') : T('changes_empty', { n: this._days() }))}</span>`}
      <span class="source">${this._source()}</span>
    </ha-card>`;
  }
}
CenyPalivChangesCard.prototype._dateTime = CenyPalivCard.prototype._dateTime;

// ------------------------------------------------------------------ 9. the trend of the week
// The latest daily value and how it moved since 7 and 14 days before (the last day with a value at or before then).
function trendDeltas(values, days) {
  let last = -1;
  for (let i = days.length - 1; i >= 0; i -= 1) if (values[days[i]] != null) { last = i; break; }
  if (last < 0) return null;
  const before = (n) => {
    for (let i = last - n; i >= 0; i -= 1) if (values[days[i]] != null) return values[days[i]];
    return null;
  };
  const latest = values[days[last]];
  const delta = (v) => (v == null ? null : Math.round((latest - v) * 100) / 100);
  return { latest, d7: delta(before(7)), d14: delta(before(14)) };
}

const TREND_STYLE = `
  .trend-rows { display: flex; flex-direction: column; gap: var(--ha-space-3, 12px); }
  .trend-row { display: grid; grid-template-columns: minmax(0, 1fr) 72px auto auto; gap: var(--ha-space-3, 12px); align-items: center; }
  .trend-row .label { display: flex; flex-direction: column; min-width: 0; }
  .trend-row .label b { font-weight: var(--ha-font-weight-medium, 500); font-size: var(--ha-font-size-m, 14px); }
  .trend-row .label span { font-size: var(--ha-font-size-s, 12px); color: var(--cp-muted); font-variant-numeric: tabular-nums; }
  .trend-row svg { width: 72px; height: 24px; display: block; }
  .trend-row path { fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linejoin: round; stroke-linecap: round; }
  .trend-row .d { display: inline-flex; align-items: center; gap: 2px; justify-content: flex-end; min-width: 56px;
    font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; --mdc-icon-size: 14px; }
  .trend-head { display: grid; grid-template-columns: minmax(0, 1fr) 72px auto auto; gap: var(--ha-space-3, 12px); font-size: var(--ha-font-size-xs, 10px); color: var(--cp-muted); }
  .trend-head span { min-width: 56px; text-align: end; }
`;

class CenyPalivTrendCard extends CenyPalivHistoryCard {
  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { type: 'custom:ceny-paliv-trend-card', fuel: found ? found.value : 'n95' };
  }

  static editorSchema(hass) {
    return [{ name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } }];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-trend-card: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  getCardSize() { return 4; }

  _series() {
    const fuel = this._config.fuel;
    const f = this._sensors[fuel] || {};
    const home = f.home && this._hass.states[f.home];
    return [
      f.area_average && { key: 'average', id: f.area_average, type: 'mean', label: this._T('series_average') },
      home && { key: 'mine', id: (home.attributes && home.attributes.statistic_id) || f.home, type: 'mean', label: this._T('my_station') },
      f.top5 && { key: 'cheapest', id: f.top5, type: 'min', label: this._T('series_cheapest') },
    ].filter(Boolean);
  }

  async _load(series) {
    const ids = series.map((x) => x.id);
    const zone = this._hass.config?.time_zone;
    const key = `${ids.join('|')}|${zone}|${this._historySignature()}`;
    if (!ids.length || key === this._loadKey || key === this._failedKey || typeof this._hass.callWS !== 'function') return;
    this._failedKey = null;
    this._loadKey = key;
    const start = new Date(Date.now() - 31 * 86400000);
    let rows = {};
    try {
      rows = (await this._hass.callWS({
        type: 'recorder/statistics_during_period', start_time: start.toISOString(), end_time: new Date().toISOString(),
        statistic_ids: ids, period: 'day', types: ['mean', 'min'],
      })) || {};
    } catch (err) {
      this._requestFailed(key);
      return;
    }
    if (key !== this._loadKey) return;
    this._values = {};
    for (const x of series) this._values[x.id] = dailyValues(rows[x.id], x.type, zone);
    this._sig = '';
    this.hass = this._hass;
  }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const top = this._state(fuel, 'top5');
    if (!top) { this._why = 'missing'; return this._message(); }
    const at = top.attributes || {};
    const series = this._series();
    this._load(series);
    const today = calendarDay(new Date(), this._hass.config?.time_zone);
    const days = graphDays(new Date(today + 'T12:00:00'), 31);
    const delta = (d) => {
      if (d == null) return '<span class="d muted">—</span>';
      const r = this._arrow({ dir: d < 0 ? 'down' : d > 0 ? 'up' : 'flat', delta: d });
      return `<span class="d ${r.cls}"><ha-icon icon="${r.icon}"></ha-icon>${esc(r.txt)}</span>`;
    };
    const rows = (this._failedKey ? [] : series).map((x) => {
      const values = (this._values || {})[x.id] || {};
      const t = trendDeltas(values, days);
      if (!t) return '';
      // a sparkline of the 15 days, in the row's own scale
      const known = days.slice(-15).map((d, i) => [i, values[d]]).filter(([, v]) => v != null);
      const lo = Math.min(...known.map(([, v]) => v));
      const hi = Math.max(...known.map(([, v]) => v));
      const path = known.map(([i, v], n) => `${n ? 'L' : 'M'}${(i * 72 / 14).toFixed(1)},${(hi > lo ? 22 - (v - lo) * 20 / (hi - lo) : 12).toFixed(1)}`).join('');
      return `<div class="trend-row ${x.key}"><span class="label"><b>${esc(x.label)}</b><span>${esc(this._num(t.latest))} ${esc(at.unit_of_measurement || 'Kč/l')}</span></span>
        <svg viewBox="0 0 72 24" aria-hidden="true"><path d="${path}"></path></svg>${delta(t.d7)}${delta(t.d14)}</div>`;
    }).join('');
    return `<ha-card class="card"><style>${TREND_STYLE}</style>
      <div class="head"><span class="icon home"><ha-icon icon="mdi:chart-timeline-variant"></ha-icon></span>
        <div class="info"><span class="primary">${esc(T('trend_title'))} · ${esc(at.fuel_label || fuel)}</span>
          <span class="secondary">${esc(at.city_name || '')}</span></div></div>
      ${rows ? `<div class="trend-head"><span></span><span></span><span>7 d</span><span>14 d</span></div><div class="trend-rows">${rows}</div>` : `<span class="note">${esc(T(this._failedKey ? 'history_error' : 'graph_empty'))}</span>`}
      <span class="source">${this._source()}</span>
    </ha-card>`;
  }
}

// ------------------------------------------------------------------ 11. a badge with a price
const BADGE_STYLE = `
  :host { display: inline-block; }
  .badge {
    display: inline-flex; align-items: center; gap: var(--ha-space-2, 8px); height: 36px; min-width: 36px; padding: 0 12px;
    box-sizing: border-box; cursor: pointer; outline: none; font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif);
    border-radius: var(--ha-badge-border-radius, 18px);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
    background: var(--ha-card-background, var(--card-background-color, #fff));
  }
  .badge:focus-visible { box-shadow: 0 0 0 2px var(--cp-home); }
  .badge ha-icon { --mdc-icon-size: 18px; margin-inline-start: -4px; color: var(--badge-color, var(--cp-fuel)); }
  .badge.mine ha-icon { color: var(--cp-home); }
  .badge .text { display: flex; flex-direction: column; }
  .badge .label { font-size: var(--ha-font-size-xs, 10px); font-weight: var(--ha-font-weight-medium, 500); line-height: 10px; letter-spacing: 0.1px; color: var(--cp-muted); }
  .badge .content { font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500); line-height: 1.2; letter-spacing: 0.1px; color: var(--cp-text); font-variant-numeric: tabular-nums; }
`;
const BADGE_SHOWS = { cheapest: 'top5', mine: 'home', area: 'area_average' };

class CenyPalivBadge extends CenyPalivMiniCard {
  static get defaults() { return { price: 'cheapest' }; }

  static getStubConfig(hass) {
    const found = CenyPalivCard.fuels(hass)[0];
    return { fuel: found ? found.value : 'n95' };  // a badge's stub has no type (Home Assistant adds it)
  }

  static editorSchema(hass, L) {
    return [
      { name: 'fuel', required: true, selector: { select: { mode: 'dropdown', options: CenyPalivCard.fuels(hass) } } },
      { name: 'price', selector: { select: { mode: 'dropdown', options: Object.keys(BADGE_SHOWS).map((value) => ({ value, label: L[`badge_${value}`] || value })) } } },
    ];
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-badge: set "fuel", for example "n95"');
    super.setConfig(config);
  }

  set hass(hass) {
    super.hass = hass;
    // the base draws a card around a message: a badge stays a badge
    if (!this._area && this.shadowRoot.innerHTML.includes('class="card message"')) {
      this.shadowRoot.innerHTML = `<style>${STYLE}${BADGE_STYLE}</style><div class="badge"><ha-icon icon="mdi:gas-station-off-outline"></ha-icon><span class="text"><span class="content">—</span></span></div>`;
    }
  }

  _render() {
    const T = (k, v) => this._T(k, v);
    const fuel = this._config.fuel;
    const show = BADGE_SHOWS[this._config.price] ? this._config.price : 'cheapest';
    const top = this._state(fuel, 'top5');
    const st = this._state(fuel, BADGE_SHOWS[show]);
    const at = (top && top.attributes) || {};
    const ok = st && !['unavailable', 'unknown'].includes(st.state) && isFinite(Number(st.state));
    const unit = at.unit_of_measurement || 'Kč/l';
    const label = { cheapest: at.fuel_label || fuel, mine: `${at.fuel_label || fuel} · ${T('my_station')}`, area: `${at.fuel_label || fuel} · ${T('series_average')}` }[show];
    const icon = { cheapest: 'mdi:gas-station', mine: 'mdi:gas-station-in-use', area: 'mdi:map-marker-radius' }[show];
    const id = (this._sensors[fuel] || {})[BADGE_SHOWS[show]] || (this._sensors[fuel] || {}).top5 || '';
    const value = ok ? `${this._num(st.state)} ${unit}` : '—';
    return `<style>${BADGE_STYLE}</style><div class="badge ${show}" role="button" tabindex="0" data-more-info="${esc(id)}" aria-label="${esc(label)}: ${esc(value)}">
      <ha-icon icon="${icon}"></ha-icon><span class="text"><span class="label">${esc(label)}</span><span class="content">${esc(value)}</span></span></div>`;
  }
}

// ------------------------------------------------------------------ 12. a feature for the tile card
// Added under a tile card of a Ceny paliv sensor (Features > Ceny paliv): what the sensor's attributes say in one
// line, with the trend since yesterday, in a row like Home Assistant's own features.
const FEATURE_ROLES = ['top5', 'home', 'position', 'area_average', 'region_average'];

function supportsPriceFeature(hass, context) {
  const st = context && context.entity_id && hass && hass.states && hass.states[context.entity_id];
  return !!(st && context.entity_id.startsWith('sensor.ceny_paliv_') && FEATURE_ROLES.includes((st.attributes || {}).cp_role));
}

const FEATURE_STYLE = `
  :host { display: block; }
  .feature {
    position: relative; overflow: hidden; display: flex; align-items: center; gap: var(--ha-space-2, 8px);
    height: var(--feature-height, 42px); padding: 0 var(--ha-space-3, 12px); box-sizing: border-box;
    border-radius: var(--feature-border-radius, 12px); color: var(--cp-text);
    font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif); font-size: var(--ha-font-size-s, 12px);
  }
  .feature::before { content: ""; position: absolute; inset: 0; background: var(--cp-neutral); opacity: 0.2; }
  .feature > * { position: relative; }
  .feature .what { flex: 1 1 auto; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .feature .change { flex: none; display: inline-flex; align-items: center; gap: 2px; font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; --mdc-icon-size: 14px; }
`;

class CenyPalivPriceFeature extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  static getStubConfig() { return { type: 'custom:ceny-paliv-price-feature' }; }

  setConfig(config) {
    if (!config) throw new Error('ceny-paliv-price-feature: missing configuration');
    this._config = config;
    this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  set context(context) { this._context = context; this._render(); }

  _labels() {
    const st = this._state();
    const a = (st && st.attributes) || {};
    if (a.labels) return a.labels;
    // the texts are on the area's top5 sensor
    for (const other of Object.values(this._hass.states)) {
      const o = other.attributes || {};
      if (o.cp_role === 'top5' && o.cp_fuel === a.cp_fuel && o.cp_config_id === a.cp_config_id && o.labels) return o.labels;
    }
    return {};
  }

  _state() {
    return this._hass && this._context && this._context.entity_id ? this._hass.states[this._context.entity_id] : null;
  }

  _render() {
    if (!this._hass || !this._context || !this._config) return;
    const st = this._state();
    if (!supportsPriceFeature(this._hass, this._context)) { this.shadowRoot.innerHTML = ''; return; }
    const sig = `${this._context.entity_id}|${st.state}|${st.last_updated}|${this._hass.language}`;
    if (sig === this._sig) return;
    this._sig = sig;
    const T = (k, v) => this._T(k, v);
    const a = st.attributes || {};
    let what = '';
    let trend = null;
    if (a.cp_role === 'top5') {
      const first = (a.stations || [])[0];
      what = first ? (first.title || first.name || '') : T('no_recent');
      trend = first && first.trends && first.trends['1'];
    } else if (a.cp_role === 'home') {
      const vs = Number(a.vs_cheapest);
      what = [a.rank != null ? T('rank_of', { rank: a.rank, n: a.fresh_count }) : T('not_ranked'),
        isFinite(vs) ? (vs <= 0 ? T('cheapest_badge') : T('more_than_cheapest', { d: this._num(vs) })) : ''].filter(Boolean).join(' · ');
      trend = a.trends && a.trends['1'];
    } else if (a.cp_role === 'position') {
      what = a.station || '';
    } else {
      const vs = Number(a.vs_national);
      what = [a.region || '', isFinite(vs) ? `${T('compare_country')} ${vs > 0 ? '+' : vs < 0 ? '−' : '±'}${this._num(Math.abs(vs))}` : ''].filter(Boolean).join(' · ');
    }
    const r = this._arrow(trend);
    this.shadowRoot.innerHTML = `<style>${STYLE}${FEATURE_STYLE}</style><div class="feature">
      <span class="what">${esc(what)}</span>
      ${trend ? `<span class="change ${r.cls}" title="${esc(T('vs_yesterday'))}"><ha-icon icon="${r.icon}"></ha-icon>${esc(r.txt)}</span>` : ''}</div>`;
  }
}
for (const m of ['_T', '_numberLocale', '_num', '_arrow']) CenyPalivPriceFeature.prototype[m] = CenyPalivCard.prototype[m];

// ------------------------------------------------------------------ the editor of the small cards
class CenyPalivMiniEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._render(); }
  set hass(hass) { this._hass = hass; this._render(); }

  _render() {
    if (!this._hass || !this._config || !this.card) return;
    const code = (this._hass.language || 'en').split('-')[0];
    const L = EDITOR_TEXT[code in EDITOR_TEXT ? code : 'en'];
    const areas = areaOptions(this._hass);
    const stale = !!this._config.config_id && !areas.some((a) => a.value === this._config.config_id);
    const schema = [
      ...(areas.length > 1 || stale ? [{ name: 'config_id', selector: { select: { mode: 'dropdown', options: areas } } }] : []),
      ...this.card.editorSchema(this._hass, L),
    ];
    const key = JSON.stringify([code, schema, this._config]);
    if (key === this._key) return;
    this._key = key;
    if (!this._form) {
      this._form = document.createElement('ha-form');
      this._form.addEventListener('value-changed', (e) => {
        // keep only what the user set: the defaults shown in the form are not saved
        const defaults = this.card.defaults;
        const config = Object.assign({}, this._config);
        for (const [k, v] of Object.entries(e.detail.value || {})) {
          if (!(k in this._config) && JSON.stringify(v) === JSON.stringify(defaults[k])) continue;
          config[k] = v;
        }
        for (const k of Object.keys(config)) {
          const v = config[k];
          if (v === undefined || v === null || v === '' || (Array.isArray(v) && !v.length)) delete config[k];
        }
        this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = Object.assign({}, this.card.defaults, this._config);
    this._form.schema = schema;
    this._form.computeLabel = (field) => L[field.name] || field.name;
  }
}

class CenyPalivChainsCard extends CenyPalivMiniCard {
  static getStubConfig(hass) {
    return { type: 'custom:ceny-paliv-chains-card', fuel: CenyPalivCard.fuels(hass)[0]?.value || 'n95' };
  }

  static editorSchema(hass) {
    return [{ name: 'fuel', required: true, selector: { select: { options: CenyPalivCard.fuels(hass) } } }];
  }

  setConfig(config) {
    if (!config?.fuel) throw new Error('ceny-paliv-chains-card: set "fuel"');
    super.setConfig(config);
  }

  _render() {
    const fuel = this._config.fuel;
    const national = this._state(fuel, 'national_average');
    const top = this._state(fuel, 'top5');
    const chains = national?.attributes.chains || [];
    const unit = national?.attributes.unit_of_measurement || top?.attributes.unit_of_measurement || '';
    const row = (chain, index) => `<div class="row">
      <span class="icon fuel">${index + 1}</span><div class="info"><span class="primary">${esc(chain.name)}</span>
      <span class="secondary">${esc(this._T('chain_count', { n: chain.station_count }))}</span></div>
      <span class="number">${esc(this._num(chain.average))} <small>${esc(unit)}</small></span></div>`;
    const rows = chains.map(row);
    return `<ha-card class="card"><div class="head"><span class="icon home"><ha-icon icon="mdi:podium"></ha-icon></span>
      <div class="info"><span class="primary">${esc(this._T('chains_title'))} · ${esc(top?.attributes.fuel_label || fuel)}</span>
      <span class="secondary">${esc(this._T('chains_sub'))}</span></div></div>
      <div class="rows">${rows.slice(0, 10).join('')}</div>
      ${rows.length > 10 ? `<details><summary>${esc(this._T('chains_more', { n: rows.length - 10 }))}</summary><div class="rows">${rows.slice(10).join('')}</div></details>` : ''}
      ${rows.length ? '' : `<span class="note">${esc(this._T('chains_empty'))}</span>`}
      <span class="source">${this._source()}</span></ha-card>`;
  }
}

const COST_FUELS = ['n95', 'diesel', 'lpg', 'cng'];

class CenyPalivFuelCostCard extends CenyPalivMiniCard {
  static get defaults() {
    return { consumption_n95: 6.5, consumption_diesel: 5.5, consumption_lpg: 8, consumption_cng: 4 };
  }

  static getStubConfig() { return { type: 'custom:ceny-paliv-fuel-cost-card' }; }

  static editorSchema() {
    return COST_FUELS.map((fuel) => ({
      name: `consumption_${fuel}`,
      selector: { number: { min: 0.1, step: 0.1, mode: 'box', unit_of_measurement: fuel === 'cng' ? 'kg/100 km' : 'l/100 km' } },
    }));
  }

  _render() {
    const rows = [];
    for (const fuel of COST_FUELS) {
      const average = this._state(fuel, 'area_average');
      const price = Number(average?.state);
      const used = Number(this._config[`consumption_${fuel}`]);
      if (!average?.state?.trim() || !Number.isFinite(price) || price <= 0 || !Number.isFinite(used) || used <= 0) continue;
      const top = this._state(fuel, 'top5');
      const unit = fuel === 'cng' ? 'kg' : 'l';
      rows.push({ label: top?.attributes.fuel_label || fuel.toUpperCase(), unit, price, used, cost: price * used / 100 });
    }
    rows.sort((a, b) => a.cost - b.cost);
    const body = rows.map((row) => `<div class="row"><div class="info"><span class="primary">${esc(row.label)}</span>
      <span class="secondary">${esc(this._num(row.price))} Kč/${row.unit} · ${esc(this._num(row.used, 1))} ${row.unit}/100 km</span></div>
      <span class="price"><span class="number">${esc(this._num(row.cost))}</span><small>Kč/km</small></span></div>`).join('');
    return `<ha-card class="card"><div class="head"><span class="icon home"><ha-icon icon="mdi:car"></ha-icon></span>
      <div class="info"><span class="primary">${esc(this._T('cost_title'))}</span><span class="secondary">${esc(this._T('cost_sub'))}</span></div></div>
      ${body ? `<div class="rows">${body}</div>` : `<span class="note">${esc(this._T('cost_empty'))}</span>`}
      <span class="source">${this._source()}</span></ha-card>`;
  }
}

const MINI_CARDS = [
  ['ceny-paliv-fuel-cost-card', CenyPalivFuelCostCard, 'Ceny paliv: cost per kilometre', 'Compare LPG, CNG, petrol and diesel for one vehicle.'],
  ['ceny-paliv-chains-card', CenyPalivChainsCard, 'Ceny paliv: chain ranking', 'Average prices by chain across the Czech Republic.'],
  ['ceny-paliv-fuels-card', CenyPalivFuelsCard, 'Ceny paliv: all fuels', 'Every fuel of an area at a glance: the cheapest price, your station and the trend.'],
  ['ceny-paliv-savings-card', CenyPalivSavingsCard, 'Ceny paliv: full tank', 'What a full tank costs at your station, the cheapest one and the average, and whether the drive pays off.'],
  ['ceny-paliv-compare-card', CenyPalivCompareCard, 'Ceny paliv: comparison', 'Your station and area against the region and the country, and the 14 regions ranked.'],
  ['ceny-paliv-regions-card', CenyPalivRegionsCard, 'Ceny paliv: regions map', 'A map of the 14 Czech regions coloured by their average price.'],
  ['ceny-paliv-areas-card', CenyPalivAreasCard, 'Ceny paliv: areas', 'One fuel in every area: where it is cheapest now and by how much.'],
  ['ceny-paliv-road-card', CenyPalivRoadCard, 'Ceny paliv: on the road', 'The nearest stations, large, with a navigate button: for a phone in the car.'],
  ['ceny-paliv-big-card', CenyPalivBigCard, 'Ceny paliv: big price', 'One price, large, readable from across the room.'],
  ['ceny-paliv-changes-card', CenyPalivChangesCard, 'Ceny paliv: what changed', 'The last price changes: your station cheaper or dearer, a cheaper station in the area.'],
  ['ceny-paliv-trend-card', CenyPalivTrendCard, 'Ceny paliv: trend', 'How the area average, your station and the cheapest moved over 7 and 14 days.'],
  ['ceny-paliv-stations-map-card', CenyPalivStationsMapCard, 'Ceny paliv: stations map', 'The area\'s stations as coloured prices around its centre; tap one for details and navigation.'],
];
if (!customElements.get('ceny-paliv-mini-editor')) customElements.define('ceny-paliv-mini-editor', CenyPalivMiniEditor);
for (const [type, cls, name, description] of MINI_CARDS) {
  if (!customElements.get(type)) customElements.define(type, cls);
  if (!window.customCards.some((c) => c.type === type)) window.customCards.push({ type, name, preview: true, description });
}
if (!customElements.get('ceny-paliv-badge')) customElements.define('ceny-paliv-badge', CenyPalivBadge);
window.customBadges = window.customBadges || [];
if (!window.customBadges.some((b) => b.type === 'ceny-paliv-badge')) {
  window.customBadges.push({ type: 'ceny-paliv-badge', name: 'Ceny paliv', preview: true, description: 'A fuel price: the cheapest in the area, your station or the area average.' });
}
if (!customElements.get('ceny-paliv-price-feature')) customElements.define('ceny-paliv-price-feature', CenyPalivPriceFeature);
window.customCardFeatures = window.customCardFeatures || [];
if (!window.customCardFeatures.some((f) => f.type === 'ceny-paliv-price-feature')) {
  window.customCardFeatures.push({ type: 'ceny-paliv-price-feature', name: 'Ceny paliv: price details', isSupported: supportsPriceFeature });
}

console.info(`%c Ceny paliv card %c ${CARD_VERSION} `, 'color:#fff;background:#f5b14c;font-weight:700', 'color:#f5b14c;background:#171a20');
