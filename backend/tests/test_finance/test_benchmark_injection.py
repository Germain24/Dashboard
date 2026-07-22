"""Le benchmark comme référence du score : injection et non-duplication.

Le score d'optimisation mesure l'écart au benchmark (CW8.PA). Deux cas doivent
être traités séparément :

- le benchmark est ABSENT de l'univers optimisé (écarté par la présélection ETF) :
  ses rendements doivent être injectés par l'appelant, sinon le score n'a aucun
  sens et on échoue bruyamment ;
- le benchmark est DÉJÀ PRÉSENT (cas réel : CW8.PA est un ETF éligible et très
  liquide) : sa colonne doit être RÉUTILISÉE. En ajouter une seconde ferait
  apparaître la même série deux fois dans la simulation, donc une paire de
  corrélation 1,0 qui peut rendre la matrice de corrélation singulière.
"""

import numpy as np
import pandas as pd
import pytest


def _rets(n_obs=800, n_cols=3, seed=0):
    data = np.random.default_rng(seed).normal(0.0005, 0.01, (n_obs, n_cols))
    return pd.DataFrame(data)


def test_absence_de_benchmark_leve_une_erreur_explicite():
    """Un score mesuré contre un benchmark absent n'aurait aucun sens : on échoue
    bruyamment plutôt que de retomber sur un benchmark nul."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    with pytest.raises(ValueError, match="benchmark"):
        optimize_portfolio_de(
            ["A", "B", "C"], _rets(), [[True], [True], [True]], ["Trading212"],
            benchmark_returns=None,
        )


def test_message_d_erreur_designe_l_appelant_et_pas_le_ticker():
    """Le bouton manuel de création de portefeuille a longtemps appelé
    l'optimiseur sans transmettre la série : le message doit dire que l'appelant
    ne l'a pas fournie, pas laisser croire que CW8.PA est injoignable."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    with pytest.raises(ValueError, match="aucune serie benchmark_returns fournie"):
        optimize_portfolio_de(
            ["A", "B", "C"], _rets(), [[True], [True], [True]], ["Trading212"],
            benchmark_returns=None,
        )


def test_benchmark_trop_court_leve_une_erreur():
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    court = pd.Series(np.random.default_rng(1).normal(0, 0.01, 10))
    with pytest.raises(ValueError, match="benchmark"):
        optimize_portfolio_de(
            ["A", "B", "C"], _rets(), [[True], [True], [True]], ["Trading212"],
            benchmark_returns=court,
        )


def test_benchmark_deja_dans_l_univers_ne_reclame_aucune_injection(monkeypatch):
    """Si le benchmark fait partie des titres optimisés, sa colonne existante
    suffit : exiger en plus une série injectée serait une fausse erreur."""
    from app.services.finance.buffett import optimizer as opt

    monkeypatch.setattr(opt.Config, "STARR_BENCHMARK_TICKER", "B", raising=False)
    # Aucun ValueError ne doit être levé pour cause de benchmark manquant. On
    # arrête l'exécution juste après la validation pour ne pas payer un DE complet.
    class _Stop(RuntimeError):
        pass

    def _boom(*args, **kwargs):
        raise _Stop

    monkeypatch.setattr(opt, "load_etf_tickers", _boom, raising=False)
    with pytest.raises((_Stop, RuntimeError)) as exc:
        opt.optimize_portfolio_de(
            ["A", "B", "C"], _rets(), [[True], [True], [True]], ["Trading212"],
            benchmark_returns=None,
        )
    assert not isinstance(exc.value, ValueError), (
        "le benchmark est dans l'univers : aucune injection ne doit être exigée"
    )


def test_le_benchmark_non_eligible_est_retire_de_l_univers_par_le_runner():
    """Garde-fou contre le candidat fantôme : le benchmark téléchargé pour servir
    de référence ne doit pas devenir un titre achetable. `prepare_optimization`
    accorde l'accès broker par défaut aux tickers absents du tableau, donc un
    benchmark laissé dans les rendements serait réellement allouable."""
    from app.services.finance.buffett.optimizer import prepare_optimization

    df = pd.DataFrame([
        {"Ticker Yahoo Finance": "A", "Nom": "a", "Achat": True},
        {"Ticker Yahoo Finance": "B", "Nom": "b", "Achat": True},
    ])
    # CW8.PA n'est PAS dans le tableau : s'il restait dans la liste des tickers
    # optimisés, il recevrait un accès broker par défaut à True.
    access, _brokers = prepare_optimization(["A", "B", "CW8.PA"], df)
    assert any(access[2]), (
        "hypothèse du garde-fou : un ticker absent du tableau obtient bien un "
        "accès broker par défaut -- c'est pourquoi le runner doit le retirer"
    )
