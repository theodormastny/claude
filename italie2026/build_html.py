#!/usr/bin/env python3
"""Vygeneruje prohlížecí stránku se všemi body — filtrování podle dne, kategorie a textu.

Navazuje na vizuální styl cestovního hubu Itálie 2026 (stejné barvy i písma),
aby to vypadalo jako jeho další stránka. Data bere ze stejných souborů jako build_kmz.py.
"""

import html
import os
from collections import Counter

from build_kmz import CATEGORIES, DATA, REGIONS, parse_file, validate

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out", "mista.html")

# Odstíny odpovídají barvám špendlíků v maps.me, ale posazené tak,
# aby malý puntík zůstal čitelný na krémovém i tmavém podkladu.
SWATCH = {
    "vyhlidka":      "#D6453C",
    "architektura":  "#7A5AA8",
    "hidden":        "#C9538A",
    "priroda":       "#3E8E4E",
    "voda":          "#2C7DBF",
    "dobrodruzstvi": "#E07B2A",
    "jidlo":         "#C0921A",
    "prakticke":     "#8A6A4F",
}

PIN = {
    "vyhlidka": "červený", "architektura": "fialový", "hidden": "růžový",
    "priroda": "zelený", "voda": "modrý", "dobrodruzstvi": "oranžový",
    "jidlo": "žlutý", "prakticke": "hnědý",
}

CSS = """
:root {
  --bg: #FBFAF6; --surface: #FFFFFF; --surface-2: #F2F0E8;
  --ink: #22302E; --muted: #6D7A76; --line: #E2DFD4;
  --accent: #0E7466; --accent-soft: #E0EFEB;
  --ochre: #B97F14;
  --shadow: 0 1px 2px rgba(34,48,46,.06), 0 6px 18px rgba(34,48,46,.05);
  --chip-bg: #FFFFFF;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #131D1B; --surface: #1B2725; --surface-2: #223030;
    --ink: #E9EFEA; --muted: #93A29D; --line: #2C3B38;
    --accent: #4CC3AE; --accent-soft: #1D3531;
    --ochre: #E4B04A;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 6px 18px rgba(0,0,0,.25);
    --chip-bg: #1B2725;
  }
}
:root[data-theme="dark"] {
  --bg: #131D1B; --surface: #1B2725; --surface-2: #223030;
  --ink: #E9EFEA; --muted: #93A29D; --line: #2C3B38;
  --accent: #4CC3AE; --accent-soft: #1D3531;
  --ochre: #E4B04A;
  --shadow: 0 1px 2px rgba(0,0,0,.3), 0 6px 18px rgba(0,0,0,.25);
  --chip-bg: #1B2725;
}

* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  line-height: 1.55; -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1080px; margin: 0 auto; padding: 30px 18px 80px; }

.eyebrow {
  font-size: .72rem; letter-spacing: .14em; text-transform: uppercase;
  color: var(--accent); font-weight: 700; margin: 0 0 6px;
}
h1 {
  font-family: "Iowan Old Style", "Palatino Nova", Palatino, Georgia, serif;
  font-size: clamp(2rem, 7vw, 2.7rem); line-height: 1.08; margin: 0 0 8px;
  text-wrap: balance; font-weight: 600;
}
.sub { color: var(--muted); margin: 0 0 4px; font-size: .95rem; max-width: 62ch; }
.route { color: var(--muted); margin: 0 0 24px; font-size: .85rem; }

.toolbar {
  position: sticky; top: 0; z-index: 20;
  background: var(--bg); border-bottom: 1px solid var(--line);
  padding: 12px 0 12px; margin-bottom: 22px;
  display: flex; flex-direction: column; gap: 10px;
}
.filter-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.filter-label {
  font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted); font-weight: 700; margin-right: 4px; flex-basis: 100%;
}
.chip {
  font: inherit; font-size: .82rem; cursor: pointer;
  background: var(--chip-bg); color: var(--ink);
  border: 1px solid var(--line); border-radius: 999px;
  padding: 5px 11px; display: inline-flex; align-items: center; gap: 6px;
  transition: border-color .12s, background .12s;
}
.chip:hover { border-color: var(--accent); }
.chip[aria-pressed="true"] { background: var(--accent-soft); border-color: var(--accent); font-weight: 600; }
.chip .dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
.chip .n { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .76rem; }
.chip[aria-pressed="true"] .n { color: var(--accent); }
.chip-star[aria-pressed="true"] { background: var(--ochre); border-color: var(--ochre); color: #fff; }
:root[data-theme="dark"] .chip-star[aria-pressed="true"],
:root:not([data-theme="light"]) .chip-star[aria-pressed="true"] { color: #22302E; }

.search {
  font: inherit; font-size: .9rem; width: 100%; max-width: 340px;
  padding: 8px 12px; border-radius: 10px;
  border: 1px solid var(--line); background: var(--surface); color: var(--ink);
}
.search::placeholder { color: var(--muted); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.count { font-size: .8rem; color: var(--muted); font-variant-numeric: tabular-nums; }

.day { margin-bottom: 34px; }
.day-head {
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
  border-bottom: 2px solid var(--ink); padding-bottom: 6px; margin-bottom: 14px;
}
.day-head h2 {
  font-family: "Iowan Old Style", Palatino, Georgia, serif;
  font-size: 1.35rem; font-weight: 600; margin: 0;
}
.day-head .where { color: var(--muted); font-size: .88rem; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.card {
  background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
  box-shadow: var(--shadow); padding: 14px 15px 13px;
  display: flex; flex-direction: column; gap: 7px;
}
.card.top { border-left: 3px solid var(--ochre); }
.card h3 {
  margin: 0; font-size: 1rem; font-weight: 650; line-height: 1.3;
  display: flex; align-items: baseline; gap: 7px;
}
.card h3 .dot { width: 9px; height: 9px; border-radius: 50%; flex: none; transform: translateY(-1px); }
.star { color: var(--ochre); }
.card p { margin: 0; font-size: .875rem; color: var(--ink); }
.meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: .74rem; color: var(--muted); margin-top: auto; padding-top: 4px; }
.meta a { color: var(--accent); text-decoration: none; font-weight: 600; }
.meta a:hover { text-decoration: underline; }

.legend { background: var(--surface-2); border-radius: 12px; padding: 14px 16px; margin-bottom: 24px; }
.legend h2 { font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin: 0 0 9px; }
.legend ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 5px 14px; }
.legend li { display: flex; align-items: baseline; gap: 8px; font-size: .82rem; }
.legend .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; transform: translateY(1px); }
.legend .pin { color: var(--muted); white-space: nowrap; }

.empty { color: var(--muted); font-size: .9rem; padding: 30px 0; display: none; }
.day[hidden], .card[hidden] { display: none; }

footer { margin-top: 40px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); font-size: .8rem; }
footer p { margin: 0 0 6px; max-width: 68ch; }
"""

JS = """
const cards = Array.from(document.querySelectorAll('.card'));
const days = Array.from(document.querySelectorAll('.day'));
const search = document.getElementById('search');
const counter = document.getElementById('count');
const empty = document.getElementById('empty');
const state = { days: new Set(), cats: new Set(), top: false, q: '' };

function apply() {
  let shown = 0;
  for (const c of cards) {
    const okDay = !state.days.size || state.days.has(c.dataset.day);
    const okCat = !state.cats.size || state.cats.has(c.dataset.cat);
    const okTop = !state.top || c.dataset.top === '1';
    const okQ = !state.q || c.dataset.search.includes(state.q);
    const show = okDay && okCat && okTop && okQ;
    c.hidden = !show;
    if (show) shown++;
  }
  for (const d of days) d.hidden = !d.querySelector('.card:not([hidden])');
  counter.textContent = shown === cards.length
    ? cards.length + ' míst'
    : shown + ' z ' + cards.length + ' míst';
  empty.style.display = shown ? 'none' : 'block';
}

function toggle(btn, set, key) {
  const on = btn.getAttribute('aria-pressed') === 'true';
  btn.setAttribute('aria-pressed', String(!on));
  if (on) set.delete(key); else set.add(key);
  apply();
}

document.querySelectorAll('.chip-day').forEach(b =>
  b.addEventListener('click', () => toggle(b, state.days, b.dataset.day)));
document.querySelectorAll('.chip-cat').forEach(b =>
  b.addEventListener('click', () => toggle(b, state.cats, b.dataset.cat)));

const starBtn = document.getElementById('only-top');
starBtn.addEventListener('click', () => {
  state.top = starBtn.getAttribute('aria-pressed') !== 'true';
  starBtn.setAttribute('aria-pressed', String(state.top));
  apply();
});

search.addEventListener('input', () => {
  state.q = search.value.trim().toLowerCase();
  apply();
});

document.getElementById('reset').addEventListener('click', () => {
  state.days.clear(); state.cats.clear(); state.top = false; state.q = '';
  search.value = '';
  document.querySelectorAll('[aria-pressed]').forEach(b => b.setAttribute('aria-pressed', 'false'));
  apply();
});

apply();
"""


def norm(s):
    """Naivní odstranění diakritiky, ať hledání funguje i bez háčků."""
    table = str.maketrans(
        "áäčďéěëíĺľňóôöŕřšťúůüýžÁÄČĎÉĚËÍĹĽŇÓÔÖŔŘŠŤÚŮÜÝŽ",
        "aacdeeeillnooorrstuuuyzAACDEEEILLNOOORRSTUUUYZ")
    return s.translate(table).lower()


def main():
    points = []
    for f in sorted(x for x in os.listdir(DATA) if x.endswith(".txt")):
        points += parse_file(os.path.join(DATA, f))
    points, _ = validate(points)

    day_order = {d: i for i, (_, d, _) in enumerate(REGIONS)}
    cat_order = {c: i for i, c in enumerate(
        ["vyhlidka", "hidden", "dobrodruzstvi", "voda", "architektura",
         "priroda", "jidlo", "prakticke"])}
    points.sort(key=lambda p: (day_order.get(p["day"], 99),
                               0 if p["top"] else 1,
                               cat_order.get(p["cat"], 99),
                               p["name"]))

    per_day = Counter(p["day"] for p in points)
    per_cat = Counter(p["cat"] for p in points)
    cities_by_day = {}
    for p in points:
        cities_by_day.setdefault(p["day"], [])
        if p["city"] and p["city"] not in cities_by_day[p["day"]]:
            cities_by_day[p["day"]].append(p["city"])

    out = []
    out.append('<div class="wrap">')
    out.append('<p class="eyebrow">Itálie 2026 · mapa míst</p>')
    out.append("<h1>Co stojí za to vidět</h1>")
    out.append(
        f'<p class="sub">{len(points)} míst na trase, vybraných spíš pro to, jak vypadají, '
        "než pro to, jak jsou slavná. Hvězdička značí ty, kvůli kterým se vyplatí "
        "přeskládat den. Stejná data jsou i v souborech pro maps.me.</p>")
    out.append('<p class="route">Praha → Treviso → Benátky → Florencie → Pisa → '
               "La Spezia → Cinque Terre → Milán · 10.–16. srpna 2026</p>")

    # legenda barev
    out.append('<div class="legend"><h2>Barvy špendlíků v maps.me</h2><ul>')
    for cat, (_, label) in CATEGORIES.items():
        if per_cat.get(cat):
            out.append(f'<li><span class="dot" style="background:{SWATCH[cat]}"></span>'
                       f'<span>{html.escape(label)} '
                       f'<span class="pin">· {PIN[cat]}</span></span></li>')
    out.append("</ul></div>")

    # filtry
    out.append('<div class="toolbar">')
    out.append('<div class="filter-row"><span class="filter-label">Den</span>')
    for _, day, _ in REGIONS:
        if per_day.get(day):
            out.append(f'<button class="chip chip-day" type="button" aria-pressed="false" '
                       f'data-day="{html.escape(day)}">{html.escape(day)} '
                       f'<span class="n">{per_day[day]}</span></button>')
    out.append("</div>")
    out.append('<div class="filter-row"><span class="filter-label">Kategorie</span>')
    for cat, (_, label) in CATEGORIES.items():
        if per_cat.get(cat):
            out.append(f'<button class="chip chip-cat" type="button" aria-pressed="false" '
                       f'data-cat="{cat}"><span class="dot" style="background:{SWATCH[cat]}"></span>'
                       f'{html.escape(label)} <span class="n">{per_cat[cat]}</span></button>')
    out.append("</div>")
    out.append('<div class="filter-row">'
               '<input id="search" class="search" type="search" '
               'placeholder="Hledat v názvech i popisech…" aria-label="Hledat">'
               '<button id="only-top" class="chip chip-star" type="button" aria-pressed="false">'
               f'★ jen top <span class="n">{sum(1 for p in points if p["top"])}</span></button>'
               '<button id="reset" class="chip" type="button">Zrušit filtry</button>'
               '<span class="count" id="count"></span></div>')
    out.append("</div>")

    # body po dnech
    for _, day, _ in REGIONS:
        group = [p for p in points if p["day"] == day]
        if not group:
            continue
        where = ", ".join(cities_by_day.get(day, [])[:6])
        out.append('<section class="day">')
        out.append(f'<div class="day-head"><h2>{html.escape(day)}</h2>'
                   f'<span class="where">{html.escape(where)}</span></div>')
        out.append('<div class="grid">')
        for p in group:
            label = CATEGORIES[p["cat"]][1]
            blob = norm(p["name"] + " " + p["desc"] + " " + p["city"] + " " + label)
            gmaps = f'https://www.google.com/maps/search/?api=1&query={p["lat"]:.5f},{p["lon"]:.5f}'
            star = '<span class="star">★</span> ' if p["top"] else ""
            top_class = " top" if p["top"] else ""
            out.append(
                f'<article class="card{top_class}" '
                f'data-day="{html.escape(day)}" data-cat="{p["cat"]}" '
                f'data-top="{"1" if p["top"] else "0"}" '
                f'data-search="{html.escape(blob, quote=True)}">'
                f'<h3><span class="dot" style="background:{SWATCH[p["cat"]]}"></span>'
                f'<span>{star}{html.escape(p["name"])}</span></h3>'
                f'<p>{html.escape(p["desc"])}</p>'
                f'<div class="meta"><span>{html.escape(p["city"])} · {html.escape(label)}</span>'
                f'<a href="{gmaps}" target="_blank" rel="noopener">mapa ↗</a></div>'
                "</article>")
        out.append("</div></section>")

    out.append('<p class="empty" id="empty">Nic neodpovídá filtrům.</p>')
    out.append(
        "<footer><p>Otevírací doby a ceny jsou z rešerše, ne z rezervačního systému — "
        "u placených vstupů a věcí s povinnou rezervací si to potvrďte na oficiálním webu. "
        "Místa označená v popisu jako šedá zóna mají důvod uvedený přímo u sebe.</p>"
        "<p>Odkaz „mapa“ otevře souřadnici v Mapách Google, kdybyste chtěli ověřit polohu.</p>"
        "</footer>")
    out.append("</div>")

    page = (f"<title>Itálie 2026 · co stojí za to vidět</title>\n"
            f"<style>{CSS}</style>\n" + "\n".join(out) + f"\n<script>{JS}</script>\n")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"→ {os.path.relpath(OUT, ROOT)}  ({len(points)} bodů, {len(page)//1024} kB)")


if __name__ == "__main__":
    main()
