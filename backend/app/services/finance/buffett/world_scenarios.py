"""Identification et sérialisation des scénarios de plancher MSCI World."""

from __future__ import annotations

import re

SCENARIOS = {"free": 0.0, "world_25": 0.25, "world_40": 0.40, "world_55": 0.55}
_TILTS = {
    "water", "eau", "technology", "tech", "sector", "quality", "momentum",
    "minimum", "small", "value", "growth", "sri", "esg", "screened",
}


def is_broad_msci_world(*values: object) -> bool:
    text = " ".join(str(value or "") for value in values).casefold()
    if "acwi" in text or not re.search(r"\bmsci\s+world\b", text):
        return False
    return not any(re.search(rf"\b{re.escape(marker)}\b", text) for marker in _TILTS)


def identify_world_tickers(tickers: list[str], metadata: dict[str, dict]) -> set[str]:
    result = set()
    for ticker in tickers:
        info = metadata.get(str(ticker).upper(), {})
        if is_broad_msci_world(info.get("Nom"), info.get("Indice"), info.get("Index")):
            result.add(str(ticker).upper())
    return result


def serialize_allocation(allocation: list[dict]) -> list[dict]:
    fields = ("Ticker", "AnalysisTicker", "Broker", "shares", "eur", "prix", "type", "pie_pct", "Poids total (%)")
    return [{key: row.get(key) for key in fields if key in row} for row in allocation]
