"""Jeden obchodni cyklus: data -> AI rozhodnuti -> risk kontrola -> obchody.

Spousti se planovane (GitHub Actions / cron), typicky 1x denne:

    python trading/tools/run_cycle.py            # ostry beh (potrebuje Gemini klice)
    python trading/tools/run_cycle.py --mock     # test bez site a bez AI

AI dostane trzni data a stav portfolia, vrati JSON s rozhodnutimi.
Deterministicka risk vrstva kazde rozhodnuti oreze nebo zamitne podle
limitu v config.toml - AI limity nemuze obejit.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gemini_client import GeminiClient, QuotaExhausted  # noqa: E402
from portfolio import DEFAULT_DATA_DIR, Portfolio, now_iso  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- prompt

def summarize_market(market: dict[str, dict]) -> str:
    lines = []
    for sym, d in market.items():
        closes = [c["close"] for c in d["candles"]]
        price = d["price"]
        chg7 = (price / closes[-8] - 1) * 100 if len(closes) >= 8 else 0.0
        chg30 = (price / closes[0] - 1) * 100 if len(closes) >= 2 else 0.0
        hi, lo = max(closes), min(closes)
        recent = ", ".join(f"{c:.2f}" for c in closes[-10:])
        lines.append(
            f"- {sym}: cena {price:.2f} USD | 7d {chg7:+.1f}% | "
            f"{len(closes)}d {chg30:+.1f}% | min/max {lo:.2f}/{hi:.2f}\n"
            f"  poslednich 10 dennich zaviracich cen: {recent}"
        )
    return "\n".join(lines)


def summarize_portfolio(pf: Portfolio, prices: dict[str, float]) -> str:
    equity = pf.equity(prices)
    lines = [
        f"- hodnota portfolia: {equity:.2f} USD "
        f"(start {pf.state['starting_cash']:.2f} USD)",
        f"- hotovost: {pf.state['cash']:.2f} USD",
    ]
    for sym, pos in pf.state["positions"].items():
        value = pos["qty"] * prices.get(sym, 0)
        pnl = value - pos["cost_usd"]
        lines.append(
            f"- pozice {sym}: {pos['qty']:.6f} ks, hodnota {value:.2f} USD, "
            f"nerealizovany P/L {pnl:+.2f} USD"
        )
    if not pf.state["positions"]:
        lines.append("- zadne otevrene pozice")
    trades = pf.read_jsonl("trades.jsonl")[-5:]
    if trades:
        lines.append("- poslednich az 5 obchodu:")
        for t in trades:
            lines.append(
                f"  {t['ts']} {t['side']} {t['symbol']} "
                f"za {t['amount_usd']:.2f} USD @ {t['price']:.2f}"
            )
    return "\n".join(lines)


def build_prompt(cfg: dict, pf: Portfolio, market: dict[str, dict]) -> str:
    prices = {s: d["price"] for s, d in market.items()}
    risk = cfg["risk"]
    return f"""{cfg['strategy']['mandate'].strip()}

TVRDE LIMITY (vynucene kodem, nezadavej obchody mimo ne):
- max {risk['max_trades_per_cycle']} obchody za cyklus
- jeden obchod max {risk['max_trade_pct']*100:.0f} % hodnoty portfolia
- jedna pozice max {risk['max_position_pct']*100:.0f} % hodnoty portfolia
- vzdy zustava min {risk['min_cash_pct']*100:.0f} % v hotovosti
- povolene symboly: {', '.join(cfg['strategy']['symbols'])}

TRZNI DATA (denni svicky):
{summarize_market(market)}

STAV PORTFOLIA:
{summarize_portfolio(pf, prices)}

Rozhodni, co udelat v tomto cyklu. Odpovez POUZE validnim JSON:
{{
  "analysis": "strucna analyza trhu a zduvodneni (cesky, max 3 vety)",
  "decisions": [
    {{"action": "BUY" | "SELL" | "HOLD", "symbol": "BTC", "amount_usd": 500, "reason": "kratke zduvodneni"}}
  ]
}}
Pro HOLD nastav amount_usd na 0. Kdyz nechces obchodovat, vrat jedine
rozhodnuti HOLD - to je casto spravna odpoved."""


# ---------------------------------------------------------------- risk vrstva

def apply_risk_limits(decisions: list[dict], cfg: dict, pf: Portfolio,
                      prices: dict[str, float]) -> tuple[list[dict], list[str]]:
    """Vrati (schvalene obchody, zaznamy o zamitnutich/orezech)."""
    risk = cfg["risk"]
    equity = pf.equity(prices)
    approved: list[dict] = []
    notes: list[str] = []
    for dec in decisions:
        action = str(dec.get("action", "")).upper()
        if action == "HOLD":
            continue
        symbol = str(dec.get("symbol", "")).upper()
        try:
            amount = float(dec.get("amount_usd", 0))
        except (TypeError, ValueError):
            amount = 0.0
        if action not in ("BUY", "SELL"):
            notes.append(f"zamitnuto: neznama akce {dec.get('action')!r}")
            continue
        if symbol not in cfg["strategy"]["symbols"]:
            notes.append(f"zamitnuto: {symbol} neni povoleny symbol")
            continue
        if len(approved) >= risk["max_trades_per_cycle"]:
            notes.append(f"zamitnuto: {action} {symbol} - limit obchodu na cyklus")
            continue

        price = prices[symbol]
        original = amount
        amount = min(amount, risk["max_trade_pct"] * equity)
        if action == "BUY":
            max_cash = pf.state["cash"] - risk["min_cash_pct"] * equity
            room = risk["max_position_pct"] * equity - pf.position_value(symbol, price)
            amount = min(amount, max_cash, room)
        else:
            amount = min(amount, pf.position_value(symbol, price))
        if amount < risk["min_trade_usd"]:
            notes.append(
                f"zamitnuto: {action} {symbol} {original:.0f} USD - po orezani "
                f"limity zbylo {max(amount, 0):.2f} USD (< min {risk['min_trade_usd']})"
            )
            continue
        if amount < original - 0.01:
            notes.append(
                f"orezano: {action} {symbol} {original:.0f} -> {amount:.2f} USD"
            )
        approved.append({
            "action": action,
            "symbol": symbol,
            "amount_usd": round(amount, 2),
            "reason": str(dec.get("reason", "")),
        })
    return approved, notes


# ---------------------------------------------------------------- mock rezim

def mock_market(symbols: list[str], days: int, seed: int) -> dict[str, dict]:
    """Syntetiky nahodna prochazka - pro testovani bez site."""
    base = {"BTC": 67000.0, "ETH": 3500.0, "SOL": 150.0}
    rng = random.Random(seed)
    out = {}
    for sym in symbols:
        price = base.get(sym, 100.0)
        candles = []
        for i in range(days):
            drift = rng.gauss(0.001, 0.025)
            new_price = price * (1 + drift)
            candles.append({
                "t": 0, "open": price,
                "high": max(price, new_price) * 1.01,
                "low": min(price, new_price) * 0.99,
                "close": new_price, "volume": rng.uniform(1e3, 1e4),
            })
            price = new_price
        out[sym] = {"price": price, "candles": candles}
    return out


def mock_ai_response(market: dict[str, dict]) -> str:
    """Jednoducha momentum heuristika misto Gemini - jen pro test pipeline."""
    decisions = []
    for sym, d in market.items():
        closes = [c["close"] for c in d["candles"]]
        chg7 = closes[-1] / closes[-8] - 1 if len(closes) >= 8 else 0
        if chg7 > 0.05:
            decisions.append({"action": "BUY", "symbol": sym, "amount_usd": 800,
                              "reason": f"mock: 7d momentum {chg7:+.1%}"})
        elif chg7 < -0.06:
            decisions.append({"action": "SELL", "symbol": sym, "amount_usd": 600,
                              "reason": f"mock: 7d pokles {chg7:+.1%}"})
    if not decisions:
        decisions = [{"action": "HOLD", "symbol": "BTC", "amount_usd": 0,
                      "reason": "mock: zadny silny signal"}]
    return json.dumps({"analysis": "Mock rezim - heuristika misto AI.",
                       "decisions": decisions})


# ---------------------------------------------------------------- hlavni beh

def parse_ai_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI nevratila JSON: {text[:200]}")
    return json.loads(text[start:end + 1])


def run_cycle(config_path: Path, data_dir: Path, mock: bool = False,
              mock_seed: int = 1, mock_ts: str | None = None) -> dict:
    cfg = tomllib.loads(config_path.read_text())
    pf = Portfolio(cfg["portfolio"]["starting_cash"], data_dir)
    symbols = cfg["strategy"]["symbols"]
    days = cfg["strategy"]["history_days"]
    ts = mock_ts or now_iso()

    if mock:
        market = mock_market(symbols, days, mock_seed)
    else:
        from market_data import get_market_data
        market = get_market_data(symbols, days)
    prices = {s: d["price"] for s, d in market.items()}

    prompt = build_prompt(cfg, pf, market)
    skipped = None
    if mock:
        raw = mock_ai_response(market)
        model = "mock"
    else:
        client = GeminiClient(
            cfg["ai"]["model"], cfg["ai"]["temperature"],
            cfg["ai"]["max_output_tokens"], data_dir,
        )
        try:
            raw = client.generate(prompt)
            model = cfg["ai"]["model"]
        except QuotaExhausted as exc:
            # Vsechny klice vycerpane -> tento cyklus jen drzime a logujeme.
            raw = json.dumps({"analysis": f"Cyklus preskocen: {exc}",
                              "decisions": []})
            model = "none"
            skipped = str(exc)

    ai = parse_ai_json(raw)
    decisions = ai.get("decisions", [])
    approved, risk_notes = apply_risk_limits(decisions, cfg, pf, prices)

    executed = []
    for trade in approved:
        executed.append(pf.execute(
            trade["action"], trade["symbol"], trade["amount_usd"],
            prices[trade["symbol"]], trade["reason"], ts=ts,
        ))

    snap = pf.snapshot(prices, ts=ts)
    pf.log_decision({
        "ts": ts,
        "model": model,
        "analysis": ai.get("analysis", ""),
        "decisions": decisions,
        "risk_notes": risk_notes,
        "executed": len(executed),
        "skipped": skipped,
    })

    print(f"[{ts}] equity {snap['equity']:.2f} USD | "
          f"obchodu: {len(executed)} | {ai.get('analysis', '')[:120]}")
    for note in risk_notes:
        print(f"  risk: {note}")
    for t in executed:
        print(f"  {t['side']} {t['symbol']} {t['amount_usd']:.2f} USD @ {t['price']:.2f}")
    return snap


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_DIR / "config.toml")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--mock", action="store_true",
                        help="beh bez site a bez AI (test pipeline)")
    parser.add_argument("--mock-seed", type=int, default=1)
    parser.add_argument("--mock-ts", default=None,
                        help="timestamp pro mock beh (ISO)")
    args = parser.parse_args()
    run_cycle(args.config, args.data_dir, args.mock, args.mock_seed, args.mock_ts)


if __name__ == "__main__":
    main()
