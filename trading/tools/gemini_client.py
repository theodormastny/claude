"""Gemini API klient s automatickou rotaci API klicu.

Klice se ctou z env promenne GEMINI_API_KEYS (carkou oddeleny seznam),
pripadne GEMINI_API_KEY (jeden klic), pripadne z trading/.env.
Pri vycerpani kvoty (HTTP 429 / RESOURCE_EXHAUSTED) se prepne na dalsi
klic; index aktivniho klice se uklada do data/key_state.json, takze
rotace prezije i restart.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

QUOTA_MARKERS = ("RESOURCE_EXHAUSTED", "quota", "rateLimitExceeded")


class QuotaExhausted(RuntimeError):
    """Vsechny dostupne klice maji vycerpanou kvotu."""


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def load_keys() -> list[str]:
    _load_dotenv(PROJECT_DIR / ".env")
    raw = os.environ.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise RuntimeError(
            "Chybi Gemini API klice. Nastav GEMINI_API_KEYS (carkou oddelene) "
            "v prostredi nebo v trading/.env."
        )
    return keys


class GeminiClient:
    def __init__(self, model: str, temperature: float = 0.2,
                 max_output_tokens: int = 2048, data_dir: Path | None = None):
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.keys = load_keys()
        self.state_path = (data_dir or PROJECT_DIR / "data") / "key_state.json"
        self.key_index = self._load_index()

    def _load_index(self) -> int:
        try:
            idx = json.loads(self.state_path.read_text())["index"]
            return idx % len(self.keys)
        except Exception:  # noqa: BLE001 - chybejici/poskozeny stav = zacni od 0
            return 0

    def _save_index(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({"index": self.key_index}))

    def _call(self, key: str, prompt: str) -> str:
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }).encode()
        req = urllib.request.Request(
            API_URL.format(model=self.model),
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Neocekavana odpoved Gemini: {data}") from exc

    def generate(self, prompt: str) -> str:
        """Zavola Gemini; pri vycerpane kvote zrotuje klice.

        Kazdy klic se zkusi maximalne jednou. Jine chyby nez kvota se
        zkusi jednou zopakovat (kratke sitove vypadky).
        """
        last_error: Exception | None = None
        for attempt in range(len(self.keys)):
            key = self.keys[self.key_index]
            try:
                text = self._call(key, prompt)
                self._save_index()
                return text
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                quota = exc.code == 429 or any(m in detail for m in QUOTA_MARKERS)
                if quota:
                    print(f"[gemini] klic #{self.key_index + 1} vycerpan, rotuji")
                    self.key_index = (self.key_index + 1) % len(self.keys)
                    self._save_index()
                    last_error = QuotaExhausted(f"HTTP {exc.code}: {detail[:300]}")
                    continue
                raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:500]}") from exc
            except urllib.error.URLError as exc:
                last_error = exc
                time.sleep(5)
                continue
        if isinstance(last_error, QuotaExhausted):
            raise QuotaExhausted(
                f"Vsech {len(self.keys)} klicu ma vycerpanou kvotu."
            ) from last_error
        raise RuntimeError(f"Gemini volani selhalo: {last_error}") from last_error
