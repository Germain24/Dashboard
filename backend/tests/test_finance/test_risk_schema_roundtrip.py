"""`/finance/risk` perdait silencieusement volatilité et concentration.

`get_risk_metrics` renvoie `volatilite_annualisee_pct` et `concentration` ;
`RiskMetricsOut` déclarait `volatilite_annuelle_pct` et `hhi_label`. Pydantic
ignore les clés en trop et remplit les manquantes avec leurs défauts : l'endpoint
a donc TOUJOURS répondu `volatilite = 0.0` et `hhi_label = "—"`, quelles que
soient les données. Aucune erreur, aucun test rouge — juste deux champs morts.

Troisième orthographe au passage : la branche « pas de données » renvoyait
`volatilite_pct`, qui ne correspondait ni au service ni au schéma.

Ces tests verrouillent le contrat : tout ce que le service produit doit
traverser le schéma sans être perdu.
"""

from __future__ import annotations

from app.api.schemas_finance import RiskMetricsOut
from app.services.finance.risk import get_risk_metrics


def _snapshots_volatils() -> list[dict]:
    """Série qui monte et descend : volatilité franchement non nulle."""
    valeurs = [100, 112, 98, 121, 95, 130, 104, 138]
    return [
        {"date": f"2026-01-{i + 1:02d}", "valeur": float(v), "investit": 100.0}
        for i, v in enumerate(valeurs)
    ]


def _positions_concentrees() -> list[dict]:
    return [
        {"ticker": "AAA", "valeur_actuelle": 9000.0},
        {"ticker": "BBB", "valeur_actuelle": 1000.0},
    ]


def test_toutes_les_cles_du_service_existent_dans_le_schema():
    """Aucune clé produite par le service ne doit être ignorée par le schéma."""
    metrics = get_risk_metrics(_snapshots_volatils(), _positions_concentrees())

    inconnues = set(metrics) - set(RiskMetricsOut.model_fields)
    assert not inconnues, f"clés perdues en traversant RiskMetricsOut : {sorted(inconnues)}"


def test_volatilite_non_nulle_survit_au_schema():
    """Une série volatile ne doit pas ressortir de l'API avec une volatilité nulle."""
    metrics = get_risk_metrics(_snapshots_volatils(), _positions_concentrees())
    assert metrics["volatilite_annualisee_pct"] > 0, "prérequis : la série doit être volatile"

    out = RiskMetricsOut(**metrics)

    assert out.volatilite_annualisee_pct == metrics["volatilite_annualisee_pct"]
    assert out.volatilite_annualisee_pct > 0


def test_concentration_survit_au_schema():
    """Un portefeuille 90/10 est concentré : le label doit sortir, pas « — »."""
    metrics = get_risk_metrics(_snapshots_volatils(), _positions_concentrees())

    out = RiskMetricsOut(**metrics)

    assert out.concentration == metrics["concentration"]
    assert out.concentration == "élevée"


def test_branche_sans_donnees_utilise_les_memes_cles():
    """La branche vide doit parler le même vocabulaire que la branche normale."""
    vide = get_risk_metrics([], [])
    normale = get_risk_metrics(_snapshots_volatils(), _positions_concentrees())

    assert set(vide) == set(normale)
    out = RiskMetricsOut(**vide)
    assert out.volatilite_annualisee_pct == 0
    assert out.concentration == "inconnu"
