# Itálie 2026 — body do maps.me

381 míst pro cestu Praha → Treviso → Benátky → Florencie → Pisa → La Spezia → Cinque Terre → Milán
(10.–16. srpna 2026). Ke každému bodu je český popis: proč tam jít, kdy, kolik to stojí a co si ohlídat.

## Soubory

Hotové mapy jsou v `out/`. Každý seznam je ve třech formátech — `.kml`, `.kmz` a `.gpx`.
Maps.me umí všechny tři, ale ne vždycky stejně spolehlivě: začni `.kml`.

| Soubor | Co obsahuje |
|---|---|
| `Italie2026_TOP.kmz` | 113 nejlepších bodů, v názvu s hvězdičkou ★ |
| `Italie2026_ZBYTEK.kmz` | 268 zbývajících bodů |
| `Italie2026_VSE.kmz` | všech 381 bodů v jednom seznamu |

Naimportuj buď TOP + ZBYTEK (dva seznamy, dají se v appce zvlášť zapínat a vypínat),
nebo jen VSE, když chceš všechno pohromadě. Vedle každého `.kmz` leží i rozbalené `.kml`
pro případ, že by appka zazipovanou verzi nevzala.

## Import do maps.me

Otevři soubor přímo v telefonu (z e-mailu, Souborů nebo Disku) a zvol otevřít v maps.me —
appka body naimportuje jako novou záložkovou kolekci. Funguje stejně i v Organic Maps.
Nejdřív si stáhni offline mapy Benátska, Toskánska a Ligurie, ať to jede bez dat.

## Barvy podle kategorie

Držíme se osmi klasických barev MAPS.ME, které načte každá verze appky:

| Barva | Kategorie |
|---|---|
| 🔴 červená | vyhlídka a foto spot |
| 🟣 fialová | architektura a umění |
| 🩷 růžová | hidden gem, kuriozita |
| 🟢 zelená | příroda a stezky |
| 🔵 modrá | voda a koupání |
| 🟠 oranžová | dobrodružství |
| 🟡 žlutá | jídlo a pití |
| 🟤 hnědá | praktické (úschovny, zastávky, supermarkety, WC) |

V popisu každého bodu je navíc na prvním řádku den, město a přesnější kategorie.

## Přegenerování

Body jsou v `data/*.txt` jako textové bloky oddělené `---`. Po úpravě spusť:

```
python3 build_kmz.py
```

Skript ověří, že souřadnice leží v očekávaném regionu, vyhodí duplicitní názvy,
rozestrčí body sdílející stejnou souřadnici a poskládá všechny tři KMZ.

## Na co si dát pozor

- Otevírací doby a ceny jsou z rešerše, ne z rezervačního systému — u placených vstupů
  a věcí s povinnou rezervací (Scala Contarini, Torre dell'Orologio, Via dell'Amore,
  Torre San Niccolò, La Specola) si to potvrď na oficiálním webu.
- Souřadnice s nízkou jistotou jsou v datech označené `COORD_CONF: low` — u nich ověř
  polohu v mapě na místě.
- Body označené jako šedá zóna (opuštěné pevnosti, spaní na pláži, Poveglia, Guvano)
  mají důvod uvedený přímo v popisu. Čti ho dřív, než tam vyrazíš.
