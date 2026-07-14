# Workflow: Obchodni cyklus

## Cil
Jednou denne nechat AI rozhodnout o uprave paper trading portfolia a
zaznamenat vysledek tak, aby byl videt na dashboardu.

## Vstupy
- `config.toml` — strategie, symboly, risk limity, Gemini model
- env `GEMINI_API_KEYS` — carkou oddelene API klice (lokalne v `trading/.env`,
  na GitHubu jako repository secret)

## Kroky
1. Spust `tools/run_cycle.py`. Ten postupne:
   - stahne denni svicky z Kraken public API (fallback Coinbase) — bez klice
   - sestavi prompt: mandat strategie + trzni data + stav portfolia + limity
   - zavola Gemini (`tools/gemini_client.py`); pri vycerpani kvoty rotuje
     klice, pri vycerpani vsech cyklus bezpecne preskoci (= HOLD)
   - kazde rozhodnuti AI projde deterministickou risk vrstvou
     (`apply_risk_limits`) — oreze nebo zamitne vse mimo limity
   - provede paper obchody a zapise snapshot do `data/`
2. Spust `tools/build_dashboard.py` — vygeneruje `dashboard/index.html`.

## Vystupy
- `data/state.json` — hotovost a pozice
- `data/trades.jsonl`, `data/equity.jsonl`, `data/decisions.jsonl` — historie
- `dashboard/index.html` — sobestacny dashboard (kopiruje se i do `docs/`
  pro GitHub Pages)

## Edge cases a poznatky
- **Vycerpane kvoty vsech klicu**: cyklus se preskoci, do `decisions.jsonl`
  se zapise `skipped`. Zadny obchod se neprovede.
- **Vypadek trznich dat**: Kraken -> Coinbase fallback; kdyz selzou oba,
  cyklus spadne a nic se nezapise (bezpecne — zadna data, zadny obchod).
- **AI vrati nevalidni JSON / nesmyslny obchod**: parser je tolerantni
  (code fences apod.); co neprojde risk vrstvou, se zaloguje a zahodi.
- **Testovani bez site**: `python tools/run_cycle.py --mock` bezi na
  syntetickych datech s heuristikou misto AI.
- Scheduled workflow bezi na GitHubu az z default branche (main).
