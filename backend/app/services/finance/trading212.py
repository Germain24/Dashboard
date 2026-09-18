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

from sqlmodel import Session, select

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


# Table « Invest account - executed trades » : colonnes ORDER TYPE/EXECUTION
# VENUE/SESSION/FX FEE/... qui suivent VALUE ont une largeur variable (ex.
# "Regular hours" vs "Overnight", "-" pour une case vide) -> non ancrables de
# façon fiable par simple split(). On ancre seulement le préfixe fixe et
# univoque de chaque ligne (jusqu'à VALUE inclus), qui suffit à reconstituer
# une transaction (date, ticker, sens, quantité, prix) ; les frais de la queue
# de ligne ne sont pas extraits (mieux vaut frais=0 qu'un mauvais mapping de
# colonne sur de l'argent réel).
_TRADE_RE = re.compile(
    rf"^(\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}})\s+(\S+)\s+({_ISIN})\s+(\S+)\s+"
    rf"(\d+)\s+(Buy|Sell)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
)


def parse_trading212_trades(text: str) -> list[dict]:
    """Extrait la table « Invest account - executed trades » d'un relevé.

    Renvoie une liste de `{date, ticker, isin, direction, quantity,
    execution_price, devise}` (`direction` = "Buy"/"Sell", `execution_price`
    dans `devise` = devise de l'instrument, ex. USD/GBX). "No data available"
    -> liste vide."""
    out: list[dict] = []
    for line in text.splitlines():
        m = _TRADE_RE.match(line.strip())
        if not m:
            continue
        (ts, instrument, isin, devise, order_id, direction,
         quantity, price, _value) = m.groups()
        out.append({
            "date": dt.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"),
            "ticker": instrument,
            "isin": isin,
            "order_id": order_id,
            "direction": direction,
            "quantity": _num(quantity),
            "execution_price": _num(price),
            "devise": devise,
        })
    return out


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

def _all_statements(dir_: Path | None = None) -> list[Path]:
    """Tous les Activity Statements du dossier -- deux conventions de nom
    coexistent (export mensuel « Activity-Statement-JJ-MM-AAAA-... » et export
    à la demande « ActivityStatement<id>-AAAA-MM-JJ »), donc pas de tri
    lexicographique fiable entre les deux."""
    d = dir_ or _statements_dir()
    if not d.exists():
        return []
    return list(d.rglob("Activity-Statement-*.pdf")) + list(d.rglob("ActivityStatement*.pdf"))


def _latest_statement(dir_: Path | None = None) -> Path | None:
    """Dernier Activity Statement (par date de modification -- les deux
    conventions de nom ne sont pas triables lexicographiquement entre elles)."""
    pdfs = _all_statements(dir_)
    return max(pdfs, key=lambda p: p.stat().st_mtime) if pdfs else None


def _refresh_from_api(compte: str) -> dict | None:
    """Valeur du compte + composition depuis l'API Trading 212.

    Source préférée : elle donne la valeur en direct (et non celle, figée, de
    la fin du dernier relevé) et enregistre au passage le point du jour dans le
    journal d'historique, seule façon de construire une série -- l'API n'expose
    aucun historique de valorisation.
    """
    from app.services.finance import trading212_api as api

    cash = api.fetch_cash()
    total = float(cash.get("total") or 0.0)
    today = dt.date.today().isoformat()

    positions: list[dict] = []
    try:
        by_ticker = {i["ticker"]: i for i in api.load_instruments()}
        symbols = api.symbol_map()
        from app.services.finance.impots_transactions import _to_eur_per_unit
        for pos in api.fetch_portfolio():
            meta = by_ticker.get(pos["ticker"], {})
            devise = str(meta.get("currencyCode") or "EUR")
            qty = float(pos.get("quantity") or 0.0)
            prix_eur = _to_eur_per_unit(float(pos.get("currentPrice") or 0.0), devise)
            positions.append({
                "instrument": symbols.get(pos["ticker"], pos["ticker"]),
                "isin": meta.get("isin"),
                "currency": devise,
                "quantity": qty,
                "value_eur": round(qty * prix_eur, 2),
            })
    except Exception as exc:  # la valeur du compte prime sur le détail
        logger.warning("[trading212] positions API ignorées (%s)", exc)

    from app.services.finance.account_balances import set_balance
    set_balance(compte, total, devise="EUR", date=today, source="api")
    try:
        api.record_snapshot(cash)
    except Exception:
        pass
    parsed = {"account_value": total, "devise": "EUR", "date": today,
              "positions": positions, "invested": cash.get("invested")}
    try:
        pos_path = _positions_path()
        pos_path.parent.mkdir(parents=True, exist_ok=True)
        pos_path.write_text(json.dumps({
            "compte": compte, "date": today, "account_value": total,
            "invested": cash.get("invested"), "source": "api",
            "positions": positions,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return parsed


def refresh_trading212_balance(*, compte: str = "trading212") -> dict | None:
    """Mémorise la valeur du compte Trading212 + sa composition.

    Source par ordre de préférence : l'API (valeur en direct) puis, si la clé
    n'est pas configurée ou que l'appel échoue, le dernier Activity Statement
    PDF. Best-effort : toute erreur renvoie None sans rien casser.
    """
    try:
        from app.services.finance import trading212_api as api
        if api.is_configured():
            try:
                return _refresh_from_api(compte)
            except Exception as exc:  # quota, réseau : on retombe sur les PDF
                logger.warning("[trading212] API indisponible, repli relevé (%s)", exc)
    except Exception:
        pass
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


def _trades_state_path() -> Path:
    return settings.imports_dir / "Finances" / ".trading212_trades_state.json"


def _load_trades_state() -> dict[str, float]:
    try:
        return json.loads(_trades_state_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_trades_state(state: dict[str, float]) -> None:
    try:
        path = _trades_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def import_trading212_trades(session: Session, *, compte: str = "trading212") -> dict:
    """Importe les trades exécutés de TOUS les relevés du dossier (pas
    seulement le dernier, contrairement au solde -- un trade est un
    événement historique daté, chaque relevé mensuel n'en couvre qu'une
    tranche). Idempotent à deux niveaux : un fichier déjà scanné (mtime
    inchangé, mémorisé dans un petit fichier d'état) n'est pas re-parsé --
    évite de re-décoder ~20 PDF à chaque chargement de la page Patrimoine --
    et chaque trade est dédoublonné par ORDER ID (unique par exécution),
    stocké dans `note`. Best-effort : toute erreur renvoie un résultat vide
    plutôt que de casser l'appelant."""
    try:
        from app.models.finance import Transaction
        from app.services.budget.desjardins_pdf import extract_pdf_text
        from app.services.finance.impots_transactions import _to_eur_per_unit
        from app.services.finance.transactions import create_transaction

        state = _load_trades_state()
        existing_orders = {
            t.note for t in session.exec(
                select(Transaction).where(Transaction.broker == compte)
            ).all() if t.note
        }
        imported, skipped, parsed_total = 0, 0, 0
        for pdf_path in _all_statements():
            key = str(pdf_path)
            mtime = pdf_path.stat().st_mtime
            if state.get(key) == mtime:
                continue  # déjà scanné, fichier inchangé depuis
            try:
                trades = parse_trading212_trades(extract_pdf_text(pdf_path.read_bytes()))
            except Exception:
                continue
            parsed_total += len(trades)
            for t in trades:
                note = f"T212 order {t['order_id']}"
                if note in existing_orders:
                    skipped += 1
                    continue
                existing_orders.add(note)
                # `execution_price` est dans la devise NATIVE de l'instrument
                # (USD, ou GBX = pence sterling) -- converti en EUR à
                # l'import, comme le chemin CSV (`_parse_trading212_row`) qui
                # dérive son prix du Total déjà en EUR pour la même raison :
                # `compute_portfolio_state` traite tout `prix_unitaire` comme
                # déjà en EUR sans jamais regarder `.devise`.
                prix_eur = _to_eur_per_unit(t["execution_price"], t["devise"])
                create_transaction(session, {
                    "date": t["date"], "ticker": t["ticker"], "broker": compte,
                    "type": "achat" if t["direction"] == "Buy" else "vente",
                    "quantite": t["quantity"], "prix_unitaire": prix_eur,
                    "devise": "EUR", "frais": 0.0, "note": note,
                })
                imported += 1
            state[key] = mtime
        _save_trades_state(state)
        return {"imported": imported, "skipped": skipped, "parsed": parsed_total}
    except Exception as exc:
        logger.warning("[trading212] import des trades ignoré (%s)", exc)
        return {"imported": 0, "skipped": 0, "parsed": 0}
