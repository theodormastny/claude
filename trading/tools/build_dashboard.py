"""Vygeneruje staticky HTML dashboard z dat portfolia.

    python trading/tools/build_dashboard.py
    python trading/tools/build_dashboard.py --data-dir ... --out .../index.html

Vystup je jeden sobestacny soubor (zadne CDN, inline CSS/JS/SVG),
funguje v light i dark rezimu. Hodi se pro GitHub Pages.
"""
from __future__ import annotations

import argparse
import html
import json
import tomllib
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_DIR / "dashboard" / "index.html"

# rozmery grafu (viewBox)
W, H = 960, 300
PAD_L, PAD_R, PAD_T, PAD_B = 64, 16, 14, 30


def _nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    if hi <= lo:
        hi = lo + 1
    span = hi - lo
    raw = span / n
    mag = 10 ** len(str(int(raw))) / 10 if raw >= 1 else 1
    step = max(round(raw / mag) * mag, mag)
    start = int(lo / step) * step
    ticks = []
    t = start
    while t <= hi + step * 0.5:
        if t >= lo - step * 0.5:
            ticks.append(t)
        t += step
    return ticks


def _fmt_usd(v: float) -> str:
    return f"${v:,.0f}" if abs(v) >= 1000 else f"${v:,.2f}"


def equity_chart_svg(snaps: list[dict], starting_cash: float) -> str:
    if len(snaps) < 2:
        return (
            '<div class="empty">Zatim malo dat pro graf - kazdy obchodni '
            "cyklus prida jeden bod.</div>"
        )
    values = [s["equity"] for s in snaps]
    lo = min(min(values), starting_cash)
    hi = max(max(values), starting_cash)
    margin = (hi - lo) * 0.08 or hi * 0.02
    lo, hi = lo - margin, hi + margin

    def x(i: int) -> float:
        return PAD_L + i * (W - PAD_L - PAD_R) / (len(values) - 1)

    def y(v: float) -> float:
        return PAD_T + (hi - v) * (H - PAD_T - PAD_B) / (hi - lo)

    grid, labels = [], []
    for t in _nice_ticks(lo, hi):
        gy = y(t)
        # popisek u samotne spodni osy by kolidoval s datumy
        if gy > H - PAD_B - 8 or gy < PAD_T:
            continue
        grid.append(
            f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W - PAD_R}" y2="{gy:.1f}" '
            f'class="grid"/>'
        )
        labels.append(
            f'<text x="{PAD_L - 8}" y="{gy + 4:.1f}" class="tick" '
            f'text-anchor="end">{_fmt_usd(t)}</text>'
        )
    # datumove popisky: max ~6
    step = max(1, len(snaps) // 6)
    for i in range(0, len(snaps), step):
        labels.append(
            f'<text x="{x(i):.1f}" y="{H - 8}" class="tick" '
            f'text-anchor="middle">{snaps[i]["ts"][:10]}</text>'
        )

    path = " ".join(
        f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}"
        for i, v in enumerate(values)
    )
    sy = y(starting_cash)
    start_line = (
        f'<line x1="{PAD_L}" y1="{sy:.1f}" x2="{W - PAD_R}" y2="{sy:.1f}" '
        f'class="startline"/>'
        f'<text x="{W - PAD_R}" y="{sy - 5:.1f}" class="tick" '
        f'text-anchor="end">start {_fmt_usd(starting_cash)}</text>'
    )
    last_x, last_y = x(len(values) - 1), y(values[-1])
    return f"""
<svg id="equity-svg" viewBox="0 0 {W} {H}" role="img"
     aria-label="Vyvoj hodnoty portfolia v case">
  {''.join(grid)}
  <line x1="{PAD_L}" y1="{H - PAD_B}" x2="{W - PAD_R}" y2="{H - PAD_B}" class="axis"/>
  {start_line}
  <path d="{path}" class="series" fill="none"/>
  <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" class="series-dot"/>
  {''.join(labels)}
  <line id="crosshair" x1="0" y1="{PAD_T}" x2="0" y2="{H - PAD_B}"
        class="crosshair" visibility="hidden"/>
  <circle id="hover-dot" r="4" class="series-dot" visibility="hidden"/>
  <rect id="hit" x="{PAD_L}" y="{PAD_T}" width="{W - PAD_L - PAD_R}"
        height="{H - PAD_T - PAD_B}" fill="transparent"/>
</svg>"""


def stat_tile(label: str, value: str, delta: str = "", delta_cls: str = "") -> str:
    delta_html = f'<div class="delta {delta_cls}">{delta}</div>' if delta else ""
    return (
        f'<div class="tile"><div class="tile-label">{label}</div>'
        f'<div class="tile-value">{value}</div>{delta_html}</div>'
    )


def build(data_dir: Path, config_path: Path, out: Path) -> None:
    cfg = tomllib.loads(config_path.read_text())
    starting_cash = cfg["portfolio"]["starting_cash"]

    def read_jsonl(name: str) -> list[dict]:
        p = data_dir / name
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

    snaps = read_jsonl("equity.jsonl")
    trades = read_jsonl("trades.jsonl")
    decisions = read_jsonl("decisions.jsonl")
    state_path = data_dir / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {
        "cash": starting_cash, "positions": {}}

    last = snaps[-1] if snaps else None
    equity = last["equity"] if last else starting_cash
    prices = last["prices"] if last else {}
    ret_pct = (equity / starting_cash - 1) * 100
    ret_cls = "good" if ret_pct >= 0 else "bad"

    tiles = "".join([
        stat_tile("Hodnota portfolia", _fmt_usd(equity),
                  f"{ret_pct:+.2f} % od startu", ret_cls),
        stat_tile("Hotovost", _fmt_usd(state["cash"])),
        stat_tile("Pocet obchodu", str(len(trades))),
        stat_tile("Posledni cyklus", last["ts"][:16].replace("T", " ") + " UTC"
                  if last else "zatim zadny"),
    ])

    # pozice
    pos_rows = []
    for sym, pos in sorted(state.get("positions", {}).items()):
        price = prices.get(sym, 0.0)
        value = pos["qty"] * price
        pnl = value - pos["cost_usd"]
        pnl_pct = (pnl / pos["cost_usd"] * 100) if pos["cost_usd"] else 0.0
        alloc = value / equity * 100 if equity else 0.0
        pnl_cls = "good" if pnl >= 0 else "bad"
        pos_rows.append(f"""<tr>
      <td class="sym">{html.escape(sym)}</td>
      <td class="num">{pos['qty']:.6f}</td>
      <td class="num">{_fmt_usd(price)}</td>
      <td class="num">{_fmt_usd(value)}</td>
      <td class="num {pnl_cls}">{pnl:+,.2f} $ ({pnl_pct:+.1f} %)</td>
      <td><div class="allocbar-track"><div class="allocbar" style="width:{alloc:.1f}%"></div></div>
          <span class="alloc-num">{alloc:.1f} %</span></td>
    </tr>""")
    cash_alloc = state["cash"] / equity * 100 if equity else 100.0
    pos_rows.append(f"""<tr>
      <td class="sym">Hotovost</td><td class="num">–</td><td class="num">–</td>
      <td class="num">{_fmt_usd(state['cash'])}</td><td class="num">–</td>
      <td><div class="allocbar-track"><div class="allocbar cash" style="width:{cash_alloc:.1f}%"></div></div>
          <span class="alloc-num">{cash_alloc:.1f} %</span></td>
    </tr>""")

    # obchody (nejnovejsi nahore, max 30)
    trade_rows = []
    for t in reversed(trades[-30:]):
        side_cls = "buy" if t["side"] == "BUY" else "sell"
        trade_rows.append(f"""<tr>
      <td class="num">{t['ts'][:16].replace('T', ' ')}</td>
      <td><span class="side {side_cls}">{t['side']}</span></td>
      <td class="sym">{html.escape(t['symbol'])}</td>
      <td class="num">{t['qty']:.6f}</td>
      <td class="num">{_fmt_usd(t['price'])}</td>
      <td class="num">{_fmt_usd(t['amount_usd'])}</td>
      <td class="reason">{html.escape(t.get('reason', ''))}</td>
    </tr>""")
    trades_html = (
        f'<table><thead><tr><th>Cas (UTC)</th><th>Smer</th><th>Symbol</th>'
        f'<th class="num-h">Mnozstvi</th><th class="num-h">Cena</th>'
        f'<th class="num-h">Objem</th><th>Duvod</th></tr></thead>'
        f'<tbody>{"".join(trade_rows)}</tbody></table>'
        if trade_rows else '<div class="empty">Zatim zadne obchody.</div>'
    )

    # posledni AI komentar
    decision_html = ""
    if decisions:
        d = decisions[-1]
        notes = "".join(f"<li>{html.escape(n)}</li>" for n in d.get("risk_notes", []))
        notes_html = (
            f'<p class="risk-title">Zasahy risk vrstvy:</p><ul>{notes}</ul>'
            if notes else ""
        )
        decision_html = f"""
  <section class="card">
    <h2>Posledni rozhodnuti AI <span class="meta">{d['ts'][:16].replace('T', ' ')} UTC
      · model {html.escape(str(d.get('model', '?')))}</span></h2>
    <p class="analysis">{html.escape(str(d.get('analysis', '')))}</p>
    {notes_html}
  </section>"""

    chart = equity_chart_svg(snaps, starting_cash)
    chart_data = json.dumps(
        [{"ts": s["ts"][:16].replace("T", " "), "equity": s["equity"]}
         for s in snaps]
    )

    page = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Paper Trading</title>
<style>
:root {{
  color-scheme: light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7;
  --series:#2a78d6; --good:#006300; --bad:#d03b3b;
  --border:rgba(11,11,11,.10);
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7;
    --muted:#898781; --grid:#2c2c2a; --axis:#383835;
    --series:#3987e5; --good:#0ca30c; --bad:#e66767;
    --border:rgba(255,255,255,.10);
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --series:#3987e5; --good:#0ca30c; --bad:#e66767;
  --border:rgba(255,255,255,.10);
}}
* {{ box-sizing:border-box; margin:0; }}
body {{
  background:var(--page); color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
  padding:24px; max-width:1060px; margin:0 auto;
}}
h1 {{ font-size:22px; margin-bottom:2px; }}
.sub {{ color:var(--ink-2); margin-bottom:20px; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:12px; margin-bottom:16px; }}
.tile {{ background:var(--surface); border:1px solid var(--border);
  border-radius:10px; padding:14px 16px; }}
.tile-label {{ font-size:12px; color:var(--muted); text-transform:uppercase;
  letter-spacing:.04em; }}
.tile-value {{ font-size:26px; font-weight:600; margin-top:2px; }}
.delta {{ font-size:13px; margin-top:2px; }}
.good {{ color:var(--good); }} .bad {{ color:var(--bad); }}
.card {{ background:var(--surface); border:1px solid var(--border);
  border-radius:10px; padding:18px 20px; margin-bottom:16px; }}
h2 {{ font-size:15px; margin-bottom:12px; }}
.meta {{ font-weight:400; font-size:12px; color:var(--muted); }}
svg {{ width:100%; height:auto; display:block; }}
.grid {{ stroke:var(--grid); stroke-width:1; }}
.axis {{ stroke:var(--axis); stroke-width:1; }}
.startline {{ stroke:var(--axis); stroke-width:1; stroke-dasharray:4 4; }}
.tick {{ font:11px system-ui,sans-serif; fill:var(--muted); }}
.series {{ stroke:var(--series); stroke-width:2; stroke-linejoin:round; }}
.series-dot {{ fill:var(--series); stroke:var(--surface); stroke-width:2; }}
.crosshair {{ stroke:var(--muted); stroke-width:1; stroke-dasharray:3 3; }}
#tooltip {{ position:fixed; pointer-events:none; background:var(--surface);
  border:1px solid var(--border); border-radius:8px; padding:6px 10px;
  font-size:12px; box-shadow:0 2px 8px rgba(0,0,0,.15); display:none; z-index:9; }}
#tooltip .tt-v {{ font-weight:600; font-variant-numeric:tabular-nums; }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
th {{ text-align:left; font-size:11px; color:var(--muted);
  text-transform:uppercase; letter-spacing:.04em; padding:6px 10px;
  border-bottom:1px solid var(--grid); }}
th.num-h {{ text-align:right; }}
td {{ padding:7px 10px; border-bottom:1px solid var(--grid); vertical-align:middle; }}
tr:last-child td {{ border-bottom:none; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
td.sym {{ font-weight:600; }}
td.reason {{ color:var(--ink-2); font-size:12.5px; }}
.side {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px;
  border:1px solid currentColor; }}
.side.buy {{ color:var(--good); }} .side.sell {{ color:var(--bad); }}
.allocbar-track {{ background:var(--grid); border-radius:4px; height:8px;
  width:120px; display:inline-block; vertical-align:middle; }}
.allocbar {{ background:var(--series); border-radius:4px; height:8px; }}
.allocbar.cash {{ background:var(--muted); }}
.alloc-num {{ font-size:12px; color:var(--ink-2); margin-left:8px;
  font-variant-numeric:tabular-nums; }}
.empty {{ color:var(--muted); padding:24px 0; text-align:center; }}
.analysis {{ color:var(--ink-2); }}
.risk-title {{ font-size:12px; color:var(--muted); margin-top:10px; }}
ul {{ margin:4px 0 0 18px; color:var(--ink-2); font-size:13px; }}
footer {{ color:var(--muted); font-size:12px; margin-top:8px; }}
</style>

<h1>AI Paper Trading</h1>
<p class="sub">Virtualni portfolio rizene AI · strategie set&nbsp;and&nbsp;forget
· {html.escape(', '.join(cfg['strategy']['symbols']))}</p>

<div class="tiles">{tiles}</div>

<section class="card">
  <h2>Vyvoj hodnoty portfolia (USD)</h2>
  {chart}
</section>
{decision_html}
<section class="card">
  <h2>Pozice a alokace</h2>
  <table><thead><tr><th>Aktivum</th><th class="num-h">Mnozstvi</th>
    <th class="num-h">Cena</th><th class="num-h">Hodnota</th>
    <th class="num-h">Nerealizovany P/L</th><th>Alokace</th></tr></thead>
  <tbody>{''.join(pos_rows)}</tbody></table>
</section>

<section class="card">
  <h2>Obchody <span class="meta">poslednich {min(len(trades), 30)}
    z {len(trades)}</span></h2>
  {trades_html}
</section>

<footer>Paper trading – zadne realne penize. Generovano automaticky
po kazdem obchodnim cyklu.</footer>
<div id="tooltip"></div>

<script>
(function () {{
  var data = {chart_data};
  var svg = document.getElementById("equity-svg");
  if (!svg || data.length < 2) return;
  var hit = document.getElementById("hit"),
      cross = document.getElementById("crosshair"),
      dot = document.getElementById("hover-dot"),
      tip = document.getElementById("tooltip");
  var PL = {PAD_L}, PR = {PAD_R}, PT = {PAD_T}, PB = {PAD_B},
      W = {W}, H = {H};
  var vals = data.map(function (d) {{ return d.equity; }});
  var sc = {starting_cash};
  var lo = Math.min(Math.min.apply(null, vals), sc),
      hi = Math.max(Math.max.apply(null, vals), sc);
  var m = (hi - lo) * 0.08 || hi * 0.02; lo -= m; hi += m;
  function xi(i) {{ return PL + i * (W - PL - PR) / (data.length - 1); }}
  function yv(v) {{ return PT + (hi - v) * (H - PT - PB) / (hi - lo); }}
  function fmt(v) {{ return "$" + v.toLocaleString("en-US",
    {{maximumFractionDigits: 0}}); }}
  hit.addEventListener("mousemove", function (ev) {{
    var pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
    var p = pt.matrixTransform(svg.getScreenCTM().inverse());
    var i = Math.round((p.x - PL) / ((W - PL - PR) / (data.length - 1)));
    i = Math.max(0, Math.min(data.length - 1, i));
    var cx = xi(i), cy = yv(data[i].equity);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx);
    cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", cx); dot.setAttribute("cy", cy);
    dot.setAttribute("visibility", "visible");
    tip.style.display = "block";
    tip.innerHTML = data[i].ts + " UTC<br><span class='tt-v'>" +
      fmt(data[i].equity) + "</span>";
    tip.style.left = (ev.clientX + 14) + "px";
    tip.style.top = (ev.clientY - 10) + "px";
  }});
  hit.addEventListener("mouseleave", function () {{
    cross.setAttribute("visibility", "hidden");
    dot.setAttribute("visibility", "hidden");
    tip.style.display = "none";
  }});
}})();
</script>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("<!doctype html>\n<html lang=\"cs\">\n" + page + "</html>\n")
    print(f"Dashboard: {out} ({out.stat().st_size} B)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_DIR / "data")
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "config.toml")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.data_dir, args.config, args.out)


if __name__ == "__main__":
    main()
