"""Import des relevés de compte chèque Banque Populaire (PDF).

Format « DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUE » : chaque opération
tient sur une ligne « date_compta libellé date_opération date_valeur montant »,
suivie éventuellement de lignes de référence (à ignorer). Contrairement au
relevé Desjardins EOP, le montant signé est déjà présent sur la ligne (pas
besoin de le déduire d'une variation de solde) — le solde de clôture
(« SOLDE CREDITEUR/DEBITEUR AU JJ/MM/AAAA* ») sert seulement à auto-remplir
le patrimoine.

`parse_banque_populaire` est pur (testable sur le texte extrait en mode
plain) ; `import_banque_populaire_pdf` lit le PDF et alimente le budget.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from sqlmodel import Session, select

from app.models.budget import BudgetTransaction
from app.services.budget.transactions import create_transaction

# Section utile : entre l'en-tête de tableau et le total des mouvements — le
# reste du document (récapitulatif des frais, détail SEPA) répète les mêmes
# opérations dans un format différent et doublonnerait l'import.
_SECTION_RE = re.compile(
    r"VALEURLIBELLE / REFERENCE MONTANT(.*?)TOTAL DES MOUVEMENTS DEBITEURS",
    re.DOTALL,
)
_LINE_RE = re.compile(
    r"^(\d{2})/(\d{2})\s+(.+?)\s+\d{2}/\d{2}\s+\d{2}/\d{2}\s*(-)?\s*(\d[\d ]*,\d{2})"
)
_CLOSING_RE = re.compile(r"SOLDE (CREDITEUR|DEBITEUR) AU (\d{2})/(\d{2})/(\d{4})\*\s*(\d[\d ]*,\d{2})")


def _to_float(montant: str) -> float:
    return float(montant.replace(" ", "").replace(",", "."))


def parse_banque_populaire(text: str) -> list[tuple[dt.date, float, str]]:
    """Extrait les opérations du compte chèque. Renvoie `[(date, montant, libellé)]`,
    montant signé (débit < 0, crédit > 0). L'année est déduite du solde de
    clôture : un mois d'opération postérieur à celui du relevé appartient à
    l'année précédente (cas décembre → janvier)."""
    closing = _CLOSING_RE.search(text)
    if not closing:
        return []
    stmt = dt.date(int(closing.group(4)), int(closing.group(3)), int(closing.group(2)))

    section = _SECTION_RE.search(text)
    if not section:
        return []

    out: list[tuple[dt.date, float, str]] = []
    for line in section.group(1).splitlines():
        m = _LINE_RE.match(line.strip())
        if not m:
            continue
        jour, mois, libelle, signe, montant_s = m.groups()
        montant = _to_float(montant_s)
        if signe:
            montant = -montant
        mois_i = int(mois)
        annee = stmt.year if mois_i <= stmt.month else stmt.year - 1
        try:
            d = dt.date(annee, mois_i, int(jour))
        except ValueError:
            continue
        out.append((d, round(montant, 2), re.sub(r"\s+", " ", libelle).strip()))
    return out


def closing_balance(text: str) -> tuple[dt.date, float] | None:
    """Solde de clôture (date, montant signé) — auto-remplit le patrimoine."""
    m = _CLOSING_RE.search(text)
    if not m:
        return None
    sens, jj, mm, aaaa, montant_s = m.groups()
    montant = _to_float(montant_s)
    if sens == "DEBITEUR":
        montant = -montant
    return dt.date(int(aaaa), int(mm), int(jj)), montant


def import_banque_populaire_pdf(
    session: Session, text: str, compte: str = "banquepopulaire",
) -> dict[str, Any]:
    """Importe un relevé de compte chèque Banque Populaire déjà extrait en texte
    (plain). Idempotent : une opération identique (date, montant, libellé) déjà
    présente sur le compte est ignorée."""
    parsed = parse_banque_populaire(text)

    bal = closing_balance(text)
    if bal is not None:
        try:
            from app.services.finance.account_balances import set_balance
            set_balance(compte, bal[1], devise="EUR", date=bal[0].isoformat())
        except Exception:
            pass  # best-effort : ne jamais casser l'import

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
                                compte=compte, devise="EUR")
        imported += 1
        if t.category_id is not None:
            categorised += 1
    return {
        "imported": imported, "skipped": skipped, "categorised": categorised,
        "parsed": len(parsed), "format": "banque-populaire", "compte": compte,
    }
