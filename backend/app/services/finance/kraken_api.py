"""Client Kraken REST privé, limité aux opérations de lecture.

La signature est calculée localement. Les clés ne sont jamais incluses dans les
URLs, les logs, les exceptions ou les données persistées.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import threading
import time
from urllib.parse import urlencode

import httpx

from app.core.config import settings

_nonce_lock = threading.Lock()
_last_nonce = 0


def configured() -> bool:
    return bool(settings.kraken_api_key and settings.kraken_api_secret)


def _nonce() -> str:
    global _last_nonce
    with _nonce_lock:
        candidate = time.time_ns() // 1_000_000
        _last_nonce = max(candidate, _last_nonce + 1)
        return str(_last_nonce)


def _signature(path: str, data: dict[str, str], secret: str) -> str:
    encoded = urlencode(data).encode()
    digest = hashlib.sha256(data["nonce"].encode() + encoded).digest()
    mac = hmac.new(base64.b64decode(secret), path.encode() + digest, hashlib.sha512)
    return base64.b64encode(mac.digest()).decode()


def private(method: str, **params) -> dict:
    if not configured():
        raise RuntimeError("Kraken n'est pas configuré")
    path = f"/0/private/{method}"
    data = {k: str(v) for k, v in params.items() if v is not None}
    data["nonce"] = _nonce()
    headers = {
        "API-Key": settings.kraken_api_key,
        "API-Sign": _signature(path, data, settings.kraken_api_secret),
    }
    try:
        response = httpx.post(
            settings.kraken_base_url.rstrip("/") + path,
            data=data,
            headers=headers,
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"Kraken indisponible ({type(exc).__name__})") from None
    errors = payload.get("error") or []
    if errors:
        raise RuntimeError("Kraken a refusé la requête: " + ", ".join(map(str, errors)))
    return payload.get("result") or {}


def public(method: str, **params) -> dict:
    try:
        response = httpx.get(
            f"{settings.kraken_base_url.rstrip('/')}/0/public/{method}",
            params=params,
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"Kraken public indisponible ({type(exc).__name__})") from None
    if payload.get("error"):
        raise RuntimeError("Kraken public a refusé la requête")
    return payload.get("result") or {}


_ALIASES = {
    "XXBT": "BTC", "XBT": "BTC", "XETH": "ETH", "ZEUR": "EUR",
    "ZUSD": "USD", "ZCAD": "CAD", "ZGBP": "GBP", "ZJPY": "JPY",
}


def asset_symbol(code: str) -> str:
    """Retire les préfixes/suffixes internes Kraken sans altérer les symboles."""
    base = str(code).split(".", 1)[0].upper()
    return _ALIASES.get(base, base)


def balances() -> dict[str, float]:
    result: dict[str, float] = {}
    for asset, quantity in private("Balance").items():
        value = float(quantity or 0)
        if abs(value) > 1e-12:
            symbol = asset_symbol(asset)
            result[symbol] = result.get(symbol, 0.0) + value
    return result


def asset_pairs() -> dict[str, dict]:
    return public("AssetPairs")


def closed_trades(*, max_pages: int = 20) -> list[tuple[str, dict]]:
    """Historique paginé (50 lignes/page), du plus récent au plus ancien."""
    rows: list[tuple[str, dict]] = []
    offset = 0
    for _ in range(max_pages):
        result = private("TradesHistory", ofs=offset)
        trades = result.get("trades") or {}
        rows.extend((str(txid), trade) for txid, trade in trades.items())
        offset += len(trades)
        if not trades or offset >= int(result.get("count") or 0):
            break
    return rows
