"""Le NOM d'un fonds a le dernier mot pour les métaux précieux.

Cas réel : « UBS Solactive Global Pure Gold Miners UCITS ETF » (UBUD.DE) est
renseigné dans ToutBroker en Actions / Diversifié / **Monde**. Il échappait donc
au plafond « Or » (10 %) et tombait sous le plafond par défaut (25 %) — si bien
qu'il pouvait cohabiter avec un GDX correctement étiqueté « Or » sans qu'aucune
contrainte ne lie les deux : 10,5 % de mineurs d'or dans un portefeuille censé en
plafonner 10.
"""

import pandas as pd
import pytest

from app.services.finance.buffett.sector_constraints import (
    SectorCaps,
    is_precious_metals_fund,
    resolve_risk_categories,
)

TCOL = "Ticker Yahoo Finance"


@pytest.mark.parametrize("nom", [
    "UBS Solactive Global Pure Gold Miners UCITS ETF USD dis",
    "VanEck Gold Miners ETF",
    "iShares Physical Gold ETC",
    "Invesco Physical Silver",
    "WisdomTree Precious Metals",
    "Amundi Physical Metaux Precieux",
    "abrdn Platinum ETF Trust",
])
def test_precious_metals_names_are_detected(nom):
    assert is_precious_metals_fund(nom)


@pytest.mark.parametrize("nom", [
    "Goldman Sachs Group, Inc.",          # 'gold' ne doit pas matcher 'Goldman'
    "Banco BBVA Argentina S.A.",          # 'argent' volontairement hors du motif
    "iShares Core MSCI World UCITS ETF",
    "Golden Ocean Group Limited",         # transport maritime
    "",
])
def test_unrelated_names_are_not_detected(nom):
    assert not is_precious_metals_fund(nom)


def _table(rows):
    return pd.DataFrame(rows).rename(columns={"Ticker": TCOL})


def test_gold_miners_labelled_world_are_reclassified(capsys):
    table = _table([{
        "Ticker": "UBUD.DE", "Nom": "UBS Solactive Global Pure Gold Miners UCITS ETF USD dis",
        "Secteur 1": "ETF", "Secteur 2": "Actions", "Secteur 3": "Diversifié",
        "Secteur 4": "Monde", "Secteur 5": "",
    }])
    resolved, meta = resolve_risk_categories({"UBUD.DE": "ETF"}, broker_table=table)

    assert resolved["UBUD.DE"] == "Or"
    assert meta["precious_metals_overrides"] == ["UBUD.DE"]
    # La correction doit être auditable, pas silencieuse.
    assert "UBUD.DE" in capsys.readouterr().out


def test_correctly_labelled_gold_is_left_alone():
    table = _table([{
        "Ticker": "GDX", "Nom": "VanEck Gold Miners ETF", "Secteur 1": "ETF",
        "Secteur 2": "Matières premières", "Secteur 3": "Métaux précieux",
        "Secteur 4": "Or", "Secteur 5": "Physique",
    }])
    resolved, meta = resolve_risk_categories({"GDX": "ETF"}, broker_table=table)

    assert resolved["GDX"] == "Or"
    assert meta["precious_metals_overrides"] == []


def test_ordinary_funds_keep_their_manual_classification():
    table = _table([{
        "Ticker": "IWDA.L", "Nom": "iShares Core MSCI World UCITS ETF",
        "Secteur 1": "ETF", "Secteur 2": "Actions", "Secteur 3": "Diversifié",
        "Secteur 4": "Monde", "Secteur 5": "",
    }])
    resolved, _ = resolve_risk_categories({"IWDA.L": "ETF"}, broker_table=table)

    assert resolved["IWDA.L"] == "Monde"


def test_both_gold_funds_now_share_the_same_capped_bucket(monkeypatch):
    """Le fond du probleme : les deux lignes doivent etre bornees ENSEMBLE."""
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 0.25)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT_OVERRIDES", {"Or": 0.10})
    table = _table([
        {"Ticker": "UBUD.DE", "Nom": "UBS Solactive Global Pure Gold Miners UCITS ETF",
         "Secteur 1": "ETF", "Secteur 2": "Actions", "Secteur 3": "Diversifié",
         "Secteur 4": "Monde", "Secteur 5": ""},
        {"Ticker": "GDX", "Nom": "VanEck Gold Miners ETF", "Secteur 1": "ETF",
         "Secteur 2": "Matières premières", "Secteur 3": "Métaux précieux",
         "Secteur 4": "Or", "Secteur 5": "Physique"},
    ])
    resolved, _ = resolve_risk_categories(
        {"UBUD.DE": "ETF", "GDX": "ETF"}, broker_table=table
    )
    caps = SectorCaps.from_config()

    assert resolved["UBUD.DE"] == resolved["GDX"] == "Or"
    assert caps.for_label(resolved["UBUD.DE"]) == pytest.approx(0.10)
    assert caps.for_label(resolved["GDX"]) == pytest.approx(0.10)
