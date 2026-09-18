"""Déduplication d'une même ENTREPRISE cotée sur plusieurs places.

L'ISIN manque sur ~36 % de l'univers, et précisément sur les cotations
PRINCIPALES (BBVA.MC, MC.PA, SAN.MC, GOOGL, ORNBV.HE...). Grouper par ISIN seul
laissait donc passer deux fois le même émetteur : BBVA.MC (ISIN vide) et BVA.L
(ES0113211835) se retrouvaient tous deux dans le portefeuille, cumulant 12,9 % et
franchissant ainsi MAX_POSITION_PCT.

Le garde-fou de la fusion par nom est le score `Chance MOAT`, calculé une fois par
émetteur puis propagé à toutes ses cotations.
"""

import numpy as np
import pandas as pd

from app.services.finance.buffett.dedup import deduplicate_tickers

_TCOL = "Ticker Yahoo Finance"


def _setup(rows):
    tickers = [r["Ticker"] for r in rows]
    returns = pd.DataFrame(
        np.random.RandomState(0).randn(20, len(tickers)), columns=tickers
    )
    df = pd.DataFrame(rows).rename(columns={"Ticker": _TCOL})
    return returns, df


_BBVA = "Banco Bilbao Vizcaya Argentaria, S.A."


def test_bbva_cross_listings_collapse_to_the_primary_quote():
    """Le cas rapporté : BBVA.MC et BVA.L dans le même portefeuille.

    BBVA.MC n'a pas d'ISIN mais EST la place principale ; BVA.L et BOY.DE portent
    ES0113211835 ; BBVA.F est l'ADR (autre ISIN). Toutes partagent le score 94,43,
    ce qui suffit à les réunir. Une seule ligne doit survivre, la principale.
    """
    returns, df = _setup([
        {"Ticker": "BBVA.MC", "Nom": _BBVA, "Volume": 5000, "Secteur": "Financial Services",
         "ISIN": None, "Primary Market": True, "Chance MOAT": 94.43},
        {"Ticker": "BVA.L", "Nom": _BBVA, "Volume": 900, "Secteur": "Financial Services",
         "ISIN": "ES0113211835", "Primary Market": False, "Chance MOAT": 94.43},
        {"Ticker": "BOY.DE", "Nom": _BBVA, "Volume": 400, "Secteur": "Financial Services",
         "ISIN": "ES0113211835", "Primary Market": False, "Chance MOAT": 94.43},
        {"Ticker": "BBVA.F", "Nom": _BBVA, "Volume": 100, "Secteur": "Financial Services",
         "ISIN": "US05946K1016", "Primary Market": False, "Chance MOAT": 94.43},
    ])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["BBVA.MC"]


def test_isin_only_grouping_would_have_kept_the_duplicate():
    """Sans le rapprochement par nom, le doublon passe : c'est la régression."""
    returns, df = _setup([
        {"Ticker": "BBVA.MC", "Nom": _BBVA, "Volume": 5000, "Secteur": "Financial Services",
         "ISIN": None, "Primary Market": True, "Chance MOAT": 94.43},
        {"Ticker": "BVA.L", "Nom": _BBVA, "Volume": 900, "Secteur": "Financial Services",
         "ISIN": "ES0113211835", "Primary Market": False, "Chance MOAT": 94.43},
    ])
    assert len(deduplicate_tickers(returns, df).columns) == 1


def test_same_normalized_name_but_different_scores_stays_separate():
    """Deux sociétés distinctes que `normalize` rapproche ne doivent PAS fusionner.

    « Orion Oyj » (Finlande) et « Orion Corporation » (Corée) se réduisent tous
    deux à `orion`. Leurs scores diffèrent : ce sont bien deux entreprises.
    """
    returns, df = _setup([
        {"Ticker": "ORNBV.HE", "Nom": "Orion Oyj", "Volume": 500, "Secteur": "Healthcare",
         "ISIN": None, "Primary Market": True, "Chance MOAT": 84.02},
        {"Ticker": "271560.KS", "Nom": "Orion Corporation", "Volume": 700, "Secteur": "Consumer Defensive",
         "ISIN": None, "Primary Market": True, "Chance MOAT": 61.10},
    ])
    out = deduplicate_tickers(returns, df)
    assert set(out.columns) == {"ORNBV.HE", "271560.KS"}


def test_etfs_are_not_merged_by_name_and_score():
    """Les ETF valent tous 200 : le garde-fou du score y serait inopérant.

    Deux indices distincts ont des noms qui se normalisent pareil ; seuls l'ISIN
    ou un nom EXACTEMENT identique peuvent les réunir.
    """
    returns, df = _setup([
        {"Ticker": "IWDA.L", "Nom": "iShares Core MSCI World UCITS ETF", "Volume": 900,
         "Secteur": "ETF", "ISIN": "IE00B4L5Y983", "Primary Market": True, "Chance MOAT": 200.0},
        {"Ticker": "EIMI.L", "Nom": "iShares Core MSCI EM IMI UCITS ETF", "Volume": 800,
         "Secteur": "ETF", "ISIN": "IE00BKM4GZ66", "Primary Market": True, "Chance MOAT": 200.0},
    ])
    out = deduplicate_tickers(returns, df)
    assert set(out.columns) == {"IWDA.L", "EIMI.L"}


def test_missing_score_acts_as_a_joker_not_as_a_separate_key():
    """Catalogue partiel : une ligne sans score rejoint son groupe de nom."""
    returns, df = _setup([
        {"Ticker": "BBVA.MC", "Nom": _BBVA, "Volume": 5000, "Secteur": "Financial Services",
         "ISIN": None, "Primary Market": True, "Chance MOAT": 94.43},
        {"Ticker": "BVA.L", "Nom": _BBVA, "Volume": 900, "Secteur": "Financial Services",
         "ISIN": None, "Primary Market": False, "Chance MOAT": float("nan")},
    ])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["BBVA.MC"]


def test_forced_tickers_are_never_merged():
    from app.services.finance.buffett.config import Config

    original = Config.FORCED_BUY_TICKERS
    Config.FORCED_BUY_TICKERS = ["BVA.L"]
    try:
        returns, df = _setup([
            {"Ticker": "BBVA.MC", "Nom": _BBVA, "Volume": 5000, "Secteur": "Financial Services",
             "ISIN": "ES0113211835", "Primary Market": True, "Chance MOAT": 94.43},
            {"Ticker": "BVA.L", "Nom": _BBVA, "Volume": 900, "Secteur": "Financial Services",
             "ISIN": "ES0113211835", "Primary Market": False, "Chance MOAT": 94.43},
        ])
        out = deduplicate_tickers(returns, df)
        assert set(out.columns) == {"BBVA.MC", "BVA.L"}
    finally:
        Config.FORCED_BUY_TICKERS = original


# ── Un ETF s'identifie par son INDICE, pas par son emetteur. `normalize` tronque
# au premier « - », ce qui reduisait « Amundi Index Solutions - X » a l'emetteur
# seul : quatre indices sans rapport fusionnaient, et le Core S&P 500 disparaissait
# dans un Pacific ex-Japan. Cas observes sur les vraies donnees ToutBroker.


def _etf(ticker, nom, volume, isin=None):
    return {"Ticker": ticker, "Nom": nom, "Volume": volume, "Secteur": "ETF",
            "ISIN": isin, "Primary Market": True, "Chance MOAT": 200.0}


def test_same_issuer_different_index_are_not_merged():
    returns, df = _setup([
        _etf("AEEM.PA", "Amundi Index Solutions - Amundi MSCI Emerging Markets Swap UCITS ETF EUR", 900),
        _etf("C40.PA", "Amundi Index Solutions - AMUNDI CAC 40 ESG UCITS ETF DR - EUR (C)", 800),
        _etf("RS2K.PA", "Amundi Index Solutions - Amundi Russell 2000 ETF-C EUR", 700),
        _etf("FMI.MI", "Amundi Index Solutions - Amundi ITALY MIB ESG UCITS ETF DR - EUR C", 600),
    ])
    out = deduplicate_tickers(returns, df)
    assert set(out.columns) == {"AEEM.PA", "C40.PA", "RS2K.PA", "FMI.MI"}


def test_core_sp500_is_not_absorbed_by_pacific_ex_japan():
    returns, df = _setup([
        _etf("CSPX.L", "iShares VII PLC - iShares Core S&P 500 UCITS ETF", 9000),
        _etf("CPXJ.L", "iShares VII PLC - iShares Core MSCI Pacific ex-Japan UCITS ETF", 100),
    ])
    out = deduplicate_tickers(returns, df)
    assert set(out.columns) == {"CSPX.L", "CPXJ.L"}


def test_hedged_and_unhedged_share_classes_stay_separate():
    """Couvert et non couvert sont deux expositions differentes."""
    returns, df = _setup([
        _etf("PE500.PA", "Amundi PEA S&P 500 Screened UCITS ETF - Acc", 900),
        _etf("P500H.PA", "Amundi PEA S&P 500 Screened UCITS ETF - EUR Hedged Acc", 300),
    ])
    out = deduplicate_tickers(returns, df)
    assert set(out.columns) == {"PE500.PA", "P500H.PA"}


def test_two_quotations_of_the_same_fund_still_merge():
    """Le correctif ne doit pas casser le vrai dedoublonnage de cotations."""
    nom = "iShares Core MSCI World UCITS ETF USD (Acc)"
    returns, df = _setup([_etf("IWDA.L", nom, 9000), _etf("SWDA.L", nom, 100)])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["IWDA.L"]


def test_stock_normalization_still_drops_the_quotation_suffix():
    """Pour une ACTION le suffixe designe une ligne de cotation, pas un actif."""
    from app.services.finance.buffett.dedup import normalize, normalize_fund

    assert normalize("Banco Santander - SPONS ADR") == normalize("Banco Santander")
    # ... alors que pour un fonds, ce qui suit le tiret EST l'identite.
    assert normalize_fund("Amundi Index Solutions - Amundi Russell 2000 ETF-C EUR") != \
        normalize_fund("Amundi Index Solutions - AMUNDI CAC 40 ESG UCITS ETF DR - EUR (C)")


def test_transitive_merge_across_both_relations():
    """Chaîne mixte : A—B par ISIN, B—C par nom+score. Les trois se rejoignent.

    C'est ce que le groupement par clé unique ne pouvait pas faire : il fallait
    choisir l'une OU l'autre relation.
    """
    returns, df = _setup([
        {"Ticker": "A.DE", "Nom": "Siemens Healthineers AG", "Volume": 100, "Secteur": "Healthcare",
         "ISIN": "DE000SHL1006", "Primary Market": False, "Chance MOAT": 80.10},
        {"Ticker": "SHL.DE", "Nom": "Siemens Healthineers AG (Frankfurt line)", "Volume": 900,
         "Secteur": "Healthcare", "ISIN": "DE000SHL1006", "Primary Market": True, "Chance MOAT": 80.10},
        {"Ticker": "SMMNY", "Nom": "Siemens Healthineers AG", "Volume": 50, "Secteur": "Healthcare",
         "ISIN": None, "Primary Market": False, "Chance MOAT": 80.10},
    ])
    out = deduplicate_tickers(returns, df)
    assert list(out.columns) == ["SHL.DE"]
