"""Écriture des scores de l'analyse Buffett dans ToutBroker.xlsx.

Vérifie l'upsert par ticker (mise à jour de l'existant, création sinon) tout en
préservant les colonnes de disponibilité broker.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from app.services.finance.buffett.broker_availability import update_broker_file_scores


def _make_file(path) -> None:
    df = pd.DataFrame(
        [
            {
                "Ticker Yahoo Finance": "AAPL", "Nom": "Apple", "Chance MOAT": 10.0,
                "Achat": False, "Prix": 100.0, "EPS": 5.0, "PER": 20.0,
                "Croissance": 8.0, "PEG": 2.0, "Volume": 1000.0,
                "Tradding 212": 1.0, "Bourse Direct": 0.0,
            },
            {
                "Ticker Yahoo Finance": "MSFT", "Nom": "Microsoft", "Chance MOAT": 20.0,
                "Achat": False, "Prix": 200.0, "EPS": 9.0, "PER": 30.0,
                "Croissance": 12.0, "PEG": 2.5, "Volume": 2000.0,
                "Tradding 212": 1.0, "Bourse Direct": 1.0,
            },
        ]
    )
    df.to_excel(path, index=False)


def _row(ticker, **kw):
    base = dict(
        ticker=ticker, nom=None, pays=None, secteur=None, prix=None, eps=None,
        per=None, croissance=None, peg=None, volume=None, chance_moat=None, achat=False,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_update_existing_and_create_missing(tmp_path):
    f = tmp_path / "ToutBroker.xlsx"
    _make_file(f)

    rows = [
        _row("AAPL", chance_moat=88.0, achat=True, prix=190.0, eps=6.0, per=21.0,
             croissance=9.5, peg=1.8, volume=1500.0),
        _row("NVDA", nom="Nvidia", chance_moat=95.0, achat=True, prix=900.0),
    ]
    n = update_broker_file_scores(rows, path=str(f))
    assert n == 2

    out = pd.read_excel(f).set_index("Ticker Yahoo Finance")

    # Ticker existant : score + Achat + indicateurs mis à jour
    assert out.loc["AAPL", "Chance MOAT"] == 88.0
    assert bool(out.loc["AAPL", "Achat"]) is True
    assert out.loc["AAPL", "Prix"] == 190.0
    assert out.loc["AAPL", "PER"] == 21.0
    # Disponibilité broker PRÉSERVÉE
    assert out.loc["AAPL", "Tradding 212"] == 1.0
    assert out.loc["AAPL", "Bourse Direct"] == 0.0

    # Ticker non analysé cette fois : inchangé
    assert out.loc["MSFT", "Chance MOAT"] == 20.0
    assert out.loc["MSFT", "Tradding 212"] == 1.0

    # Ticker absent : nouvelle ligne créée avec le score
    assert "NVDA" in out.index
    assert out.loc["NVDA", "Chance MOAT"] == 95.0
    assert bool(out.loc["NVDA", "Achat"]) is True


def test_no_file_returns_zero(tmp_path):
    missing = tmp_path / "absent.xlsx"
    assert update_broker_file_scores([_row("AAPL", chance_moat=50.0)], path=str(missing)) == 0
