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
    """Dividendes et interets, sans confondre brut, retenue et net credite."""
    revenues = list(session.exec(
        select(Transaction)
        .where(Transaction.type.in_(["dividende", "interet"]))
        .order_by(Transaction.date.desc())
    ).all())
    divs = [transaction for transaction in revenues if transaction.type == "dividende"]
    interests = [transaction for transaction in revenues if transaction.type == "interet"]

    def _gross(t: Transaction) -> float:
        stored = getattr(t, "montant_brut", None)
        return round(float(stored) if stored is not None else (t.quantite or 0) * (t.prix_unitaire or 0), 2)

    total_brut = round(sum(_gross(t) for t in divs), 2)
    total_retenue = round(sum(float(getattr(t, "retenue_source", 0) or 0) for t in divs), 2)
    total_net = round(total_brut - total_retenue - sum(float(t.frais or 0) for t in divs), 2)
    total_interets = round(
        sum(_gross(t) - float(t.frais or 0) for t in interests), 2
    )

    par_ticker: dict[str, float] = {}
    par_mois: dict[str, float] = {}
    lignes = []
    for t in divs:
        brut = _gross(t)
        retenue = round(float(getattr(t, "retenue_source", 0) or 0), 2)
        net = round(brut - retenue - float(t.frais or 0), 2)
        par_ticker[t.ticker] = round(par_ticker.get(t.ticker, 0) + net, 2)
        mois = t.date.strftime("%Y-%m")
        par_mois[mois] = round(par_mois.get(mois, 0) + net, 2)
        lignes.append({
            "date": t.date.date().isoformat() if hasattr(t.date, "date") else str(t.date),
            "ticker": t.ticker,
            "montant": net,
            "montant_brut": brut,
            "retenue_source": retenue,
            "devise": t.devise,
        })

    return {
        "total_recu": total_net,
        "total_brut": total_brut,
        "total_retenue_source": total_retenue,
        "n_versements": len(divs),
        "interets_recus": total_interets,
        "n_interets": len(interests),
        "revenus_nets": round(total_net + total_interets, 2),
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
    total = abs(float(row.get("Total", 0) or 0))
    return {
        "date": dt.datetime.fromisoformat(row.get("Time", "").replace("Z", "")),
        "ticker": "CASH",
        "broker": "Trading212",
        "type": type_,
        "quantite": 1.0,
        "prix_unitaire": total,
        "devise": str(row.get("Currency (Total)", "EUR")),
        "frais": 0.0,
        "montant_brut": total if type_ in ("dividende", "interet") else None,
        "retenue_source": 0.0,
        "note": f"T212 {row.get('ID')}" if row.get("ID") else None,
    }


def _trading212_amount_eur(row: dict, amount_key: str, currency_key: str) -> float:
    """Convertit une colonne annexe du CSV dans la devise du compte.

    Les exports du compte utilise ici sont en EUR. Pour une retenue exprimee
    dans la devise native, ``Exchange rate`` represente le nombre d'unites de
    cette devise pour un euro (ex. 1,16 USD/EUR), donc le montant est divise
    par ce taux.
    """
    amount = abs(float(row.get(amount_key, 0) or 0))
    if amount == 0:
        return 0.0
    total_currency = str(row.get("Currency (Total)", "EUR") or "EUR").upper()
    amount_currency = str(row.get(currency_key, total_currency) or total_currency).upper()
    if amount_currency == total_currency:
        return round(amount, 8)
    exchange_rate = abs(float(row.get("Exchange rate", 0) or 0))
    if total_currency == "EUR" and exchange_rate > 0:
        return round(amount / exchange_rate, 8)
    return 0.0


def _trading212_fees_eur(row: dict) -> float:
    columns = (
        ("Currency conversion fee", "Currency (Currency conversion fee)"),
        ("French transaction tax", "Currency (French transaction tax)"),
        ("Stamp duty", "Currency (Stamp duty)"),
        ("Stamp duty reserve tax", "Currency (Stamp duty reserve tax)"),
    )
    return round(sum(_trading212_amount_eur(row, amount, currency) for amount, currency in columns), 8)


def _parse_trading212_row(row: dict) -> Optional[dict]:
    """Ligne CSV Trading 212 → dict Transaction.

    Reconnaît aussi les mouvements de cash purs (Deposit/Withdrawal/Interest
    on cash) -- sans eux, `cash_total`/`investi_net` (portfolio_state.py) ne
    voient jamais l'argent réellement déposé et ne comptent que les achats/
    ventes, ce qui fait dériver le cash très négatif (argent "dépensé" sans
    jamais avoir été "reçu").

    Le prix unitaire est reconstruit en EUR depuis ``Total``. Trading 212
    inclut les frais dans Total pour un achat et les retranche pour une vente ;
    on les retire/reajoute avant de stocker le prix brut, puis on les conserve
    separement dans ``frais``. Sans cela, ils etaient comptes deux fois.
    """
    try:
        action = str(row.get("Action", "")).lower()
        if "deposit" in action:
            return _parse_trading212_cash_row(row, "depot")
        if "withdrawal" in action:
            return _parse_trading212_cash_row(row, "retrait")
        if "interest" in action:
            return _parse_trading212_cash_row(row, "interet")
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
        frais = _trading212_fees_eur(row)
        note = f"T212 {row.get('ID')}" if row.get("ID") else None

        if type_ == "dividende":
            retenue = _trading212_amount_eur(
                row, "Withholding tax", "Currency (Withholding tax)"
            )
            # Pour un dividende, ``Total`` est le net credite par T212. La
            # retenue est fournie a part : le brut fiscal est donc leur somme.
            gross_eur = round(total_eur + retenue, 8)
            if "manufactured" in action:
                note = f"{note or 'T212'} [manufactured]"
            return {
                "date": date, "ticker": ticker or "CASH", "broker": "Trading212",
                "type": "dividende", "quantite": 1.0, "prix_unitaire": gross_eur,
                "devise": "EUR", "frais": frais, "montant_brut": gross_eur,
                "retenue_source": retenue, "note": note,
            }

        qte = float(row.get("No. of shares", 0) or 0)
        total_brut = total_eur - frais if type_ == "achat" else total_eur + frais
        prix_unitaire_eur = round(total_brut / qte, 8) if qte else 0.0
        return {
            "date": date, "ticker": ticker, "broker": "Trading212", "type": type_,
            "quantite": qte, "prix_unitaire": prix_unitaire_eur,
            "devise": "EUR", "frais": frais, "montant_brut": None,
            "retenue_source": 0.0, "note": note,
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


def _find_existing(session: Session, parsed: dict) -> Transaction | None:
    """Une transaction est consideree deja importee si broker+ticker+type+date+
    quantite+prix_unitaire correspondent exactement -- evite de dupliquer
    gains/pertes et impot calcule quand un export deja traite est reimporte
    (cas plausible : reexport "tout l'historique" depuis un broker)."""
    exact = session.exec(
        select(Transaction).where(
            Transaction.broker == parsed.get("broker"),
            Transaction.ticker == parsed.get("ticker"),
            Transaction.type == parsed.get("type"),
            Transaction.date == parsed.get("date"),
            Transaction.quantite == parsed.get("quantite"),
        )
    ).first()
    if exact is not None:
        return exact

    # Les anciennes versions importaient "Interest on cash" comme dividende.
    # Cette correspondance permet une migration idempotente par reimport CSV.
    if parsed.get("type") == "interet" and parsed.get("ticker") == "CASH":
        legacy = list(session.exec(
            select(Transaction).where(
                Transaction.broker == parsed.get("broker"),
                Transaction.ticker == "CASH",
                Transaction.type == "dividende",
                Transaction.date == parsed.get("date"),
                Transaction.quantite == parsed.get("quantite"),
            )
        ).all())
        if len(legacy) == 1:
            return legacy[0]

    # Les API de broker et les exports CSV n'emploient pas toujours le meme
    # symbole (ex. SGLN.L cote Yahoo contre SGLN chez Trading 212). Date,
    # sens, broker et quantite identiques forment un repli fiable seulement
    # s'il ne retourne qu'une ligne ; le ticker canonique deja stocke est
    # alors conserve.
    candidates = list(session.exec(
        select(Transaction).where(
            Transaction.broker == parsed.get("broker"),
            Transaction.type == parsed.get("type"),
            Transaction.date == parsed.get("date"),
            Transaction.quantite == parsed.get("quantite"),
        )
    ).all())
    return candidates[0] if len(candidates) == 1 else None


def _is_duplicate(session: Session, parsed: dict) -> bool:
    return _find_existing(session, parsed) is not None


def _update_existing(existing: Transaction, parsed: dict) -> bool:
    changed = False
    for field in (
        "type", "prix_unitaire", "frais", "devise", "montant_brut",
        "retenue_source", "note",
    ):
        incoming = parsed.get(field)
        current = getattr(existing, field, None)
        if isinstance(incoming, float) and isinstance(current, (int, float)):
            equal = abs(float(current) - incoming) <= 1e-9
        else:
            equal = current == incoming
        if not equal:
            setattr(existing, field, incoming)
            changed = True
    return changed


def import_csv(session: Session, content: str, broker_hint: str = "auto") -> dict:
    """Importe des transactions depuis un CSV broker.

    broker_hint : 'trading212' | 'boursedirect' | 'auto' (détection automatique).
    Retourne {"imported": N, "updated": N, "skipped": N, "errors": [...]}.
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
    imported = updated = skipped = 0
    errors: list[str] = []

    for i, row in enumerate(rows):
        parsed = parser(row)
        if not parsed:
            skipped += 1
            continue
        if not parsed.get("ticker") or not parsed.get("quantite") or parsed["quantite"] == 0:
            skipped += 1
            continue
        existing = _find_existing(session, parsed)
        if existing is not None:
            if _update_existing(existing, parsed):
                session.add(existing)
                session.commit()
                updated += 1
            else:
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

    if imported or updated:
        _invalidate_state()
    return {"imported": imported, "updated": updated, "skipped": skipped, "errors": errors}
