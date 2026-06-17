"""Import des relevés Desjardins en PDF — carte Mastercard ET compte chèque (#256).

Deux formats détectés automatiquement, après déballage éventuel d'une enveloppe
Java sérialisée (`_unwrap_pdf`) :
- Carte Mastercard : pypdf concatène les transactions, on les délimite sur leur
  préfixe de date (cf. `parse_desjardins_mastercard`).
- Compte chèque (EOP) : tableau extrait en mode layout, montant signé déduit de
  la variation de solde (cf. `parse_desjardins_eop`) ; revenus (Paie…) inclus,
  transferts internes et paiements de la carte exclus.

pypdf concatène toutes les transactions sur une même ligne, sans espace dans la
date (« 24122412PATISSERIE… QC 2,00 % 15,40 »). On délimite donc chaque
transaction sur son préfixe de date JJMMJJMM (8 chiffres suivis d'une lettre,
avec jours ≤ 31 et mois ≤ 12 — ce qui écarte les dates d'en-tête en JJMMAAAA),
puis on lit la remise « X,XX % » et le montant. Les paiements (« PAIEMENT
CAISSE … CR ») n'ont pas de remise et sont donc naturellement exclus.

`parse_desjardins_mastercard` est pur (testable sur le texte extrait) ;
`import_desjardins_pdf` lit le PDF et alimente le budget (catégorisation #115).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from sqlmodel import Session, select

from app.models.budget import BudgetTransaction
from app.services.budget.transactions import create_transaction

_PREFIX_RE = re.compile(r"(\d{2})(\d{2})(\d{2})(\d{2})(?=[A-Za-zÀ-ÿ])")
_AMOUNT_RE = re.compile(r"(\d{1,2},\d{2})\s*%\s+(\d{1,3}(?:[ ]\d{3})*,\d{2})")
_RELEVE_RE = re.compile(r"DATE DU RELEV.{0,3}?(\d{2})(\d{2})(\d{4})")


def _to_float(montant: str) -> float:
    return float(montant.replace(" ", "").replace(",", "."))


def _valid_dates(jt: int, mt: int, ji: int, mi: int) -> bool:
    return 1 <= jt <= 31 and 1 <= mt <= 12 and 1 <= ji <= 31 and 1 <= mi <= 12


def parse_desjardins_mastercard(text: str) -> list[tuple[dt.date, float, str]]:
    """Extrait les achats (débits) d'un relevé Mastercard Desjardins.

    Renvoie ``[(date, montant<0, marchand)]``. L'année est déduite de la date du
    relevé : une transaction postérieure au relevé appartient à l'année passée
    (cas décembre→janvier). Les paiements (sans remise %) sont exclus.
    """
    rel = _RELEVE_RE.search(text)
    if not rel:
        return []
    stmt = dt.date(int(rel.group(3)), int(rel.group(2)), int(rel.group(1)))

    prefixes = [
        pm for pm in _PREFIX_RE.finditer(text)
        if _valid_dates(int(pm.group(1)), int(pm.group(2)), int(pm.group(3)), int(pm.group(4)))
    ]

    out: list[tuple[dt.date, float, str]] = []
    for i, pm in enumerate(prefixes):
        jt, mt = int(pm.group(1)), int(pm.group(2))
        end = prefixes[i + 1].start() if i + 1 < len(prefixes) else len(text)
        chunk = text[pm.end():end]
        am = _AMOUNT_RE.search(chunk)
        if not am:
            continue  # paiement (CR, sans remise) ou ligne non-transaction → exclu
        marchand = re.sub(r"\s+", " ", chunk[: am.start()]).strip()
        if not marchand:
            continue
        try:
            d = dt.date(stmt.year, mt, jt)
        except ValueError:
            continue
        if d > stmt:  # transaction de l'année précédente (décembre → janvier)
            try:
                d = dt.date(stmt.year - 1, mt, jt)
            except ValueError:
                continue
        out.append((d, -_to_float(am.group(2)), marchand))
    return out


# ─── Relevé de compte chèque (EOP) ───────────────────────────────────────────
# Format différent : tableau Date | Code | Description | Frais | Retrait | Dépôt |
# Solde. pypdf en mode "layout" aligne les colonnes ; le DERNIER nombre de chaque
# ligne est le solde courant → le montant signé = solde − solde_précédent (dépôt
# positif, retrait négatif), ce qui se réconcilie tout seul. Les virements internes
# (épargne/placement) sont exclus (ni revenu ni dépense).

_EOP_MONTHS = {
    "JAN": 1, "FEV": 2, "FV": 2, "MAR": 3, "AVR": 4, "MAI": 5, "JUN": 6, "JUIN": 6,
    "JUL": 7, "JUIL": 7, "AOU": 8, "AO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12, "DC": 12,
}
_EOP_AMT = re.compile(r"\d[\d \xa0]*\.\d{2}")
_EOP_LINE = re.compile(r"^\s*(\d{1,2})\s+(\S{3})([A-Z]{2,4})\s+(.+)$")
# À exclure du suivi : transferts internes chèque ↔ épargne/placement, et
# paiements de la carte Mastercard (déjà représentés par les achats détaillés du
# relevé carte → éviter le double comptage).
_EOP_SKIP = re.compile(
    r"Virement.*Acc.*\bET\b|Virement automatique au compte|Remises?\s*Mastercard",
    re.IGNORECASE,
)


def _eop_num(s: str) -> float:
    return float(s.replace(" ", "").replace("\xa0", ""))


def parse_desjardins_eop(text: str) -> list[tuple[dt.date, float, str]]:
    """Extrait les opérations d'un relevé de compte chèque Desjardins (EOP).

    `text` doit être extrait en mode layout. Renvoie `[(date, montant, libellé)]`
    avec montant signé (dépôt > 0, retrait < 0) déduit de la variation de solde.
    Les transferts internes (vers épargne/placement) sont exclus.
    """
    text = re.split(r"COMPTE D'EPARGNE", text)[0]  # ignore la section épargne
    ym = re.search(r"(20\d{2})", text)
    msr = re.search(r"Solde report\S*\s+([\d \xa0]+\.\d{2})", text)
    if not ym or not msr:
        return []
    year = int(ym.group(1))
    prev = _eop_num(msr.group(1))

    out: list[tuple[dt.date, float, str]] = []
    for line in text.splitlines():
        m = _EOP_LINE.match(line)
        if not m:
            continue
        amts = _EOP_AMT.findall(m.group(4))
        mon = _EOP_MONTHS.get(re.sub(r"[^A-Z]", "", m.group(2).upper()))
        if not amts or not mon:
            continue
        solde = _eop_num(amts[-1])
        montant = round(solde - prev, 2)
        prev = solde  # le solde évolue même pour les lignes exclues
        rest = m.group(4)
        marchand = re.sub(r"\s+", " ", rest[: rest.find(amts[0])]).strip()
        if not marchand or _EOP_SKIP.search(marchand):
            continue
        try:
            d = dt.date(year, mon, int(m.group(1)))
        except ValueError:
            continue
        out.append((d, montant, marchand))
    return out


def _unwrap_pdf(data: bytes) -> bytes | None:
    """Renvoie les octets PDF de `data`.

    Certains relevés sont stockés dans une enveloppe Java sérialisée (en-tête
    `\\xac\\xed`) contenant le PDF comme byte[]. On extrait alors `%PDF-…%%EOF`.
    Renvoie None si aucun PDF n'est trouvé.
    """
    if data[:5] == b"%PDF-":
        return data
    start = data.find(b"%PDF-")
    end = data.rfind(b"%%EOF")
    if start != -1 and end != -1:
        return data[start: end + 5]
    return None


def looks_like_pdf(data: bytes) -> bool:
    """True si `data` est un PDF (éventuellement emballé dans une enveloppe)."""
    return _unwrap_pdf(data) is not None


def extract_pdf_text(data: bytes, *, layout: bool = False) -> str:
    """Texte concaténé de toutes les pages d'un PDF (via pypdf, mode layout opt.)."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    mode = "layout" if layout else "plain"
    return "\n".join(page.extract_text(extraction_mode=mode) or "" for page in reader.pages)


def import_desjardins_pdf(
    session: Session, data: bytes, compte: str | None = None,
) -> dict[str, Any]:
    """Importe un relevé Desjardins (PDF) : carte Mastercard OU compte chèque (EOP).

    Détecte le format, déballe l'enveloppe Java si besoin, et alimente le budget
    (catégorisation #115). Idempotent : une transaction identique (date, montant,
    marchand) déjà présente sur le compte est ignorée (réimport sans doublon).
    """
    pdf = _unwrap_pdf(data)
    if pdf is None:
        return {"imported": 0, "skipped": 0, "categorised": 0, "parsed": 0, "format": "inconnu"}
    plain = extract_pdf_text(pdf)
    # "TRANSACTIONS COURANTES" est propre au relevé carte ; le mot "MASTERCARD"
    # apparaît aussi sur le compte chèque (lignes de paiement de la carte).
    if "TRANSACTIONS COURANTES" in plain.upper():
        parsed = parse_desjardins_mastercard(plain)
        fmt = "desjardins-mc"
    else:
        parsed = parse_desjardins_eop(extract_pdf_text(pdf, layout=True))
        fmt = "desjardins-eop"
    compte = compte or fmt
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
        t = create_transaction(session, date=date, montant=montant, marchand=marchand, compte=compte)
        imported += 1
        if t.category_id is not None:
            categorised += 1
    return {
        "imported": imported, "skipped": skipped, "categorised": categorised,
        "parsed": len(parsed), "format": fmt, "compte": compte,
    }
