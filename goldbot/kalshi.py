"""Small Kalshi API client.

Market data is public, so the scanner needs no API key. The signed request
helper is here for later, when we move to the demo account for paper orders.
"""

import base64
import os
import time
from urllib.parse import urlparse

import requests

PROD_URL = "https://external-api.kalshi.com/trade-api/v2"
DEMO_URL = "https://external-api.demo.kalshi.co/trade-api/v2"


class Kalshi:
    def __init__(self, base_url: str | None = None, key_id: str | None = None,
                 private_key_path: str | None = None):
        self.base_url = (base_url or os.getenv("KALSHI_BASE_URL") or PROD_URL).rstrip("/")
        self.key_id = key_id or os.getenv("KALSHI_KEY_ID")
        self.private_key_path = private_key_path or os.getenv("KALSHI_PRIVATE_KEY_PATH")
        self._private_key = None
        self.session = requests.Session()

    # Public market data

    def get(self, path: str, params: dict | None = None, auth: bool = False) -> dict:
        url = self.base_url + path
        headers = self._auth_headers("GET", url) if auth else {}
        r = self.session.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def series(self, series_ticker: str) -> dict:
        return self.get(f"/series/{series_ticker}")["series"]

    def open_markets(self, series_ticker: str) -> list[dict]:
        markets, cursor = [], None
        while True:
            params = {"series_ticker": series_ticker, "status": "open", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            data = self.get("/markets", params)
            markets += data.get("markets", [])
            cursor = data.get("cursor")
            if not cursor:
                return markets

    # Signed requests (needed for balance, positions and orders)

    def _auth_headers(self, method: str, url: str) -> dict:
        if not (self.key_id and self.private_key_path):
            raise RuntimeError("Set KALSHI_KEY_ID and KALSHI_PRIVATE_KEY_PATH in your .env file")
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519, padding

        if self._private_key is None:
            with open(self.private_key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(f.read(), password=None)
        ts = str(int(time.time() * 1000))
        message = (ts + method + urlparse(url).path).encode()
        if isinstance(self._private_key, ed25519.Ed25519PrivateKey):
            sig = self._private_key.sign(message)
        else:
            sig = self._private_key.sign(
                message,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                hashes.SHA256(),
            )
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        }

    def balance(self) -> dict:
        return self.get("/portfolio/balance", auth=True)


def dollars(value) -> float | None:
    """Kalshi sends prices as strings like '0.5600'. Empty or zero means no quote."""
    if value in (None, ""):
        return None
    v = float(value)
    return v if v > 0 else None
