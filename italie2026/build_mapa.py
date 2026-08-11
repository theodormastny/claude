#!/usr/bin/env python3
"""Vygeneruje jeden samostatný HTML soubor s mapou, filtry a hledáním — pro mobil.

Soubor je celý offline-samonosný (žádné externí skripty ani styly), jen mapové
dlaždice se tahají z OpenStreetMap, takže bez signálu zůstane funkční seznam
i hledání, jen podklad mapy bude prázdný.
"""

import html
import json
import os
from collections import Counter

from build_kmz import CATEGORIES, DATA, REGIONS, parse_file, validate

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out", "mapa.html")

SWATCH = {
    "vyhlidka": "#D6453C", "architektura": "#7A5AA8", "hidden": "#C9538A",
    "priroda": "#3E8E4E", "voda": "#2C7DBF", "dobrodruzstvi": "#E07B2A",
    "jidlo": "#C0921A", "prakticke": "#8A6A4F",
}

CONF_NOTE = {
    "high": "",
    "med": "Poloha je přibližná — v Apple Maps si ji potvrď podle názvu.",
    "low": "Poloha je jen orientační. Otevři to podle názvu, souřadnici neber jako přesnou.",
}


def norm(s):
    table = str.maketrans(
        "áäčďéěëíĺľňóôöŕřšťúůüýžÁÄČĎÉĚËÍĹĽŇÓÔÖŔŘŠŤÚŮÜÝŽ",
        "aacdeeeillnooorrstuuuyzAACDEEEILLNOOORRSTUUUYZ")
    return s.translate(table).lower()


CSS = r"""
:root{
  --bg:#FBFAF6; --surface:#FFF; --surface-2:#F2F0E8;
  --ink:#22302E; --muted:#6D7A76; --line:#E2DFD4;
  --accent:#0E7466; --accent-soft:#E0EFEB; --ochre:#B97F14;
  --shadow:0 1px 2px rgba(34,48,46,.07),0 4px 14px rgba(34,48,46,.06);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#131D1B; --surface:#1B2725; --surface-2:#223030;
    --ink:#E9EFEA; --muted:#93A29D; --line:#2C3B38;
    --accent:#4CC3AE; --accent-soft:#1D3531; --ochre:#E4B04A;
    --shadow:0 1px 2px rgba(0,0,0,.35),0 4px 14px rgba(0,0,0,.3);
  }
}
:root[data-theme="dark"]{
  --bg:#131D1B; --surface:#1B2725; --surface-2:#223030;
  --ink:#E9EFEA; --muted:#93A29D; --line:#2C3B38;
  --accent:#4CC3AE; --accent-soft:#1D3531; --ochre:#E4B04A;
  --shadow:0 1px 2px rgba(0,0,0,.35),0 4px 14px rgba(0,0,0,.3);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;padding:0}
body{
  background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  line-height:1.5;-webkit-font-smoothing:antialiased;
  font-size:16px;
}
.pad{padding:0 12px}

header{padding:14px 12px 8px}
.eyebrow{font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700;margin:0 0 3px}
h1{font-family:"Iowan Old Style",Palatino,Georgia,serif;font-size:1.5rem;margin:0 0 3px;font-weight:600}
.tagline{margin:0;font-size:.8rem;color:var(--muted)}

/* ---------- filtry ---------- */
.filters{position:sticky;top:0;z-index:40;background:var(--bg);padding:8px 0 8px;border-bottom:1px solid var(--line)}
.srow{display:flex;gap:6px;padding:0 12px 6px;align-items:center}
.search{
  flex:1;min-width:0;font:inherit;font-size:.92rem;padding:9px 12px;
  border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);
}
.search::placeholder{color:var(--muted)}
.scroller{display:flex;gap:6px;overflow-x:auto;padding:0 12px 2px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.scroller::-webkit-scrollbar{display:none}
.chip{
  flex:none;font:inherit;font-size:.8rem;cursor:pointer;white-space:nowrap;
  background:var(--surface);color:var(--ink);border:1px solid var(--line);
  border-radius:999px;padding:6px 11px;display:inline-flex;align-items:center;gap:5px;
}
.chip .dot{width:8px;height:8px;border-radius:50%;flex:none}
.chip .n{color:var(--muted);font-size:.74rem;font-variant-numeric:tabular-nums}
.chip[aria-pressed="true"]{background:var(--accent-soft);border-color:var(--accent);font-weight:600}
.chip[aria-pressed="true"] .n{color:var(--accent)}
.chip-star[aria-pressed="true"]{background:var(--ochre);border-color:var(--ochre);color:#fff}
.chip-star[aria-pressed="true"] .n{color:rgba(255,255,255,.8)}
.bar2{display:flex;gap:8px;align-items:center;padding:6px 12px 0;font-size:.76rem;color:var(--muted)}
.bar2 button{font:inherit;font-size:.76rem;background:none;border:none;color:var(--accent);font-weight:600;padding:0;cursor:pointer}
.count{font-variant-numeric:tabular-nums}

/* ---------- mapa ---------- */
#map{
  position:relative;height:44vh;min-height:240px;max-height:460px;
  overflow:hidden;background:var(--surface-2);
  touch-action:none;cursor:grab;user-select:none;
}
#layer{position:absolute;inset:0;transform-origin:0 0;will-change:transform}
#layer img{position:absolute;width:256px;height:256px;pointer-events:none;display:block}
.mk{position:absolute;width:28px;height:28px;margin:-14px 0 0 -14px;display:grid;place-items:center;cursor:pointer}
.mk i{
  width:13px;height:13px;border-radius:50%;display:block;
  border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.5);
}
.mk.top i{width:16px;height:16px;box-shadow:0 0 0 2px var(--ochre),0 1px 3px rgba(0,0,0,.5)}
.mk.sel{z-index:5}
.mk.sel i{width:22px;height:22px;border-width:3px;box-shadow:0 0 0 3px var(--accent),0 2px 6px rgba(0,0,0,.5)}
.mapui{position:absolute;right:8px;bottom:8px;display:flex;flex-direction:column;gap:6px;z-index:10}
.mapui button{
  width:38px;height:38px;font:inherit;font-size:1.15rem;font-weight:600;
  background:var(--surface);color:var(--ink);border:1px solid var(--line);
  border-radius:9px;box-shadow:var(--shadow);cursor:pointer;display:grid;place-items:center;
}
.attrib{
  position:absolute;left:0;bottom:0;z-index:10;font-size:.6rem;
  background:rgba(255,255,255,.75);color:#333;padding:1px 5px;border-radius:0 4px 0 0;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .attrib{background:rgba(0,0,0,.55);color:#ddd}}
:root[data-theme="dark"] .attrib{background:rgba(0,0,0,.55);color:#ddd}
.attrib a{color:inherit}
.hint{position:absolute;left:8px;top:8px;z-index:10;font-size:.7rem;background:var(--surface);
  border:1px solid var(--line);border-radius:8px;padding:4px 8px;color:var(--muted);box-shadow:var(--shadow)}

/* ---------- detail ---------- */
#detail{display:none;background:var(--surface);border-bottom:1px solid var(--line);padding:12px;box-shadow:var(--shadow)}
#detail.on{display:block}
#detail h2{margin:0 0 4px;font-size:1.02rem;font-weight:650;line-height:1.28;display:flex;gap:7px;align-items:baseline}
#detail .dot{width:10px;height:10px;border-radius:50%;flex:none;transform:translateY(-1px)}
#detail .dmeta{font-size:.74rem;color:var(--muted);margin:0 0 7px}
#detail p.desc{margin:0 0 9px;font-size:.87rem}
#detail .warn{font-size:.74rem;color:var(--ochre);margin:0 0 9px;font-weight:600}
.acts{display:flex;gap:7px;flex-wrap:wrap}
.btn{
  font:inherit;font-size:.82rem;font-weight:600;text-decoration:none;
  padding:9px 13px;border-radius:9px;border:1px solid var(--accent);
  background:var(--accent);color:#fff;display:inline-block;
}
.btn.alt{background:var(--surface);color:var(--accent)}
.btn.close{background:none;border-color:var(--line);color:var(--muted);font-weight:500}
.coords{font-size:.7rem;color:var(--muted);margin:8px 0 0;font-variant-numeric:tabular-nums}

/* ---------- seznam ---------- */
#list{padding:4px 0 60px}
.dayhead{
  position:sticky;top:0;z-index:5;background:var(--bg);
  font-family:"Iowan Old Style",Palatino,Georgia,serif;font-size:1rem;font-weight:600;
  padding:12px 12px 5px;border-bottom:1px solid var(--line);margin:0 0 4px;
}
.dayhead span{font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:.72rem;color:var(--muted);font-weight:400;margin-left:6px}
.row{
  display:flex;gap:9px;align-items:baseline;width:100%;text-align:left;
  background:none;border:none;border-bottom:1px solid var(--line);
  font:inherit;color:var(--ink);padding:11px 12px;cursor:pointer;
}
.row:active{background:var(--surface-2)}
.row.sel{background:var(--accent-soft)}
.row .dot{width:9px;height:9px;border-radius:50%;flex:none;transform:translateY(4px)}
.row .txt{flex:1;min-width:0}
.row .nm{font-size:.92rem;font-weight:600;line-height:1.3}
.row .sn{font-size:.76rem;color:var(--muted);margin-top:1px;overflow:hidden;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.star{color:var(--ochre)}
.empty{display:none;padding:28px 14px;color:var(--muted);font-size:.88rem;text-align:center}
.jsmsg{margin:0;padding:11px 12px;background:var(--ochre);color:#20180a;font-size:.82rem;font-weight:600}
footer{padding:16px 12px 40px;color:var(--muted);font-size:.72rem;border-top:1px solid var(--line)}
footer p{margin:0 0 6px}
button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
"""

JS = r"""
const CATS = __CATS__;
const P = __POINTS__.map(a => ({
  name:a[0], lat:a[1], lon:a[2], cat:a[3], top:!!a[4],
  day:a[5], city:a[6], desc:a[7], conf:a[8], q:a[9]
}));
const CONF = __CONF__;

/* ===== mapa: minimalistický slippy map nad dlaždicemi OSM ===== */
const TS = 256, MINZ = 5, MAXZ = 18;
const map = document.getElementById('map');
const layer = document.getElementById('layer');
const lon2x = (lon,z) => (lon+180)/360 * TS * Math.pow(2,z);
const lat2y = (lat,z) => { const s=Math.sin(lat*Math.PI/180);
  return (0.5 - Math.log((1+s)/(1-s))/(4*Math.PI)) * TS * Math.pow(2,z); };
const x2lon = (x,z) => x/(TS*Math.pow(2,z))*360 - 180;
const y2lat = (y,z) => { const n=Math.PI - 2*Math.PI*y/(TS*Math.pow(2,z));
  return 180/Math.PI*Math.atan(0.5*(Math.exp(n)-Math.exp(-n))); };

let z = 7, ox = 0, oy = 0, tx = 0, ty = 0;   // origin ve světových px, translate v px
const tiles = new Map();
let marks = [];

/* Bez signálu se dlaždice nenačtou — ať je jasné, že chybí podklad, ne body. */
let offlineShown = false;
function offline(){
  if(offlineShown) return;
  offlineShown = true;
  const h = document.getElementById('hint');
  if(h){ h.textContent = 'Podklad mapy se nenačetl (offline) — body a filtry fungují dál'; h.style.display = ''; }
}

const W = () => map.clientWidth, H = () => map.clientHeight;
function paint(){ layer.style.transform = `translate3d(${tx}px,${ty}px,0)`; }

function fillTiles(){
  const n = Math.pow(2,z);
  const x0 = Math.floor((ox - tx)/TS), x1 = Math.floor((ox - tx + W())/TS);
  const y0 = Math.floor((oy - ty)/TS), y1 = Math.floor((oy - ty + H())/TS);
  const need = new Set();
  for(let x=x0-1;x<=x1+1;x++) for(let y=y0-1;y<=y1+1;y++){
    if(y<0||y>=n) continue;
    const xi = ((x % n) + n) % n, k = z+'/'+xi+'/'+y;
    need.add(k+'@'+x);
    if(!tiles.has(k+'@'+x)){
      const img = document.createElement('img');
      img.src = `https://tile.openstreetmap.org/${z}/${xi}/${y}.png`;
      img.alt = ''; img.loading = 'eager'; img.decoding = 'async';
      img.onerror = function(){ this.style.visibility = 'hidden'; offline(); };
      img.style.left = (x*TS - ox)+'px';
      img.style.top  = (y*TS - oy)+'px';
      layer.appendChild(img);
      tiles.set(k+'@'+x, img);
    }
  }
  for(const [k,img] of tiles) if(!need.has(k)){ img.remove(); tiles.delete(k); }
}

function placeMarks(){
  for(const m of marks){
    m.el.style.left = (lon2x(m.p.lon,z) - ox)+'px';
    m.el.style.top  = (lat2y(m.p.lat,z) - oy)+'px';
  }
}

function setView(lat, lon, nz){
  z = Math.max(MINZ, Math.min(MAXZ, nz===undefined ? z : nz));
  ox = lon2x(lon,z) - W()/2;
  oy = lat2y(lat,z) - H()/2;
  tx = ty = 0;
  for(const [k,img] of tiles){ img.remove(); tiles.delete(k); }
  paint(); fillTiles(); placeMarks();
}

function zoomAt(sx, sy, dz){
  const nz = Math.max(MINZ, Math.min(MAXZ, z + dz));
  if(nz === z) return;
  const wx = (ox - tx + sx) * Math.pow(2, nz - z);
  const wy = (oy - ty + sy) * Math.pow(2, nz - z);
  z = nz; ox = wx - sx; oy = wy - sy; tx = ty = 0;
  for(const [k,img] of tiles){ img.remove(); tiles.delete(k); }
  paint(); fillTiles(); placeMarks();
}

function fit(pts){
  if(!pts.length) return;
  let a=90,b=-90,c=180,d=-180;
  for(const p of pts){ a=Math.min(a,p.lat); b=Math.max(b,p.lat); c=Math.min(c,p.lon); d=Math.max(d,p.lon); }
  const clat=(a+b)/2, clon=(c+d)/2;
  let best = MINZ;
  for(let t=MAXZ;t>=MINZ;t--){
    const w = lon2x(d,t)-lon2x(c,t), h = lat2y(a,t)-lat2y(b,t);
    if(w <= W()*0.82 && h <= H()*0.78){ best=t; break; }
  }
  setView(clat, clon, pts.length===1 ? Math.min(16,MAXZ) : best);
}

/* tažení a pinch */
const pts = new Map();
let pinch = null, moved = 0, lastTap = 0;
map.addEventListener('pointerdown', e => {
  map.setPointerCapture(e.pointerId);
  pts.set(e.pointerId, {x:e.clientX, y:e.clientY});
  moved = 0;
  if(pts.size === 2){
    const [p1,p2] = [...pts.values()];
    pinch = {d:Math.hypot(p1.x-p2.x, p1.y-p2.y),
             mx:(p1.x+p2.x)/2 - map.getBoundingClientRect().left,
             my:(p1.y+p2.y)/2 - map.getBoundingClientRect().top};
  }
});
map.addEventListener('pointermove', e => {
  const prev = pts.get(e.pointerId);
  if(!prev) return;
  const dx = e.clientX - prev.x, dy = e.clientY - prev.y;
  pts.set(e.pointerId, {x:e.clientX, y:e.clientY});
  if(pts.size === 2 && pinch){
    const [p1,p2] = [...pts.values()];
    pinch.now = Math.hypot(p1.x-p2.x, p1.y-p2.y);
    return;
  }
  moved += Math.abs(dx) + Math.abs(dy);
  tx += dx; ty += dy; paint();
  if(!map._raf){ map._raf = requestAnimationFrame(() => { map._raf=0; fillTiles(); }); }
});
function up(e){
  pts.delete(e.pointerId);
  if(pinch && pts.size < 2){
    if(pinch.now && pinch.d > 0){
      const dz = Math.round(Math.log2(pinch.now / pinch.d));
      if(dz) zoomAt(pinch.mx, pinch.my, dz);
    }
    pinch = null;
  }
  if(pts.size === 0) fillTiles();
}
map.addEventListener('pointerup', up);
map.addEventListener('pointercancel', up);
map.addEventListener('dblclick', e => {
  const r = map.getBoundingClientRect();
  zoomAt(e.clientX - r.left, e.clientY - r.top, 1);
});
map.addEventListener('wheel', e => {
  e.preventDefault();
  const r = map.getBoundingClientRect();
  zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1 : -1);
}, {passive:false});
document.getElementById('zin').onclick  = () => zoomAt(W()/2, H()/2, 1);
document.getElementById('zout').onclick = () => zoomAt(W()/2, H()/2, -1);
document.getElementById('zfit').onclick = () => fit(shown());

/* ===== body, filtry, seznam ===== */
const state = {days:new Set(), cats:new Set(), top:false, q:''};
let sel = -1;
const rowEls = [];

function shown(){ return P.filter(p => p._on); }

function pass(p){
  return (!state.days.size || state.days.has(p.day))
      && (!state.cats.size || state.cats.has(p.cat))
      && (!state.top || p.top)
      && (!state.q || p.q.includes(state.q));
}

const listEl = document.getElementById('list');
const emptyEl = document.getElementById('empty');
const countEl = document.getElementById('count');

/* Seznam už je v HTML (aby byl čitelný i bez skriptu) — jen si na něj navěsíme
   obsluhu a doplníme značky do mapy. */
(function build(){
  document.querySelectorAll('.row').forEach(b => {
    const i = +b.dataset.i;
    rowEls[i] = b;
    b.addEventListener('click', () => select(i, true));

    const p = P[i];
    const mk = document.createElement('div');
    mk.className = 'mk' + (p.top ? ' top' : '');
    mk.innerHTML = '<i style="background:'+CATS[p.cat].c+'"></i>';
    mk.addEventListener('click', ev => { ev.stopPropagation(); select(i, false); });
    layer.appendChild(mk);
    marks[i] = {el:mk, p};
  });
  if(rowEls.filter(Boolean).length !== P.length){
    throw new Error('seznam v HTML neodpovídá datům');
  }
})();

function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

const dEl = document.getElementById('detail');
function select(i, fromList){
  if(sel >= 0){ marks[sel].el.classList.remove('sel'); rowEls[sel].classList.remove('sel'); }
  if(sel === i){ sel = -1; dEl.classList.remove('on'); return; }
  sel = i;
  const p = P[i];
  marks[i].el.classList.add('sel');
  rowEls[i].classList.add('sel');

  const apple = 'https://maps.apple.com/?q=' + encodeURIComponent(p.name + ', ' + p.city)
              + '&sll=' + p.lat.toFixed(5) + ',' + p.lon.toFixed(5) + '&z=16';
  const exact = 'https://maps.apple.com/?ll=' + p.lat.toFixed(5) + ',' + p.lon.toFixed(5)
              + '&q=' + encodeURIComponent(p.name) + '&z=17';
  const goog  = 'https://www.google.com/maps/search/?api=1&query='
              + encodeURIComponent(p.name + ', ' + p.city);
  const note = CONF[p.conf] || '';

  dEl.innerHTML =
    '<h2><span class="dot" style="background:'+CATS[p.cat].c+'"></span><span>' +
      (p.top ? '<span class="star">★</span> ' : '') + esc(p.name) + '</span></h2>' +
    '<p class="dmeta">' + esc(p.day) + ' · ' + esc(p.city) + ' · ' + esc(CATS[p.cat].l) + '</p>' +
    '<p class="desc">' + esc(p.desc) + '</p>' +
    (note ? '<p class="warn">' + esc(note) + '</p>' : '') +
    '<div class="acts">' +
      '<a class="btn" href="'+apple+'">Apple Maps ↗</a>' +
      '<a class="btn alt" href="'+exact+'">Přesný bod ↗</a>' +
      '<a class="btn alt" href="'+goog+'">Google ↗</a>' +
      '<button class="btn close" type="button" id="dclose">Zavřít</button>' +
    '</div>' +
    '<p class="coords">' + p.lat.toFixed(5) + ', ' + p.lon.toFixed(5) + '</p>';
  dEl.classList.add('on');
  document.getElementById('dclose').onclick = () => {
    marks[sel].el.classList.remove('sel'); rowEls[sel].classList.remove('sel');
    sel = -1; dEl.classList.remove('on');
  };

  if(fromList){
    setView(p.lat, p.lon, Math.max(z, 15));
    dEl.scrollIntoView({behavior:'smooth', block:'start'});
  } else {
    dEl.scrollIntoView({behavior:'smooth', block:'nearest'});
  }
}

function apply(){
  let n = 0;
  P.forEach((p,i) => {
    p._on = pass(p);
    marks[i].el.style.display = p._on ? '' : 'none';
    rowEls[i].style.display = p._on ? '' : 'none';
    if(p._on) n++;
  });
  document.querySelectorAll('.dayhead').forEach(h => {
    const any = P.some(p => p._on && p.day === h.dataset.day);
    h.style.display = any ? '' : 'none';
  });
  countEl.textContent = n === P.length ? P.length + ' míst' : n + ' z ' + P.length;
  emptyEl.style.display = n ? 'none' : 'block';
  if(sel >= 0 && !P[sel]._on){
    marks[sel].el.classList.remove('sel'); rowEls[sel].classList.remove('sel');
    sel = -1; dEl.classList.remove('on');
  }
}

function toggle(btn, set, key){
  const on = btn.getAttribute('aria-pressed') === 'true';
  btn.setAttribute('aria-pressed', String(!on));
  if(on) set.delete(key); else set.add(key);
  apply(); fit(shown());
}
document.querySelectorAll('.chip-day').forEach(b =>
  b.onclick = () => toggle(b, state.days, b.dataset.day));
document.querySelectorAll('.chip-cat').forEach(b =>
  b.onclick = () => toggle(b, state.cats, b.dataset.cat));
const sb = document.getElementById('star');
sb.onclick = () => { state.top = sb.getAttribute('aria-pressed') !== 'true';
  sb.setAttribute('aria-pressed', String(state.top)); apply(); fit(shown()); };

const search = document.getElementById('search');
let sdeb;
search.oninput = () => {
  clearTimeout(sdeb);
  sdeb = setTimeout(() => { state.q = norm(search.value.trim()); apply(); }, 160);
};
function norm(s){
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
}
document.getElementById('reset').onclick = () => {
  state.days.clear(); state.cats.clear(); state.top = false; state.q = '';
  search.value = '';
  document.querySelectorAll('[aria-pressed]').forEach(b => b.setAttribute('aria-pressed','false'));
  apply(); fit(shown());
};

let rz;
addEventListener('resize', () => {
  clearTimeout(rz);
  rz = setTimeout(() => {
    const lat = y2lat(oy - ty + H()/2, z), lon = x2lon(ox - tx + W()/2, z);
    setView(lat, lon, z);
  }, 200);
});

apply();
fit(shown());
setTimeout(() => { const h=document.getElementById('hint'); if(h && !offlineShown) h.style.display='none'; }, 6000);

/* rukojeť pro ověřovací skripty */
window.__dbg = {P, marks, setView, fit, shown, state, apply, lon2x, lat2y, x2lon, y2lat,
  get z(){return z}, get ox(){return ox}, get oy(){return oy},
  get tx(){return tx}, get ty(){return ty}};
"""


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

    rows = []
    for p in points:
        conf = (p.get("COORD_CONF") or "med").strip().lower()
        if conf not in ("high", "med", "low"):
            conf = "med"
        blob = norm(" ".join([p["name"], p["desc"], p["city"],
                              CATEGORIES[p["cat"]][1], p["day"]]))
        rows.append([p["name"], round(p["lat"], 5), round(p["lon"], 5), p["cat"],
                     1 if p["top"] else 0, p["day"], p["city"], p["desc"], conf, blob])

    cats_js = {c: {"c": SWATCH[c], "l": CATEGORIES[c][1]} for c in CATEGORIES}

    js = (JS.replace("__CATS__", json.dumps(cats_js, ensure_ascii=False))
            .replace("__POINTS__", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
            .replace("__CONF__", json.dumps(CONF_NOTE, ensure_ascii=False)))
    # Když skript spadne, ať to stránka řekne — ne aby filtry jen tiše nereagovaly.
    js = ("(function(){try{\n" + js + "\n}catch(e){\n"
          "var b=document.getElementById('jserr');\n"
          "if(b){b.style.display='block';"
          "b.textContent='Interaktivní část se nespustila: '+e.message+"
          "' — seznam níž funguje i tak.';}\n"
          "console.error(e);\n}})();\n")

    # Seznam vysázíme staticky do HTML, ať je dokument čitelný i bez skriptu.
    list_html = []
    cur_day = None
    for i, p in enumerate(points):
        if p["day"] != cur_day:
            cur_day = p["day"]
            list_html.append(
                f'<h2 class="dayhead" data-day="{html.escape(p["day"])}">'
                f'{html.escape(p["day"])}<span>{html.escape(p["city"])}</span></h2>')
        snippet = p["desc"][:110]
        star = '<span class="star">★</span> ' if p["top"] else ""
        list_html.append(
            f'<button class="row" type="button" data-i="{i}">'
            f'<span class="dot" style="background:{SWATCH[p["cat"]]}"></span>'
            f'<span class="txt"><span class="nm">{star}'
            f'{html.escape(p["name"])}</span>'
            f'<span class="sn">{html.escape(p["city"])} · '
            f'{html.escape(CATEGORIES[p["cat"]][1])} — {html.escape(snippet)}…</span>'
            f"</span></button>")
    list_html = "\n".join(list_html)

    # filtry
    chips_day = "".join(
        f'<button class="chip chip-day" type="button" aria-pressed="false" '
        f'data-day="{html.escape(day)}">{html.escape(day)} '
        f'<span class="n">{per_day[day]}</span></button>'
        for _, day, _ in REGIONS if per_day.get(day))
    chips_cat = "".join(
        f'<button class="chip chip-cat" type="button" aria-pressed="false" data-cat="{c}">'
        f'<span class="dot" style="background:{SWATCH[c]}"></span>'
        f'{html.escape(CATEGORIES[c][1])} <span class="n">{per_cat[c]}</span></button>'
        for c in CATEGORIES if per_cat.get(c))
    n_top = sum(1 for p in points if p["top"])

    page = f"""<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>Itálie 2026 · mapa míst</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <p class="eyebrow">Itálie 2026</p>
  <h1>Mapa míst</h1>
  <p class="tagline">{len(points)} míst · 10.–16. srpna · klepni na bod v mapě nebo na položku v seznamu</p>
</header>

<div class="filters">
  <div class="srow">
    <input id="search" class="search" type="search" placeholder="Hledat místo…" aria-label="Hledat místo">
    <button id="star" class="chip chip-star" type="button" aria-pressed="false">★ <span class="n">{n_top}</span></button>
  </div>
  <div class="scroller">{chips_day}</div>
  <div class="scroller">{chips_cat}</div>
  <div class="bar2"><span class="count" id="count"></span><button id="reset" type="button">Zrušit filtry</button></div>
</div>

<noscript><p class="jsmsg">Tahle stránka potřebuje JavaScript kvůli mapě a filtrům.
Seznam všech míst i tak najdeš níž.</p></noscript>
<p class="jsmsg" id="jserr" style="display:none"></p>

<div id="map">
  <div id="layer"></div>
  <div class="hint" id="hint">Táhni, dvěma prsty přibliž</div>
  <div class="mapui">
    <button id="zin" type="button" aria-label="Přiblížit">+</button>
    <button id="zout" type="button" aria-label="Oddálit">−</button>
    <button id="zfit" type="button" aria-label="Zobrazit vše">⤢</button>
  </div>
  <div class="attrib">© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a></div>
</div>

<div id="detail"></div>
<div id="list">{list_html}</div>
<p class="empty" id="empty">Nic neodpovídá filtrům.</p>

<footer>
  <p><strong>Souřadnice jsou z rešerše, ne z geokodéru.</strong> U nádraží a velkých památek jsou
  přesné, u malých podniků a schovaných uliček mohou být o desítky metrů vedle. Proto tlačítko
  <em>Apple Maps</em> hledá místo podle názvu v okolí té souřadnice — mapa si ho najde sama.
  <em>Přesný bod</em> otevře čistou souřadnici tak, jak je tady.</p>
  <p>Otevírací doby a ceny ověřuj u placených vstupů na oficiálním webu. Mapový podklad
  se stahuje z OpenStreetMap, takže bez signálu zůstane funkční seznam, hledání i filtry,
  jen dlaždice budou prázdné.</p>
</footer>
<script>{js}</script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"→ {os.path.relpath(OUT, ROOT)}  ({len(points)} bodů, {len(page)//1024} kB)")


if __name__ == "__main__":
    main()
