"""La disponibilité broker ne doit JAMAIS échouer en silence.

`merge_broker_columns` avalait toute exception et renvoyait le DataFrame sans
colonne de disponibilité — ce que l'optimiseur interprète comme « tous les titres
achetables chez tous les brokers ». Une seule ligne au ticker vide dans le fichier
broker suffisait à déclencher ce chemin, et le run produisait alors un
portefeuille inachetable : actions américaines, canadiennes et coréennes allouées
sur un PEA, sans autre trace qu'une ligne de log.

La cause profonde : `astype(str)` préserve les valeurs manquantes dans les pandas
récents (au lieu de produire "nan"), si bien qu'un flottant NaN survivait jusqu'à
un `.upper()`.
"""

import numpy as np
import pandas as pd
import pytest

from app.services.finance.buffett import broker_availability as ba
from app.services.finance.buffett.config import Config

TCOL = "Ticker Yahoo Finance"


@pytest.fixture(autouse=True)
def _brokers(monkeypatch):
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 100.0, "BoursDirect2": 900.0})
    ba.reset_etf_cache() if hasattr(ba, "reset_etf_cache") else None


def _table(rows):
    return pd.DataFrame(rows)


def test_a_blank_ticker_row_no_longer_breaks_the_merge(monkeypatch):
    """LE bug : une ligne au ticker vide désactivait toute la disponibilité."""
    table = _table([
        {TCOL: "AIR.PA", "Tradding 212": 1, "Bourse Direct 2": 1},
        {TCOL: np.nan, "Tradding 212": np.nan, "Bourse Direct 2": np.nan},
        {TCOL: "GSL", "Tradding 212": 1, "Bourse Direct 2": 0},
    ])
    monkeypatch.setattr(ba, "load_broker_table", lambda: table)

    analyse = pd.DataFrame({TCOL: ["AIR.PA", "GSL"]})
    out = ba.merge_broker_columns(analyse, ticker_col=TCOL)

    assert "BoursDirect2" in out.columns
    par_ticker = dict(zip(out[TCOL], out["BoursDirect2"], strict=True))
    assert bool(par_ticker["AIR.PA"]) is True
    assert bool(par_ticker["GSL"]) is False      # explicitement indisponible


def test_a_missing_ticker_in_the_analysed_frame_is_tolerated(monkeypatch):
    """Le NaN peut aussi venir du DataFrame analysé, pas seulement du tableur."""
    table = _table([{TCOL: "AIR.PA", "Tradding 212": 1, "Bourse Direct 2": 1}])
    monkeypatch.setattr(ba, "load_broker_table", lambda: table)

    analyse = pd.DataFrame({TCOL: ["AIR.PA", np.nan]})
    out = ba.merge_broker_columns(analyse, ticker_col=TCOL)

    assert len(out) == 2
    assert bool(out["BoursDirect2"].iloc[0]) is True


def test_an_unrecoverable_failure_raises_instead_of_silently_allowing_everything(
    monkeypatch,
):
    """Mieux vaut un run interrompu qu'un portefeuille inachetable.

    Renvoyer le DataFrame sans colonne broker revenait à déclarer tout le monde
    disponible partout — l'exact contraire d'un garde-fou.
    """
    table = _table([{TCOL: "AIR.PA", "Tradding 212": 1, "Bourse Direct 2": 1}])
    monkeypatch.setattr(ba, "load_broker_table", lambda: table)

    def _boom(*_a, **_k):
        raise ValueError("colonne broker illisible")

    monkeypatch.setattr(ba, "_match_broker_column", _boom)

    with pytest.raises(RuntimeError, match="inachetable"):
        ba.merge_broker_columns(pd.DataFrame({TCOL: ["AIR.PA"]}), ticker_col=TCOL)


def test_no_broker_file_still_returns_the_frame_untouched(monkeypatch):
    """Ce repli-là reste légitime : sans fichier, aucune contrainte connue."""
    monkeypatch.setattr(ba, "load_broker_table", lambda: None)
    analyse = pd.DataFrame({TCOL: ["AIR.PA"]})

    out = ba.merge_broker_columns(analyse, ticker_col=TCOL)

    assert out is analyse or out.equals(analyse)
