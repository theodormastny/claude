#!/usr/bin/env python3
"""Sestaví KMZ soubory pro maps.me / Organic Maps z blokových datových souborů.

Vstup:  data/*.txt  — bloky oddělené řádkem '---', klíče NAME/LAT/LON/CITY/CAT/TOP/DESC
Výstup: out/Italie2026_TOP.kmz, out/Italie2026_ZBYTEK.kmz, out/Italie2026_VSE.kmz
"""

import html
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")

# Držíme se osmi klasických barev MAPS.ME — ty umí každá verze appky i Organic Maps.
CATEGORIES = {
    "vyhlidka":     ("red",    "Vyhlídka & foto"),
    "architektura": ("purple", "Architektura & umění"),
    "hidden":       ("pink",   "Hidden gem"),
    "priroda":      ("green",  "Příroda & stezky"),
    "voda":         ("blue",   "Voda & koupání"),
    "dobrodruzstvi":("orange", "Dobrodružství"),
    "jidlo":        ("yellow", "Jídlo & pití"),
    "prakticke":    ("brown",  "Praktické"),
}

# jemnější kategorie od agentů sloučíme do osmi barevných kbelíků
ALIASES = {
    "foto": "vyhlidka", "vyhled": "vyhlidka", "view": "vyhlidka",
    "umeni": "architektura", "umění": "architektura", "kostel": "architektura",
    "bar": "jidlo", "kavarna": "jidlo", "jídlo": "jidlo", "gelato": "jidlo",
    "priroda": "priroda", "park": "priroda", "trek": "priroda",
    "koupani": "voda", "plaz": "voda", "more": "voda",
    "adrenalin": "dobrodruzstvi", "dobrodruzství": "dobrodruzstvi",
    "kuriozita": "hidden", "tajne": "hidden",
    "praktické": "prakticke", "doprava": "prakticke", "nakup": "prakticke",
}

# kdy jsou v jakém městě + hrubý bounding box pro kontrolu souřadnic
REGIONS = [
    (("treviso",),                                    "Po 10. 8.",            (45.60, 45.75, 12.15, 12.35)),
    (("mestre", "marghera"),                          "Po 10. 8. večer",      (45.44, 45.53, 12.18, 12.30)),
    (("benátky", "benatky", "venezia", "venice", "lido", "murano", "burano",
      "torcello", "giudecca", "sant'erasmo", "santerasmo", "poveglia",
      "san michele", "certosa", "vignole", "pellestrina", "malamocco",
      "san servolo", "san lazzaro"),                  "Út 11. 8.",            (45.20, 45.53, 12.20, 12.60)),
    (("florencie", "firenze", "florence", "fiesole", "settignano",
      "bagno a ripoli", "signa", "sieci", "compiobbi"),
                                                      "St 12. – Pá 14. 8.",   (43.68, 43.87, 11.05, 11.42)),
    (("pisa",),                                       "Pá 14. 8. 11:11–13:20",(43.68, 43.76, 10.34, 10.44)),
    (("la spezia", "portovenere", "porto venere", "lerici", "palmaria",
      "tellaro", "fiascherino", "campiglia", "biassa", "san terenzo"),
                                                      "Pá 14. 8. odpoledne",  (44.02, 44.16, 9.72, 9.95)),
    (("riomaggiore", "manarola", "corniglia", "vernazza", "monterosso",
      "volastra", "groppo", "cinque terre", "levanto", "montenero",
      "soviore", "reggio", "san bernardino"),         "So 15. 8. + noc",      (44.05, 44.22, 9.62, 9.82)),
    (("milán", "milan", "milano", "malpensa"),        "Ne 16. 8. ráno",       (45.40, 45.68, 8.68, 9.32)),
]


def region_for(city):
    key = (city or "").strip().lower()
    for names, day, box in REGIONS:
        for n in names:
            if n in key:
                return day, box
    return None, None


def parse_file(path):
    raw = open(path, encoding="utf-8").read()
    points = []
    for chunk in re.split(r"^\s*---\s*$", raw, flags=re.M):
        if "NAME:" not in chunk or "LAT:" not in chunk:
            continue
        rec = {}
        key = None
        for line in chunk.splitlines():
            m = re.match(r"^\s*(NAME|LAT|LON|COORD_CONF|CITY|CAT|TOP|DESC)\s*:\s*(.*)$", line)
            if m:
                key = m.group(1)
                rec[key] = m.group(2).strip()
            elif key == "DESC" and line.strip():
                rec["DESC"] = (rec.get("DESC", "") + " " + line.strip()).strip()
        try:
            rec["lat"] = float(rec["LAT"])
            rec["lon"] = float(rec["LON"])
        except (KeyError, ValueError):
            print(f"  ! přeskočeno (chybná souřadnice): {rec.get('NAME')!r} v {os.path.basename(path)}")
            continue
        rec["name"] = rec.get("NAME", "").strip()
        rec["city"] = rec.get("CITY", "").strip()
        cat = rec.get("CAT", "hidden").strip().lower().split(",")[0].strip()
        cat = ALIASES.get(cat, cat)
        rec["cat"] = cat if cat in CATEGORIES else "hidden"
        rec["cat_raw"] = rec.get("CAT", "").strip().lower()
        rec["top"] = rec.get("TOP", "no").strip().lower().startswith("y")
        rec["desc"] = rec.get("DESC", "").strip()
        rec["src"] = os.path.basename(path)
        if rec["name"]:
            points.append(rec)
    return points


def validate(points):
    """Vyhodí body mimo očekávaný region a duplicity."""
    ok, dropped = [], []
    for p in points:
        day, box = region_for(p["city"])
        p["day"] = day or ""
        if box:
            lo_lat, hi_lat, lo_lon, hi_lon = box
            if not (lo_lat <= p["lat"] <= hi_lat and lo_lon <= p["lon"] <= hi_lon):
                dropped.append((p, f"souřadnice mimo region {p['city']}"))
                continue
        ok.append(p)

    # Duplicitou je jen shodný název. Body, které jen sdílejí souřadnici s něčím
    # jiným (jeden roh, dvě různá místa), rozestrčíme o ~15 m, ať se piny nepřekrývají.
    by_name = {}
    uniq = []
    for p in ok:
        key = re.sub(r"[^a-z0-9]+", "", p["name"].lower())[:24]
        prev = by_name.get(key)
        if prev is not None:
            if (p["top"], len(p["desc"])) > (prev["top"], len(prev["desc"])):
                uniq[uniq.index(prev)] = p
                by_name[key] = p
                dropped.append((prev, f"duplicita s „{p['name']}“"))
            else:
                dropped.append((p, f"duplicita s „{prev['name']}“"))
            continue
        by_name[key] = p
        uniq.append(p)

    taken = {}
    for p in uniq:
        pos = (round(p["lat"], 5), round(p["lon"], 5))
        n = taken.get(pos, 0)
        if n:
            # spirálovité rozestrčení: ~15 m na krok
            p["lat"] += 0.00013 * ((n + 1) // 2) * (1 if n % 2 else -1)
            p["lon"] += 0.00018 * (n // 2) * (1 if n % 2 else -1)
        taken[pos] = n + 1
    return uniq, dropped


def sort_points(points):
    order = {c: i for i, c in enumerate(
        ["vyhlidka", "hidden", "dobrodruzstvi", "voda", "architektura",
         "priroda", "jidlo", "prakticke"])}
    daykey = {d: i for i, (_, d, _) in enumerate(REGIONS)}
    return sorted(points, key=lambda q: (daykey.get(q["day"], 99),
                                         order.get(q["cat"], 99),
                                         q["name"]))


def describe(p):
    head = " · ".join(x for x in [p["day"], p["city"], CATEGORIES[p["cat"]][1]] if x)
    return f"{head}\n\n{p['desc']}" if head else p["desc"]


def kml(doc_name, points):
    """KML v dialektu, který exportuje sám MAPS.ME.

    Jeho parser je ruční a citlivý: chce starý jmenný prostor earth.google.com,
    definice všech stylů předem a popis jako obyčejný escapovaný text — CDATA
    a novější schéma OGC mu import tiše shodí.
    """
    styles = "\n".join(
        f'  <Style id="placemark-{color}">\n'
        f'    <IconStyle>\n'
        f'      <Icon>\n'
        f'        <href>http://mapswith.me/placemarks/placemark-{color}.png</href>\n'
        f'      </Icon>\n'
        f'    </IconStyle>\n'
        f'  </Style>'
        for color in ["red", "blue", "purple", "yellow",
                      "pink", "brown", "green", "orange"]
    )

    marks = []
    for p in sort_points(points):
        color = CATEGORIES[p["cat"]][0]
        name = ("★ " if p["top"] else "") + p["name"]
        marks.append(
            "  <Placemark>\n"
            f"    <name>{html.escape(name)}</name>\n"
            f"    <description>{html.escape(describe(p))}</description>\n"
            f"    <TimeStamp><when>2026-08-10T08:00:00Z</when></TimeStamp>\n"
            f"    <styleUrl>#placemark-{color}</styleUrl>\n"
            f"    <Point><coordinates>{p['lon']:.6f},{p['lat']:.6f}</coordinates></Point>\n"
            "  </Placemark>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://earth.google.com/kml/2.2">\n'
        '<Document>\n'
        f'  <name>{html.escape(doc_name)}</name>\n'
        '  <visibility>1</visibility>\n'
        + styles + "\n"
        + "\n".join(marks) + "\n"
        '</Document>\n'
        '</kml>\n'
    )


def gpx(doc_name, points):
    """Záložní formát. Barvy v něm nepřežijí, ale importuje ho úplně každá appka."""
    wpts = []
    for p in sort_points(points):
        name = ("★ " if p["top"] else "") + p["name"]
        wpts.append(
            f'  <wpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}">\n'
            f"    <name>{html.escape(name)}</name>\n"
            f"    <desc>{html.escape(describe(p))}</desc>\n"
            "  </wpt>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="Italie2026" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"  <metadata><name>{html.escape(doc_name)}</name></metadata>\n"
        + "\n".join(wpts) + "\n"
        "</gpx>\n"
    )


def write_all(path, doc_name, points):
    """Uloží stejný seznam jako .kmz, .kml i .gpx — ať je co zkusit, když appka vzdoruje."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc = kml(doc_name, points)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", doc)
    with open(path[:-4] + ".kml", "w", encoding="utf-8") as f:
        f.write(doc)
    with open(path[:-4] + ".gpx", "w", encoding="utf-8") as f:
        f.write(gpx(doc_name, points))
    print(f"  → {os.path.relpath(path, ROOT)[:-4]}.{{kmz,kml,gpx}}  ({len(points)} bodů)")


def main():
    files = sorted(f for f in os.listdir(DATA) if f.endswith(".txt"))
    if not files:
        sys.exit("V data/ nejsou žádné .txt soubory.")

    points = []
    for f in files:
        got = parse_file(os.path.join(DATA, f))
        print(f"{f}: {len(got)} bodů")
        points += got

    points, dropped = validate(points)
    if dropped:
        print(f"\nVyřazeno {len(dropped)} bodů:")
        for p, why in dropped:
            print(f"  - {p['name']} ({p['city']}): {why}")

    top = [p for p in points if p["top"]]
    rest = [p for p in points if not p["top"]]

    print(f"\nCelkem {len(points)} bodů · TOP {len(top)} · zbytek {len(rest)}")
    per_day = Counter(p["day"] or "?" for p in points)
    for _, day, _ in REGIONS:
        if per_day.get(day):
            n_top = sum(1 for p in top if p["day"] == day)
            print(f"  {day:24s} {per_day[day]:3d} bodů (z toho {n_top} TOP)")
    per_cat = Counter(p["cat"] for p in points)
    print("  " + " · ".join(f"{CATEGORIES[c][1]} {n}" for c, n in per_cat.most_common()))

    write_all(os.path.join(OUT, "Italie2026_TOP.kmz"), "Itálie 2026 ★ TOP", top)
    write_all(os.path.join(OUT, "Italie2026_ZBYTEK.kmz"), "Itálie 2026 · zbytek", rest)
    write_all(os.path.join(OUT, "Italie2026_VSE.kmz"), "Itálie 2026 · vše", points)
    # Tři body na ověření, že import v appce vůbec funguje, než se řeší velký soubor.
    write_all(os.path.join(OUT, "TEST_3body.kmz"), "TEST 3 body", top[:3])
    return points


if __name__ == "__main__":
    main()
