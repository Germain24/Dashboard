"""Import des relevés de compte Westpac (Australie, PDF).

Format tabulaire DATE|TRANSACTION DESCRIPTION|DEBIT|CREDIT|BALANCE, extrait en
mode layout pypdf : chaque opération commence par « JJ/MM/AA » collé à sa
description (pas d'espace), et se termine — parfois sur une ligne de
continuation indentée — par deux nombres « montant solde ». Le débit/crédit
n'est PAS distinguable par position de colonne (celle-ci dérive avec la
longueur de la description en mode layout) : le montant signé est donc déduit
de la variation de solde (solde − solde précédent), comme pour Desjardins EOP.
La ligne de solde de clôture apparaît parfois hors-séquence dans le flux extrait
(artefact pypdf sur la dernière page) — elle est ignorée sans casser la chaîne
de deltas, qui ne dépend que de l'ordre des VRAIES opérations entre elles.

`parse_westpac` est pur (testable sur le texte extrait en mode layout) ;
`import_westpac_pdf` lit le PDF et alimente le budget. Devise : AUD.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from sqlmodel import Session, select

from app.models.budget import BudgetTransaction
from app.services.budget.transactions import create_transaction

_ROW_START_RE = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{2})(.*)$")
_ONE_NUM_RE = re.compile(r"(\d[\d,]*\.\d{2})\s*$")
_TWO_NUMS_RE = re.compile(r"(\d[\d,]*\.\d{2})\s+(\d[\d,]*\.\d{2})\s*$")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_westpac(text: str) -> list[tuple[dt.date, float, str]]:
    """Extrait les opérations d'un relevé Westpac (texte en mode layout).

    Renvoie `[(date, montant, libellé)]`, montant signé (débit < 0, crédit >
    0), déduit de la variation de solde. La ligne "STATEMENT OPENING BALANCE"
    amorce la chaîne ; "CLOSING BALANCE" est ignorée (résumé, pas une
    opération)."""
    rows: list[str] = []
    for line in text.splitlines():
        if _ROW_START_RE.match(line):
            rows.append(line.strip())
        elif rows and not _ONE_NUM_RE.search(rows[-1]):
            rows[-1] += " " + line.strip()

    out: list[tuple[dt.date, float, str]] = []
    prev: float | None = None
    for row in rows:
        m = _ROW_START_RE.match(row)
        jj, mm, aa, rest = m.groups()
        upper = rest.upper()
        if "OPENING BALANCE" in upper:
            if prev is None:
                one = _ONE_NUM_RE.search(rest)
                if one:
                    prev = _num(one.group(1))
            continue
        if "CLOSING BALANCE" in upper:
            continue  # résumé (position peu fiable en fin de relevé) -> jamais une opération
        two = _TWO_NUMS_RE.search(rest)
        if not two or prev is None:
            continue
        solde = _num(two.group(2))
        montant = round(solde - prev, 2)
        prev = solde
        libelle = re.sub(r"\s+", " ", rest[: two.start()]).strip()
        if not libelle:
            continue
        try:
            d = dt.date(2000 + int(aa), int(mm), int(jj))
        except ValueError:
            continue
        out.append((d, montant, libelle))
    return out


def import_westpac_pdf(
    session: Session, text: str, compte: str = "westpac",
) -> dict[str, Any]:
    """Importe un relevé Westpac déjà extrait en texte (mode layout).
    Idempotent : une opération identique (date, montant, libellé) déjà
    présente sur le compte est ignorée."""
    parsed = parse_westpac(text)

    existing = {
        (t.date, round(t.montant, 2), t.marchand)
        for t in session.exec(
            select(BudgetTransaction).where(BudgetTransaction.compte == compte)
        ).all()
    }
    imported, skipped, categorised = 0, 0, 0
    for date, montant, marchand in parsed:
        key = (date, round(montant, 2), marchand)
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        t = create_transaction(session, date=date, montant=montant, marchand=marchand,
                                compte=compte, devise="AUD")
        imported += 1
        if t.category_id is not None:
            categorised += 1
    return {
        "imported": imported, "skipped": skipped, "categorised": categorised,
        "parsed": len(parsed), "format": "westpac", "compte": compte,
    }
