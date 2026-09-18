"""Prior de rendement : médiane de la CLASSE et non médiane globale."""

import numpy as np


def test_obligation_nest_plus_tiree_vers_la_mediane_des_actions():
    """Le bug d'origine : une obligation à 3,5 % recevait ~12,7 % espérés."""
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.02, 0.03, 0.20, 0.22, 0.24])       # 2 titres de taux, 3 actions
    classes = ["taux", "taux", "actions", "actions", "actions"]
    prior = class_aware_prior(mu, classes)
    assert prior[0] == prior[1] == 0.025                # médiane des taux
    assert prior[2] == prior[3] == prior[4] == 0.22     # médiane des actions


def test_ordre_intra_classe_preserve():
    """Le prior est un centre de gravité, pas une valeur imposée."""
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.01, 0.03, 0.05])
    prior = class_aware_prior(mu, ["taux"] * 3)
    estim = 0.25 * mu + 0.75 * prior
    assert estim[0] < estim[1] < estim[2]


def test_classe_singleton_vaut_sa_propre_moyenne():
    """Pas de taille minimale : un seuil ferait retomber sur la médiane globale."""
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.01, 0.20, 0.30])
    prior = class_aware_prior(mu, ["taux", "actions", "actions"])
    assert prior[0] == 0.01


def test_classe_inconnue_retombe_sur_la_mediane_globale():
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.01, 0.20, 0.30, 0.40])
    prior = class_aware_prior(mu, ["taux", "actions", "actions", None])
    assert prior[3] == float(np.median(mu))


def test_valeurs_non_finies_ignorees_dans_la_mediane():
    from app.services.finance.buffett.optimizer import class_aware_prior
    mu = np.array([0.02, np.nan, 0.04])
    prior = class_aware_prior(mu, ["taux", "taux", "taux"])
    assert prior[0] == 0.03
