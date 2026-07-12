"""CRUD transactions + import CSV broker (Trading 212, Bourse Direct)."""

from __future__ import annotations

import csv
import datetime as dt
import io
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.finance import Transaction


def list_transactions(
    session: Session,
    ticker: Optional[str] = None,
    broker: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    limit: int = 500,
) -> list[Transaction]:
    q = select(Transaction).order_by(Transaction.date.desc())
    if ticker:
        q = q.where(Transaction.ticker == ticker.upper())
    if broker:
        q = q.where(Transaction.broker == broker)
    if date_from:
        q = q.where(Transaction.date >= dt.datetime.combine(date_from, dt.time.min))
    if date_to:
        q = q.where(Transaction.date <= dt.datetime.combine(date_to, dt.time.max))
    return list(session.exec(q.limit(limit)).all())


def get_dividends_summary(session: Session) -> dict:
    """Dividendes reçus (transactions de type 'dividende') : total, par ticker, par mois.

    Montant d'une ligne = quantité × prix_unitaire (montant total versé).
    """
    divs = list(session.exec(
        select(Transaction)
        .where(Transaction.type == "dividende")
        .order_by(Transaction.date.desc())
    ).all())

    def _montant(t: Transaction) -> float:
        return round((t.quantite or 0) * (t.prix_unitaire or 0), 2)

    total = round(sum(_montant(t) for t in divs), 2)

    par_ticker: dict[str, float] = {}
    par_mois: dict[str, float] = {}
    lignes = []
    for t in divs:
        m = _montant(t)
        par_ticker[t.ticker] = round(par_ticker.get(t.ticker, 0) + m, 2)
        mois = t.date.strftime("%Y-%m")
        par_mois[mois] = round(par_mois.get(mois, 0) + m, 2)
        lignes.append({
            "date": t.date.date().isoformat() if hasattr(t.date, "date") else str(t.date),
            "ticker": t.ticker,
            "montant": m,
            "devise": t.devise,
        })

    return {
        "total_recu": total,
        "n_versements": len(divs),
        "par_ticker": par_ticker,
        "par_mois": dict(sorted(par_mois.items())),
        "lignes": lignes,
    }


def create_transaction(session: Session, data: dict) -> Transaction:
    # Passe par le repository (cf. app/repositories/finance.py) pour découpler
    # le service de la persistance SQLModel.
    from app.repositories.finance import TransactionRepository
    tx = TransactionRepository(session).create(data)
    _invalidate_state()
    return tx


def delete_transaction(session: Session, tx_id: int) -> bool:
    from app.repositories.finance import TransactionRepository
    ok = TransactionRepository(session).delete_by_id(tx_id)
    if ok:
        _invalidate_state()
    return ok


def _invalidate_state() -> None:
    """Invalide l'état dérivé du portefeuille après écriture (best-effort)."""
    try:
        from app.services.finance.portfolio_state import invalidate_state
        invalidate_state()
    except Exception:
        pass


# ── Parseurs CSV broker ────────────────────────────────────────────────────

def _parse_trading212_cash_row(row: dict, type_: str) -> Optional[dict]:
    """Ligne de mouvement de cash pur (Deposit/Withdrawal/Interest on cash) --
    pas de ticker/quantité, le montant est dans la colonne "Total". `ticker`
    "CASH" est la convention déjà utilisée par `portfolio_state.py` pour
    exclure ces lignes du lookup de cours (cf. `get_portfolio_state`).
    `quantite=1.0` (et non 0) car `import_csv` écarte les lignes à quantité
    nulle, et `_montant()` (portfolio_state.py) attend soit quantite=1 +
    prix_unitaire=montant, soit quantite=0 + prix_unitaire=montant -- les
    deux marchent, on choisit la forme documentée dans son docstring."""
    return {
        "date": dt.datetime.fromisoformat(row.get("Time", "").replace("Z", "")),
        "ticker": "CASH",
        "broker": "Trading212",
        "type": type_,
        "quantite": 1.0,
        "prix_unitaire": abs(float(row.get("Total", 0) or 0)),
        "devise": str(row.get("Currency (Total)", "EUR")),
        "frais": 0.0,
    }


def _parse_trading212_row(row: dict) -> Optional[dict]:
    """Ligne CSV Trading 212 → dict Transaction.

    Reconnaît aussi les mouvements de cash purs (Deposit/Withdrawal/Interest
    on cash) -- sans eux, `cash_total`/`investi_net` (portfolio_state.py) ne
    voient jamais l'argent réellement déposé et ne comptent que les achats/
    ventes, ce qui fait dériver le cash très négatif (argent "dépensé" sans
    jamais avoir été "reçu").

    Le prix unitaire des achats/ventes/dividendes est dérivé de la colonne
    "Total" (déjà convertie par Trading212 dans la devise du compte, EUR ici)
    plutôt que de "Price / share" (souvent dans la devise NATIVE du titre --
    CAD, USD, DKK…). Utiliser "Price / share" tel quel comme s'il était en EUR
    fait dériver `cash_total`/`pl_latent` de dizaines de milliers d'euros pour
    tout titre non-EUR (ex. Dollarama 206 CAD ≈ 128 EUR/action au vrai taux).
    """
    try:
        action = str(row.get("Action", "")).lower()
        if "deposit" in action:
            return _parse_trading212_cash_row(row, "depot")
        if "withdrawal" in action:
            return _parse_trading212_cash_row(row, "retrait")
        if "interest" in action:
            # Pas un vrai dividende, mais le modèle n'a pas de type "intérêt"
            # dédié -- traité comme un revenu de cash (compte dans
            # dividendes_total / base d'impôt dividendes, approximation
            # raisonnable pour de petits montants d'intérêt sur cash).
            return _parse_trading212_cash_row(row, "dividende")
        if "buy" in action:
            type_ = "achat"
        elif "sell" in action:
            type_ = "vente"
        elif "dividend" in action:
            type_ = "dividende"
        else:
            return None

        ticker = str(row.get("Ticker", "")).strip().upper()
        total_eur = abs(float(row.get("Total", 0) or 0))
        date = dt.datetime.fromisoformat(row.get("Time", "").replace("Z", ""))
        frais = float(row.get("Currency conversion fee", 0) or 0)

        if type_ == "dividende":
            # Montant reçu = Total (EUR) ; quantite=1 pour éviter de mélanger
            # le compte de titres (devise native) avec le montant en EUR.
            return {
                "date": date, "ticker": ticker or "CASH", "broker": "Trading212",
                "type": "dividende", "quantite": 1.0, "prix_unitaire": total_eur,
                "devise": "EUR", "frais": frais,
            }

        qte = float(row.get("No. of shares", 0) or 0)
        prix_unitaire_eur = total_eur / qte if qte else 0.0
        return {
            "date": date, "ticker": ticker, "broker": "Trading212", "type": type_,
            "quantite": qte, "prix_unitaire": prix_unitaire_eur,
            "devise": "EUR", "frais": frais,
        }
    except Exception:
        return None


def _parse_boursedirect_row(row: dict) -> Optional[dict]:
    """Ligne CSV Bourse Direct → dict Transaction."""
    try:
        sens = str(row.get("Sens", "")).upper()
        if "ACHAT" in sens or "A" == sens:
            type_ = "achat"
        elif "VENTE" in sens or "V" == sens:
            type_ = "vente"
        else:
            return None
        date_str = row.get("Date opération", "") or row.get("Date", "")
        try:
            date_ = dt.datetime.strptime(date_str.strip(), "%d/%m/%Y")
        except Exception:
            date_ = dt.datetime.fromisoformat(date_str.strip())
        return {
            "date": date_,
            "ticker": str(row.get("Code ISIN", row.get("Libellé", ""))).strip().upper(),
            "broker": "BoursDirect",
            "type": type_,
            "quantite": float(str(row.get("Quantité", 0)).replace(",", ".") or 0),
            "prix_unitaire": float(str(row.get("Cours", 0)).replace(",", ".") or 0),
            "devise": "EUR",
            "frais": float(str(row.get("Frais", 0)).replace(",", ".") or 0),
        }
    except Exception:
        return None


def _is_duplicate(session: Session, parsed: dict) -> bool:
    """Une transaction est consideree deja importee si broker+ticker+type+date+
    quantite+prix_unitaire correspondent exactement -- evite de dupliquer
    gains/pertes et impot calcule quand un export deja traite est reimporte
    (cas plausible : reexport "tout l'historique" depuis un broker)."""
    existing = session.exec(
        select(Transaction).where(
            Transaction.broker == parsed.get("broker"),
            Transaction.ticker == parsed.get("ticker"),
            Transaction.type == parsed.get("type"),
            Transaction.date == parsed.get("date"),
            Transaction.quantite == parsed.get("quantite"),
            Transaction.prix_unitaire == parsed.get("prix_unitaire"),
        )
    ).first()
    return existing is not None


def import_csv(session: Session, content: str, broker_hint: str = "auto") -> dict:
    """Importe des transactions depuis un CSV broker.

    broker_hint : 'trading212' | 'boursedirect' | 'auto' (détection automatique).
    Retourne {"imported": N, "skipped": N, "errors": [...]}.
    """
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return {"imported": 0, "skipped": 0, "errors": ["CSV vide"]}

    # Détection automatique du broker
    headers = set(rows[0].keys())
    if broker_hint == "auto":
        if "Action" in headers and "No. of shares" in headers:
            broker_hint = "trading212"
        elif "Sens" in headers or "Quantité" in headers:
            broker_hint = "boursedirect"
        else:
            return {"imported": 0, "skipped": 0, "errors": ["Format CSV non reconnu"]}

    parser = _parse_trading212_row if broker_hint == "trading212" else _parse_boursedirect_row
    imported = skipped = 0
    errors: list[str] = []

    for i, row in enumerate(rows):
        parsed = parser(row)
        if not parsed:
            skipped += 1
            continue
        if not parsed.get("ticker") or not parsed.get("quantite") or parsed["quantite"] == 0:
            skipped += 1
            continue
        if _is_duplicate(session, parsed):
            skipped += 1
            continue
        tx = Transaction(**parsed)
        session.add(tx)
        try:
            session.commit()
            imported += 1
        except Exception as e:
            session.rollback()
            errors.append(f"Ligne {i+2}: {e}")
            skipped += 1

    if imported:
        _invalidate_state()
    return {"imported": imported, "skipped": skipped, "errors": errors}
