"""Trzni data (denni svicky + aktualni cena) bez API klice.

Primarni zdroj: Kraken public API. Fallback: Coinbase Exchange public API.
Oba jsou zdarma a nevyzaduji autentizaci.
"""
from __future__ import annotations

import json
import time
import urllib.request

KRAKEN_PAIRS = {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"}
USER_AGENT = "paper-trading-bot/1.0"


def _http_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _kraken_candles(symbol: str, days: int) -> list[dict]:
    pair = KRAKEN_PAIRS.get(symbol, f"{symbol}USD")
    since = int(time.time()) - (days + 2) * 86400
    data = _http_json(
        f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440&since={since}"
    )
    if data.get("error"):
        raise RuntimeError(f"Kraken error for {symbol}: {data['error']}")
    result = data["result"]
    key = next(k for k in result if k != "last")
    candles = [
        {
            "t": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[6]),
        }
        for row in result[key]
    ]
    return candles[-days:]


def _coinbase_candles(symbol: str, days: int) -> list[dict]:
    data = _http_json(
        f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles"
        f"?granularity=86400"
    )
    rows = sorted(data, key=lambda r: r[0])  # Coinbase vraci od nejnovejsich
    candles = [
        {
            "t": int(r[0]),
            "open": float(r[3]),
            "high": float(r[2]),
            "low": float(r[1]),
            "close": float(r[4]),
            "volume": float(r[5]),
        }
        for r in rows
    ]
    return candles[-days:]


def get_market_data(symbols: list[str], days: int = 30) -> dict[str, dict]:
    """Vrati {symbol: {price, candles}} pro kazdy symbol.

    Cena = close posledni svicky (u denni svicky prubezne aktualizovany
    poslednim obchodem). Kdyz selze Kraken, zkusi Coinbase.
    """
    out: dict[str, dict] = {}
    errors: list[str] = []
    for sym in symbols:
        candles = None
        for fetch in (_kraken_candles, _coinbase_candles):
            try:
                candles = fetch(sym, days)
                break
            except Exception as exc:  # noqa: BLE001 - zkusime dalsi zdroj
                errors.append(f"{fetch.__name__}({sym}): {exc}")
        if not candles:
            raise RuntimeError(
                f"Nepodarilo se ziskat data pro {sym}. Pokusy: {errors}"
            )
        out[sym] = {"price": candles[-1]["close"], "candles": candles}
    return out


if __name__ == "__main__":
    data = get_market_data(["BTC", "ETH", "SOL"], days=5)
    for sym, d in data.items():
        print(sym, d["price"], f"({len(d['candles'])} svicek)")
