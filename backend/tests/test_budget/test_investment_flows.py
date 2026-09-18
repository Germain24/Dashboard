import datetime as dt
from types import SimpleNamespace

from app.services.budget.categories import seed_categories
from app.services.budget.transactions import create_transaction
from app.services.budget.investment_flows import (
    build_investment_flow_summary,
    identify_platform,
)


def _budget_tx(
    amount,
    merchant,
    *,
    date=dt.date(2026, 1, 1),
    category_id=None,
    currency="CAD",
    account="wise",
):
    return SimpleNamespace(
        date=date,
        montant=amount,
        marchand=merchant,
        description="",
        compte=account,
        devise=currency,
        category_id=category_id,
    )


def _finance_tx(kind, broker, amount, *, date=dt.datetime(2026, 1, 1), currency="EUR"):
    return SimpleNamespace(
        date=date,
        type=kind,
        broker=broker,
        note="",
        quantite=1,
        prix_unitaire=amount,
        devise=currency,
    )


def test_identifies_requested_platforms_and_common_aliases():
    assert identify_platform("Virement sortant TRADDING212").name == "Trading 212"
    assert identify_platform("SEPA IBKR Ireland").name == "IBKR"
    assert identify_platform("RealToken / RealT").name == "RealT"
    assert identify_platform("Kraken").name == "Kraken"
    assert identify_platform("Binance").name == "Binance"
    assert identify_platform("DEGIRO").name == "DEGIRO"


def test_platform_ledger_is_used_once_and_withdrawals_reduce_net():
    summary = build_investment_flow_summary(
        bank_transactions=[
            _budget_tx(-140, "Trading 212 Limassol", currency="CAD"),
            _budget_tx(-0.35, "Trading 212 Limassol", currency="CAD"),
            _budget_tx(-0.35, "Trading 212 Limassol", currency="CAD"),
            _budget_tx(-80, "Virement Kraken", currency="CAD"),
        ],
        finance_transactions=[
            _finance_tx("depot", "Trading212", 100),
            _finance_tx("depot", "Trading212", 100),
            _finance_tx("retrait", "Trading212", 25),
            _finance_tx("achat", "Trading212", 60),
        ],
        categories=[],
    )

    assert summary["plateformes"] == [
        {
            "plateforme": "Kraken",
            "classe": "crypto",
            "devise": "CAD",
            "versements": 80.0,
            "retraits": 0.0,
            "net": 80.0,
            "mouvements": 1,
            "source": "bank",
        },
        {
            "plateforme": "Trading 212",
            "classe": "brokerage",
            "devise": "CAD",
            "versements": 0.35,
            "retraits": 0.0,
            "net": 0.35,
            "mouvements": 1,
            "source": "bank",
        },
        {
            "plateforme": "Trading 212",
            "classe": "brokerage",
            "devise": "EUR",
            "versements": 100.0,
            "retraits": 25.0,
            "net": 75.0,
            "mouvements": 2,
            "source": "platform",
        },
    ]
    assert summary["totaux_par_devise"] == [
        {"devise": "CAD", "versements": 80.35, "retraits": 0.0, "net": 80.35, "mouvements": 2},
        {"devise": "EUR", "versements": 100.0, "retraits": 25.0, "net": 75.0, "mouvements": 2},
    ]
    assert summary["mouvements_bancaires_ecartes"] == 2
    assert summary["mouvements_bancaires_associes_plateforme"] == 1
    assert summary["doublons_bancaires_ecartes"] == 1
    assert summary["doublons_bancaires_intercomptes_ecartes"] == 0
    assert summary["doublons_plateformes_ecartes"] == 1
    assert summary["mouvements_plateformes_comptes"] == 2


def test_unrecognized_transfer_in_investment_category_is_included_and_date_filtered(mem_session):
    seed_categories(mem_session)
    from sqlmodel import select

    from app.models.budget import BudgetCategory

    placement_category = mem_session.exec(
        select(BudgetCategory).where(BudgetCategory.nom == "Placements")
    ).first()
    summary = build_investment_flow_summary(
        bank_transactions=[
            _budget_tx(
                -50,
                "Virement vers compte externe",
                date=dt.date(2026, 1, 2),
                category_id=placement_category.id,
                currency="EUR",
            ),
            _budget_tx(
                10,
                "Virement non relié",
                date=dt.date(2025, 12, 31),
                category_id=placement_category.id,
                currency="EUR",
            ),
        ],
        finance_transactions=[],
        categories=mem_session.exec(select(BudgetCategory)).all(),
        from_date=dt.date(2026, 1, 1),
        to_date=dt.date(2026, 1, 31),
    )

    assert summary["plateformes"] == [
        {
            "plateforme": "Autres placements",
            "classe": "other",
            "devise": "EUR",
            "versements": 50.0,
            "retraits": 0.0,
            "net": 50.0,
            "mouvements": 1,
            "source": "category",
        }
    ]


def test_known_platform_transactions_are_auto_categorized(mem_session):
    seed_categories(mem_session)

    transaction = create_transaction(
        mem_session,
        date=dt.date(2026, 9, 12),
        montant=-125,
        marchand="Virement Binance",
        compte="banquepopulaire",
        devise="EUR",
    )

    from sqlmodel import select

    from app.models.budget import BudgetCategory

    category = mem_session.exec(
        select(BudgetCategory).where(BudgetCategory.id == transaction.category_id)
    ).first()
    assert category.nom == "Cryptoactifs"


def test_same_platform_transfer_seen_on_two_bank_accounts_counts_once():
    summary = build_investment_flow_summary(
        bank_transactions=[
            _budget_tx(-100, "Binance", currency="EUR", account="desjardins-debit"),
            _budget_tx(-100, "BINANCE", currency="EUR", account="wise"),
        ],
        finance_transactions=[],
        categories=[],
    )

    assert summary["totaux_par_devise"] == [
        {"devise": "EUR", "versements": 100.0, "retraits": 0.0, "net": 100.0, "mouvements": 1}
    ]
    assert summary["doublons_bancaires_intercomptes_ecartes"] == 1


def test_date_range_does_not_drop_a_bank_transfer_when_platform_date_is_outside_range():
    summary = build_investment_flow_summary(
        bank_transactions=[
            _budget_tx(-100, "DEGIRO", date=dt.date(2026, 1, 31), currency="EUR"),
        ],
        finance_transactions=[
            _finance_tx("depot", "DEGIRO", 100, date=dt.datetime(2026, 2, 1)),
        ],
        categories=[],
        from_date=dt.date(2026, 1, 1),
        to_date=dt.date(2026, 1, 31),
    )

    assert summary["totaux_par_devise"] == [
        {"devise": "EUR", "versements": 100.0, "retraits": 0.0, "net": 100.0, "mouvements": 1}
    ]
    assert summary["mouvements_bancaires_associes_plateforme"] == 0
