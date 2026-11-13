/*
 * Ceny paliv card — shipped with the Ceny paliv integration, nothing to install separately.
 * Prices come from mBenzin.cz; this project is independent and not affiliated with mBenzin.
 *
 *   type: custom:ceny-paliv-card
 *   fuel: n95            # n95 | benzinplus | diesel | dieselplus | lpg | cng | adblue
 *
 * Optional (all of them are also in the visual editor: Add card > Ceny paliv):
 *   show: [home, list, map, graph]   # which parts to draw; use several cards to place them freely
 *   layout: auto         # auto = 2 columns when the card is wide | columns | stack
 *   stations: 5          # 1-5 stations in the list
 *   compact: false       # dense version: one line per station, short footer
 *   show_footer: true    # update times, legend (default: false when compact)
 *   map_height: 300      # px, default: the map card's own height
 *   logo_path: /local/   # only to use your own PNG files instead of the downloaded logo pack
 *
 * Station logos: tick the chains in the integration's setup (Configure > Station logos); the card finds them by
 * itself. Chains without a logo get a coloured badge with their initials.
 *
 * Texts come from the language chosen in the integration setup (attribute `labels` of the top5 sensor).
 */
const CARD_VERSION = '0.5.3';

const PARTS = ['home', 'list', 'map', 'graph'];

// Parts a config shows. show_map / show_graph: options of the first versions, still honoured when `show` is not set.
function shownParts(config) {
  const legacy = PARTS.filter((p) => !(p === 'map' && config.show_map === false) && !(p === 'graph' && config.show_graph === false));
  const show = (Array.isArray(config.show) ? config.show : config.show ? [config.show] : legacy).filter((p) => PARTS.includes(p));
  return show.length ? show : PARTS;
}

// What the card uses for an option the config does not set (the editor shows these, but never saves them).
function editorDefaults(config) {
  return { show: shownParts(config), layout: 'auto', stations: 5, compact: false, show_footer: !config.compact, map_height: 0 };
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
  /* header texts wrap instead of cutting "GPS area" or "price from … — may be outdated" on a phone */
  .head > .info .primary, .home .head > .info .secondary { white-space: normal; }
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

  .map, .graph { border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px)); overflow: hidden; }
  .map.fixed { position: relative; min-width: 200px; }
  .map.fixed > * { position: absolute; inset: 0; display: block; }
  @media (prefers-reduced-motion: reduce) { .row::before { transition: none; } }
`;

// A state Home Assistant restored for an entity no integration provides (yet): it carries no data or attributes.
const restored = (state) => !!(state && state.attributes && state.attributes.restored);

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
    root.addEventListener('pointermove', (e) => this._move(e));
    // pointerleave does not bubble to the root: moving away is caught by pointermove / pointercancel
    ['pointerup', 'pointercancel'].forEach((n) => root.addEventListener(n, () => clearTimeout(this._timer)));
  }

  setConfig(config) {
    if (!config || !config.fuel) throw new Error('ceny-paliv-card: set "fuel", for example "n95"');
    this._config = Object.assign({ layout: 'auto', stations: 5, compact: false, logo_path: '' }, config);
    this._show = shownParts(config);
    this._layout = ['auto', 'columns', 'stack'].includes(this._config.layout) ? this._config.layout : 'auto';
    this._n = Math.min(5, Math.max(1, Math.round(Number(this._config.stations) || 5)));
    this._compact = !!this._config.compact;
    this._footer = this._config.show_footer != null ? !!this._config.show_footer : !this._compact;
    this._mapHeight = Number(this._config.map_height) > 0 ? Number(this._config.map_height) : 0;
    this._ids = null;
    this._scanAt = 0;
    this._sig = '';
    this._children = null;
    this._build();
    if (this._hass) this.hass = this._hass;  // a new config (e.g. the editor preview) renders at once
  }

  set hass(hass) {
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
    const sig = [JSON.stringify(this._ids), top && top.last_updated, home && home.last_updated, top && top.state, home && home.state, new Date().toDateString()].join('|');
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
    if (!sd.wide) return sizes.reduce((x, y) => x + y, 0);
    const left = ['home', 'list'].filter((p) => this._show.includes(p)).reduce((x, p) => x + h[p], 0);
    const right = ['map', 'graph'].filter((p) => this._show.includes(p)).reduce((x, p) => x + h[p], 0);
    return Math.max(left, right);
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
    if (!grid || !grid.classList.contains('auto')) return;
    const w = this.getBoundingClientRect().width;
    if (w >= 640) grid.classList.add('wide');
    else if (w < 600) grid.classList.remove('wide');
  }

  connectedCallback() {
    if (!this._ro && window.ResizeObserver) this._ro = new ResizeObserver(() => this._fit());
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
    if (this._show.includes('graph') && hasHome) {
      kids.push({
        id: 'graph',
        cls: 'graph',
        config: {
          type: 'statistics-graph', title: '30 d', entities: [this._ids.home], days_to_show: 30, period: 'day',
          chart_type: 'line', stat_types: ['mean', 'min', 'max'],
        },
      });
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
    return `<span class="avatar${best ? ' best' : ''}">${this._disc(s)}<span class="rank">${rank}</span></span>`;
  }

  // ---------------------------------------------------------------- rendering
  _renderTexts() {
    const hass = this._hass;
    const top = hass.states[this._ids.top5];
    const root = this.shadowRoot;
    const slot = (p, html) => { const el = root.getElementById(p); if (el) el.innerHTML = html; };
    const first = this._show.find((p) => p === 'home' || p === 'list') || this._show[0];
    if (!top || top.state === 'unavailable') {
      // the message replaces the map and graph containers' content: rebuild them once the data is back
      this._resetExtra();
      const why = !top ? (this._ambiguous ? 'ambiguous' : 'missing') : 'unavailable';
      this._show.forEach((p) => slot(p, p === first ? this._message(why) : ''));
      return;
    }
    slot('home', this._show.includes('home') ? this._homeHtml() : '');
    slot('list', this._show.includes('list') ? this._listHtml() : '');
    // only "my station" and its graph were asked for, but no favourite is set: say so instead of an empty card
    if (!hass.states[this._ids.home] && this._show.every((p) => p === 'home' || p === 'graph')) slot(first, this._message('no_home'));
    this._buildExtra();
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
    const stale = a.age_days == null || Number(a.age_days) > 1;
    const updated = a.age_days == 0 ? T('updated_today') : (a.age_days == 1 ? T('updated_yesterday')
      : T('price_from', { d: this._day(a.updated_date, { day: 'numeric', month: 'numeric', year: 'numeric' }) || a.updated || '—' }));
    const tr = a.trends || {};
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
    const trends = cp
      ? `<div class="trends-inline">${[1, 7, 30].map((n) => { const r = this._arrow(tr[String(n)]); return `<span class="muted">${n} d <span class="delta ${r.cls}">${esc(r.txt)}</span></span>`; }).join('')}</div>`
      : `<div class="trends">${[1, 2, 7, 14, 30].map(tile).join('')}</div>`;
    const anyTrend = Object.values(tr).some(Boolean);
    const note = cp ? '' : !anyTrend ? T('trends_start')
      : (partial ? T('since_partial', { d: this._day(partial, { day: 'numeric', month: 'short' }) || partial }) : '');
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

  _listHtml() {
    const S = this._hass.states[this._ids.top5];
    const at = S.attributes;
    const T = (k, v) => this._T(k, v);
    const all = Array.isArray(at.stations) ? at.stations : [];
    const maxAge = at.max_age_days != null ? Number(at.max_age_days) : 1;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const fresh = all.filter((s) => this._age(s, today) <= maxAge);
    const list = fresh.slice(0, this._n);
    const cp = this._compact;
    const prices = list.map((s) => Number(s.price)).filter((p) => !isNaN(p));
    const min = prices.length ? Math.min(...prices) : null;
    const unit = at.unit_of_measurement || 'Kč/l';
    const n = min === null ? 0 : fresh.filter((s) => Number(s.price) === min).length;
    const sub = min === null ? T('no_recent') : T('cheapest_price', { p: this._num(min), unit }) + (n > 1 ? ' · ' + T('stations_same', { n }) : '');
    const head = `<div class="head"><span class="icon fuel"><ha-icon icon="mdi:gas-station"></ha-icon></span>
      <div class="info"><span class="primary">${esc(at.fuel_label || this._config.fuel)} · ${esc(at.city_name || '')}</span>
        <span class="secondary">${esc(sub)}</span></div>
      <div class="value"><span class="number${min === null ? ' muted' : ''}">${min === null ? '—' : this._num(min)}</span><span class="unit">${esc(unit)}</span></div></div>`;
    const rows = list.map((s, i) => {
      const best = Number(s.price) === min;
      const name = s.name || '—';
      const a0 = s.address || '';
      // the address often repeats the name, sometimes without its accents ("Am oil Milicin parkoviste")
      const addr = norm(a0).startsWith(norm(name)) ? a0.slice(name.length).trim() : a0;
      const tr = this._arrow((s.trends || {})['1']);
      const when = this._when(s, this._age(s, today));
      const home = s.home ? `<ha-icon icon="mdi:home" title="${esc(T('my_station'))}"></ha-icon>` : '';
      // the price date first: a long address is what gets cut
      const where = [`<span class="${when.old ? 'warn' : ''}">${esc(when.text)}</span>`, esc(addr)].filter((w) => w !== '');
      return `<div class="row" role="link" tabindex="0" data-maps="${esc(s.maps)}" aria-label="${esc(name)} ${esc(addr)}: ${this._num(s.price)} ${esc(unit)}">
        ${this._avatar(s, i + 1, best)}
        <div class="info"><span class="primary">${esc(name)}${cp && addr ? ` <span class="muted">${esc(addr)}</span>` : ''}${home}</span>
          ${cp ? '' : `<span class="secondary">${where.join(' · ')}</span>`}</div>
        <span class="change ${tr.cls}" title="${esc(T('vs_yesterday'))}">${s.trends && s.trends['1'] ? `<ha-icon icon="${tr.icon}"></ha-icon>` : ''}${esc(tr.txt)}</span>
        <span class="price${best ? ' best' : ''}"><span class="number">${this._num(s.price)}</span>${cp ? '' : `<span class="diff">${esc(best ? T('cheapest_badge') : '+' + this._num(Number(s.price) - min))}</span>`}</span>
      </div>`;
    }).join('');
    // footer
    const now = new Date();
    const time = (d) => (d.toDateString() === now.toDateString()
      ? this._dateTime(d, { hour: 'numeric', minute: '2-digit' })
      : this._dateTime(d, { weekday: 'short', hour: 'numeric', minute: '2-digit' }));
    const fa = at.fetched_at ? new Date(at.fetched_at) : null;
    const la = at.last_attempt ? new Date(at.last_attempt) : null;
    const nu = at.next_update ? new Date(at.next_update) : null;
    const hidden = (at.excluded || 0) + (all.length - fresh.length);
    const alert = at.fetch_error
      ? `<div class="alert warning" role="status"><ha-icon icon="mdi:alert-outline"></ha-icon><span>${esc(T('refresh_failed', { at: la ? T('at') + time(la) : '', err: at.fetch_error }))}</span></div>`
      : '';
    const lines = [`<span>${esc(T('table_updated', { t: fa ? time(fa) : '—', n: nu ? time(nu) : '—' }))}</span>`];
    if (at.city_total) lines.push(`<span>${esc(T('hidden', { h: hidden, t: at.city_total, age: maxAge > 1 ? T('days_l', { n: maxAge }) : (maxAge === 1 ? T('yesterday_l') : T('today_l')) }))}</span>`);
    lines.push(`<span class="legend">${esc(T('arrows'))}: <span class="good"><ha-icon icon="mdi:arrow-down"></ha-icon> ${esc(T('down'))}</span> · <span class="warn"><ha-icon icon="mdi:equal"></ha-icon> ${esc(T('stable'))}</span> · <span class="bad"><ha-icon icon="mdi:arrow-up"></ha-icon> ${esc(T('up'))}</span> · ${esc(T('longpress'))}</span>`);
    lines.push(`<span>${this._source()} · ${esc(at.fuel_label || '')}${at.fuel === 'n95' ? ' ' + esc(T('e10_note')) : ''} · ${esc(T('tap_station'))}</span>`);
    const foot = this._footer ? `<div class="foot">${lines.join('')}</div>` : `<div class="foot"><span>${this._source()}</span></div>`;
    return `<ha-card class="card list${cp ? ' compact' : ''}" data-more-info="${esc(this._ids.home || this._ids.top5)}">${head}${alert}<div class="rows">${rows}</div>${foot}</ha-card>`;
  }

  // ---------------------------------------------------------------- interaction
  _entityId(e) {
    const t = e.composedPath ? e.composedPath().find((n) => n.dataset && (n.dataset.maps || n.dataset.moreInfo)) : null;
    return t || null;
  }

  _down(e) {
    const t = this._entityId(e);
    this._long = false;
    clearTimeout(this._timer);
    this._start = { x: e.clientX, y: e.clientY };
    if (t && t.dataset.maps) {
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
    if (t.dataset.maps) window.open(t.dataset.maps, '_blank', 'noopener');
    else if (t.dataset.moreInfo && !e.composedPath().some((n) => n.dataset && n.dataset.maps)) this._moreInfo(t.dataset.moreInfo);
  }

  _moreInfo(entityId) {
    this.dispatchEvent(new CustomEvent('hass-more-info', { bubbles: true, composed: true, detail: { entityId } }));
  }
}


// ------------------------------------------------------------------ visual editor
const EDITOR_TEXT = {
  en: {
    fuel: 'Fuel', config_id: 'Configuration / area', show: 'Parts to show', layout: 'Layout', stations: 'Stations in the list', compact: 'Compact', show_footer: 'Show update times and legend',
    map_height: 'Map height in px (0 = automatic)', logo_path: 'Folder of your own logos (leave empty for the logo pack)',
    home: 'My station', list: 'Cheapest stations', map: 'Map', graph: '30-day graph',
    auto: 'Automatic: 2 columns when the card is wide', columns: 'Always 2 columns', stack: 'Always 1 column',
  },
  cs: {
    fuel: 'Palivo', config_id: 'Konfigurace / oblast', show: 'Zobrazené části', layout: 'Rozvržení', stations: 'Počet stanic v seznamu', compact: 'Kompaktní', show_footer: 'Zobrazit časy aktualizace a legendu',
    map_height: 'Výška mapy v px (0 = automaticky)', logo_path: 'Složka s vlastními logy (prázdné = balíček log)',
    home: 'Moje stanice', list: 'Nejlevnější stanice', map: 'Mapa', graph: 'Graf za 30 dní',
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
      // shown while several configurations offer the fuel, or to repair a pinned one that no longer exists
      ...(configurations.length > 1 || (stale && configurations.length)
        ? [{ name: 'config_id', selector: { select: { options: configurations, mode: 'dropdown' } } }]
        : []),
      { name: 'show', selector: { select: { multiple: true, mode: 'list', options: PARTS.map((p) => ({ value: p, label: L[p] })) } } },
      { name: 'layout', selector: { select: { mode: 'dropdown', options: ['auto', 'columns', 'stack'].map((p) => ({ value: p, label: L[p] })) } } },
      { name: 'stations', selector: { number: { min: 1, max: 5, step: 1, mode: 'slider' } } },
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
    description: 'Czech fuel prices: cheapest stations of your city, your favourite station, map and 30-day graph (data from mBenzin.cz).',
  });
}
console.info(`%c Ceny paliv card %c ${CARD_VERSION} `, 'color:#fff;background:#f5b14c;font-weight:700', 'color:#f5b14c;background:#171a20');
