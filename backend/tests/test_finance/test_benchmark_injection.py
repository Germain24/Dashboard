"""Le benchmark n'est pas dans l'univers : il doit être injecté explicitement."""

import numpy as np
import pandas as pd
import pytest


def test_absence_de_benchmark_leve_une_erreur_explicite():
    """Un score mesuré contre un benchmark absent n'aurait aucun sens : on échoue
    bruyamment plutôt que de retomber sur un benchmark nul."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    rets = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, (800, 3)))
    with pytest.raises(ValueError, match="benchmark"):
        optimize_portfolio_de(
            ["A", "B", "C"], rets, [[True], [True], [True]], ["Trading212"],
            benchmark_returns=None,
        )


def test_benchmark_trop_court_leve_une_erreur():
    from app.services.finance.buffett.optimizer import optimize_portfolio_de
    rets = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, (800, 3)))
    court = pd.Series(np.random.default_rng(1).normal(0, 0.01, 10))
    with pytest.raises(ValueError, match="benchmark"):
        optimize_portfolio_de(
            ["A", "B", "C"], rets, [[True], [True], [True]], ["Trading212"],
            benchmark_returns=court,
        )
