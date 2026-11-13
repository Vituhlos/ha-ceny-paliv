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
