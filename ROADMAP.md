# Ceny paliv – plán

Vlastní projekt (od 13. 11. 2026 už ne příprava změn pro upstream `donthedandy/ha-ceny-paliv`).
Cíl: integrace na nejvyšší úrovni **škály kvality integrací Home Assistantu – Platinum** a k ní karta,
která vypadá a chová se jako nativní součást Home Assistantu.

## Měřítko

- Pravidla: <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules> (54 pravidel:
  Bronze 20, Silver 10, Gold 21, Platinum 3). Úroveň platí, jen když jsou splněná všechna pravidla jí i nižších.
- Stav každého pravidla je v [`custom_components/ceny_paliv/quality_scale.yaml`](custom_components/ceny_paliv/quality_scale.yaml)
  (`done` / `exempt` s důvodem / `todo`). `python script/check_quality_scale.py` vypíše dosaženou úroveň; CI
  kontroluje, že soubor obsahuje všechna pravidla.
- Oficiální odznak mají jen integrace v jádru HA – tady jde o poctivé sebehodnocení. Pravidlo je `done`, jen když
  to dokazuje kód a test.
- CI hlídá pokrytí testy alespoň 95 % (pravidlo `test-coverage`).
- Karta: vzhled podle návrhového systému HA (tokeny motivu, nativní vzory, světlý i tmavý motiv, Fluvy), ověřený
  na ukázkové stránce a pak na skutečném dashboardu; snímky ke schválení před každým vydáním.

Výchozí stav (0.5.3 + #27): Bronze 14/20, Silver 4/10, Gold 5/21, Platinum 0/3; pokrytí testy 96 %,
konfigurační průvodce 94 %.

## 0.6 – kvalitativní základ (Bronze → Gold)

- `quality_scale.yaml`, kontrola v CI, měření pokrytí, tento plán.
- Zařízení pro každou oblast; entity pojmenované přes zařízení (`has_entity_name`) a překlady názvů, ikon
  a chybových hlášek; kategorie entit; méně entit (senzory pozic vypnuté nebo pryč); odstranění zařízení,
  která po změně oblasti nebo paliv nikam nepatří.
- Diagnostika ke stažení (klíč skrytý), Opravy (Repairs) – např. dlouho nepřicházející data.
- Akce `ceny_paliv.refresh` (registrovaná v `async_setup`, chyby přes překlady) se zarážkou proti zahlcení mBenzinu;
  `PARALLEL_UPDATES`; výpadek i obnova se zalogují jen jednou; při výpadku mBenzinu se entity stanou nedostupnými
  (pravidlo `entity-unavailable`) – poslední známé ceny zůstanou v kartě jako „poslední známá data“.
- Čitelné názvy stanic („VS Petrol · Obory“), správná města, žádné opakování.
- Historie podle stanice v dlouhodobých statistikách HA – změna oblíbené stanice ani nové přidání integrace
  o historii nepřijde.
- Kratší nastavení s popisem každého pole (`data_description`); loga podle řetězců v okolí automaticky.
- Automatický přechod z 0.5.
- Repozitář: codeowner @Vituhlos, odkazy na fork, README se všemi sekcemi, které vyžadují pravidla `docs-*`.

## 0.7 – Platinum

- Knihovna **`aiombenzin`** (samostatný veřejný repozitář, PyPI): asynchronní, přebírá HTTP session od HA,
  typy (`py.typed`), testy, vydávání přes CI. Bez jakéhokoli klíče. Účet a trusted publishing na PyPI zakládá správce.
- Integrace plně staticky typovaná (`mypy --strict` v CI).

## 0.8 – chytrá data a upozornění

- Okolí jede se mnou: mimo domov se okolí posouvá podle polohy osoby (data jsou celostátní, takže bez dalších
  požadavků na mBenzin).
- Celostátní a krajské průměry, postavení okolí, dlouhodobé statistiky.
- Události a blueprinty: oblíbená stanice zlevnila, cena pod limit, levná stanice blízko na cestě.

## 0.9 – karta a dashboard

- Nová karta: více paliv s přepínačem, detail stanice (vysouvací panel s historií a navigací do Mapy.cz,
  Google Maps a Waze), vlastní graf (moje stanice proti nejlevnější v okolí), vlastní mapa s barevnými cenami
  a kruhem oblasti, řazení podle ceny / vzdálenosti / „vyplatí se dojet?“.
- Odznak s nejnižší cenou a prvky pro dlaždicovou (tile) kartu.
- Strategie, která sama vygeneruje celý dashboard „Ceny paliv“.

## 0.10 – kniha tankování a hlas

- Kniha tankování (litry, cena, km) se senzory útraty a spotřeby; „vyplatí se dojet?“ s vlastní nádrží a spotřebou.
- Assist v češtině („Kde je nejlevnější nafta?“) – nejdřív ověřit, jak spolehlivě umí vlastní integrace dodat
  české věty.

## 1.0 – závěrečný audit

- Kontrola pravidlo po pravidle: u každého `done` konkrétní kód a test, který to dokazuje.
- README s obrázky karty ve světlém i tmavém motivu; ukázková stránka a srovnání vzhledu jako nástroj v repozitáři.
- Balíček log doplněný o řetězce z okolí (VS Petrol, Petrol, Am oil, Oktan…).
