"""Parseur des relevés Trading212 (Activity Statement PDF).

Le dernier relevé contient un snapshot complet : « Account value » (valeur du
compte = positions + cash en fin de période) et le tableau « Open positions »
(composition : instrument, ISIN, quantité, valeur en EUR). On s'en sert pour
auto-remplir la valeur du compte-titres Trading212 dans le patrimoine (comme
l'auto-solde Desjardins) et exposer sa composition.

`parse_trading212_statement` est pur (testable sur le texte) ; le rafraîchissement
lit le dernier PDF du dossier et persiste la valeur (best-effort).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

def _statements_dir() -> Path:
    """Dossier où l'utilisateur dépose ses Activity Statements (1 par mois).
    Résolu à l'appel pour respecter un imports_dir monkeypatché en test."""
    return settings.imports_dir / "Finances" / "Releve" / "Tradding212"


def _positions_path() -> Path:
    return settings.imports_dir / "Finances" / "trading212_positions.json"

# Ligne de position : TICKER ISIN(12) DEVISE QUANTITÉ … €return €valeur
_ISIN = r"[A-Z]{2}[A-Z0-9]{9}[0-9]"
_POSITION_RE = re.compile(
    rf"^(\S+)\s+({_ISIN})\s+(\S+)\s+([\d.]+)\s+.*€(-?[\d.,]+)\s*$"
)


def _num(s: str) -> float:
    return float(s.replace(",", ""))   # le séparateur décimal Trading212 est le point


def parse_trading212_statement(text: str) -> dict:
    """Extrait {account_value, devise, date, positions[]} d'un relevé Trading212.

    `date` = fin de la période couverte (YYYY-MM-DD) si trouvée. `positions` :
    liste {instrument, isin, currency, quantity, value_eur}.
    """
    av = re.search(r"Account value\s*€?\s*([\d.,]+)", text)
    account_value = _num(av.group(1)) if av else None

    date = None
    d = re.search(r"to\s+(\d{2})\.(\d{2})\.(\d{4})", text)
    if d:
        date = f"{d.group(3)}-{d.group(2)}-{d.group(1)}"

    positions: list[dict] = []
    in_pos = False
    for raw in text.splitlines():
        s = raw.strip()
        if s == "Open positions":
            in_pos = True
            continue
        if not in_pos:
            continue
        if re.match(r"^\d+/\d+$", s) or s.lower().startswith("invest account"):
            break  # fin de la section (saut de page / section suivante)
        m = _POSITION_RE.match(s)
        if m:
            positions.append({
                "instrument": m.group(1), "isin": m.group(2), "currency": m.group(3),
                "quantity": _num(m.group(4)), "value_eur": _num(m.group(5)),
            })
    return {"account_value": account_value, "devise": "EUR", "date": date, "positions": positions}


# ── Rafraîchissement depuis le dossier (best-effort) ─────────────────────────

def _latest_statement(dir_: Path | None = None) -> Path | None:
    """Dernier Activity Statement (nom horodaté → tri lexicographique)."""
    d = dir_ or _statements_dir()
    if not d.exists():
        return None
    pdfs = sorted(d.rglob("Activity-Statement-*.pdf"))
    return pdfs[-1] if pdfs else None


def refresh_trading212_balance(*, compte: str = "trading212") -> dict | None:
    """Lit le dernier relevé Trading212 et mémorise la valeur du compte + la
    composition. Idempotent (ne re-parse pas si le dernier relevé est inchangé).
    Best-effort : toute erreur renvoie None sans rien casser.
    """
    try:
        pdf = _latest_statement()
        if pdf is None:
            return None
        from app.services.finance.account_balances import get_balances, set_balance
        if get_balances().get(compte, {}).get("source") == pdf.name:
            return None  # déjà à jour
        from app.services.budget.desjardins_pdf import extract_pdf_text
        parsed = parse_trading212_statement(extract_pdf_text(pdf.read_bytes()))
        if parsed["account_value"] is None:
            return None
        set_balance(compte, parsed["account_value"], devise=parsed["devise"],
                    date=parsed["date"], source=pdf.name)
        try:
            pos_path = _positions_path()
            pos_path.parent.mkdir(parents=True, exist_ok=True)
            pos_path.write_text(json.dumps({
                "compte": compte, "date": parsed["date"],
                "account_value": parsed["account_value"],
                "positions": parsed["positions"],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return parsed
    except Exception as exc:
        logger.warning("[trading212] rafraîchissement ignoré (%s)", exc)
        return None
