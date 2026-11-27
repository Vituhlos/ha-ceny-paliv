<p align="center"><img src="https://raw.githubusercontent.com/Vituhlos/ha-ceny-paliv/main/docs/logo.png" alt="Ceny paliv" width="420"></p>

# ⛽ Ceny paliv – ceny paliv v Home Assistantu

[English](README.md) · **Česky**

Integrace pro HACS, která v Home Assistantu ukazuje ceny paliv z [mBenzin.cz](https://www.mbenzin.cz) pro **vaše město** nebo **GPS oblast o poloměru 5–50 km**: **Natural 95, naftu, LPG, CNG** a další. Najdete v ní žebříček nejlevnějších čerpacích stanic, mapu a **vaši oblíbenou stanici** s historií cen a trendy. Všechno se nastavuje v rozhraní Home Assistantu, bez úprav souborů.

![Dashboard](docs/screenshot.webp)

> **Ceny paliv** je nezávislý projekt. Ceny pocházejí z [mBenzin.cz](https://www.mbenzin.cz); projekt nevytváří, nepodporuje ani neschvaluje mBenzin.cz.

## Co umí

- Vyberete si **město**, **jedno či více paliv** (třeba Natural 95 a LPG pro vůz na dvě paliva) a pro každé palivo **oblíbenou stanici**.
- Nebo nastavíte GPS oblast kolem polohy domácnosti Home Assistantu, **osoby nebo zařízení, které sledujete** (oblast jede s vámi), uložené zóny `zone.*`, bodu vybraného na mapě nebo (pokročile) ručně zadaných souřadnic. Poloměr je **5–50 km**, výchozí **40 km**. Poloha osoby nebo telefonu se použije, jen pokud ji zvolíte; nepoužívá se geokódovací služba ani další požadavek na mBenzin.
- Pro každé palivo **5 nejlevnějších stanic ve městě** (jen z vašeho města, nikoli z celého kraje) a **mapu s cenami**; klepnutím na stanici zobrazíte podrobnosti a **navigaci v Mapy.com, Google Maps nebo Waze**.
- U oblíbené stanice: aktuální cena, **trendy oproti 1, 2, 7, 14 a 30 dnům**, pořadí ve městě a dlouhodobá statistika (graf za 30 dní).
- **Průměrné ceny** v celé republice, ve vašem kraji a ve vaší oblasti a to, jak si vaše oblast proti nim stojí, s dlouhodobými statistikami a ze stejného stažení.
- Hotová **karta pro dashboard** (`ceny-paliv-card`) přímo v integraci – přidáte ji z nabídky karet, bez kopírování YAML – s volbou jazyka **čeština / angličtina**. Je **přizpůsobitelná**: na širokém dashboardu dva sloupce, v telefonu jeden, kompaktní verze a každou část (oblíbená stanice, seznam, mapa, graf) lze umístit jako samostatnou kartu.
- Volitelná **loga čerpacích stanic** (Orlen, MOL, Shell, Tesco…): zaškrtnete řetězce při nastavení a stáhnou se za vás. Řetězce bez loga dostanou barevný odznak s iniciálami.
- Zastaralé ceny se skrývají: u benzínu a nafty cena starší než včerejšek, u CNG starší než 3 dny, u LPG a AdBlue starší než 7 dní. Menší stanice aktualizují ceny méně často: volba **Zobrazit i starší ceny** (až 3 nebo 7 dní) je v přehledu ponechá a zobrazí u nich datum ceny.

## K čemu se hodí

- **Tankovat tam, kde je to nejlevnější**: karta ukáže pět nejlevnějších stanic ve vašem městě nebo kolem domova, s datem ceny; klepnutím na stanici se k ní necháte navigovat v Mapy.com, Google Maps nebo Waze.
- **Sledovat svou obvyklou stanici**: její cenu, pořadí ve městě, o kolik je dražší než nejlevnější a jak se cena změnila za 1–30 dní, s grafem za 30 dní.
- **Auto na dvě paliva nebo víc aut**: jedna karta na palivo (třeba Natural 95 a LPG), nebo jedna oblast na každé město, kde jezdíte.
- **Nechat si to hlásit**: upozornění do telefonu, když vaše stanice zlevní, když cena klesne pod váš limit, nebo na levnou stanici poblíž na cestě (viz [Blueprinty](#blueprinty)).
- **Venkov**: GPS kruh 5–50 km posbírá stanice několika malých obcí a volba „Zobrazit i starší ceny“ ponechá stanice, které ceny aktualizují zřídka.

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
- Stahování obstarává knihovna [aiombenzin](https://pypi.org/project/aiombenzin/) (od stejného autora), kterou Home Assistant nainstaluje spolu s integrací.
- Integrace používá data cenové mapy mBenzin, nikoli oficiálně zdokumentované API. Buďte k serveru ohleduplní a respektujte podmínky mBenzin.

## 2. Instalace přes HACS

1. V HACS otevřete menu **⋮ → Vlastní repozitáře** a přidejte `https://github.com/Vituhlos/ha-ceny-paliv` s kategorií **Integrace** (Integration).
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

### Nastavení

Vše kromě přístupového klíče se zadává při přidání integrace a dá se později změnit tlačítkem **Konfigurovat**. Přístupový klíč změníte přes **⋮ → Překonfigurovat** (anglicky Reconfigure; nebo když si o nový řekne Home Assistant).

| Volba | Kdy | Co dělá |
|---|---|---|
| Přístupový klíč | přidání, ⋮ → Překonfigurovat | Váš osobní klíč k mBenzin.cz; před uložením se ověří skutečným stažením dat. |
| Oblast vyhledávání | vždy | **Město**: stanice jednoho města. **GPS okolí**: stanice v okruhu kolem bodu. |
| Zdroj polohy | GPS okolí | Střed: poloha domácnosti v Home Assistantu, osoba nebo zařízení, které sledujete, uložená zóna, bod na mapě nebo ruční souřadnice. |
| Osoba nebo zařízení | zdroj polohy Osoba | `person.*` nebo `device_tracker.*` (např. aplikace Home Assistant v telefonu). Oblast se s ním posune, jakmile je aspoň 1 km daleko, a spočítá se z už stažených cen; bez polohy zůstane kolem domova. |
| Zóna | zdroj polohy Zóna | Zóna, jejíž střed se použije; přesun zóny vyvolá aktualizaci, smazaná zóna nechá oblast prázdnou. |
| Střed GPS oblasti | zdroj polohy Mapa | Bod vybraný na mapě. |
| Zeměpisná šířka, délka | zdroj polohy Ruční | Ve stupních (−90 až 90, −180 až 180). |
| Poloměr (km) | GPS okolí | 5–50 km, výchozí 40 km. |
| Město | Město | Jen stanice tohoto města, ne celého okolí. |
| Paliva | vždy | Jedno nebo více z Natural 95, Natural 98, Diesel, Diesel Plus, LPG, CNG, AdBlue; každé dostane vlastní senzory. |
| Jazyk textů v dashboardu | vždy | Angličtina nebo čeština pro popisky karty; názvy entit a obrazovky nastavení se řídí jazykem Home Assistantu. |
| Zobrazit i starší ceny | vždy | Započítají se ceny staré až 1 (výchozí), 3 nebo 7 dní; LPG a AdBlue vždy 7 dní, CNG 3. |
| Oblíbená stanice | pro každé palivo | Volitelná (**—** = žádná); dostane vlastní senzor s historií, trendy a pořadím. Výběr jiné stanice založí nový senzor. |
| Loga | vždy | Řetězce, jejichž loga se stáhnou z balíčku log; viz [Loga čerpacích stanic](#4-loga-čerpacích-stanic-volitelné). |

## Senzory

Pro každé palivo `<palivo>` (`n95`, `benzinplus`, `diesel`, `dieselplus`, `lpg`, `cng`, `adblue`):

| Entita | Co obsahuje |
|---|---|
| `sensor.ceny_paliv_<palivo>_top5` | cena nejlevnější stanice s dlouhodobými statistikami (`state_class: measurement`, od 0.9); atributy obsahují 5 nejlevnějších stanic. GPS režim přidává metadata `gps_area` a samostatný kompaktní seznam nejvýše 10 stanic `gps_nearest_stations` seřazených podle vzdálenosti |
| `sensor.ceny_paliv_<palivo>_home` | cena u vaší oblíbené stanice (jen pokud jste nějakou vybrali), trendy, pořadí, statistika |
| `sensor.ceny_paliv_<palivo>_1` … `_5` | 5 nejlevnějších stanic se zeměpisnou šířkou a délkou pro kartu mapy |
| `sensor.ceny_paliv_<palivo>_national_average` | průměrná cena stanic s aktuální cenou v České republice; 14 krajů v atributech |
| `sensor.ceny_paliv_<palivo>_region_average` | průměrná cena v kraji vaší oblasti |
| `sensor.ceny_paliv_<palivo>_area_average` | průměrná cena ve vaší oblasti (město nebo GPS okolí) a srovnání |
| `event.ceny_paliv_<palivo>_price_change` | události, když vaše oblíbená stanice zlevní nebo zdraží nebo když klesne nejnižší cena v oblasti |

Každá nastavená oblast je zařízení typu služba (pojmenované podle záznamu, např. `Ceny paliv Praha`) a její senzory mají pod ním přeložené názvy, např. `Ceny paliv Praha Natural 95 · 1. nejlevnější`; stanici, kterou senzor pozice nebo oblíbené stanice právě ukazuje, najdete v atributu `station`. Identifikátory stávajících senzorů se při aktualizaci ani při přepnutí oblasti nemění. Bývalá oblíbená stanice si kvůli statistikám ponechá archivovaný senzor (diagnostický, zakázaný; viz [oddíl 5](#5-bez-karty-standardní-karty)).

Všechny senzory ukazují cenu v Kč/l (CNG v Kč/kg) a nesou uvedení zdroje `Ceny: mbenzin.cz`. Karta své senzory pozná podle atributů `cp_fuel`, `cp_role` (`top5`, `home`, `position`, `home_archive`, `national_average`, `region_average`, `area_average`), `cp_index` a `cp_config_id`.

### Atributy

**`sensor.ceny_paliv_<palivo>_top5`** — stav: nejnižší cena.

| Atribut | Obsah |
|---|---|
| `stations` | 5 nejlevnějších stanic s aktuální cenou (položky níže) |
| `home` | vaše oblíbená stanice ve stejné podobě, s pořadím a srovnáním (nebo `null`) |
| `fetched_at`, `last_attempt`, `next_update` | kdy se ceny stáhly, kdy proběhla poslední aktualizace a kdy proběhne další |
| `fetch_error` | u dostupného senzoru vždy `null` (palivo, které se nenačte, má senzory nedostupné) |
| `city_name`, `city_total`, `excluded` | název oblasti; v městském režimu počet stanic města; kolik stanic vypadlo kvůli příliš staré ceně |
| `max_age_days` | jak stará smí cena být, aby se započítala (volba, nebo delší limit paliva) |
| `fuel`, `fuel_label`, `unit` | kód paliva, jeho název a jednotka |
| `gps_area` | GPS režim: způsob, střed, poloměr, zóna, chyba polohy, počet stanic v kruhu |
| `gps_nearest_stations` | GPS režim: nejvýše 10 nejbližších stanic, zkráceně (název, město, adresa, cena, souřadnice, datum, vzdálenost) |
| `language`, `labels`, `logos` | jazyk karty, její texty a stažená loga |

Každá stanice v `stations` (i v `home`) má `rank`, `name`, `title` (čitelný popis: název a ulice, a když stanice ulici nemá, obec, např. `Benzina · Karlovarská`), `chain`, `street` (adresa bez opakovaného názvu stanice; u obce bez ulic její název a číslo domu), `city` (obec bez čísla domu), `address` (adresa od mBenzinu, např. `Selbská 15/2732, Aš`), `price`, `lat`, `lng`, `updated` (vlastní údaj mBenzinu, např. `Dnes`), `updated_date`, `maps` (odkaz do Google Maps), `home` (zda je to vaše oblíbená) a `trends`; v GPS režimu navíc `distance_km`. Ulice a obec pocházejí z adresy od mBenzinu, s diakritikou; u stanice bez adresy z jejího odkazu, bez diakritiky. `trends` má klíče `1`, `2`, `7`, `14` a `30` (dny); každý je `null`, dokud neexistuje starší cena, jinak obsahuje `dir` (`up`, `down`, `flat`), `delta` (Kč), `ref_date` a `ref_price`.

**`sensor.ceny_paliv_<palivo>_home`** — stav: cena u vaší oblíbené stanice; dlouhodobé statistiky (`state_class: measurement`).

| Atribut | Obsah |
|---|---|
| `station`, `price`, `latitude`, `longitude`, `maps`, `distance_km` | čitelný popis stanice (jako `title` výše) a kde stanice je (`distance_km` v GPS režimu) |
| `updated`, `updated_date`, `age_days` | kdy stanice naposledy aktualizovala cenu |
| `rank`, `fresh_count`, `vs_cheapest`, `cheapest_name` | její pořadí mezi stanicemi s aktuální cenou, kolik jich je, o kolik je dražší než nejlevnější a která to je |
| `trends` | jako výše |
| `statistic_id` | vlastní dlouhodobé statistiky stanice, např. `ceny_paliv:n95_3fa2b1c4d5e6` (viz níže) |

**`sensor.ceny_paliv_<palivo>_1` … `_5`** — stav: cena n-té nejlevnější stanice; atributy `station` (čitelný popis), `price`, `latitude` a `longitude` pro mapu (bez souřadnic, když je to vaše oblíbená stanice, kterou kreslí senzor oblíbené stanice). Pozice bez stanice má stav `unknown`.

**Průměrné ceny** – tři senzory níže počítají jen stanice s aktuální cenou (stejný limit stáří jako přehled, včetně volby **Zobrazit i starší ceny**) a mají dlouhodobé statistiky (`state_class: measurement`). Kraj každé stanice se určí z jejích souřadnic a hranic krajů přibalených k integraci (ČÚZK, zjednodušené: stanice do zhruba 200 m od krajské hranice se může započítat do sousedního kraje).

| Senzor | Stav | Atributy |
|---|---|---|
| `_national_average` | průměr v České republice | `station_count`, `median`, `regions`: u každého kraje `code` (NUTS 3, např. `CZ010`), `name`, `average`, `station_count`, `vs_national` a `rank` (1 = nejlevnější kraj). `chains` obsahuje až 100 nejlevnějších řetězců podle nezaokrouhleného průměru, každý s `name`, `average` a `station_count`. `chain_count` je počet všech hodnocených řetězců. |
| `_region_average` | průměr v kraji vaší oblasti (kraj města, nebo středu GPS okolí); nedostupný, když je střed mimo Českou republiku | `region`, `region_code`, `station_count`, `rank`, `vs_national` |
| `_area_average` | průměr stanic ve vaší oblasti | `station_count`, `region`, `region_rank`, `vs_national` a `vs_region` (Kč; pod nulou: vaše oblast je levnější) |

Když sledovaná osoba nebo posunutá GPS oblast přejede do jiného kraje, krajský senzor pokračuje průměrem toho kraje.

**`event.ceny_paliv_<palivo>_price_change`** — entita událostí, která porovná každou aktualizaci s tou předchozí. Typy událostí:

| Typ události | Kdy |
|---|---|
| `favourite_cheaper` / `favourite_dearer` | cena u vaší oblíbené stanice klesla / stoupla (výběr jiné oblíbené stanice není změna ceny) |
| `cheapest_cheaper` | nejnižší cena v oblasti klesla (i když posunutá GPS oblast najde levnější stanici) |

Každá událost nese `fuel`, `unit`, `area`, `station`, `address`, `price`, `previous_price`, `change` (Kč), `distance_km` (v GPS režimu) a `maps`. Identifikátor entity se nemění ani při výběru jiné oblíbené stanice, takže automatizace dál fungují. Ceny při startu jsou jen výchozí bod: restart ani nepovedená aktualizace nic nehlásí.

## Jak se data aktualizují

- **Každých 6 hodin** integrace stáhne z mBenzin.cz celorepublikové ceny každého paliva (jeden požadavek na palivo), a také při přidání integrace nebo startu Home Assistantu. Oblasti se stejným klíčem každé stažení sdílejí po dobu necelých 6 hodin, takže každá plánovaná aktualizace dostane nová data a druhá oblast nestojí žádný další požadavek.
- Výběr města nebo GPS kruhu, oblíbená stanice, pořadí i trendy se počítají z tohoto stažení; změna oblasti, posun sledované osoby ani znovunačtení integrace nic dalšího nestahují. Restart Home Assistantu ho vymaže.
- Akce [`ceny_paliv.refresh`](#akce) aktualizuje hned; znovu stahuje jen data starší než 30 minut.
- **HTTP 429** (příliš mnoho požadavků): všechna paliva daného klíče počkají na hodnotu `Retry-After` od mBenzinu (nejvýše 24 hodin), bez ní necelých 6 hodin. Čekání se drží jen v paměti.
- **Když mBenzin.cz pro palivo neodpoví**, jeho senzory budou do příští úspěšné aktualizace nedostupné; výpadek i obnova se zalogují jen jednou a po 24 hodinách bez cen to ohlásí **Nastavení → Opravy**. Karta dál ukazuje poslední známé ceny s upozorněním.
- **Započítají se jen čerstvé ceny**: ve výchozím stavu dnešní a včerejší (CNG 3 dny, LPG a AdBlue 7), s volbou „Zobrazit i starší ceny“ až 3 nebo 7 dní. Relativní údaje mBenzinu („Dnes“, „Včera“) se vyhodnocují podle času stažení v českém čase.
- **Trendy**: jednou denně se ceny uloží místně (`.storage/ceny_paliv.<id záznamu>`, drží se 35 dní): v městském režimu všech stanic města, v GPS režimu pěti zobrazených a oblíbené. Trendy se počítají z tohoto záznamu.
- **Dlouhodobé statistiky podle stanice**: při každé aktualizaci se cena oblíbené stanice zapíše do dlouhodobých statistik Home Assistantu přímo pod stanici (`ceny_paliv:<palivo>_<id stanice>`, s názvem např. „Natural 95 · Benzina · Karlovarská“), spolu s až 35 dny jejího denního záznamu. Nepatří k žádnému senzoru ani oblasti: výběr jiné oblíbené stanice založí statistiky té stanice, opětovný výběr stanice naváže na její historii a odebrání a nové přidání integrace ji zachová. Graf za 30 dní v kartě ukazuje právě je; senzor oblíbené stanice má dál i své vlastní statistiky.

## 3. Karta pro dashboard (je součástí, nic dalšího se neinstaluje)

Integrace obsahuje vlastní kartu **`ceny-paliv-card`**. Po instalaci (a restartu) stačí:

1. Otevřít dashboard → **Upravit** → **Přidat kartu** → vyhledat **Ceny paliv**.
2. Vybrat **palivo** (editor nabídne paliva, která jste nastavili). Hotovo.

Nebo v YAML:

```yaml
type: custom:ceny-paliv-card
fuel: n95            # n95 | benzinplus | diesel | dieselplus | lpg | cng | adblue
```

Pro každé palivo jedna karta, nebo více paliv v jedné kartě s přepínačem nahoře (`fuels: [n95, lpg]`, třeba pro vůz na dvě paliva). Karta má čtyři části: vaši oblíbenou stanici (cena, trendy, pořadí), 5 nejlevnějších stanic, mapu a graf za 30 dní. Graf porovná vaši stanici s nejnižší cenou v oblasti (denní minimum) a s průměrem oblasti z dlouhodobých statistik Home Assistantu; najetím nebo dotykem ukáže hodnoty dne. Nejnižší cena se ukládá od 0.9 a průměr od 0.8, takže jejich čáry začínají až tehdy; bez oblíbené stanice graf ukáže jen oblast. Klepnutím na stanici z pětice zobrazíte její podrobnosti (cena, datum, pořadí, vzdálenost, trendy) a navigaci do Mapy.com, Google Maps nebo Waze; dlouhým stisknutím historii vaší oblíbené stanice. Nad seznamem stanice seřadíte podle ceny, vzdálenosti nebo podle toho, zda se **vyplatí** dojet: cena i s palivem spotřebovaným na cestu tam a zpět (2 × vzdálenost × spotřeba, rozpočítané na natankované litry), takže levná, ale vzdálená stanice prohraje s o kousek dražší za rohem. Vzdálenosti jsou vzdušnou čarou od středu GPS oblasti (ve městě od polohy domácnosti Home Assistantu); v GPS oblasti se pro tato řazení k pěti nejlevnějším přidá deset nejbližších stanic. Pokud máte pro stejné palivo více konfigurací, vyberte správnou konfiguraci ve vizuálním editoru (nebo v YAML přidejte `config_id` z atributu `cp_config_id` senzoru top5); karta bez volby konfigurace nikdy nebude míchat entity z různých oblastí. Všechny volby níže jsou i ve vizuálním editoru karty.

| Volba | Výchozí | |
|---|---|---|
| `fuel` | – | povinné (nebo `fuels`); s `fuels` palivo zobrazené jako první |
| `fuels` | – | paliva přepínače nahoře v kartě, např. `[n95, diesel]` (přepínač si nic nepamatuje: karta se otevře na `fuel`) |
| `sort` | `price` | řazení seznamu, přepínatelné i v kartě: `price` (cena), `distance` (vzdálenost) nebo `worth` (vyplatí se: cena za litr i s palivem spotřebovaným na cestu tam a zpět) |
| `tank_litres` | `40` | pro `worth`: kolik natankujete v litrech (CNG: v kg) |
| `consumption` | `6.5` | pro `worth`: spotřeba vašeho auta v l/100 km (CNG: kg/100 km) |
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

### Vygenerování dashboardu Ceny paliv

V Home Assistantu od verze 2026.5 otevřete **Nastavení → Dashboardy → Přidat dashboard** a v komunitních dashboardech zvolte **Ceny paliv**. Ve starší podporované verzi vytvořte prázdný dashboard a do editoru jeho surové konfigurace vložte:

```yaml
strategy:
  type: custom:ceny-paliv
```

Dashboard má jednu obrazovku. Při přidávání nebo konfiguraci oblasti zvolte **Nejdřív stanice**, **Nejdřív mapa** nebo **Nejdřív srovnání paliv**. Oblast, palivo i pohled pak můžete přepnout přímo na dashboardu. Dočasný pohled platí do dalšího načtení stránky. V části **Vývoj cen a srovnání** najdete historii, krajské ceny a žebříček řetězců. Spotřebu svého vozu nastavíte pod `strategy` v položce `fuel_cost` stejně jako u samostatné karty pomocí `consumption_*`. Po přidání oblasti nebo paliva dashboard načtěte znovu.

### Další karty pro dashboard

Kromě hlavní karty přináší integrace menší karty, také v nabídce karet (hledejte „Ceny paliv“). Každá ukazuje jednu oblast; máte-li jich víc, vyberte ji v editoru karty (`config_id`).

| Karta | Co ukazuje | Volby |
|---|---|---|
| `custom:ceny-paliv-fuels-card` | všechna paliva oblasti najednou: nejnižší cena a stanice, cena u vaší stanice, trend od včerejška | `fuels` (která a v jakém pořadí; výchozí všechna) |
| `custom:ceny-paliv-savings-card` | kolik stojí plná nádrž u vaší stanice, u nejlevnější a za průměrnou cenu oblasti, kolik ušetříte a zda se delší cesta k nejlevnější vyplatí | `fuel` (povinné), `tank_litres` (40; u CNG kg), `consumption` (6,5 na 100 km) |
| `custom:ceny-paliv-compare-card` | vaše stanice, oblast, váš kraj a Česko vedle sebe jako pruhy, každý proti celé republice, a 14 krajů od nejlevnějšího | `fuel` (povinné), `show_regions` (true) |
| `custom:ceny-paliv-regions-card` | mapa 14 krajů obarvená od nejlevnějšího (zelená) po nejdražší (červená), váš kraj obtažený; klepnutím na kraj jeho cena a pořadí | `fuel` (povinné) |
| `custom:ceny-paliv-areas-card` | jedno palivo ve všech vašich oblastech (domov, práce, chata…) od nejlevnější, s nejlevnější stanicí a průměrem; oblasti se jmenují podle svého zařízení | `fuel` (povinné) |
| `custom:ceny-paliv-road-card` | pro telefon v autě: nejbližší stanice GPS oblasti s aktuální cenou (nejlépe té, která jede s vámi), velkým písmem a s velkým tlačítkem navigace | `fuel` (povinné), `stations` (3), `navigator` (`google`, `mapy` nebo `waze`) |
| `custom:ceny-paliv-big-card` | jedna cena přes celou kartu pro nástěnný tablet: nejnižší, vaše nebo průměr oblasti, se stanicí a trendem; písmo roste s kartou | `fuel` (povinné), `price` (`cheapest`, `mine`, `area`) |
| `custom:ceny-paliv-changes-card` | poslední změny ceny z událostí paliva: vaše stanice zlevnila nebo zdražila, levnější stanice v oblasti, s časem a změnou; z historie Home Assistantu | `fuel` (povinné), `days` (14) |
| `custom:ceny-paliv-trend-card` | jak se za 7 a 14 dní pohnul průměr oblasti, vaše stanice a nejnižší cena oblasti, každý s malým grafem za 15 dní; z dlouhodobých statistik | `fuel` (povinné) |
| `custom:ceny-paliv-fuel-cost-card` | řadí LPG, CNG, benzín a naftu podle Kč/km z průměrné ceny oblasti × spotřeba / 100. Na každé kartě nastavte spotřebu konkrétního vozu. Paliva bez ceny se přeskočí | `consumption_n95` (6,5), `consumption_diesel` (5,5), `consumption_lpg` (8) v l/100 km, `consumption_cng` (4) v kg/100 km |
| `custom:ceny-paliv-chains-card` | celostátní průměry a počty stanic podle řetězce, od nejlevnějšího. Stanice bez údaje o řetězci se seskupují podle uvedeného názvu | `fuel` (povinné) |
| `custom:ceny-paliv-stations-map-card` | uliční mapa s cenovkami a kruhem GPS oblasti. Tažením mapu posunete, tlačítky +/− přiblížíte a klepnutím na stanici otevřete detail s navigací. Mapu vybranou klávesnicí posunou šipky, Home zobrazí celou oblast. Ukáže až 80 stanic s aktuální cenou včetně oblíbené stanice uvnitř oblasti | `fuel` (povinné), `street_map` (výchozí `true`) |

Prohlížeč načítá pro viditelnou oblast mapové dlaždice OpenStreetMap. Pokud chcete začínat na místní schematické mapě, nastavte `street_map: false`. Při nedostupnosti dlaždic se mapa přepne na schéma a dál zobrazuje ceny stanic i navigaci. Seznam stanic pochází z již stažených cen, bez dalšího požadavku na mBenzin.

```yaml
type: custom:ceny-paliv-savings-card
fuel: n95
tank_litres: 45
consumption: 7.2
```

**Odznak** do horní části dashboardu (Upravit dashboard → Přidat odznak → Ceny paliv): `custom:ceny-paliv-badge` s `fuel` a `price: cheapest` (výchozí), `mine` nebo `area` (průměr oblasti). **Prvek dlaždicové karty**: pod dlaždici se senzorem Ceny paliv přidejte prvek „Ceny paliv: price details“ (`type: custom:ceny-paliv-price-feature`); na jednom řádku ukáže, co senzor říká, s trendem od včerejška: u top5 nejlevnější stanici, u oblíbené její pořadí a o kolik je dražší, u průměru kraj a rozdíl proti republice.

```yaml
type: tile
entity: sensor.ceny_paliv_n95_home
features:
  - type: custom:ceny-paliv-price-feature
```

Cesta se započítá jen tehdy, je-li nejlevnější stanice dál než ta vaše: dvojnásobek vzdálenosti navíc (tam a zpět, vzdušnou čarou) při vaší spotřebě a nejnižší ceně.

Upozornění na změnu ceny na telefonu: viz `examples/price_alert.yaml`.

## 4. Loga čerpacích stanic (volitelné)

Karta u každé stanice ukazuje kulaté logo jejího řetězce. Bez loga nakreslí barevný odznak s iniciálami řetězce (`OR`, `PR`…), takže není třeba nic nastavovat.

Chcete-li skutečná loga, otevřete **Nastavení → Zařízení a služby → Ceny paliv → Konfigurovat**, přejděte na krok **Loga čerpacích stanic** a zaškrtněte řetězce. Stáhnou se (pár KB každé) z [balíčku log](logos/) v tomto repozitáři do složky `ceny_paliv_logos` v konfiguraci Home Assistantu a karta je najde sama. Odškrtnutím logo odstraníte. Při prvním nastavení jsou předvybrané řetězce z vašeho města. Nestahuje se nic, co nezaškrtnete, a balíček se s integrací neinstaluje.

Balíček je také ke stažení jako **`ceny-paliv-logos.zip`** u každého [vydání](https://github.com/Vituhlos/ha-ceny-paliv/releases): pokud to raději uděláte ručně, rozbalte ho do `<config>/ceny_paliv_logos/` (nové soubory se načtou po restartu nebo znovunačtení integrace). Můžete tam dát i vlastní čtvercové PNG pojmenované podle řetězce malými písmeny, bez diakritiky, s pomlčkami místo mezer (`eurobit.png`, `robin-oil.png`): takové soubory se používají a nikdy se nemažou. Chcete-li soubory z jiné složky, nastavte na kartě `logo_path: /local/logos/` (soubory pojmenované podle řetězce, např. `/local/logos/orlen.png`).

Loga jsou ochranné známky svých majitelů a slouží jen k označení stanic; projekt s nimi nijak nesouvisí. Zdroje a postup při žádosti o odstranění jsou v [logos/SOURCES.md](logos/SOURCES.md).

## 5. Bez karty: standardní karty

Každý senzor má pevný přeložený název (např. `Natural 95 · 1. nejlevnější`); čitelný popis stanice, kterou právě ukazuje (např. `Benzina · Karlovarská`), je v atributu `station` a při každé aktualizaci sleduje pořadí, identifikátory entit zůstávají stejné. Jedinou výjimkou je senzor oblíbené stanice: výběr jiné oblíbené stanice vytvoří nový senzor (např. `_home_2`), aby se nikdy nesmíchaly statistiky dvou stanic (viz Poznámky).

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

Každá stanice v `stations` má `rank`, `name`, `title`, `street`, `city`, `address`, `price`, `lat`, `lng`, `updated`, `maps`, `home` a `trends`; v GPS režimu navíc `distance_km` (viz [Atributy](#atributy)). Atribut `gps_area` senzoru top5 obsahuje způsob výběru, střed, poloměr, případnou zónu, chybu polohy a celkový počet markerů s platnými souřadnicemi v kruhu. `gps_nearest_stations` je oddělený kompaktní seznam nejvýše 10 blízkých stanic; neopakuje odkazy na mapy ani historii trendů. Text od poskytovatele se v GPS atributech omezuje, aby se celý stavový JSON vešel pod limit 16 KiB Home Assistant Recorderu. Pro oblíbenou stanici použijte senzor `_home` (obsahuje `rank`, `vs_cheapest`, `trends` a při poloze uvnitř GPS oblasti také `distance_km`).

Při změně oblíbené stanice dostane nová stanice vlastní identitu statistik. Předchozí senzor zůstane registrovaný jako archivovaná entita, aby se dlouhodobé statistiky Home Assistantu nesloučily s jinou stanicí; archivované senzory jsou diagnostické entity, které se nedostanou do automatických dashboardů, a jsou zakázané (historii zobrazíte, když entitu v jejím nastavení povolíte); opětovný výběr té stanice je znovu povolí; odebrání paliva v **Konfigurovat** odstraní jeho senzory včetně archivovaných; při návratu k dříve vybrané stanici se obnoví pouze její ověřená identita. GPS historie používá celé URL markeru a nové vzorky zapisuje jen pro aktuálních pět nejlevnějších stanic a oblíbenou stanici. Záznamy stanic, které dočasně vypadnou z první pětice, zůstávají po stávající 35denní dobu a lze na ně navázat po návratu stanice; při aktualizaci se odstraňují prošlé nebo prázdné URL záznamy. Nová městská historie je také klíčována celým URL, aby se stejný slug v různých městech nesloučil. Historie trendů z verzí do 0.4.x (klíčovaná slugem stanice) se při první aktualizaci, která zobrazuje původní město konfigurace, přesune na URL stanice, pokud má daný slug v tomto městě právě jedna stanice – trendy tak aktualizaci přežijí. Nejednoznačné staré záznamy se ke stanici nikdy nepřiřazují a po 35 dnech zaniknou. Pokud oblíbenou stanici nelze v celorepublikových datech určit jednoznačně, uložený výběr zůstane zachován, dokud výslovně nevyberete jinou stanici.

Po výslovné změně oblíbené stanice může Home Assistant nové entitě oblíbené stanice přidělit příponu, protože původní ID zůstává archivované kvůli statistikám. Karta dashboardu aktuální senzor najde automaticky; v běžných YAML kartách s přímým odkazem na původní entitu `_home` bude nutné odkaz aktualizovat na nové ID.

## Akce

### `ceny_paliv.refresh` — aktualizovat ceny hned

Načte ceny z mBenzin.cz bez čekání na další šestihodinovou aktualizaci, třeba před cestou.

| Pole | Povinné | Co dělá |
|---|---|---|
| `config_entry_id` | ne | Oblast, která se má aktualizovat (vyberete ji v editoru akce). Bez něj se aktualizují všechny oblasti. |

- Ceny stažené před méně než **30 minutami** se použijí znovu, takže časté volání mBenzin.cz nezahltí; během čekání po chybě 429 se nestahuje nic.
- Když mBenzin.cz neodpoví, ceny, které jsou ještě platné, zůstanou a akce je ohlásí jako ponechané; palivo, pro které žádné ceny nezbyly, selže a jeho senzory budou nedostupné.
- Akce skončí chybou s popisem, když oblast neexistuje nebo neběží, nebo když se některé ceny nepodařilo aktualizovat (uvede oblast a palivo).

```yaml
action: ceny_paliv.refresh
data:
  config_entry_id: 01JC0EXAMPLE  # volitelné: oblast vybraná v editoru akce
```

## Blueprinty

Hotové automatizace: naimportujte je tlačítkem (nebo **Nastavení → Automatizace a scény → Blueprinty → Importovat blueprint** s odkazem na soubor) a pak z nich vytvořte automatizaci. U každého zvolíte jazyk zprávy (čeština nebo angličtina) a co se má stát, třeba upozornění do telefonu s `{{ title }}` a `{{ message }}`; ve výchozím stavu vytvoří oznámení v Home Assistantu.

| Blueprint | Co dělá | |
|---|---|---|
| [Změna ceny oblíbené stanice](blueprints/automation/ceny_paliv/favourite_price_change.yaml) | vaše oblíbená stanice zlevnila (nebo i zdražila), aspoň o zvolenou částku; používá události změny ceny | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FVituhlos%2Fha-ceny-paliv%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fceny_paliv%2Ffavourite_price_change.yaml) |
| [Cena pod limit](blueprints/automation/ceny_paliv/price_below_limit.yaml) | cena (nejlevnější v oblasti, oblíbená stanice nebo průměr) klesla pod váš limit; jednou při každém poklesu pod něj | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FVituhlos%2Fha-ceny-paliv%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fceny_paliv%2Fprice_below_limit.yaml) |
| [Levná stanice poblíž](blueprints/automation/ceny_paliv/cheap_station_nearby.yaml) | když jste mimo domov, nejlevnější stanice GPS oblasti do vaší ceny a vzdálenosti, s pauzou mezi zprávami; nejlépe s oblastí, která jede s vámi | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FVituhlos%2Fha-ceny-paliv%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fceny_paliv%2Fcheap_station_nearby.yaml) |

## Příklady

**Upozornění, když se změní cena vaší stanice** — celá automatizace je v [`examples/price_alert.yaml`](examples/price_alert.yaml).

**Upozornění, když nejlevnější Natural 95 klesne pod 35 Kč/l:**

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.ceny_paliv_n95_top5
    below: 35
actions:
  - action: notify.mobile_app_VAS_TELEFON
    data:
      title: "⛽ Natural 95 pod 35 Kč"
      message: >-
        {% set s = state_attr('sensor.ceny_paliv_n95_top5', 'stations')[0] %}
        {{ s.title }}: {{ '%.2f' | format(s.price) }} Kč/l
```

**Upozornění, když je vaše oblíbená stanice nejlevnější:**

```yaml
triggers:
  - trigger: template
    value_template: "{{ state_attr('sensor.ceny_paliv_n95_home', 'vs_cheapest') | float(1) <= 0 }}"
actions:
  - action: notify.mobile_app_VAS_TELEFON
    data:
      message: "Vaše stanice je dnes nejlevnější: {{ states('sensor.ceny_paliv_n95_home') }} Kč/l"
```

**Čerstvé ceny před cestou** (skript; aktualizace ohlásí, co se nepodařilo, proto smí selhat):

```yaml
sequence:
  - action: ceny_paliv.refresh
    continue_on_error: true
  - action: notify.mobile_app_VAS_TELEFON
    data:
      message: >-
        Nejlevnější Diesel: {{ states('sensor.ceny_paliv_diesel_top5') }} Kč/l
        ({{ (state_attr('sensor.ceny_paliv_diesel_top5', 'stations') or [{'name': 'bez dat'}])[0].name }})
```

Místo `notify.mobile_app_VAS_TELEFON` použijte svou akci pro upozornění a místo ID entit svá (Nastavení → Entity, hledejte „Ceny paliv“).

## Přechod z 0.5

Není potřeba nic dělat: aktualizujte v HACS a restartujte Home Assistant. ID entit, historie, statistiky, nastavení
i karty v dashboardech zůstanou. Při prvním startu se stane:

- Každá oblast se stane zařízením a její senzory se přesunou pod něj; jejich názvy pocházejí z překladů (např.
  `Natural 95 · 1. nejlevnější` místo názvu stanice, který je teď v atributu `station`).
- Automatický název oblasti s více mezerami za sebou se upraví („Ceny paliv Brandys nad Labem Stara Boleslav“).
- Archivované senzory oblíbených stanic se stanou diagnostickými entitami.
- Historie cen oblíbené stanice založí statistiky stanice, doplněné o až 35 dní, které už jsou uložené.
- Senzory paliva jsou nově **nedostupné**, když mBenzin.cz neodpovídá (dřív si nechaly poslední cenu); automatizace,
  které je čtou, mohou potřebovat podmínku. Karta dál ukazuje poslední známé ceny.
- Pokud máte v HACS přidaný `donthedandy/ha-ceny-paliv`, nahraďte ho `https://github.com/Vituhlos/ha-ceny-paliv`.

## Odebrání integrace

1. **Nastavení → Zařízení a služby → Ceny paliv**, u každé nastavené oblasti **⋮ → Smazat** (anglicky Delete). Spolu s ní se smažou její senzory i uložená historie cen. Dlouhodobé statistiky vašich oblíbených stanic v Home Assistantu zůstanou (smazat je můžete v **Vývojářské nástroje → Statistiky**, hledejte `ceny_paliv`).
2. Odstraňte z dashboardů karty `custom:ceny-paliv-card`. Kartu poskytuje sama integrace, nic dalšího se neodinstalovává.
3. **HACS → Ceny paliv → ⋮ → Odebrat** (Remove) a restartujte Home Assistant.
4. Volitelně smažte složku `ceny_paliv_logos` v konfiguraci Home Assistantu: stažená loga se automaticky neodstraňují.

## Známá omezení

- **Neoficiální zdroj dat**: ceny pocházejí z cenové mapy mBenzin.cz, ne z dokumentovaného veřejného API, a je k nim potřeba osobní klíč od mBenzin.cz. mBenzin.cz nepotvrdil žádný limit požadavků.
- **Ceny jsou tak čerstvé, jak je zadají stanice**: každá stanice aktualizuje cenu na mBenzin.cz sama, malé zřídka. Starší ceny se skryjí (s volbou „Zobrazit i starší ceny“ se ukážou s datem).
- **E10** se nerozlišuje: „Natural 95“ je cena 95oktanového benzínu.
- Jen Česká republika; sedm paliv, která mBenzin.cz zveřejňuje; nejvýše **5 stanic** na palivo a oblast; GPS poloměr 5–50 km.
- Automatická aktualizace každých **6 hodin**; rychleji jen akcí pro aktualizaci, a ne častěji než jednou za 30 minut.
- Po restartu Home Assistantu během výpadku mBenzin.cz se oblast nespustí, dokud ceny nepřijdou (Home Assistant to sám zkouší znovu), a karta ukazuje hlášku „nedostupné“.
- Karta si poslední známé ceny pamatuje **v každém prohlížeči zvlášť**: jiné zařízení nebo anonymní okno během výpadku nic neukáže.
- Trendy potřebují historii: začnou den po přidání a 30denní je k dispozici po měsíci (hvězdička označuje kratší historii).
- Názvy senzorů jsou pevné (např. „Natural 95 · 1. nejlevnější“); stanice je v atributu `station`.
- Stanice, která na mBenzin.cz nemá adresu, ukazuje ulici a obec bez diakritiky (z jejího odkazu).
- Texty jen v češtině a angličtině.

## Řešení potíží

| Potíž | Co dělat |
|---|---|
| „mBenzin klíč nepřijal“ nebo výzva k **opětovnému ověření** (Reauthenticate) | Vložte celý klíč bez mezer (⋮ → Překonfigurovat). Pokud to stále nejde, zeptejte se na reklama@mbenzin.cz, zda klíč platí. |
| „dočasně omezil požadavky (HTTP 429)“ | Počkejte: integrace na mBenzin.cz počká sama. Nevolejte `ceny_paliv.refresh` ve smyčce. |
| Senzory jsou **nedostupné** | mBenzin.cz pro dané palivo neodpověděl. Vrátí se s příští úspěšnou aktualizací; po 24 hodinách **Nastavení → Opravy** vysvětlí, co ověřit. |
| V GPS oblasti **nejsou žádné stanice** | Podívejte se do **Nastavení → Opravy** (smazaná zóna, neplatná poloha); větší poloměr; „Zobrazit i starší ceny“ pro oblasti se zřídka aktualizovanými stanicemi. |
| Oblíbená stanice má **starou cenu** nebo je „mimo pořadí“ | Stanice cenu na mBenzin.cz neaktualizovala; do pořadí se vrátí, jakmile to udělá. |
| Karta chce **vybrat oblast** | Stejné palivo je nastavené ve více oblastech: oblast vyberte v editoru karty (`config_id`). |
| Karta po aktualizaci chybí nebo vypadá postaru | Obnovte stránku v prohlížeči (Ctrl+F5). |

Pro hlubší pohled: **Nastavení → Zařízení a služby → Ceny paliv → ⋮ → Povolit protokolování ladění** (anglicky Enable debug logging), zopakujte potíž a pak **Zakázat protokolování ladění** (Disable debug logging) – stáhne se protokol. Přiložte ho k [issue](https://github.com/Vituhlos/ha-ceny-paliv/issues) spolu s diagnostikou (níže). Ani jedno neobsahuje váš klíč.

## Poznámky

- **E10** mBenzin nerozlišuje: u Natural 95 jde o cenu pro všechny 95oktanové benzíny.
- Entity se jmenují `sensor.ceny_paliv_<palivo>_…`; druhá konfigurace stejného paliva má v Home Assistantu vlastní ID. Pro přiřazení karty použijte `config_id`.
- Denní záznam cen potřebný pro trendy ukládá Home Assistant a postupně se plní (hvězdička u trendu v kartě označuje trend z kratší historie).
- **Nastavení → Opravy** vás upozorní, když je potřeba váš zásah: palivo bez cen z mBenzin.cz déle než 24 hodin (ověřte web a svůj klíč), smazaná zóna nebo osoba, kolem které byla GPS oblast, nebo střed GPS oblasti bez platných souřadnic. Zpráva sama zmizí, jakmile příčina pomine.
- K hlášení problému přiložte diagnostiku: **Nastavení → Zařízení a služby → Ceny paliv → ⋮ → Stáhnout diagnostiku** (anglicky Download diagnostics). Soubor ukazuje nastavení a průběh poslední aktualizace každého paliva; přístupový klíč, střed GPS oblasti a oblíbené stanice jsou nahrazené `**REDACTED**` a seznamy stanic v něm nejsou. Obsahuje také seznam polí, která mBenzin.cz u stanice posílá, s jednou ukázkou: první stanicí celostátního seznamu, nikdy stanicí z vaší oblasti.

## Vývojářské testy

Použijte Python 3.12, nainstalujte `requirements_test.txt` a spusťte `python -m pytest`.
Testy používají simulovaná data a blokují síťové sockety; klíč mBenzin není potřeba.
CI testuje také Python 3.14 s `requirements_test_latest.txt`. Tyto soubory fixují
verzi testovacího frameworku, který následně fixuje Home Assistant na 2025.1.0,
respektive 2026.10.4. Frontend a HTTP server Home Assistantu jsou v integračních
testech simulovány.
Karta má vlastní testy bez závislostí: `node --test tests/test_card.js` (Node 22+). Prohlédnout si ji bez Home Assistantu můžete tak, že repozitář zpřístupníte (`python -m http.server 8765`) a otevřete `http://localhost:8765/tools/card-demo.html?theme=dark&lang=cs` (vymyšlená data; `theme`, `lang`, `width`, `compact`, `show`).
CI navíc spouští hassfest, validaci HACS, ruff, `mypy --strict custom_components/ceny_paliv` (s verzí Home Assistantu 2026.10) a kontrolu, že verze manifestu a karty souhlasí.

## Licence

MIT – viz [LICENSE](LICENSE).

Hranice krajů (`regions.json`) jsou odvozené z dat RÚIAN Českého úřadu zeměměřického a katastrálního (ČÚZK) pod licencí [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); zjednodušené.
