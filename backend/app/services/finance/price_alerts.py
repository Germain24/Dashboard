"""Alertes de marché : seuils de prix par ticker (#265).

Persisté dans `data/finance_price_alerts.json` (liste de dicts).
Pas de migration SQL — JSON local suffisant (voir app/services/cuisine/pantry.py).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from app.core.config import settings

DIRECTIONS = {"au_dessus", "en_dessous"}


def _alerts_path() -> Path:
    return settings.data_dir / "finance_price_alerts.json"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_id(items: list[dict]) -> int:
    return max((i.get("id", 0) for i in items), default=0) + 1


def check_alerts(alerts: list[dict], prices: dict[str, float]) -> list[dict]:
    """Pur : évalue chaque alerte active contre les prix fournis.

    Renvoie toutes les alertes actives évaluées (déclenchées ou non), enrichies
    de `prix_actuel` et `declenchee`. Les alertes inactives sont ignorées.
    """
    out: list[dict] = []
    for alert in alerts:
        if not alert.get("actif", True):
            continue
        ticker = alert.get("ticker")
        prix = prices.get(ticker)
        if prix is None:
            out.append({**alert, "prix_actuel": None, "declenchee": False})
            continue
        seuil = alert.get("seuil")
        direction = alert.get("direction")
        if direction == "au_dessus":
            declenchee = prix >= seuil
        elif direction == "en_dessous":
            declenchee = prix <= seuil
        else:
            declenchee = False
        out.append({**alert, "prix_actuel": prix, "declenchee": declenchee})
    return out


def list_alerts(*, path: Optional[Path] = None) -> list[dict]:
    return _read(path or _alerts_path())


def add_alert(
    ticker: str,
    seuil: float,
    direction: str,
    *,
    path: Optional[Path] = None,
) -> dict:
    if direction not in DIRECTIONS:
        raise ValueError(f"direction invalide : {direction!r} (attendu {DIRECTIONS})")
    p = path or _alerts_path()
    items = _read(p)
    alert: dict = {
        "id": _next_id(items),
        "ticker": ticker.strip().upper(),
        "seuil": seuil,
        "direction": direction,
        "actif": True,
        "cree_le": date.today().isoformat(),
    }
    items.append(alert)
    _write(p, items)
    return alert


def update_alert(
    alert_id: int,
    patch: dict,
    *,
    path: Optional[Path] = None,
) -> Optional[dict]:
    p = path or _alerts_path()
    items = _read(p)
    for i, alert in enumerate(items):
        if alert.get("id") == alert_id:
            items[i] = {**alert, **{k: v for k, v in patch.items() if k != "id"}}
            _write(p, items)
            return items[i]
    return None


def remove_alert(alert_id: int, *, path: Optional[Path] = None) -> bool:
    p = path or _alerts_path()
    items = _read(p)
    new = [i for i in items if i.get("id") != alert_id]
    if len(new) == len(items):
        return False
    _write(p, new)
    return True


def alerts_with_status(session=None, *, path: Optional[Path] = None) -> list[dict]:
    """Wrapper DB-aware : résout les prix courants puis évalue les alertes.

    ``session`` n'est pas utilisé ici (le store est du JSON, pas la DB) mais est
    accepté pour rester cohérent avec les autres wrappers Finance qui reçoivent
    la session FastAPI (`Depends(get_session)`).
    """
    from app.services.finance.prices import get_price

    alerts = list_alerts(path=path)
    tickers = {a["ticker"] for a in alerts if a.get("actif", True) and a.get("ticker")}
    prices: dict[str, float] = {}
    for ticker in tickers:
        try:
            price = get_price(ticker)
            prices[ticker] = price if price else None
        except Exception:
            prices[ticker] = None
    prices = {t: p for t, p in prices.items() if p is not None}
    return check_alerts(alerts, prices)
