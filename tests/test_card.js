const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor() {
    this.children = [];
    this.listeners = {};
    const listeners = {};
    this.shadowRoot = {
      listeners,
      innerHTML: "",
      getElementById: () => ({ replaceChildren() {}, appendChild() {} }),
      querySelector: () => null,
      addEventListener(name, callback) { (listeners[name] = listeners[name] || []).push(callback); },
    };
  }
  attachShadow() { return this.shadowRoot; }
  appendChild(child) { this.children.push(child); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  dispatchEvent(event) { this.lastEvent = event; }
}

class Form extends Element {}

const timers = [];
const cleared = [];
const source = readFileSync(
  `${__dirname}/../custom_components/ceny_paliv/frontend/ceny-paliv-card.js`,
  "utf8",
);
const context = {
  HTMLElement: Element,
  customElements: { get: () => undefined, define() {} },
  document: { createElement: () => new Form() },
  window: { customCards: [], opened: [], open(url) { this.opened.push(url); } },
  setTimeout: (callback) => { timers.push(callback); return timers.length; },
  clearTimeout: (id) => { cleared.push(id); },
  CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
  console: { info() {} },
};
vm.runInNewContext(
  `${source}\nglobalThis.testExports = { CenyPalivCard, CenyPalivCardEditor, editorDefaults, withLastKnown, navigationLinks, switchFuels, withDrive, kmBetween, dailyValues, graphDays, chartModel, areaIds, areaSensors, fillUpSaving, CenyPalivFuelsCard, CenyPalivSavingsCard, CenyPalivMiniEditor, CenyPalivCompareCard, CenyPalivRegionsCard, regionPaths, CenyPalivStationsMapCard, toKm, CenyPalivBadge, CenyPalivPriceFeature, supportsPriceFeature };`,
  context,
);
const { CenyPalivCard, CenyPalivCardEditor, editorDefaults, withLastKnown, navigationLinks, switchFuels, withDrive, kmBetween, dailyValues, graphDays, chartModel, areaIds, areaSensors, fillUpSaving, CenyPalivFuelsCard, CenyPalivSavingsCard, CenyPalivMiniEditor, CenyPalivCompareCard, CenyPalivRegionsCard, regionPaths, CenyPalivStationsMapCard, toKm, CenyPalivBadge, CenyPalivPriceFeature, supportsPriceFeature } = context.testExports;

const sensor = (fuel, role, configId, extra = {}) => ({
  state: "32.00",
  last_updated: "2026-11-12T00:00:00Z",
  attributes: {
    cp_fuel: fuel,
    cp_role: role,
    cp_config_id: configId,
    fuel,
    fuel_label: fuel.toUpperCase(),
    ...extra,
  },
});

test("cached home binding is rescanned after it becomes an archive without disappearing", () => {
  const hass = {
    states: {
      "sensor.ceny_paliv_n95_top5": sensor("n95", "top5", "area-a", { home: { price: 32 } }),
      "sensor.ceny_paliv_n95_home": sensor("n95", "home", "area-a"),
    },
  };
  const card = {
    _ids: null,
    _config: { fuel: "n95", config_id: "area-a" },
    _scanAt: 0,
  };

  card._ids = CenyPalivCard.prototype._resolve.call(card, hass);
  assert.equal(card._ids.home, "sensor.ceny_paliv_n95_home");

  hass.states["sensor.ceny_paliv_n95_home"] = sensor("n95", "home_archive", "area-a");
  hass.states["sensor.ceny_paliv_n95_home"].state = "unavailable";
  hass.states["sensor.ceny_paliv_n95_home_abc"] = sensor("n95", "home", "area-a");

  const resolved = CenyPalivCard.prototype._resolve.call(card, hass);

  assert.equal(resolved.home, "sensor.ceny_paliv_n95_home_abc");
  assert.notEqual(resolved.home, "sensor.ceny_paliv_n95_home");
});

test("resolver rejects home entities from another fuel or area and permits no active home", () => {
  const card = {
    _ids: null,
    _config: { fuel: "n95", config_id: "area-a" },
    _scanAt: 0,
  };
  const hass = {
    states: {
      "sensor.ceny_paliv_n95_top5": sensor("n95", "top5", "area-a"),
      "sensor.ceny_paliv_n95_home_other_area": sensor("n95", "home", "area-b"),
      "sensor.ceny_paliv_lpg_home": sensor("lpg", "home", "area-a"),
      "sensor.ceny_paliv_n95_home_old": sensor("n95", "home_archive", "area-a"),
    },
  };

  assert.equal(CenyPalivCard.prototype._resolve.call(card, hass).home, null);
});

test("cached positions are rebound to the selected configuration", () => {
  const card = {
    _ids: null,
    _config: { fuel: "n95", config_id: "area-a" },
    _scanAt: 0,
  };
  const hass = {
    states: {
      "sensor.ceny_paliv_n95_top5_a": sensor("n95", "top5", "area-a"),
      "sensor.ceny_paliv_n95_home_a": sensor("n95", "home", "area-a"),
      "sensor.ceny_paliv_n95_1_a": sensor("n95", "position", "area-a", { cp_index: 1 }),
      "sensor.ceny_paliv_n95_1_b": sensor("n95", "position", "area-b", { cp_index: 1 }),
    },
  };

  card._ids = {
    top5: "sensor.ceny_paliv_n95_top5_a",
    home: "sensor.ceny_paliv_n95_home_a",
    pos: ["sensor.ceny_paliv_n95_1_b"],
  };

  const resolved = CenyPalivCard.prototype._resolve.call(card, hass);

  assert.equal(resolved.pos[0], "sensor.ceny_paliv_n95_1_a");
});

test("a missing active favourite produces no statistics graph", async () => {
  context.window.loadCardHelpers = async () => ({
    createCardElement: () => new Element(),
  });
  const card = {
    _extraReady: false,
    _hass: { states: {} },
    _ids: { home: null, pos: [] },
    _show: ["graph"],
    _mapHeight: 0,
    _children: null,
    shadowRoot: { getElementById: () => ({ appendChild() {} }) },
  };

  await CenyPalivCard.prototype._buildExtra.call(card);

  assert.equal(card._children.length, 0);
});

test("map markers show the bare price attribute, not the state with its unit", async () => {
  const configs = [];
  context.window.loadCardHelpers = async () => ({
    createCardElement: (config) => { configs.push(config); return new Element(); },
  });
  const card = {
    _extraReady: false,
    _hass: { states: { "sensor.home": {} } },
    _ids: { home: "sensor.home", pos: ["sensor.p1", "sensor.p2"] },
    _show: ["map"],
    _n: 5,
    _mapHeight: 0,
    _children: null,
    shadowRoot: { getElementById: () => ({ replaceChildren() {} }) },
  };

  await CenyPalivCard.prototype._buildExtra.call(card);

  const map = configs.find((c) => c.type === "map");
  assert.deepEqual(map.entities.map((e) => [e.entity, e.label_mode, e.attribute]), [
    ["sensor.p1", "attribute", "price"],
    ["sensor.p2", "attribute", "price"],
    ["sensor.home", "attribute", "price"],
  ]);
});

test("editor clears an incompatible area on fuel change and keeps a valid choice", () => {
  const top = (fuel, configId) => [
    `sensor.ceny_paliv_${fuel}_${configId}_top5`,
    {
      attributes: {
        cp_role: "top5",
        cp_fuel: fuel,
        cp_config_id: configId,
        fuel,
        fuel_label: fuel.toUpperCase(),
        city_name: configId,
      },
    },
  ];
  const hass = {
    language: "en",
    states: Object.fromEntries([
      top("n95", "a"),
      top("n95", "b"),
      top("lpg", "only"),
      top("diesel", "x"),
      top("diesel", "y"),
    ]),
  };
  const editor = new CenyPalivCardEditor();
  editor.setConfig({ fuel: "n95", config_id: "a" });
  editor.hass = hass;
  const form = editor.children[0];

  form.listeners["value-changed"]({ detail: { value: { fuel: "lpg" } } });
  assert.equal(editor.lastEvent.detail.config.config_id, "only");

  editor.setConfig({ fuel: "n95", config_id: "a" });
  editor.hass = hass;
  form.listeners["value-changed"]({ detail: { value: { fuel: "diesel" } } });
  assert.equal("config_id" in editor.lastEvent.detail.config, false);

  editor.setConfig({ fuel: "diesel" });
  editor.hass = hass;
  assert.ok(editor.children[0].schema.some((field) => field.name === "config_id"));
  form.listeners["value-changed"]({
    detail: { value: { fuel: "diesel", config_id: "y" } },
  });
  assert.equal(editor.lastEvent.detail.config.config_id, "y");
});

test("editor preserves a compatible config across fuels and selects the only GPS area", () => {
  const top = (fuel, configId) => [
    `sensor.ceny_paliv_${fuel}_${configId}_top5`,
    {
      attributes: {
        cp_role: "top5",
        cp_fuel: fuel,
        cp_config_id: configId,
        fuel,
        fuel_label: fuel.toUpperCase(),
        city_name: configId,
      },
    },
  ];
  const editor = new CenyPalivCardEditor();
  editor.setConfig({ fuel: "n95", config_id: "shared-area" });
  editor.hass = {
    language: "en",
    states: Object.fromEntries([
      top("n95", "shared-area"),
      top("lpg", "shared-area"),
      top("lpg", "other-area"),
      top("diesel", "only-area"),
    ]),
  };
  const form = editor.children[0];

  form.listeners["value-changed"]({ detail: { value: { fuel: "lpg" } } });
  assert.equal(editor.lastEvent.detail.config.config_id, "shared-area");

  form.listeners["value-changed"]({ detail: { value: { fuel: "diesel" } } });
  assert.equal(editor.lastEvent.detail.config.config_id, "only-area");
});

const resolveFresh = (config, hass) => CenyPalivCard.prototype._resolve.call(
  { _ids: null, _config: config, _scanAt: 0 }, hass,
);
const area = (id, fuel = "n95", extra = {}) => ({
  [`sensor.ceny_paliv_${fuel}_top5_${id}`]: sensor(fuel, "top5", id, extra.top),
  [`sensor.ceny_paliv_${fuel}_home_${id}`]: sensor(fuel, "home", id),
  [`sensor.ceny_paliv_${fuel}_1_${id}`]: sensor(fuel, "position", id, { cp_index: 1 }),
});
const same = (a, b) => assert.equal(JSON.stringify(a), JSON.stringify(b));
const empty = { top5: null, home: null, pos: [] };

test("single area binds automatically; a second area invalidates the cached binding", () => {
  const hass = { states: { ...area("a") } };
  const card = { _ids: null, _config: { fuel: "n95" }, _scanAt: 0 };
  const resolve = () => { card._ids = CenyPalivCard.prototype._resolve.call(card, hass); return card._ids; };

  assert.equal(resolve().top5, "sensor.ceny_paliv_n95_top5_a");
  assert.equal(resolve().home, "sensor.ceny_paliv_n95_home_a");

  Object.assign(hass.states, area("b"));
  same(resolve(), empty);
  same(resolve(), resolveFresh({ fuel: "n95" }, hass));

  delete hass.states["sensor.ceny_paliv_n95_top5_a"];
  delete hass.states["sensor.ceny_paliv_n95_home_a"];
  delete hass.states["sensor.ceny_paliv_n95_1_a"];
  const remaining = resolve();
  assert.equal(remaining.top5, "sensor.ceny_paliv_n95_top5_b");
  assert.equal(remaining.home, "sensor.ceny_paliv_n95_home_b");
  same(remaining.pos, ["sensor.ceny_paliv_n95_1_b"]);
});

test("explicit config_id survives additional areas and matches a fresh scan", () => {
  const hass = { states: { ...area("a"), ...area("b") } };
  const config = { fuel: "n95", config_id: "b" };
  const card = { _ids: null, _config: config, _scanAt: 0 };
  card._ids = CenyPalivCard.prototype._resolve.call(card, hass);
  assert.equal(card._ids.top5, "sensor.ceny_paliv_n95_top5_b");
  Object.assign(hass.states, area("c"));
  const cached = CenyPalivCard.prototype._resolve.call(card, hass);
  same(cached, resolveFresh(config, hass));
  assert.equal(cached.pos[0], "sensor.ceny_paliv_n95_1_b");
});

test("fuel change with a cached binding never reuses the old fuel's sensors", () => {
  const hass = { states: { ...area("a"), ...area("a", "lpg"), ...area("b", "lpg") } };
  const card = { _ids: null, _config: { fuel: "n95" }, _scanAt: 0 };
  card._ids = CenyPalivCard.prototype._resolve.call(card, hass);
  assert.equal(card._ids.top5, "sensor.ceny_paliv_n95_top5_a");
  card._config = { fuel: "lpg" };
  same(CenyPalivCard.prototype._resolve.call(card, hass), empty);
});

test("archived or changed favourite with several areas never mixes areas", () => {
  const hass = { states: { ...area("a"), ...area("b") } };
  const config = { fuel: "n95", config_id: "a" };
  const card = { _ids: null, _config: config, _scanAt: 0 };
  card._ids = CenyPalivCard.prototype._resolve.call(card, hass);
  hass.states["sensor.ceny_paliv_n95_home_a"] = sensor("n95", "home_archive", "a");
  hass.states["sensor.ceny_paliv_n95_home_b2"] = sensor("n95", "home", "b");
  card._scanAt = 0;
  const resolved = CenyPalivCard.prototype._resolve.call(card, hass);
  assert.equal(resolved.home, null);
  assert.ok([resolved.top5, ...resolved.pos].every((id) => !id || id.endsWith("_a")));
  same(resolved, resolveFresh(config, hass));
});

test("legacy entities without attributes resolve only when unambiguous", () => {
  const legacy = (suffix) => ({ [`sensor.ceny_paliv_n95_${suffix}`]: { state: "1", attributes: {} } });
  const hass = { states: { ...legacy("top5") } };
  const card = { _ids: null, _config: { fuel: "n95" }, _scanAt: 0 };
  card._ids = CenyPalivCard.prototype._resolve.call(card, hass);
  assert.equal(card._ids.top5, "sensor.ceny_paliv_n95_top5");
  Object.assign(hass.states, area("a"));
  same(CenyPalivCard.prototype._resolve.call(card, hass), empty);
});

test("hass update shows the area picker message once a second area appears", () => {
  const hass = { states: { ...area("a") } };
  const card = {
    _config: { fuel: "n95" }, _ids: null, _scanAt: 0, _sig: "", _children: null, rendered: 0,
    _resolve: CenyPalivCard.prototype._resolve,
    _resetExtra: CenyPalivCard.prototype._resetExtra,
    shadowRoot: { getElementById: () => null },
    _renderTexts() { this.rendered += 1; },
  };
  const setHass = Object.getOwnPropertyDescriptor(CenyPalivCard.prototype, "hass").set;
  setHass.call(card, hass);
  assert.equal(card._ids.top5, "sensor.ceny_paliv_n95_top5_a");
  Object.assign(hass.states, area("b"));
  setHass.call(card, { states: hass.states });
  same(card._ids, empty);
  assert.equal(card.rendered, 2);
});

test("editor offers area choice for several areas and none for one", () => {
  const editor = new CenyPalivCardEditor();
  editor.setConfig({ fuel: "n95" });
  editor.hass = { language: "en", states: { ...area("a"), ...area("b") } };
  assert.ok(editor.children[0].schema.some((field) => field.name === "config_id"));
  assert.equal(CenyPalivCard.configurations({ states: { ...area("a") } }, "n95").length, 1);
});

test("a restored orphan top5 of a removed area never makes the binding ambiguous", () => {
  const card = { _ids: null, _config: { fuel: "n95" }, _scanAt: 0 };
  const hass = {
    states: {
      ...area("b"),
      // what Home Assistant restores at start-up for an entity that no loaded entry provides
      "sensor.ceny_paliv_n95_top5": { state: "unavailable", attributes: { restored: true, friendly_name: "old" } },
    },
  };
  assert.equal(CenyPalivCard.prototype._resolve.call(card, hass).top5, "sensor.ceny_paliv_n95_top5_b");
});

test("with the entity registry, the single-area check reruns when the registry changes", () => {
  const card = { _ids: null, _config: { fuel: "n95" }, _scanAt: 0 };
  const states = { ...area("a") };
  const resolve = (hass) => { card._ids = CenyPalivCard.prototype._resolve.call(card, hass); return card._ids; };
  assert.equal(resolve({ states, entities: { first: 1 } }).top5, "sensor.ceny_paliv_n95_top5_a");
  // a second area adds entities, so Home Assistant hands over a new registry object
  Object.assign(states, area("b"));
  same(resolve({ states, entities: { second: 1 } }), empty);
  assert.equal(card._ambiguous, true);
});

test("the unavailable message clears map and graph so they are rebuilt when data returns", () => {
  const slots = {};
  const card = {
    _hass: { language: "cs", states: { "sensor.ceny_paliv_n95_top5": { state: "unavailable", attributes: {} } } },
    _ids: { top5: "sensor.ceny_paliv_n95_top5", home: null, pos: [] },
    _config: { fuel: "n95" },
    _show: ["list", "map", "graph"],
    _extraReady: true,
    _children: [{}],
    _gen: 1,
    shadowRoot: { getElementById: (id) => (slots[id] = slots[id] || { innerHTML: "" }) },
    _message: CenyPalivCard.prototype._message,
    _resetExtra: CenyPalivCard.prototype._resetExtra,
    _switchHtml: CenyPalivCard.prototype._switchHtml,
  };
  CenyPalivCard.prototype._renderTexts.call(card);
  assert.equal(card._extraReady, false);
  assert.equal(card._children, null);
  assert.equal(card._gen, 2);
  assert.match(slots.list.innerHTML, /nedostupné/);
  assert.equal(slots.map.innerHTML, "");
});

test("listeners are registered once however often the config changes", () => {
  const card = new CenyPalivCard();
  card.getBoundingClientRect = () => ({ width: 400 });
  for (let i = 0; i < 3; i += 1) card.setConfig({ fuel: "n95", stations: i + 1 });
  assert.equal(card.shadowRoot.listeners.click.length, 1);
  assert.equal(card.shadowRoot.listeners.pointerdown.length, 1);
});

// what ha-form really sends: all of its data (the defaults it displays included) with the user's change
const edit = (editor, change) => {
  const form = editor.children[0];
  form.listeners["value-changed"]({ detail: { value: { ...form.data, ...change } } });
  return editor.lastEvent.detail.config;
};

test("editing a legacy card keeps show_map/show_graph and never saves displayed defaults", () => {
  const editor = new CenyPalivCardEditor();
  editor.setConfig({ fuel: "n95", show_map: false });
  editor.hass = { language: "en", states: { ...area("a") } };
  assert.deepEqual([...editor.children[0].data.show], ["home", "list", "graph"]);

  const saved = edit(editor, { stations: 3 });
  same(saved, { fuel: "n95", show_map: false, stations: 3 });

  editor.setConfig(saved);
  const compact = edit(editor, { compact: true });
  assert.equal("show_footer" in compact, false); // the footer keeps following "compact"

  editor.setConfig(compact);
  const explicit = edit(editor, { show: ["list", "map"] });
  same(explicit.show, ["list", "map"]);
  assert.equal("show_map" in explicit, false);
});

test("with one configuration the editor neither saves nor needs config_id, but repairs a stale one", () => {
  const editor = new CenyPalivCardEditor();
  const hass = { language: "cs", states: { ...area("a"), ...area("b", "lpg") } };
  editor.setConfig({ fuel: "n95" });
  editor.hass = hass;
  assert.equal(editor.children[0].schema.some((field) => field.name === "config_id"), false);
  assert.equal("config_id" in edit(editor, { fuel: "lpg" }), false);

  // the integration was removed and added again: the pinned id no longer exists
  editor.setConfig({ fuel: "n95", config_id: "old-entry" });
  editor.hass = hass;
  assert.ok(editor.children[0].schema.some((field) => field.name === "config_id"));
  assert.equal(edit(editor, {}).config_id, "a");
});

test("the editor does not rebuild its form on unrelated state changes", () => {
  const editor = new CenyPalivCardEditor();
  editor.setConfig({ fuel: "n95" });
  editor.hass = { language: "en", states: { ...area("a") } };
  const schema = editor.children[0].schema;
  editor.hass = { language: "en", states: { ...area("a"), "light.kitchen": { state: "on", attributes: {} } } };
  assert.equal(editor.children[0].schema, schema);
  assert.equal(editorDefaults({ compact: true }).show_footer, false);
});

test("a long press is cancelled when the pointer moves away, and Enter opens a focused row", () => {
  const row = { dataset: { station: "1" } };
  const opened = [];
  const card = { _ids: { top5: "t", home: null }, _entityId: CenyPalivCard.prototype._entityId, _openStation: (i) => opened.push(i) };
  const event = { clientX: 0, clientY: 0, composedPath: () => [row] };
  CenyPalivCard.prototype._down.call(card, event);
  const timer = card._timer;
  CenyPalivCard.prototype._move.call(card, { clientX: 3, clientY: 2 });
  assert.equal(cleared.includes(timer), false); // a small wobble keeps the press
  CenyPalivCard.prototype._move.call(card, { clientX: 40, clientY: 0 });
  assert.equal(cleared.includes(timer), true);

  card._click = CenyPalivCard.prototype._click;
  CenyPalivCard.prototype._key.call(card, { key: "Enter", preventDefault() {}, composedPath: () => [row] });
  assert.deepEqual(opened, [1]); // the station's details, no longer straight to Google Maps
});

test("numbers and times follow the Home Assistant profile, texts the integration's language", () => {
  const card = Object.create(CenyPalivCard.prototype);
  const top = { attributes: { labels: { locale: "cs-CZ" } } };
  const at = (locale) => Object.assign(card, {
    _hass: { language: "cs", locale, states: { "sensor.t": top }, config: { time_zone: "Europe/Prague" } },
    _ids: { top5: "sensor.t" },
  });
  at({ number_format: "language" });
  assert.equal(card._num(38.5), "38,50"); // Czech decimal comma, two digits for a price
  assert.equal(card._num("x"), "—");
  at({ number_format: "comma_decimal" });
  assert.equal(card._num(38.5), "38.50");
  at({ number_format: "decimal_comma" });
  assert.equal(card._num(1238.5), "1.238,50");

  const evening = new Date("2026-11-13T19:58:00+01:00");
  at({ time_format: "24", time_zone: "server" });
  assert.equal(card._dateTime(evening, { hour: "numeric", minute: "2-digit" }), "19:58");
  at({ time_format: "12", time_zone: "server" });
  assert.match(card._dateTime(evening, { hour: "numeric", minute: "2-digit" }), /7:58\s?(PM|odp\.)/i);

  // a price date is a calendar day: no time zone (browser or server) may move it to the day before
  assert.equal(card._day("2026-11-10", { day: "numeric", month: "numeric" }), "10. 11.");
  assert.equal(card._day("not a date", { day: "numeric" }), null);
});

test("a row does not repeat the station name in its address, even without accents", () => {
  const now = new Date(); // the card counts days in local time
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const top = {
    state: "38.5", last_updated: "x",
    attributes: {
      stations: [{ name: "Am oil Miličín", chain: "Am oil Miličín", address: "Am oil Milicin parkoviste", price: 38.5, updated_date: today, trends: {} }],
      fuel: "n95", fuel_label: "Natural 95", labels: { locale: "cs-CZ", today: "Dnes" }, max_age_days: 1,
    },
  };
  const card = Object.create(CenyPalivCard.prototype);
  Object.assign(card, {
    _hass: { language: "cs", states: { "sensor.t": top } },
    _ids: { top5: "sensor.t", home: null, pos: [] },
    _config: { fuel: "n95" }, _n: 5, _compact: false, _footer: false, _show: ["list"],
  });
  const html = card._listHtml();
  assert.match(html, /Dnes<\/span> · parkoviste/);
  assert.doesNotMatch(html, /Milicin parkoviste/);
  assert.match(html, /38,50/);

  // from 0.6 the integration sends the street itself, and the town for a station without a street
  top.attributes.stations = [
    { name: "Robin Oil", address: "Robin Oil", street: "", city: "Lhota", price: 38.9, updated_date: today, trends: {} },
    { name: "Petrol", address: "Petrol Prazska 310", street: "Prazska 310", city: "Neveklov", price: 39, updated_date: today, trends: {} },
  ];
  const rows = card._listHtml();
  assert.match(rows, /Dnes<\/span> · Lhota/);
  assert.match(rows, /Dnes<\/span> · Prazska 310/);
});

test("prices always show the required source 'Ceny: mbenzin.cz' as a link", () => {
  const top = {
    state: "30", last_updated: "x",
    attributes: {
      stations: [{ name: "Orlen", address: "Orlen Praha", price: 30, updated_date: new Date().toISOString().slice(0, 10), trends: {} }],
      fuel: "n95", fuel_label: "Natural 95", labels: { source: "Ceny: mbenzin.cz" }, max_age_days: 1,
    },
  };
  const home = { state: "31", last_updated: "x", attributes: { trends: {}, unit_of_measurement: "Kč/l" } };
  const card = Object.create(CenyPalivCard.prototype);
  Object.assign(card, {
    _hass: { states: { "sensor.t": top, "sensor.h": home } },
    _ids: { top5: "sensor.t", home: "sensor.h", pos: [] },
    _config: { fuel: "n95" }, _n: 5, _compact: false, _footer: true, _show: ["home", "list"],
  });
  const link = /<a href="https:\/\/www\.mbenzin\.cz"[^>]*>Ceny: mbenzin\.cz<\/a>/;
  assert.match(card._listHtml(), link);
  card._footer = false; // the short footer keeps it too
  assert.match(card._listHtml(), link);
  assert.doesNotMatch(card._homeHtml(), link); // shown once, under the list
  card._show = ["home"]; // the favourite card on its own carries it
  assert.match(card._homeHtml(), link);

  // a tap on the link opens only the link: no more-info, no map
  const opened = context.window.opened.length;
  card._entityId = () => ({ dataset: { moreInfo: "sensor.t" } });
  card._moreInfo = () => assert.fail("more-info must not open");
  card._click({ composedPath: () => [{ tagName: "A" }, { dataset: { moreInfo: "sensor.t" } }] });
  assert.equal(context.window.opened.length, opened);
});

// What Home Assistant shows for an unavailable sensor: no attributes beyond its name.
const unavailable = () => ({ state: "unavailable", last_updated: "2026-11-14T06:00:00Z", attributes: { friendly_name: "x" } });

test("during an outage the card shows the last known sensors with a warning", () => {
  const ids = ["sensor.ceny_paliv_n95_top5", "sensor.ceny_paliv_n95_home", "sensor.ceny_paliv_n95_1"];
  const labels = { stale: "mBenzin.cz je nedostupný — zobrazeny poslední známé ceny" };
  const live = {
    [ids[0]]: sensor("n95", "top5", "outage", { stations: [], labels }),
    [ids[1]]: sensor("n95", "home", "outage", { station: "Orlen", trends: {}, age_days: 0 }),
    [ids[2]]: sensor("n95", "position", "outage", { latitude: 50.1, longitude: 14.4, price: 32 }),
  };
  const hass = { language: "cs", localize: () => "", states: { ...live } };
  assert.equal(withLastKnown(hass), hass); // nothing unavailable: Home Assistant's own object
  const down = { ...hass, states: Object.fromEntries(ids.map((id) => [id, unavailable()])) };
  const view = withLastKnown(down);
  assert.equal(view.localize, hass.localize); // everything else of hass is kept
  for (const id of ids) {
    assert.equal(view.states[id].state, "32.00");
    assert.equal(view.states[id].attributes.cp_stale, true);
  }
  assert.equal(view.states[ids[2]].attributes.latitude, 50.1); // the map keeps its markers

  const card = Object.create(CenyPalivCard.prototype);
  Object.assign(card, {
    _hass: view,
    _ids: { top5: ids[0], home: ids[1], pos: [ids[2]] },
    _config: { fuel: "n95" }, _n: 5, _compact: false, _footer: false, _show: ["home", "list"],
  });
  assert.match(card._listHtml(), /class="alert warning"[^]*nedostupný — zobrazeny poslední známé ceny/);
  assert.match(card._homeHtml(), /secondary warn[^]*nedostupný — zobrazeny poslední známé ceny/);
});

test("an archived favourite or a removed area is never revived from the last known state", () => {
  const top = "sensor.ceny_paliv_lpg_top5";
  const home = "sensor.ceny_paliv_lpg_home";
  const orphan = "sensor.ceny_paliv_lpg_top5_2";
  withLastKnown({ states: {
    [top]: sensor("lpg", "top5", "kept"),
    [home]: sensor("lpg", "home", "kept"),
    [orphan]: sensor("lpg", "top5", "removed"),
  } });
  const view = withLastKnown({ states: {
    [top]: sensor("lpg", "top5", "kept"), // the area still refreshes: the favourite was changed
    [home]: unavailable(),
    [orphan]: { ...unavailable(), attributes: { restored: true } },
  } });
  assert.equal(view.states[home].state, "unavailable");
  assert.equal(view.states[orphan].state, "unavailable");
});

test("the last known states survive a page reload in this browser only", () => {
  const saved = {};
  const storage = { getItem: (k) => saved[k] ?? null, setItem: (k, v) => { saved[k] = v; } };
  const load = (window) => {
    const ctx = { ...context, window };
    vm.runInNewContext(`${source}\nglobalThis.fn = withLastKnown;`, ctx);
    return ctx.fn;
  };
  const id = "sensor.ceny_paliv_cng_top5";
  load({ localStorage: storage })({ states: { [id]: sensor("cng", "top5", "reload"), "sensor.other": { state: "1", attributes: {} } } });
  assert.deepEqual(Object.keys(JSON.parse(saved["ceny-paliv-last-known"])), [id]);
  const view = load({ localStorage: storage })({ states: { [id]: unavailable() } });
  assert.equal(view.states[id].attributes.cp_role, "top5");
  // a blocked storage (private mode) only loses the reload case
  const blocked = { get localStorage() { throw new Error("blocked"); } };
  assert.equal(load(blocked)({ states: { [id]: unavailable() } }).states[id].state, "unavailable");
});

test("the 30-day graph: your station's own statistics, the area's cheapest (daily minimum) and its average", () => {
  const top = { state: "38", attributes: { cp_role: "top5", cp_fuel: "n95", cp_config_id: "a", labels: { my_station: "Mine", series_cheapest: "Cheapest", series_average: "Average" } } };
  const states = {
    "sensor.ceny_paliv_n95_top5": top,
    "sensor.ceny_paliv_n95_home": { state: "38.9", attributes: { statistic_id: "ceny_paliv:n95_0123456789ab" } },
    "sensor.ceny_paliv_n95_area_average": { state: "39.4", attributes: { cp_role: "area_average", cp_fuel: "n95", cp_config_id: "a" } },
    "sensor.ceny_paliv_n95_area_average_2": { state: "40", attributes: { cp_role: "area_average", cp_fuel: "n95", cp_config_id: "b" } },
  };
  const card = new CenyPalivCard();
  card._config = { fuel: "n95" };
  card._hass = { states };
  card._ids = { top5: "sensor.ceny_paliv_n95_top5", home: "sensor.ceny_paliv_n95_home", pos: [] };
  same(card._graphSeries().map((x) => [x.key, x.id, x.type, x.label]), [
    ["mine", "ceny_paliv:n95_0123456789ab", "mean", "Mine"],
    ["cheapest", "sensor.ceny_paliv_n95_top5", "min", "Cheapest"],
    ["average", "sensor.ceny_paliv_n95_area_average", "mean", "Average"], // of this area, not the other one
  ]);
  // before 0.6 the favourite had no statistics of its own: the sensor's; no favourite: the area only
  states["sensor.ceny_paliv_n95_home"].attributes = {};
  assert.equal(card._graphSeries()[0].id, "sensor.ceny_paliv_n95_home");
  card._ids.home = null;
  same(card._graphSeries().map((x) => x.key), ["cheapest", "average"]);
});

test("daily values by local day and a chart broken where a day is missing", () => {
  const noon = (d) => new Date(2026, 10, d, 12).getTime();
  same(dailyValues([{ start: noon(10), mean: 38.5 }, { start: new Date(2026, 10, 11, 12).toISOString(), mean: 38.7 }, { start: noon(12), mean: null }], "mean"),
    { "2026-11-10": 38.5, "2026-11-11": 38.7 });
  same(graphDays(new Date(2026, 10, 2), 4), ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]);

  const days = ["d1", "d2", "d3", "d4", "d5"];
  const model = chartModel([
    { values: { d1: 38.2, d2: 38.4, d4: 38.9 } }, // a gap on d3; d4 alone is a dot
    { values: {} },
  ], days, 248);
  assert.equal(model.lo, 38);
  assert.equal(model.hi, 39);
  same(model.ticks.map((t) => t.v), [39, 38.5, 38]);
  assert.equal(model.lines[0].path.split("M").length - 1, 2); // two pieces
  assert.equal(model.lines[0].dots.length, 1);
  assert.equal(model.lines[1].path, "");
  assert.equal(model.x(0), 40);
  assert.equal(model.x(4), 240); // 248 - 8 on the right
  assert.equal(chartModel([{ values: {} }], days, 248), null);
});

test("the graph loads the daily statistics once per hour and draws them with their latest values", async () => {
  const calls = [];
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const ms = (back) => today.getTime() - back * 86400000;
  const card = new CenyPalivCard();
  card._config = { fuel: "n95" };
  card._show = ["graph"];
  card._ids = { top5: "sensor.ceny_paliv_n95_top5", home: null, pos: [] };
  card._hass = {
    language: "en", locale: { number_format: "comma_decimal" },
    states: { "sensor.ceny_paliv_n95_top5": { state: "38", attributes: { cp_role: "top5", cp_fuel: "n95", cp_config_id: "a", fuel_label: "Natural 95", city_name: "Brno",
      labels: { graph_title: "Prices over 30 days", series_cheapest: "Cheapest", graph_empty: "No history yet" } } } },
    callWS: async (msg) => { calls.push(msg); return { "sensor.ceny_paliv_n95_top5": [{ start: ms(2), min: 38.4, mean: 38.9 }, { start: ms(1), min: 38.1, mean: 38.6 }] }; },
  };
  assert.match(card._graphHtml(), /No history yet/); // nothing loaded yet
  await card._loadStats();
  await card._loadStats(); // the same hour: no second request
  assert.equal(calls.length, 1);
  assert.equal(calls[0].type, "recorder/statistics_during_period");
  same(calls[0].statistic_ids, ["sensor.ceny_paliv_n95_top5"]);
  assert.equal(calls[0].period, "day");
  const html = card._graphHtml();
  assert.match(html, /<svg viewBox="0 0 360 160" role="img" aria-label="Prices over 30 days: Cheapest: 38\.10 Kč\/l"/);
  assert.match(html, /class="line cheapest" d="M[\d.]+,[\d.]+L[\d.]+,[\d.]+"/); // the daily minimum, two days joined
  assert.match(html, /<span class="name">Cheapest<\/span> <span class="value">38\.10<\/span>/);

  // the recorder cannot answer: the graph says there is no history, nothing breaks
  card._hass = { ...card._hass, callWS: async () => { throw new Error("no recorder"); } };
  card._statsKey = null;
  await card._loadStats();
  assert.match(card._graphHtml(), /No history yet/);
});

test("navigation links put each service's coordinates in its own order", () => {
  const links = navigationLinks({ lat: 49.19, lng: 16.61 });
  same(links.map((l) => l.label), ["Mapy.com", "Google Maps", "Waze"]);
  assert.equal(links[0].url, "https://mapy.com/fnc/v1/route?end=16.61,49.19&routeType=car_fast"); // lon,lat
  assert.equal(links[1].url, "https://www.google.com/maps/dir/?api=1&destination=49.19%2C16.61&travelmode=driving");
  assert.equal(links[2].url, "https://waze.com/ul?ll=49.19%2C16.61&navigate=yes");
  assert.equal(navigationLinks({ lat: "x", lng: 16 }).length, 0);
  assert.equal(navigationLinks({ lat: 99, lng: 16 }).length, 0);
});

test("the fuel switch lists the fuels once, the first shown first", () => {
  same(switchFuels({ fuel: "n95" }), ["n95"]);
  same(switchFuels({ fuel: "lpg", fuels: ["n95", "diesel", "n95"] }), ["lpg", "n95", "diesel"]);
  same(switchFuels({ fuels: ["diesel", "n95"] }), ["diesel", "n95"]);

  const card = new CenyPalivCard();
  card.getBoundingClientRect = () => ({ width: 400 });
  card.setConfig({ fuels: ["diesel", "n95"] });
  assert.equal(card._config.fuel, "diesel");
  assert.throws(() => card.setConfig({ fuels: [] }), /fuel/);
});

test("the switch shows each fuel's name and moves the card to the other fuel's sensors", () => {
  const hass = { language: "en", states: { ...area("a"), ...area("a", "diesel") } };
  const card = new CenyPalivCard();
  card.getBoundingClientRect = () => ({ width: 400 });
  card.setConfig({ fuel: "n95", fuels: ["n95", "diesel"], show: ["list"] });
  card.hass = hass;
  const html = card._switchHtml();
  assert.match(html, /role="tablist"/);
  assert.match(html, /class="option selected" role="tab" aria-selected="true" data-fuel="n95"><span>N95</);
  assert.match(html, /aria-selected="false" data-fuel="diesel"><span>DIESEL</);
  assert.equal(card._ids.top5, "sensor.ceny_paliv_n95_top5_a");

  card._click({ composedPath: () => [{ dataset: { fuel: "diesel" } }] });
  assert.equal(card._config.fuel, "diesel");
  assert.equal(card._ids.top5, "sensor.ceny_paliv_diesel_top5_a");
  card._switchFuel("lpg"); // not in the switch
  assert.equal(card._config.fuel, "diesel");
  card.setConfig({ fuel: "n95" });
  assert.equal(card._switchHtml(), "");
});

test("a station's details: price, rank, distance, trends and navigation", () => {
  const card = new CenyPalivCard();
  card._config = { fuel: "n95", logo_path: "" };
  card._hass = { language: "en", locale: { number_format: "comma_decimal" }, states: { t: { attributes: { labels: {
    rank_of: "#{rank} of {n}", more_than_cheapest: "+{d} vs the cheapest", cheapest_badge: "Cheapest", close: "Close",
    navigate: "Navigate", today: "Today", trends_start: "Trends start tomorrow",
  } } } } };
  card._ids = { top5: "t", home: null, pos: [] };
  const today = new Date().toISOString().slice(0, 10);
  const cheap = { name: "Levna", street: "Hlavni 1", city: "Brno", price: 33, lat: 49.19, lng: 16.61, updated_date: today, trends: {} };
  const dear = { ...cheap, name: "Draha", price: 34.5, distance_km: 2.345, trends: { 1: { dir: "down", delta: -0.4, ref_date: today, ref_price: 34.9 } } };
  card._rows = { list: [cheap, dear], fresh: 7, unit: "Kč/l" };

  const first = card._stationHtml(cheap, 1);
  assert.match(first, /id="sheet-title">Levna</);
  assert.match(first, /Hlavni 1, Brno/);
  assert.match(first, /#1 of 7/);
  assert.match(first, /class="good">Cheapest/);
  assert.match(first, /Trends start tomorrow/);
  assert.match(first, /aria-label="Close"/);
  assert.match(first, /href="https:\/\/mapy\.com\/fnc\/v1\/route\?end=16\.61,49\.19&amp;routeType=car_fast" target="_blank" rel="noopener noreferrer"/);
  assert.match(first, /Ceny: mbenzin\.cz/);

  const second = card._stationHtml(dear, 2);
  assert.match(second, /\+1\.50 vs the cheapest/);
  assert.match(second, /2\.3 km/);
  assert.match(second, /mdi:arrow-down/);
});

test("worth the drive adds the fuel burnt there and back to the price per litre", () => {
  // 40 l at 38 Kč/l, 10 km away, 6.5 l/100 km: 1.3 l for the trip, 49.4 Kč over 40 l = +1.235 Kč/l
  assert.equal(Math.round(withDrive(38, 10, 40, 6.5) * 1000) / 1000, 39.235);
  assert.equal(withDrive(38, 0, 40, 6.5), 38);
  assert.equal(Math.round(kmBetween(50.08, 14.42, 49.19, 16.61)), 186); // Prague to Brno in a straight line
});

test("the list sorts by price, distance or worth the drive, with the nearest stations of a GPS area", () => {
  const today = new Date().toISOString().slice(0, 10);
  const st = (name, price, km, rank) => ({ name, price, distance_km: km, lat: 49, lng: 16, updated_date: today, rank, street: "", city: "Brno", trends: {} });
  const top = {
    state: "38", attributes: {
      unit_of_measurement: "Kč/l", fuel: "n95", fuel_label: "Natural 95", city_name: "GPS", max_age_days: 1,
      gps_area: { latitude: 49.2, longitude: 16.6, station_count: 20 }, excluded: 0,
      labels: { sort: "Order", sort_price: "Price", sort_distance: "Distance", sort_worth: "Worth", with_drive: "≈ {p} with the drive", cheapest_badge: "Cheapest", more_than_cheapest: "+{d} vs the cheapest", rank_of: "#{rank} of {n}" },
      stations: [st("Far", 38, 30, 1), st("Mid", 38.5, 8, 2)],
      // the nearest list (ranked by distance) repeats a cheap station and adds a close, dear one
      gps_nearest_stations: [st("Near", 39.6, 1, 1), st("Mid", 38.5, 8, 2), { ...st("Old", 30, 0.5, 3), updated_date: "2000-01-01" }],
    },
  };
  const card = new CenyPalivCard();
  card.getBoundingClientRect = () => ({ width: 400 });
  card.setConfig({ fuel: "n95", show: ["list"], tank_litres: 40, consumption: 6.5 });
  card._hass = { language: "en", locale: { number_format: "comma_decimal" }, config: { latitude: 50, longitude: 14 }, states: { t: top } };
  card._ids = { top5: "t", home: null, pos: [] };
  const names = () => card._rows.list.map((s) => s.name);

  let html = card._listHtml();
  same(names(), ["Far", "Mid"]); // price order: only the cheapest list, as before
  assert.match(html, /role="tablist" aria-label="Order"/);
  assert.match(html, /aria-selected="true" data-sort="price"/);

  card._sort = "distance";
  html = card._listHtml();
  same(names(), ["Near", "Mid", "Far"]); // the outdated one is left out, "Mid" only once
  assert.match(html, /1\.0 km/);
  // a nearest-only station has no price rank (its rank in that list is by distance): no badge, none in its details
  const nearRow = html.split('class="row"').find((row) => row.includes(">Near<"));
  assert.doesNotMatch(nearRow, /class="rank"/);
  assert.equal(card._rows.list[0].rank, null);
  assert.doesNotMatch(card._stationHtml(card._rows.list[0], null), /of 20/);
  // its details compare with the area's cheapest price (38), which is not among the first rows here
  assert.match(card._stationHtml(card._rows.list[0], null), /\+1\.60/);

  card._sort = "worth";
  card._listHtml();
  // Far: 38 + 2*30*0.065*38/40 = 41.705; Mid: 38.5 + 2*8*0.065*38.5/40 = 39.501; Near: 39.6 + 0.1287 = 39.729
  same(names(), ["Mid", "Near", "Far"]); // not the distance order: the cheaper Mid is worth the extra 7 km
  assert.match(card._listHtml(), /≈ 39\.50 with the drive/);
  assert.match(card._listHtml(), />Far</); // the header still names the area's cheapest price
  assert.match(card._listHtml(), /class="number">38\.00</);

  card._setSort("price");
  assert.equal(card._sort, "price");
  card._setSort("nonsense");
  assert.equal(card._sort, "price");
  card._ids = { top5: "t", home: null, pos: [] }; // the mock's "t" is not a Ceny paliv entity id the resolver would keep

  // a GPS area without a centre (a location error) never measures from home
  top.attributes.gps_area = { station_count: 3 };
  card._sort = "distance";
  assert.doesNotMatch(card._listHtml(), /data-sort/);
  same(names(), ["Far", "Mid"]);

  // no location known: no sort control, price order
  card._hass = { ...card._hass, config: {} };
  delete top.attributes.gps_area;
  card._sort = "distance";
  html = card._listHtml();
  same(names(), ["Far", "Mid"]);
  assert.doesNotMatch(html, /data-sort/);
});

// ------------------------------------------------------------------ the small cards
const LABELS_EN = {
  fuels_title: "Fuel prices", mine_short: "mine {p}", savings_title: "A full tank", fill_up: "{n} {u} fill-up",
  save_at: "At {name} you save {d} Kč", mine_cheapest: "Your station is the cheapest", save_vs_avg: "At {name} {d} Kč less than at the average price",
  drive_extra: "{km} km more there and back ≈ {d} Kč", worth_yes: "worth it: you still save {d} Kč", worth_no: "not worth the drive",
  my_station: "My station", cheapest_badge: "Cheapest", series_average: "Area average", no_recent: "No recent prices",
};
const top5 = (fuel, area, price, extra = {}) => ({ entity_id: `sensor.ceny_paliv_${fuel}_top5_${area}`, state: String(price), last_updated: "t",
  attributes: { cp_role: "top5", cp_fuel: fuel, cp_config_id: area, fuel, fuel_label: fuel.toUpperCase(), unit_of_measurement: fuel === "cng" ? "Kč/kg" : "Kč/l",
    city_name: "Brno", labels: LABELS_EN, stations: [{ name: "Levna", title: "Levna · Hlavni", price, lat: 49.2, lng: 16.6, distance_km: 6, trends: { 1: { dir: "down", delta: -0.2 } } }], ...extra } });
const role = (fuel, area, r, state, extra = {}) => ({ state: String(state), last_updated: "t", attributes: { cp_role: r, cp_fuel: fuel, cp_config_id: area, ...extra } });
const miniHass = (states) => ({ language: "en", locale: { number_format: "comma_decimal" }, config: {}, states });

test("the small cards find an area's sensors by fuel, and need a choice when there are several areas", () => {
  const states = {
    "sensor.ceny_paliv_lpg_top5_a": top5("lpg", "a", 17.9),
    "sensor.ceny_paliv_n95_top5_a": top5("n95", "a", 38.5),
    "sensor.ceny_paliv_n95_home_a": role("n95", "a", "home", 38.9),
    "sensor.ceny_paliv_n95_home_old": role("n95", "a", "home", "unavailable"), // an archived favourite
    "sensor.ceny_paliv_n95_area_average_a": role("n95", "a", "area_average", 39.4),
    "sensor.ceny_paliv_n95_top5_b": top5("n95", "b", 37.9),
  };
  same(areaIds({ states }), ["a", "b"]);
  same(areaSensors({ states }, "a").n95, { top5: "sensor.ceny_paliv_n95_top5_a", home: "sensor.ceny_paliv_n95_home_a", area_average: "sensor.ceny_paliv_n95_area_average_a" });

  const card = new CenyPalivFuelsCard();
  card.setConfig({});
  card.hass = miniHass(states);
  assert.match(card.shadowRoot.innerHTML, /several areas/);
  card.setConfig({ config_id: "a" });
  const html = card.shadowRoot.innerHTML;
  // the usual order of fuels (Natural 95 before LPG), the cheapest price, your station, the trend
  assert.ok(html.indexOf(">N95<") < html.indexOf(">LPG<"));
  assert.match(html, /data-more-info="sensor.ceny_paliv_n95_top5_a"/);
  assert.match(html, /class="number">38\.50<\/span><span class="diff mine">mine 38\.90</);
  assert.match(html, /Levna · Hlavni/);
  assert.match(html, /mdi:arrow-down/);
  card.setConfig({ config_id: "a", fuels: ["lpg"] });
  assert.doesNotMatch(card.shadowRoot.innerHTML, />N95</);
  card.setConfig({ config_id: "gone" });
  assert.match(card.shadowRoot.innerHTML, /no longer exists/);
});

test("a full tank: the saving at the cheapest station, less the longer drive", () => {
  // 40 l, 39.10 at your station 2 km away, 38.50 at the cheapest 6 km away, 6.5 l/100 km
  const r = fillUpSaving({ mine: 39.1, cheapest: 38.5, tank: 40, consumption: 6.5, kmMine: 2, kmCheapest: 6 });
  assert.equal(Math.round(r.save * 100) / 100, 24);
  assert.equal(r.extraKm, 8); // 4 km further, there and back
  assert.equal(Math.round(r.driveCost * 100) / 100, 20.02);
  assert.equal(Math.round(r.net * 100) / 100, 3.98);
  assert.equal(fillUpSaving({ mine: 38.5, cheapest: 38.5, tank: 40, consumption: 6.5 }), null); // yours is the cheapest
  assert.equal(fillUpSaving({ mine: 39, cheapest: 38.5, tank: 40, consumption: 6.5 }).net, null); // no distances
});

test("the full-tank card says what you save, whether the drive pays off, and per kg for CNG", () => {
  const states = {
    "sensor.ceny_paliv_n95_top5_a": top5("n95", "a", 38.5),
    "sensor.ceny_paliv_n95_home_a": role("n95", "a", "home", 39.1, { distance_km: 2 }),
    "sensor.ceny_paliv_n95_area_average_a": role("n95", "a", "area_average", 39.4),
    "sensor.ceny_paliv_cng_top5_a": top5("cng", "a", 35),
    "sensor.ceny_paliv_cng_area_average_a": role("cng", "a", "area_average", 36),
  };
  const card = new CenyPalivSavingsCard();
  assert.throws(() => card.setConfig({}), /fuel/);
  card.setConfig({ fuel: "n95" });
  card.hass = miniHass(states);
  let html = card.shadowRoot.innerHTML;
  assert.match(html, /40 l fill-up/);
  assert.match(html, /<span class="label">My station<\/span>\s*<span class="delta">1,564 Kč</);
  assert.match(html, /1,540 Kč/);
  assert.match(html, /1,576 Kč/);
  assert.match(html, /At Levna you save 24 Kč/);
  assert.match(html, /8\.0 km more there and back ≈ 20 Kč · worth it: you still save 4 Kč/);

  card.setConfig({ fuel: "n95", consumption: 12 }); // a thirsty car: the drive eats the saving
  assert.match(card.shadowRoot.innerHTML, /class="status warn"[^]*not worth the drive/);

  states["sensor.ceny_paliv_n95_home_a"] = role("n95", "a", "home", 38.5);
  card.hass = miniHass({ ...states });
  assert.match(card.shadowRoot.innerHTML, /Your station is the cheapest/);

  card.setConfig({ fuel: "cng" }); // no favourite: against the average, per kilogram
  html = card.shadowRoot.innerHTML;
  assert.match(html, /40 kg fill-up/);
  assert.match(html, /At Levna 40 Kč less than at the average price/);
  assert.doesNotMatch(html, />My station</);
});

test("the small cards' editor offers the area only when there are several and saves no defaults", () => {
  const editor = new CenyPalivMiniEditor();
  editor.card = CenyPalivSavingsCard;
  editor.setConfig({ type: "custom:ceny-paliv-savings-card", fuel: "n95" });
  editor.hass = { language: "cs", states: { "sensor.ceny_paliv_n95_top5_a": top5("n95", "a", 38.5) } };
  const form = editor.children[0];
  same(form.schema.map((f) => f.name), ["fuel", "tank_litres", "consumption"]);
  assert.equal(form.computeLabel({ name: "fuel" }), "Palivo");
  form.listeners["value-changed"]({ detail: { value: { ...form.data, consumption: 7 } } });
  same(editor.lastEvent.detail.config, { type: "custom:ceny-paliv-savings-card", fuel: "n95", consumption: 7 });

  editor.hass = { language: "cs", states: { "sensor.ceny_paliv_n95_top5_a": top5("n95", "a", 38.5), "sensor.ceny_paliv_n95_top5_b": top5("n95", "b", 38) } };
  assert.equal(editor.children[0].schema[0].name, "config_id");
});

test("the comparison: your station, the area, the region and the country, and the regions ranked", () => {
  const regions = [
    { code: "CZ042", name: "Ústecký kraj", average: 39.33, rank: 1 },
    { code: "CZ020", name: "Středočeský kraj", average: 39.65, rank: 2 },
    { code: "CZ010", name: "Hlavní město Praha", average: 40.08, rank: 3 },
  ];
  const states = {
    "sensor.ceny_paliv_n95_top5_a": top5("n95", "a", 38.5, { labels: { ...LABELS_EN, compare_title: "Price comparison", compare_sub: "average prices in {unit}", compare_area: "Area", compare_region: "Region", compare_country: "Czech Republic", compare_ranks: "The {n} regions" } }),
    "sensor.ceny_paliv_n95_home_a": role("n95", "a", "home", 39.1),
    "sensor.ceny_paliv_n95_area_average_a": role("n95", "a", "area_average", 39.42),
    "sensor.ceny_paliv_n95_region_average_a": role("n95", "a", "region_average", 39.65, { region: "Středočeský kraj", region_code: "CZ020" }),
    "sensor.ceny_paliv_n95_national_average_a": role("n95", "a", "national_average", 39.65, { regions }),
  };
  const card = new CenyPalivCompareCard();
  card.setConfig({ fuel: "n95" });
  card.hass = miniHass(states);
  const html = card.shadowRoot.innerHTML;
  // four bars, the lowest (your station here) a quarter long and marked, each against the country
  assert.match(html, /bar-row mine best[^]*?My station[^]*?39\.10<span class="vs">−0\.55<[^]*?width:25\.0%/);
  assert.match(html, /Area · Brno[^]*?39\.42<span class="vs">−0\.23</);
  assert.match(html, /Region · Středočeský[^]*?39\.65<span class="vs">±0\.00</);
  assert.match(html, /Czech Republic<\/span><span class="value">39\.65<\/span>[^]*?width:100\.0%/);
  // the regions in two columns (1, 3 | 2), yours bold, with short names
  assert.match(html, /The 3 regions/);
  assert.match(html, /<span class="own"><span class="n">2\.<\/span><span class="r">Středočeský<\/span><b>39\.65<\/b>/);
  assert.match(html, /<span class="r">Praha<\/span>/);
  assert.ok(html.indexOf(">Ústecký<") < html.indexOf(">Praha<") && html.indexOf(">Praha<") < html.indexOf(">Středočeský<"));
  card.setConfig({ fuel: "n95", show_regions: false });
  assert.doesNotMatch(card.shadowRoot.innerHTML, /class="ranks"/);
});

test("the regions map: the boundaries projected, each region coloured by its price, a tap names it", async () => {
  // two made-up square regions side by side
  const geometry = { regions: [
    { code: "CZ010", name: "Praha", polygons: [[[[50, 14], [50, 15], [49, 15], [49, 14]]]] },
    { code: "CZ020", name: "Středočeský kraj", polygons: [[[[50, 15], [50, 16], [49, 16], [49, 15]]]] },
  ] };
  const shape = regionPaths(geometry, 400);
  assert.equal(shape.width, 400);
  assert.equal(shape.height, Math.ceil(400 / (2 * Math.cos(49.5 * Math.PI / 180)))); // a degree of longitude is shorter
  assert.match(shape.paths[0].d, /^M0\.0,0\.0L200\.0,0\.0L200\.0,[\d.]+L0\.0,[\d.]+Z$/);

  context.fetch = async (url) => { assert.match(url, /^\/ceny_paliv_static\/regions\.json\?v=/); return { ok: true, json: async () => geometry }; };
  const states = {
    "sensor.ceny_paliv_n95_top5_a": top5("n95", "a", 38.5, { labels: { ...LABELS_EN, regions_title: "Regions", regions_loading: "Loading the map…", rank_of: "#{rank} of {n}" } }),
    "sensor.ceny_paliv_n95_region_average_a": role("n95", "a", "region_average", 39.65, { region_code: "CZ020" }),
    "sensor.ceny_paliv_n95_national_average_a": role("n95", "a", "national_average", 39.7, { regions: [
      { code: "CZ020", name: "Středočeský kraj", average: 39.65, rank: 1 }, { code: "CZ010", name: "Praha", average: 40.08, rank: 2 },
    ] }),
  };
  const card = new CenyPalivRegionsCard();
  card.setConfig({ fuel: "n95" });
  card.hass = miniHass(states);
  assert.match(card.shadowRoot.innerHTML, /Loading the map/);
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
  const html = card.shadowRoot.innerHTML;
  assert.match(html, /class="own" [^>]*style="fill: color-mix\(in srgb, var\(--cp-bad-base\) 0%, var\(--cp-good-base\)\)/); // the cheapest, yours
  assert.match(html, /data-region="CZ010" aria-label="Praha: 40\.08 \(2\.\)"/);
  assert.match(html, /style="fill: color-mix\(in srgb, var\(--cp-bad-base\) 100%/); // the dearest
  assert.match(html, /Středočeský kraj: <b>39\.65 Kč\/l<\/b> · #1 of 2/); // your region until another is tapped
  card._pick({ composedPath: () => [{ dataset: { region: "CZ010" } }] });
  assert.match(card.shadowRoot.innerHTML, /Praha: <b>40\.08 Kč\/l<\/b> · #2 of 2/);
  assert.match(card.shadowRoot.innerHTML, /class="picked"/);
  delete context.fetch;
});

test("the stations map: the area's circle, every up-to-date station as a dot, labels for the cheapest and yours", () => {
  const [east, south] = toKm(49.1, 16.7, 49.2, 16.6);
  assert.equal(Math.round(east * 10) / 10, 7.3); // 0.1° of longitude at 49° north
  assert.equal(Math.round(south * 10) / 10, 11.1);

  const today = new Date().toISOString().slice(0, 10);
  const st = (name, price, lat, lng, rank, extra = {}) => ({ name, price, lat, lng, rank, updated_date: today, trends: {}, ...extra });
  const top = top5("n95", "a", 38.5, {
    labels: { ...LABELS_EN, map_title: "Stations", map_sub: "{n} up-to-date prices", map_center: "Centre", regions_source: "Boundaries: ČÚZK" },
    gps_area: { latitude: 49.2, longitude: 16.6, radius_km: 10, station_count: 30 }, excluded: 4, max_age_days: 1,
    stations: [st("A", 38.5, 49.21, 16.61, 1), st("B", 38.6, 49.25, 16.65, 2, { home: true })],
    gps_nearest_stations: [st("A", 38.5, 49.21, 16.61, 1), st("Near", 39.9, 49.201, 16.601, 2), { ...st("Old", 30, 49.2, 16.6, 3), updated_date: "2000-01-01" }],
  });
  const card = new CenyPalivStationsMapCard();
  assert.throws(() => card.setConfig({}), /fuel/);
  card.setConfig({ fuel: "n95" });
  card.hass = miniHass({ "sensor.ceny_paliv_n95_top5_a": top });
  const html = card.shadowRoot.innerHTML;
  assert.match(html, /3 up-to-date prices/); // A once, the outdated one left out
  assert.match(html, /<circle class="area" cx="200" cy="150" r="138\.9"><\/circle>/); // 10 km fits the 300 px height
  assert.equal((html.match(/<g class="st[ "]/g) || []).length, 3);
  assert.match(html, /<g class="st home"/); // your station ringed
  assert.match(html, /<g class="chip st" data-station="0"[^]*?>38\.50</); // the cheapest labelled
  assert.doesNotMatch(html, /<g class="chip st" data-station="2"/); // the nearest-only, dearest one is a dot only
  same(card._rows.list.map((x) => [x.name, x.rank]), [["A", 1], ["B", 2], ["Near", null]]);
  assert.equal(card._rows.fresh, 26); // ranked among the area's 26 up-to-date stations
  assert.match(html, /color-mix\(in srgb, var\(--cp-bad-base\) 100%, var\(--cp-good-base\)\)/); // "Near" is the dearest
});

test("the badge: the cheapest price, your station's or the area average, and a dash without sensors", () => {
  const states = {
    "sensor.ceny_paliv_n95_top5_a": top5("n95", "a", 38.5),
    "sensor.ceny_paliv_n95_home_a": role("n95", "a", "home", 39.1),
    "sensor.ceny_paliv_n95_area_average_a": role("n95", "a", "area_average", 39.42),
  };
  same(CenyPalivBadge.getStubConfig({ states }), { fuel: "n95" });
  const badge = new CenyPalivBadge();
  assert.throws(() => badge.setConfig({}), /fuel/);
  badge.setConfig({ fuel: "n95" });
  badge.hass = miniHass(states);
  assert.match(badge.shadowRoot.innerHTML, /class="badge cheapest" role="button" tabindex="0" data-more-info="sensor.ceny_paliv_n95_top5_a" aria-label="N95: 38\.50 Kč\/l"/);
  badge.setConfig({ fuel: "n95", price: "mine" });
  assert.match(badge.shadowRoot.innerHTML, /mdi:gas-station-in-use[^]*N95 · My station<\/span><span class="content">39\.10 Kč\/l/);
  badge.setConfig({ fuel: "n95", price: "area" });
  assert.match(badge.shadowRoot.innerHTML, /Area average<\/span><span class="content">39\.42 Kč\/l/);
  badge.hass = miniHass({});
  assert.match(badge.shadowRoot.innerHTML, /<div class="badge"><ha-icon icon="mdi:gas-station-off-outline">[^]*>—</);
  assert.doesNotMatch(badge.shadowRoot.innerHTML, /<ha-card/);

  const editor = new CenyPalivMiniEditor();
  editor.card = CenyPalivBadge;
  editor.setConfig({ type: "custom:ceny-paliv-badge", fuel: "n95" });
  editor.hass = { language: "en", states };
  const price = editor.children[0].schema.find((f) => f.name === "price");
  same(price.selector.select.options.map((o) => o.label), ["The cheapest in the area", "My station", "The area average"]);
});

test("the tile feature: what each Ceny paliv sensor says in one line, with the trend", () => {
  const labels = { ...LABELS_EN, rank_of: "#{rank} of {n}", more_than_cheapest: "+{d} vs the cheapest", cheapest_badge: "Cheapest", compare_country: "Czech Republic", vs_yesterday: "vs yesterday", not_ranked: "Not ranked" };
  const states = {
    "sensor.ceny_paliv_n95_top5_a": top5("n95", "a", 38.5, { labels }),
    "sensor.ceny_paliv_n95_home_a": role("n95", "a", "home", 39.1, { rank: 3, fresh_count: 14, vs_cheapest: 0.6, trends: { 1: { dir: "up", delta: 0.2 } } }),
    "sensor.ceny_paliv_n95_area_average_a": role("n95", "a", "area_average", 39.42, { region: "Jihomoravský kraj", vs_national: -0.23 }),
    "sensor.ceny_paliv_n95_national_average_a": role("n95", "a", "national_average", 39.65),
    "light.kitchen": { state: "on", attributes: {} },
  };
  const hass = miniHass(states);
  assert.equal(supportsPriceFeature(hass, { entity_id: "sensor.ceny_paliv_n95_top5_a" }), true);
  assert.equal(supportsPriceFeature(hass, { entity_id: "sensor.ceny_paliv_n95_national_average_a" }), false);
  assert.equal(supportsPriceFeature(hass, { entity_id: "light.kitchen" }), false);
  assert.equal(supportsPriceFeature(hass, {}), false);

  const feature = new CenyPalivPriceFeature();
  feature.setConfig({ type: "custom:ceny-paliv-price-feature" });
  feature.hass = hass;
  feature.context = { entity_id: "sensor.ceny_paliv_n95_top5_a" };
  assert.match(feature.shadowRoot.innerHTML, /class="what">Levna · Hlavni<[^]*mdi:arrow-down/);
  feature.context = { entity_id: "sensor.ceny_paliv_n95_home_a" };
  assert.match(feature.shadowRoot.innerHTML, /class="what">#3 of 14 · \+0\.60 vs the cheapest<[^]*class="change bad"[^]*mdi:arrow-up/);
  feature.context = { entity_id: "sensor.ceny_paliv_n95_area_average_a" };
  assert.match(feature.shadowRoot.innerHTML, /class="what">Jihomoravský kraj · Czech Republic −0\.23</);
  feature.context = { entity_id: "light.kitchen" };
  assert.equal(feature.shadowRoot.innerHTML, "");
});
