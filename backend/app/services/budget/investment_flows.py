"""Flux nets vers les plateformes d'investissement.

Le total se fonde sur les apports et retraits externes, pas sur les achats et
ventes de titres qui restent à l'intérieur d'un compte de courtage. Les flux
bancaires et ceux du courtier sont rapprochés mouvement par mouvement pour
éviter de compter deux fois un même dépôt ou retrait.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlmodel import Session, select

from app.models.budget import BudgetCategory, BudgetTransaction
from app.models.finance import Transaction as FinanceTransaction


@dataclass(frozen=True)
class InvestmentPlatform:
    key: str
    name: str
    asset_class: str
    patterns: tuple[str, ...]


PLATFORMS = (
    InvestmentPlatform("binance", "Binance", "crypto", (r"\bbinance\b",)),
    InvestmentPlatform("kraken", "Kraken", "crypto", (r"\bkraken\b", r"\bpayward\b")),
    InvestmentPlatform("realt", "RealT", "real_estate", (r"\brealt(?:oken)?(?:\.co)?\b",)),
    InvestmentPlatform(
        "trading212",
        "Trading 212",
        "brokerage",
        (r"\btrading\s*212\b", r"\btradding\s*212\b", r"\bt212\b"),
    ),
    InvestmentPlatform("degiro", "DEGIRO", "brokerage", (r"\bdegiro\b",)),
    InvestmentPlatform(
        "ibkr", "IBKR", "brokerage", (r"\bibkr\b", r"\binteractive\s+brokers?\b")
    ),
    InvestmentPlatform(
        "bourse_direct", "Bourse Direct", "brokerage", (r"\bbourse\s*direct\b", r"\bboursedirect\b")
    ),
    InvestmentPlatform("coinbase", "Coinbase", "crypto", (r"\bcoinbase\b",)),
    InvestmentPlatform("shakepay", "Shakepay", "crypto", (r"\bshakepay\b",)),
    InvestmentPlatform("crypto_com", "Crypto.com", "crypto", (r"\bcrypto[.\s]*com\b",)),
    InvestmentPlatform("newton", "Newton", "crypto", (r"\bnewton\b",)),
    InvestmentPlatform("bitstamp", "Bitstamp", "crypto", (r"\bbitstamp\b",)),
    InvestmentPlatform("bitbuy", "Bitbuy", "crypto", (r"\bbitbuy\b",)),
    InvestmentPlatform("bitpanda", "Bitpanda", "crypto", (r"\bbitpanda\b",)),
    InvestmentPlatform("bitvavo", "Bitvavo", "crypto", (r"\bbitvavo\b",)),
    InvestmentPlatform("bybit", "Bybit", "crypto", (r"\bbybit\b",)),
    InvestmentPlatform("okx", "OKX", "crypto", (r"\bokx\b",)),
    InvestmentPlatform("kucoin", "KuCoin", "crypto", (r"\bkucoin\b",)),
    InvestmentPlatform("nexo", "Nexo", "crypto", (r"\bnexo\b",)),
    InvestmentPlatform("metamask", "MetaMask", "crypto", (r"\bmetamask\b",)),
    InvestmentPlatform("wealthsimple", "Wealthsimple", "brokerage", (r"\bwealthsimple\b",)),
    InvestmentPlatform("questrade", "Questrade", "brokerage", (r"\bquestrade\b",)),
    InvestmentPlatform("qtrade", "Qtrade", "brokerage", (r"\bqtrade\b",)),
    InvestmentPlatform("disnat", "Disnat", "brokerage", (r"\bdisnat\b",)),
    InvestmentPlatform("trade_republic", "Trade Republic", "brokerage", (r"\btrade\s*republic\b",)),
    InvestmentPlatform("etoro", "eToro", "brokerage", (r"\betoro\b",)),
    InvestmentPlatform("robinhood", "Robinhood", "brokerage", (r"\brobinhood\b",)),
    InvestmentPlatform("fidelity", "Fidelity", "brokerage", (r"\bfidelity\b",)),
)

_COMPILED_PATTERNS = tuple(
    (platform, tuple(re.compile(pattern, re.IGNORECASE) for pattern in platform.patterns))
    for platform in PLATFORMS
)
_GENERIC_INVESTMENT = InvestmentPlatform(
    "other_investments", "Autres placements", "other", ()
)
_DEPOSIT_TYPES = {"depot", "deposit", "versement", "cash_in"}
_WITHDRAWAL_TYPES = {"retrait", "withdrawal", "cash_out"}


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold()


def identify_platform(text: object) -> InvestmentPlatform | None:
    """Associe un libellé bancaire ou un nom de broker à une plateforme connue."""
    normalized = _normalize(text)
    for platform, patterns in _COMPILED_PATTERNS:
        if any(pattern.search(normalized) for pattern in patterns):
            return platform
    return None


def default_investment_category_id(session: Session, text: object) -> int | None:
    """Catégorise automatiquement un flux identifié, sans écraser les règles perso."""
    platform = identify_platform(text)
    if platform is None:
        return None
    name = "Cryptoactifs" if platform.asset_class == "crypto" else "Placements"
    category = session.exec(select(BudgetCategory).where(BudgetCategory.nom == name)).first()
    return category.id if category else None


def _as_date(value: object) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return None


def _in_range(value: object, from_date: dt.date | None, to_date: dt.date | None) -> bool:
    date = _as_date(value)
    return date is not None and (from_date is None or date >= from_date) and (
        to_date is None or date <= to_date
    )


def _is_investment_category(category_id: object, categories: dict[int, BudgetCategory]) -> bool:
    try:
        current = categories.get(int(category_id))
    except (TypeError, ValueError):
        return False
    visited: set[int] = set()
    while current and current.id is not None and current.id not in visited:
        if _normalize(current.nom) == "investissements & epargne":
            return True
        visited.add(current.id)
        current = categories.get(current.parent_id) if current.parent_id is not None else None
    return False


def _finance_amount(transaction: object) -> float:
    quantity = float(getattr(transaction, "quantite", 0) or 0)
    unit_price = float(getattr(transaction, "prix_unitaire", 0) or 0)
    return abs(quantity * unit_price if quantity else unit_price)


def _movement_direction(transaction_type: object) -> str | None:
    normalized = _normalize(transaction_type)
    if normalized in _DEPOSIT_TYPES:
        return "deposit"
    if normalized in _WITHDRAWAL_TYPES:
        return "withdrawal"
    return None


def _bank_ledger_match(bank_transaction: object, finance_transaction: object) -> tuple[int, float] | None:
    """Retourne un score si deux lignes représentent probablement le même flux."""
    bank_amount = abs(float(getattr(bank_transaction, "montant", 0) or 0))
    finance_amount = _finance_amount(finance_transaction)
    if bank_amount == 0 or finance_amount == 0:
        return None
    bank_direction = "deposit" if float(getattr(bank_transaction, "montant", 0) or 0) < 0 else "withdrawal"
    if bank_direction != _movement_direction(getattr(finance_transaction, "type", "")):
        return None

    bank_date = _as_date(getattr(bank_transaction, "date", None))
    finance_date = _as_date(getattr(finance_transaction, "date", None))
    if bank_date is None or finance_date is None:
        return None
    day_gap = abs((bank_date - finance_date).days)

    bank_currency = str(getattr(bank_transaction, "devise", "CAD") or "CAD").upper()
    finance_currency = str(getattr(finance_transaction, "devise", "EUR") or "EUR").upper()
    ratio = bank_amount / finance_amount
    if bank_currency == finance_currency:
        ratio_error = abs(ratio - 1)
        return (day_gap, ratio_error) if day_gap <= 3 and ratio_error <= 0.03 else None

    # Les relevés Wise sont normalisés en CAD, alors que les relevés de courtier
    # sont souvent en EUR. Une fenêtre large couvre les frais de change; la date
    # doit alors correspondre au même jour ou au jour de comptabilisation voisin.
    cad_eur = (bank_currency, finance_currency) == ("CAD", "EUR")
    eur_cad = (bank_currency, finance_currency) == ("EUR", "CAD")
    if cad_eur or eur_cad:
        expected_ratio = 1.6 if cad_eur else 1 / 1.6
        lower, upper = (1.25, 1.9) if cad_eur else (1 / 1.9, 1 / 1.25)
        if day_gap <= 1 and lower <= ratio <= upper:
            return day_gap, abs(ratio - expected_ratio)
    return None


def build_investment_flow_summary(
    bank_transactions: Iterable[object],
    finance_transactions: Iterable[object],
    categories: Iterable[BudgetCategory],
    *,
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
) -> dict:
    """Calcule les apports nets par plateforme et devise sans compter les mêmes flux deux fois.

    Les mouvements bancaires qui correspondent à un dépôt/retrait de plateforme
    sont rapprochés un à un par plateforme, sens, date et montant. Les lignes
    bancaires non rapprochées restent comptées afin de conserver les mouvements
    présents dans un seul des deux historiques. Les doublons d'import strictement
    identiques sont écartés. Les achats, ventes, dividendes et intérêts sont exclus.
    """
    bank_rows = list(bank_transactions)
    finance_rows = list(finance_transactions)
    category_by_id = {int(category.id): category for category in categories if category.id is not None}

    platform_ledger: list[tuple[InvestmentPlatform, object]] = []
    observed_platforms: set[str] = set()
    exact_ledger_keys: set[tuple] = set()
    duplicate_ledger_rows = 0
    for transaction in finance_rows:
        movement_type = _normalize(getattr(transaction, "type", ""))
        if _movement_direction(movement_type) is None:
            continue
        platform = identify_platform(
            f"{getattr(transaction, 'broker', '')} {getattr(transaction, 'note', '')}"
        )
        if platform is None:
            continue
        exact_key = (
            platform.key,
            movement_type,
            _as_date(getattr(transaction, "date", None)),
            str(getattr(transaction, "ticker", "") or "").casefold(),
            round(float(getattr(transaction, "quantite", 0) or 0), 8),
            round(float(getattr(transaction, "prix_unitaire", 0) or 0), 8),
            str(getattr(transaction, "devise", "EUR") or "EUR").upper(),
            _normalize(getattr(transaction, "note", "")),
        )
        if exact_key in exact_ledger_keys:
            if _in_range(getattr(transaction, "date", None), from_date, to_date):
                duplicate_ledger_rows += 1
            continue
        exact_ledger_keys.add(exact_key)
        observed_platforms.add(platform.key)
        platform_ledger.append((platform, transaction))

    bank_candidates: list[tuple[InvestmentPlatform, object, str]] = []
    exact_bank_keys: set[tuple] = set()
    duplicate_bank_rows = 0
    for transaction in bank_rows:
        description = " ".join(
            str(getattr(transaction, name, "") or "")
            for name in ("marchand", "description", "compte")
        )
        platform = identify_platform(description)
        source = "bank"
        if platform is None and _is_investment_category(
            getattr(transaction, "category_id", None), category_by_id
        ):
            platform = _GENERIC_INVESTMENT
            source = "category"
        if platform is None:
            continue
        if platform.key != _GENERIC_INVESTMENT.key:
            observed_platforms.add(platform.key)
        exact_key = (
            platform.key,
            _as_date(getattr(transaction, "date", None)),
            str(getattr(transaction, "compte", "") or "").casefold(),
            round(float(getattr(transaction, "montant", 0) or 0), 2),
            str(getattr(transaction, "devise", "CAD") or "CAD").upper(),
            _normalize(getattr(transaction, "marchand", "")),
            _normalize(getattr(transaction, "description", "")),
        )
        if exact_key in exact_bank_keys:
            if _in_range(getattr(transaction, "date", None), from_date, to_date):
                duplicate_bank_rows += 1
            continue
        exact_bank_keys.add(exact_key)
        bank_candidates.append((platform, transaction, source))

    # Rapprochement un à un; garder les lignes non appariées pour ne pas perdre
    # un retrait ou un dépôt qui n'apparaît que dans l'un des deux relevés.
    matched_bank_indices: set[int] = set()
    matched_bank_rows = 0
    platform_keys = {platform.key for platform, _ in platform_ledger}
    for platform_key in platform_keys:
        bank_for_platform = [
            (index, row)
            for index, (platform, row, _source) in enumerate(bank_candidates)
            if platform.key == platform_key
        ]
        ledger_for_platform = [
            row for platform, row in platform_ledger if platform.key == platform_key
        ]
        candidates: list[tuple[int, float, int, int]] = []
        for bank_index, bank_transaction in bank_for_platform:
            if not _in_range(getattr(bank_transaction, "date", None), from_date, to_date):
                continue
            for ledger_index, finance_transaction in enumerate(ledger_for_platform):
                if not _in_range(getattr(finance_transaction, "date", None), from_date, to_date):
                    continue
                score = _bank_ledger_match(bank_transaction, finance_transaction)
                if score is not None:
                    candidates.append((*score, bank_index, ledger_index))
        used_ledger_indices: set[int] = set()
        for _day_gap, _amount_error, bank_index, ledger_index in sorted(candidates):
            if bank_index in matched_bank_indices or ledger_index in used_ledger_indices:
                continue
            matched_bank_indices.add(bank_index)
            used_ledger_indices.add(ledger_index)
            matched_bank_rows += 1

    selected: list[tuple[InvestmentPlatform, object, str, str, float]] = []
    included_bank_rows = 0
    included_platform_rows = 0
    cross_account_seen: dict[tuple, set[str]] = defaultdict(set)
    duplicate_interaccount_rows = 0

    def cross_account_key(platform: InvestmentPlatform, transaction: object) -> tuple:
        amount = float(getattr(transaction, "montant", 0) or 0)
        return (
            platform.key,
            _as_date(getattr(transaction, "date", None)),
            round(abs(amount), 2),
            str(getattr(transaction, "devise", "CAD") or "CAD").upper(),
            amount < 0,
        )

    # Les lignes de deux comptes pour lesquelles le même mouvement plateforme
    # a été rapproché sont déjà couvertes par la même entrée du ledger. On garde
    # ces comptes comme références pour écarter une copie bancaire non appariée.
    for index in matched_bank_indices:
        platform, transaction, _source = bank_candidates[index]
        if platform.key == _GENERIC_INVESTMENT.key:
            continue
        cross_account_seen[cross_account_key(platform, transaction)].add(
            str(getattr(transaction, "compte", "") or "").casefold()
        )

    for index, (platform, transaction, source) in enumerate(bank_candidates):
        if index in matched_bank_indices:
            continue
        if not _in_range(getattr(transaction, "date", None), from_date, to_date):
            continue
        bank_amount = float(getattr(transaction, "montant", 0) or 0)
        if bank_amount == 0:
            continue
        if platform.key != _GENERIC_INVESTMENT.key:
            account = str(getattr(transaction, "compte", "") or "").casefold()
            accounts = cross_account_seen[cross_account_key(platform, transaction)]
            if accounts and account not in accounts:
                duplicate_interaccount_rows += 1
                accounts.add(account)
                continue
            accounts.add(account)
        currency = str(getattr(transaction, "devise", "CAD") or "CAD").upper()
        # Les relevés bancaires stockent une sortie en négatif; pour le calcul
        # net, elle devient un apport positif. Une entrée depuis la plateforme
        # réduit le net investi.
        selected.append((platform, transaction, source, currency, -bank_amount))
        included_bank_rows += 1

    for platform, transaction in platform_ledger:
        observed_platforms.add(platform.key)
        if not _in_range(getattr(transaction, "date", None), from_date, to_date):
            continue
        movement_type = _normalize(getattr(transaction, "type", ""))
        amount = _finance_amount(transaction)
        if amount == 0:
            continue
        signed_amount = amount if _movement_direction(movement_type) == "deposit" else -amount
        currency = str(getattr(transaction, "devise", "EUR") or "EUR").upper()
        selected.append((platform, transaction, "platform", currency, signed_amount))
        included_platform_rows += 1

    by_platform_currency: dict[tuple[str, str], dict] = {}
    by_currency: dict[str, dict] = {}
    for platform, _transaction, source, currency, signed_amount in selected:
        key = (platform.key, currency)
        row = by_platform_currency.setdefault(
            key,
            {
                "plateforme": platform.name,
                "classe": platform.asset_class,
                "devise": currency,
                "versements": 0.0,
                "retraits": 0.0,
                "net": 0.0,
                "mouvements": 0,
                "source": source,
            },
        )
        if row["source"] != source:
            row["source"] = "mixed"
        total = by_currency.setdefault(
            currency,
            {"devise": currency, "versements": 0.0, "retraits": 0.0, "net": 0.0, "mouvements": 0},
        )
        if signed_amount >= 0:
            row["versements"] += signed_amount
            total["versements"] += signed_amount
        else:
            row["retraits"] += -signed_amount
            total["retraits"] += -signed_amount
        row["net"] += signed_amount
        row["mouvements"] += 1
        total["net"] += signed_amount
        total["mouvements"] += 1

    missing_platforms = [
        platform.name for platform in PLATFORMS if platform.key not in observed_platforms
    ]
    platforms = sorted(
        by_platform_currency.values(),
        key=lambda row: (row["plateforme"].casefold(), row["devise"]),
    )
    totals = sorted(by_currency.values(), key=lambda row: row["devise"])
    for row in platforms + totals:
        for key in ("versements", "retraits", "net"):
            row[key] = round(row[key], 2)

    return {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "plateformes": platforms,
        "totaux_par_devise": totals,
        "plateformes_sans_historique": missing_platforms,
        "mouvements_bancaires_comptes": included_bank_rows,
        "mouvements_plateformes_comptes": included_platform_rows,
        "mouvements_bancaires_ecartes": (
            matched_bank_rows + duplicate_bank_rows + duplicate_interaccount_rows
        ),
        "mouvements_bancaires_associes_plateforme": matched_bank_rows,
        "doublons_bancaires_ecartes": duplicate_bank_rows,
        "doublons_bancaires_intercomptes_ecartes": duplicate_interaccount_rows,
        "doublons_plateformes_ecartes": duplicate_ledger_rows,
        "regle_dedoublonnage": (
            "Les lignes bancaires sont rapprochées une à une avec les dépôts/retraits de plateforme "
            "par nom, sens, date et montant; les lignes non rapprochées restent incluses. "
            "Les doublons exacts d'import sont écartés."
        ),
    }


def get_investment_flow_summary(
    session: Session,
    *,
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
) -> dict:
    bank_transactions = session.exec(select(BudgetTransaction)).all()
    finance_transactions = session.exec(
        select(FinanceTransaction).where(
            FinanceTransaction.type.in_(sorted(_DEPOSIT_TYPES | _WITHDRAWAL_TYPES))
        )
    ).all()
    categories = session.exec(select(BudgetCategory)).all()
    return build_investment_flow_summary(
        bank_transactions,
        finance_transactions,
        categories,
        from_date=from_date,
        to_date=to_date,
    )
