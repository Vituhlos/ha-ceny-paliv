const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor() {
    this.children = [];
    this.listeners = {};
    this.shadowRoot = {
      getElementById: () => ({ replaceChildren() {}, appendChild() {} }),
    };
  }
  attachShadow() { return this.shadowRoot; }
  appendChild(child) { this.children.push(child); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  dispatchEvent(event) { this.lastEvent = event; }
}

class Form extends Element {}

const source = readFileSync(
  `${__dirname}/../custom_components/ceny_paliv/frontend/ceny-paliv-card.js`,
  "utf8",
);
const context = {
  HTMLElement: Element,
  customElements: { get: () => undefined, define() {} },
  document: { createElement: () => new Form() },
  window: { customCards: [] },
  CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
  console: { info() {} },
};
vm.runInNewContext(
  `${source}\nglobalThis.testExports = { CenyPalivCard, CenyPalivCardEditor };`,
  context,
);
const { CenyPalivCard, CenyPalivCardEditor } = context.testExports;

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
