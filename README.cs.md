<p align="center"><img src="https://raw.githubusercontent.com/donthedandy/ha-ceny-paliv/main/docs/logo.png" alt="Ceny paliv" width="420"></p>

# ⛽ Ceny paliv – ceny paliv v Home Assistantu

[English](README.md) · **Česky**

Integrace pro HACS, která v Home Assistantu ukazuje ceny paliv z [mBenzin.cz](https://www.mbenzin.cz) pro **vaše město** nebo **GPS oblast o poloměru 5–50 km**: **Natural 95, naftu, LPG, CNG** a další. Najdete v ní žebříček nejlevnějších čerpacích stanic, mapu a **vaši oblíbenou stanici** s historií cen a trendy. Všechno se nastavuje v rozhraní Home Assistantu, bez úprav souborů.

![Dashboard](docs/screenshot.webp)

> **Ceny paliv** je nezávislý projekt. Ceny pocházejí z [mBenzin.cz](https://www.mbenzin.cz); projekt nevytváří, nepodporuje ani neschvaluje mBenzin.cz.

## Co umí

- Vyberete si **město**, **jedno či více paliv** (třeba Natural 95 a LPG pro vůz na dvě paliva) a pro každé palivo **oblíbenou stanici**.
- Nebo nastavíte GPS oblast kolem polohy domácnosti Home Assistantu, uložené zóny `zone.*`, bodu vybraného na mapě nebo (pokročile) ručně zadaných souřadnic. Poloměr je **5–50 km**, výchozí **40 km**. Nepoužívá se poloha telefonu, GPS tracker, geokódovací služba ani další požadavek na mBenzin.
- Pro každé palivo **5 nejlevnějších stanic ve městě** (jen z vašeho města, nikoli z celého kraje), odkaz na Google Maps a **mapu s cenami**.
- U oblíbené stanice: aktuální cena, **trendy oproti 1, 2, 7, 14 a 30 dnům**, pořadí ve městě a dlouhodobá statistika (graf za 30 dní).
- Hotová **karta pro dashboard** (`ceny-paliv-card`) přímo v integraci – přidáte ji z nabídky karet, bez kopírování YAML – s volbou jazyka **čeština / angličtina**. Je **přizpůsobitelná**: na širokém dashboardu dva sloupce, v telefonu jeden, kompaktní verze a každou část (oblíbená stanice, seznam, mapa, graf) lze umístit jako samostatnou kartu.
- Volitelná **loga čerpacích stanic** (Orlen, MOL, Shell, Tesco…): zaškrtnete řetězce při nastavení a stáhnou se za vás. Řetězce bez loga dostanou barevný odznak s iniciálami.
- Zastaralé ceny se skrývají: u benzínu a nafty cena starší než včerejšek, u CNG starší než 3 dny, u LPG a AdBlue starší než 7 dní.

## 1. Získání přístupového klíče (zdarma)

mBenzin před automatickým stahováním dat chrání ověřením prohlížeče, ale uživatelům Home Assistantu **zdarma vystavuje osobní přístupový klíč**.

1. Napište na **reklama@mbenzin.cz**.
2. Uveďte, že ceny budete používat v Home Assistantu, **pro které město nebo stanice** a **jak často** je budete načítat (stačí napsat např. „4× denně“).
3. Klíč vám přijde e-mailem a funguje okamžitě. (Mně odpověděli rychle.)

Co je dobré vědět:

- Klíč je **osobní** – nikomu ho nesdílejte a nikam ho nezveřejňujte. **Každý si žádá vlastní.**
- mBenzin.cz požaduje, aby u cen byl viditelně uveden zdroj **„Ceny: mbenzin.cz“** (na webu jako odkaz). Karta ho zobrazuje pod seznamem (nebo pod vaší stanicí, je-li zobrazena samostatně) a každý senzor ho nese v atributu `attribution`; pokud si skládáte vlastní karty, uveďte ho i v nich.
- Klíč změníte v menu integrace ⋮ → **Překonfigurovat**. Pokud ho mBenzin.cz přestane přijímat (HTTP 401/403 nebo jeho HTML stránka s odmítnutím ve dvou aktualizacích po sobě), Home Assistant nabídne **Opětovné ověření**. Nastavení, historie cen i senzory přitom zůstanou zachovány.
- Poskytovatel zatím nepotvrdil limit požadavků pro tuto integraci. Automatická aktualizace zůstává každých **6 hodin** a požadavky se stejným klíčem a palivem se sdílejí mezi konfiguracemi. Toto sdílení a dočasná prodleva po HTTP 429 nejsou kvótou požadavků na klíč; trvalá kvóta se nevynucuje. Tu lze zavést až s potvrzeným limitem od poskytovatele a perzistentním počítáním požadavků. Po HTTP 429 se pozastaví všechna paliva daného klíče do času z platné hlavičky `Retry-After` (nejvýše 24 hodin), případně na necelých 6 hodin, pokud ji poskytovatel neposlal; restart Home Assistantu tuto paměťovou ochranu vymaže.
- Klíč se odesílá v HTTP hlavičce, nikoli v URL požadavku.
- Integrace používá data cenové mapy mBenzin, nikoli oficiálně zdokumentované API. Buďte k serveru ohleduplní a respektujte podmínky mBenzin.

## 2. Instalace přes HACS

1. V HACS otevřete menu **⋮ → Vlastní repozitáře** a přidejte `https://github.com/donthedandy/ha-ceny-paliv` s kategorií **Integrace** (Integration).
2. Vyhledejte **Ceny paliv**, stáhněte ho a **restartujte** Home Assistant.
3. Otevřete **Nastavení → Zařízení a služby → Přidat integraci → Ceny paliv** a postupně zadejte:
   1. **přístupový klíč**,
   2. **Město** (původní režim) nebo **GPS okolí**,
   3. v GPS režimu zvolit polohu domácnosti, uloženou zónu, bod na vestavěné mapě nebo pokročilé ruční souřadnice a poloměr 5–50 km (výchozí 40 km),
   4. v městském režimu vybrat **město**, následně **paliva** a **jazyk** textů v dashboardu,
   5. pro každé palivo vybrat **oblíbenou stanici** (městský režim nabízí stanice města, GPS režim přednostně nabízí stanice ve zvoleném kruhu a zachová již uloženou oblíbenou stanici mimo něj),
   6. volitelně zaškrtnout **loga** řetězců (řetězce ve vybrané oblasti jsou předvybrané; viz [Loga čerpacích stanic](#4-loga-čerpacích-stanic-volitelné)).

Režim oblasti, zdroj a bod polohy, poloměr, paliva, jazyk, oblíbené stanice i loga můžete později změnit tlačítkem **Konfigurovat** u integrace. Starší konfigurace bez volby oblasti zůstávají v městském režimu. Domácí souřadnice se znovu načtou při aktualizaci; změna zóny vyvolá okamžitou aktualizaci. Po odstranění zóny budou výsledky GPS prázdné, dokud ji neobnovíte nebo nevyberete jiný způsob.

> Texty samotného nastavení se řídí jazykem Home Assistantu (čeština i angličtina jsou k dispozici). Volba jazyka v kroku „Paliva a jazyk“ určuje jen popisky v kartě pro dashboard.

## Senzory

Pro každé palivo `<palivo>` (`n95`, `benzinplus`, `diesel`, `dieselplus`, `lpg`, `cng`, `adblue`):

| Entita | Co obsahuje |
|---|---|
| `sensor.ceny_paliv_<palivo>_top5` | cena nejlevnější stanice; atributy obsahují 5 nejlevnějších stanic. GPS režim přidává metadata `gps_area` a samostatný kompaktní seznam nejvýše 10 stanic `gps_nearest_stations` seřazených podle vzdálenosti |
| `sensor.ceny_paliv_<palivo>_home` | cena u vaší oblíbené stanice (jen pokud jste nějakou vybrali), trendy, pořadí, statistika |
| `sensor.ceny_paliv_<palivo>_1` … `_5` | 5 nejlevnějších stanic se zeměpisnou šířkou a délkou pro kartu mapy |

Senzory se jmenují podle stanice, kterou právě ukazují (např. `1 · Orlen – Bratri Stefanu 69`). Identifikátory stávajících senzorů se při přepnutí oblasti nemění. Ceny se obnovují každých 6 hodin. Pokud se aktualizace nepovede (třeba kvůli chybě 429), zůstanou zachována poslední data a atribut `fetch_error` uvede důvod. Celorepubliková data se sdílejí mezi konfiguracemi se stejným klíčem a palivem po dobu necelých 6 hodin, takže každá plánovaná aktualizace stáhne čerstvá data. GPS výpočty i výběr oblíbené stanice v kruhu používají tutéž cache; změna oblasti nevytváří další požadavek na mBenzin. Ruční aktualizace i znovunačtení integrace cache využívají; restart Home Assistantu ji vymaže. Relativní údaj o aktuálnosti se vyhodnocuje podle původního času odpovědi v českém časovém pásmu.

## 3. Karta pro dashboard (je součástí, nic dalšího se neinstaluje)

Integrace obsahuje vlastní kartu **`ceny-paliv-card`**. Po instalaci (a restartu) stačí:

1. Otevřít dashboard → **Upravit** → **Přidat kartu** → vyhledat **Ceny paliv**.
2. Vybrat **palivo** (editor nabídne paliva, která jste nastavili). Hotovo.

Nebo v YAML:

```yaml
type: custom:ceny-paliv-card
fuel: n95            # n95 | benzinplus | diesel | dieselplus | lpg | cng | adblue
```

Pro každé palivo jedna karta: pro vůz na dvě paliva přidejte druhou kartu s `fuel: lpg`. Karta má čtyři části: vaši oblíbenou stanici (cena, trendy, pořadí), 5 nejlevnějších stanic (klepnutím se otevře Google Maps), mapu a graf za 30 dní. Pokud máte pro stejné palivo více konfigurací, vyberte správnou konfiguraci ve vizuálním editoru (nebo v YAML přidejte `config_id` z atributu `cp_config_id` senzoru top5); karta bez volby konfigurace nikdy nebude míchat entity z různých oblastí. Všechny volby níže jsou i ve vizuálním editoru karty.

| Volba | Výchozí | |
|---|---|---|
| `fuel` | – | povinné |
| `config_id` | automaticky, je-li jednoznačné | při více konfiguracích stejného paliva vybere jednu oblast |
| `show` | `[home, list, map, graph]` | které části zobrazit: `home` (oblíbená stanice), `list` (nejlevnější stanice), `map`, `graph` (30 dní) |
| `layout` | `auto` | `auto`: dva sloupce (stanice a seznam vlevo, mapa a graf vpravo), je-li karta široká, a jeden sloupec, je-li úzká, třeba v telefonu; `columns`: vždy dva; `stack`: vždy jeden |
| `stations` | `5` | kolik stanic v seznamu (1–5, i na mapě) |
| `compact` | `false` | úsporná verze: jeden řádek na stanici, trendy na jednom řádku, bez legendy |
| `show_footer` | `true` (`false` při `compact`) | časy aktualizace a legenda pod seznamem |
| `map_height` | automaticky | výška mapy v pixelech |
| `logo_path` | – | jen pokud chcete vlastní PNG místo balíčku log (viz níže) |

Texty karty odpovídají jazyku zvolenému při nastavení. Pokud se karta po aktualizaci nezobrazí, obnovte stránku v prohlížeči (Ctrl+F5).

### Části si rozmístěte, kam chcete

Pomocí více karet s volbou `show` umístíte každou část kamkoli na dashboard, i s jinými kartami mezi nimi:

```yaml
type: custom:ceny-paliv-card
fuel: n95
show: [home]          # jen moje stanice
---
type: custom:ceny-paliv-card
fuel: n95
show: [list]
stations: 3
compact: true         # malá dlaždice se 3 nejlevnějšími stanicemi
---
type: custom:ceny-paliv-card
fuel: n95
show: [map, graph]
map_height: 260
```

(Jsou to tři samostatné karty; `---` je tu jen odděluje.) V dashboardu typu *sekce* si karta velikost přizpůsobí obsahu.

Upozornění na změnu ceny na telefonu: viz `examples/price_alert.yaml`.

## 4. Loga čerpacích stanic (volitelné)

Karta u každé stanice ukazuje kulaté logo jejího řetězce. Bez loga nakreslí barevný odznak s iniciálami řetězce (`OR`, `PR`…), takže není třeba nic nastavovat.

Chcete-li skutečná loga, otevřete **Nastavení → Zařízení a služby → Ceny paliv → Konfigurovat**, přejděte na krok **Loga čerpacích stanic** a zaškrtněte řetězce. Stáhnou se (pár KB každé) z [balíčku log](logos/) v tomto repozitáři do složky `ceny_paliv_logos` v konfiguraci Home Assistantu a karta je najde sama. Odškrtnutím logo odstraníte. Při prvním nastavení jsou předvybrané řetězce z vašeho města. Nestahuje se nic, co nezaškrtnete, a balíček se s integrací neinstaluje.

Balíček je také ke stažení jako **`ceny-paliv-logos.zip`** u každého [vydání](https://github.com/donthedandy/ha-ceny-paliv/releases): pokud to raději uděláte ručně, rozbalte ho do `<config>/ceny_paliv_logos/` (nové soubory se načtou po restartu nebo znovunačtení integrace). Můžete tam dát i vlastní čtvercové PNG pojmenované podle řetězce malými písmeny, bez diakritiky, s pomlčkami místo mezer (`eurobit.png`, `robin-oil.png`): takové soubory se používají a nikdy se nemažou. Chcete-li soubory z jiné složky, nastavte na kartě `logo_path: /local/logos/` (soubory pojmenované podle řetězce, např. `/local/logos/orlen.png`).

Loga jsou ochranné známky svých majitelů a slouží jen k označení stanic; projekt s nimi nijak nesouvisí. Zdroje a postup při žádosti o odstranění jsou v [logos/SOURCES.md](logos/SOURCES.md).

## 5. Bez karty: standardní karty

Každý senzor se jmenuje podle toho, co právě ukazuje (např. `1 · Orlen – Bratri Stefanu 69`), takže stanici zobrazí jakákoli standardní karta, bez šablony. Názvy sledují pořadí a mění se při každé aktualizaci; identifikátory entit zůstávají stejné. Jedinou výjimkou je senzor oblíbené stanice: výběr jiné oblíbené stanice vytvoří nový senzor (např. `_home_2`), aby se nikdy nesmíchaly statistiky dvou stanic (viz Poznámky).

Karta **Entity** s 5 nejlevnějšími stanicemi (stav senzoru je cena):

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

Karta **Markdown** s adresou a odkazem na Google Maps:

```yaml
type: markdown
title: Natural 95 – top 5
content: |-
  {% for s in (state_attr('sensor.ceny_paliv_n95_top5', 'stations') or []) %}
  {{ s.rank }}. **{{ s.name }}** – {{ s.street }}: **{{ '%.2f' | format(s.price) }} Kč/l** · [Maps]({{ s.maps }})
  {% endfor %}
```

Každá stanice v `stations` má `rank`, `name`, `street`, `address`, `price`, `lat`, `lng`, `updated`, `maps`, `home` a `trends`; v GPS režimu navíc `distance_km`. Atribut `gps_area` senzoru top5 obsahuje způsob výběru, střed, poloměr, případnou zónu, chybu polohy a celkový počet markerů s platnými souřadnicemi v kruhu. `gps_nearest_stations` je oddělený kompaktní seznam nejvýše 10 blízkých stanic; neopakuje odkazy na mapy ani historii trendů. Text od poskytovatele se v GPS atributech omezuje, aby se celý stavový JSON vešel pod limit 16 KiB Home Assistant Recorderu. Pro oblíbenou stanici použijte senzor `_home` (obsahuje `rank`, `vs_cheapest`, `trends` a při poloze uvnitř GPS oblasti také `distance_km`).

Při změně oblíbené stanice dostane nová stanice vlastní identitu statistik. Předchozí senzor zůstane registrovaný jako archivovaná entita, aby se dlouhodobé statistiky Home Assistantu nesloučily s jinou stanicí; nově archivované senzory jsou zakázané (historii zobrazíte, když entitu v jejím nastavení povolíte) a opětovný výběr té stanice je znovu povolí; při návratu k dříve vybrané stanici se obnoví pouze její ověřená identita. GPS historie používá celé URL markeru a nové vzorky zapisuje jen pro aktuálních pět nejlevnějších stanic a oblíbenou stanici. Záznamy stanic, které dočasně vypadnou z první pětice, zůstávají po stávající 35denní dobu a lze na ně navázat po návratu stanice; při aktualizaci se odstraňují prošlé nebo prázdné URL záznamy. Nová městská historie je také klíčována celým URL, aby se stejný slug v různých městech nesloučil. Historie trendů z verzí do 0.4.x (klíčovaná slugem stanice) se při první aktualizaci, která zobrazuje původní město konfigurace, přesune na URL stanice, pokud má daný slug v tomto městě právě jedna stanice – trendy tak aktualizaci přežijí. Nejednoznačné staré záznamy se ke stanici nikdy nepřiřazují a po 35 dnech zaniknou. Pokud oblíbenou stanici nelze v celorepublikových datech určit jednoznačně, uložený výběr zůstane zachován, dokud výslovně nevyberete jinou stanici.

Po výslovné změně oblíbené stanice může Home Assistant nové entitě oblíbené stanice přidělit příponu, protože původní ID zůstává archivované kvůli statistikám. Karta dashboardu aktuální senzor najde automaticky; v běžných YAML kartách s přímým odkazem na původní entitu `_home` bude nutné odkaz aktualizovat na nové ID.

## Poznámky

- **E10** mBenzin nerozlišuje: u Natural 95 jde o cenu pro všechny 95oktanové benzíny.
- Entity se jmenují `sensor.ceny_paliv_<palivo>_…`; druhá konfigurace stejného paliva má v Home Assistantu vlastní ID. Pro přiřazení karty použijte `config_id`.
- Denní záznam cen potřebný pro trendy ukládá Home Assistant a postupně se plní (hvězdička u trendu v kartě označuje trend z kratší historie).

## Vývojářské testy

Použijte Python 3.12, nainstalujte `requirements_test.txt` a spusťte `python -m pytest`.
Testy používají simulovaná data a blokují síťové sockety; klíč mBenzin není potřeba.
CI testuje také Python 3.14 s `requirements_test_latest.txt`. Tyto soubory fixují
verzi testovacího frameworku, který následně fixuje Home Assistant na 2025.1.0,
respektive 2026.10.4. Frontend a HTTP server Home Assistantu jsou v integračních
testech simulovány.
Karta má vlastní testy bez závislostí: `node --test tests/test_card.js` (Node 22+).
CI navíc spouští hassfest, validaci HACS, ruff a kontrolu, že verze manifestu a karty souhlasí.

## Licence

MIT – viz [LICENSE](LICENSE).
