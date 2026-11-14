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
  `${source}\nglobalThis.testExports = { CenyPalivCard, CenyPalivCardEditor, editorDefaults, withLastKnown };`,
  context,
);
const { CenyPalivCard, CenyPalivCardEditor, editorDefaults, withLastKnown } = context.testExports;

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
  const row = { dataset: { maps: "https://www.google.com/maps/search/?api=1&query=50.1,14.4" } };
  const card = { _ids: { top5: "t", home: null }, _entityId: CenyPalivCard.prototype._entityId };
  const event = { clientX: 0, clientY: 0, composedPath: () => [row] };
  CenyPalivCard.prototype._down.call(card, event);
  const timer = card._timer;
  CenyPalivCard.prototype._move.call(card, { clientX: 3, clientY: 2 });
  assert.equal(cleared.includes(timer), false); // a small wobble keeps the press
  CenyPalivCard.prototype._move.call(card, { clientX: 40, clientY: 0 });
  assert.equal(cleared.includes(timer), true);

  card._click = CenyPalivCard.prototype._click;
  CenyPalivCard.prototype._key.call(card, { key: "Enter", preventDefault() {}, composedPath: () => [row] });
  assert.equal(context.window.opened.at(-1), row.dataset.maps);
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
    { name: "VS Petrol", address: "VS Petrol", street: "", city: "Obory", price: 38.9, updated_date: today, trends: {} },
    { name: "Petrol", address: "Petrol Prazska 310", street: "Prazska 310", city: "Neveklov", price: 39, updated_date: today, trends: {} },
  ];
  const rows = card._listHtml();
  assert.match(rows, /Dnes<\/span> · Obory/);
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
