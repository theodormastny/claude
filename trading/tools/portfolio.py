"""Paper trading portfolio ulozene v git-friendly JSON souborech.

data/state.json     - hotovost + aktualni pozice
data/trades.jsonl   - kazdy provedeny obchod (append-only)
data/equity.jsonl   - snapshot hodnoty portfolia po kazdem cyklu
data/decisions.jsonl- plny zaznam rozhodnuti AI vcetne komentare
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_DIR / "data"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Portfolio:
    def __init__(self, starting_cash: float, data_dir: Path = DEFAULT_DATA_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "state.json"
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
        else:
            self.state = {
                "cash": starting_cash,
                "starting_cash": starting_cash,
                "positions": {},  # symbol -> {"qty": float, "cost_usd": float}
                "created": now_iso(),
            }
            self._save_state()

    # ---------- persistence ----------

    def _save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=2) + "\n")

    def _append(self, name: str, record: dict) -> None:
        with open(self.data_dir / name, "a") as fh:
            fh.write(json.dumps(record) + "\n")

    def read_jsonl(self, name: str) -> list[dict]:
        path = self.data_dir / name
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    # ---------- vypocty ----------

    def equity(self, prices: dict[str, float]) -> float:
        total = self.state["cash"]
        for sym, pos in self.state["positions"].items():
            total += pos["qty"] * prices.get(sym, 0.0)
        return total

    def position_value(self, symbol: str, price: float) -> float:
        pos = self.state["positions"].get(symbol)
        return pos["qty"] * price if pos else 0.0

    # ---------- obchody ----------

    def execute(self, side: str, symbol: str, amount_usd: float,
                price: float, reason: str, ts: str | None = None) -> dict:
        """Provede paper obchod. amount_usd je notional v USD."""
        ts = ts or now_iso()
        qty = amount_usd / price
        positions = self.state["positions"]
        if side == "BUY":
            self.state["cash"] -= amount_usd
            pos = positions.setdefault(symbol, {"qty": 0.0, "cost_usd": 0.0})
            pos["qty"] += qty
            pos["cost_usd"] += amount_usd
        elif side == "SELL":
            pos = positions[symbol]
            # pomerne snizeni porizovaci ceny
            fraction = min(qty / pos["qty"], 1.0)
            pos["cost_usd"] *= (1 - fraction)
            pos["qty"] -= qty
            self.state["cash"] += amount_usd
            if pos["qty"] * price < 0.01:
                del positions[symbol]
        else:
            raise ValueError(f"Neznamy smer obchodu: {side}")
        trade = {
            "ts": ts,
            "side": side,
            "symbol": symbol,
            "qty": round(qty, 8),
            "price": price,
            "amount_usd": round(amount_usd, 2),
            "reason": reason,
        }
        self._append("trades.jsonl", trade)
        self._save_state()
        return trade

    def snapshot(self, prices: dict[str, float], ts: str | None = None) -> dict:
        snap = {
            "ts": ts or now_iso(),
            "equity": round(self.equity(prices), 2),
            "cash": round(self.state["cash"], 2),
            "prices": {s: prices[s] for s in sorted(prices)},
        }
        self._append("equity.jsonl", snap)
        return snap

    def log_decision(self, record: dict) -> None:
        self._append("decisions.jsonl", record)
