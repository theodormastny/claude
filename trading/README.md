# AI Paper Trading

Automaticky "set and forget" paper trading system rizeny AI (Gemini).
Zadne realne penize — virtualni portfolio, realne trzni ceny.

## Jak to funguje

```
GitHub Actions (kazdou hodinu v :15)
  └─ run_cycle.py
       ├─ trzni data: Kraken/Coinbase public API (BTC, ETH, SOL) — bez klice
       ├─ Gemini rozhodne: BUY / SELL / HOLD  (rotace API klicu pri limitu)
       ├─ risk vrstva v kodu oreze/zamitne vse mimo limity
       └─ paper obchody + snapshot do data/
  └─ build_dashboard.py  →  dashboard/index.html (+ kopie do docs/)
  └─ commit vysledku zpet do repozitare
```

- **AI se vola stridme** — jednou za hodinu, jeden request (24 denne).
  Strategie (mandat,
  symboly, limity) je dana predem v `config.toml`; AI jen rozhoduje uvnitr
  techto mantinelu a **limity nemuze obejit** — vynucuje je deterministicky kod.
- **Rotace klicu**: `GEMINI_API_KEYS` je carkou oddeleny seznam. Pri
  HTTP 429 / vycerpane kvote se automaticky prepne na dalsi klic; kdyz jsou
  vycerpane vsechny, cyklus se bezpecne preskoci (drzi se pozice).
- **Vse je videt**: dashboard ukazuje vyvoj hodnoty portfolia, pozice,
  vsechny obchody i zduvodneni AI.

## Zprovozneni (jednorazove, ~3 minuty)

1. **Pridej secret s klici**: GitHub → repo *Settings → Secrets and
   variables → Actions → New repository secret*
   - Name: `GEMINI_API_KEYS`
   - Value: `klic1,klic2,klic3` (vsechny tve Gemini klice, oddelene carkou)
2. **Merge do main** — planovane workflow bezi jen z default branche.
3. *(volitelne)* **GitHub Pages**: *Settings → Pages → Deploy from a branch*
   → branch `main`, slozka `/docs`. Dashboard pak bezi na
   `https://<user>.github.io/<repo>/`.
4. Prvni cyklus muzes spustit hned rucne: *Actions → Trading Cycle →
   Run workflow*. Dal uz vse bezi samo.

## Lokalni pouziti

```bash
# test bez site a bez AI (synteticka data + heuristika)
python trading/tools/run_cycle.py --mock

# ostry cyklus (potrebuje trading/.env s GEMINI_API_KEYS)
python trading/tools/run_cycle.py

# pregenerovani dashboardu
python trading/tools/build_dashboard.py
```

Vse je ciste stdlib Python 3.11+ — zadne zavislosti k instalaci.

## Zmena strategie

Edituj `config.toml` (symboly, mandat pro AI, risk limity, model) a commitni.
Nic jineho neni potreba menit. Cetnost behu se meni v
`.github/workflows/trading-cycle.yml` (cron).

## Struktura

| Cesta | Ucel |
|---|---|
| `config.toml` | strategie, risk limity, model — jediny zdroj pravdy |
| `tools/run_cycle.py` | orchestrace jednoho cyklu + risk vrstva |
| `tools/market_data.py` | trzni data (Kraken → Coinbase fallback) |
| `tools/gemini_client.py` | Gemini API + rotace klicu |
| `tools/portfolio.py` | paper portfolio (JSON soubory v `data/`) |
| `tools/build_dashboard.py` | generator statickeho dashboardu |
| `data/` | stav, obchody, equity historie, log rozhodnuti AI |
| `dashboard/index.html` | vygenerovany dashboard |

## Upozorneni

Toto je paper trading pro testovani strategie. Vysledky AI strategie nejsou
garanci budouciho vynosu; pred pripadnym prechodem na realne penize je nutne
dlouhodobe overeni a vlastni uvazeni.
