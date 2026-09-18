"""Recuit adaptatif lent à l'intérieur de seeds indépendantes.

Les seeds indépendantes jetaient toute la population à chaque redémarrage — des
milliers de générations d'apprentissage perdues pour repartir d'un tirage
aléatoire. La recherche est désormais continue : la température baisse quand le
score progresse, monte quand il stagne, et se fige dès qu'un arrêt est demandé.

Le DE étant ÉLITISTE, la température n'agit pas sur l'acceptation dans la
population mais ENTRE BASSINS (basin hopping) : l'ANCRE d'où partent les
perturbations peut dériver vers un optimum moins bon, l'INCUMBENT livré jamais.
"""

import numpy as np
import pandas as pd
import pytest

from app.services.finance.buffett.config import Config
from app.services.finance.buffett.optimizer import (
    INVALID_OBJECTIVE_ENERGY,
    accept_new_anchor,
    build_forced_floor_probes,
    build_kick_variants,
    effective_forced_floor_targets,
    geography_guided_child,
    guided_kick_portfolio,
    is_real_improvement,
    kick_line_budget,
    kick_portfolio,
    next_hot_plateau_streak,
    next_temperature,
    project_preferences_to_deployed_support,
    reheat_amplitude,
    reheat_quota,
    relative_gain,
    sample_elite_seeds,
    sample_kick_sizes,
    sample_multiscale_kick_sizes,
    select_stratified_probe_elites,
    support_jaccard_distance,
    support_signature,
    update_diverse_support_archive,
)

# ── Loi de température ──────────────────────────────────────────────────────


def _T(t, *, gain=0.0, streak=0, stop=False):
    return next_temperature(
        t, gain=gain, stagnation_streak=streak, stop_requested=stop
    )


def test_an_improvement_cools_down():
    assert _T(0.5, gain=0.10) < 0.5


def test_a_single_barren_generation_already_heats_up():
    """AUCUN délai de carence : une génération sans progrès, c'est la stagnation.

    Exigence explicite : « si une génération après l'autre le score ne
    s'améliore pas = ça stagne ». Pas de « stagner 10 générations avant de faire
    quelque chose ».
    """
    assert _T(0.5, streak=1) > 0.5


def test_neither_leaves_the_temperature_alone():
    assert _T(0.5) == pytest.approx(0.5)


def test_temperature_stays_within_its_bounds():
    froid = 0.5
    for _ in range(200):
        froid = _T(froid, gain=0.10)
    chaud = 0.5
    for k in range(1, 201):
        chaud = _T(chaud, streak=k)
    assert froid >= float(Config.STARR_DE_T_MIN) - 1e-12
    assert chaud <= float(Config.STARR_DE_T_MAX) + 1e-12


def test_each_search_starts_in_exploitation():
    assert float(Config.STARR_DE_T0) == pytest.approx(float(Config.STARR_DE_T_MIN))


def test_initialization_keeps_the_current_seed_number_after_a_restart():
    from app.services.finance.buffett import optimization_progress

    optimization_progress.start(run_id=72)
    optimization_progress.update_de(3, 1, 0.5, best_score=-1.0, seed_score=-1.0)
    optimization_progress.update_initialization(1, 200, best_score=-1.0)
    try:
        assert optimization_progress.snapshot()["seed_num"] == 3
    finally:
        optimization_progress.reset()


def test_convergence_requires_twenty_consecutive_hot_stagnant_generations():
    streak = 0
    target = int(Config.STARR_DE_HOT_CONVERGENCE_GENERATIONS)
    assert target == 20
    for _ in range(target - 1):
        streak = next_hot_plateau_streak(
            streak, improved=False, temperature=1.0, t_max=1.0
        )
    assert streak == target - 1
    assert streak < target

    streak = next_hot_plateau_streak(
        streak, improved=False, temperature=1.0, t_max=1.0
    )
    assert streak == int(Config.STARR_DE_HOT_CONVERGENCE_GENERATIONS)


def test_hot_convergence_counter_resets_on_gain_or_cold_generation():
    assert next_hot_plateau_streak(
        12, improved=True, temperature=1.0, t_max=1.0
    ) == 0
    assert next_hot_plateau_streak(
        12, improved=False, temperature=0.999, t_max=1.0
    ) == 0


# ── Le refroidissement est PROPORTIONNEL à ce que le gain rapporte ──────────
# Exigence : « mettre la température à 0 quand il y a une minuscule amélioration
# du score me paraît encore plus lent — amélioration de 1 % = baisse de 1 %,
# amélioration de 50 % = baisse de 50 %, amélioration > 100 % = température à 0 ».
#
# Un facteur unique (×0,90) s'appliquait auparavant à TOUTE amélioration jugée
# réelle : une miette de 0,1 % éteignait l'exploration autant qu'un gain massif.


def test_a_significant_gain_reopens_a_local_exploitation_phase():
    assert _T(1.00, gain=0.001) == pytest.approx(
        float(Config.STARR_DE_IMPROVEMENT_T_MAX)
    )


def test_a_fifty_percent_gain_halves_the_temperature():
    assert _T(0.80, gain=0.50) == pytest.approx(0.40)


def test_doubling_the_score_drops_to_the_floor():
    assert _T(0.80, gain=1.00) == pytest.approx(float(Config.STARR_DE_T_MIN))
    assert _T(0.80, gain=3.50) == pytest.approx(float(Config.STARR_DE_T_MIN))


def test_the_exploitation_cap_does_not_reheat_an_already_cold_search():
    apres = _T(0.40, gain=0.001)
    assert apres == pytest.approx(0.40 * 0.999)


def test_the_floor_is_never_zero():
    """Le réchauffage est MULTIPLICATIF : une température nulle ne remonterait
    plus jamais et figerait la recherche pour de bon."""
    assert float(Config.STARR_DE_T_MIN) > 0.0
    froid = _T(0.80, gain=5.0)
    assert froid > 0.0
    assert _T(froid, streak=10) > froid


# ── Mesure du gain relatif, y compris sur des scores négatifs ───────────────


def test_the_gain_is_measured_in_percent_of_the_reference():
    # Énergies = scores changés de signe : de 4 à 6, c'est +50 %.
    assert relative_gain(-6.0, -4.0) == pytest.approx(0.50)


def test_a_negative_score_still_yields_a_sane_percentage():
    """Cas réel : les runs affichent des scores négatifs vs CW8."""
    # De −20 à −10 : le score progresse de moitié.
    assert relative_gain(10.0, 20.0) == pytest.approx(0.50)


def test_a_doubling_reads_as_one_hundred_percent():
    assert relative_gain(-8.0, -4.0) == pytest.approx(1.0)


def test_no_reference_means_no_gain():
    """Première génération : sans point de comparaison, la température ne doit
    pas plonger avant même que la recherche ait commencé."""
    assert relative_gain(-3.0, float("inf")) == 0.0
    assert _T(0.30, gain=relative_gain(-3.0, float("inf"))) == pytest.approx(0.30)


def test_a_degradation_is_never_a_gain():
    assert relative_gain(-2.0, -4.0) == 0.0


# ── Le CLIQUET : refroidir vite, réchauffer jamais ──────────────────────────
# Régression signalée : « elle baisse beaucoup trop vite et remonte pas assez du
# tout ». Mesurée, elle tenait à trois causes composées :
#   1. le refroidissement était un évènement PAR GÉNÉRATION (jusqu'à 1/gén),
#      le réchauffage un évènement PAR FENÊTRE (1 toutes les 40 gén) ;
#   2. le bloc de réchauffage réarmait la fenêtre de stagnation, si bien qu'une
#      seule vraie amélioration par fenêtre interdisait TOUT réchauffage —
#      température collée à T_MIN jusqu'à la fin du run ;
#   3. les amplitudes (×0,85 vs ×1,60) ne compensaient pas cet écart de cadence.
# La fenêtre a été supprimée, pas raccourcie.


GAIN_ORDINAIRE = 0.10  # un progrès franc mais banal : +10 % de score


def _improvements_to_floor():
    t, n = float(Config.STARR_DE_T_MAX), 0
    while t > float(Config.STARR_DE_T_MIN) + 1e-12 and n < 10_000:
        t = _T(t, gain=GAIN_ORDINAIRE)
        n += 1
    return n


def _barren_generations_to_ceiling():
    t, n = float(Config.STARR_DE_T_MIN), 0
    while t < float(Config.STARR_DE_T_MAX) - 1e-12 and n < 10_000:
        n += 1
        t = _T(t, streak=n)
    return n


def test_cooling_is_a_slope_not_a_cliff():
    """Le nouveau plancher haut reste atteint progressivement, pas en 2-3 gains."""
    assert _improvements_to_floor() >= 10


def test_temperature_floor_is_high_enough_to_restart_quickly():
    assert float(Config.STARR_DE_T_MIN) == pytest.approx(0.25)


def test_climbing_from_the_exploitation_cap_is_deliberately_slow():
    t = float(Config.STARR_DE_IMPROVEMENT_T_MAX)
    generations = 0
    while t < float(Config.STARR_DE_T_MAX) - 1e-12 and generations < 1_000:
        generations += 1
        t = _T(t, streak=generations)
    assert 90 <= generations <= 100


def test_reheating_step_is_linear_and_does_not_accelerate():
    depart = 0.10
    pas_court = _T(depart, streak=1) - depart
    pas_long = _T(depart, streak=10) - depart
    assert pas_long == pytest.approx(pas_court)
    assert pas_court > 0


def test_the_cumulated_climb_is_linear():
    def _apres(k):
        t = float(Config.STARR_DE_T_MIN)
        for streak in range(1, k + 1):
            t = _T(t, streak=streak)
        return t

    depart = float(Config.STARR_DE_T_MIN)
    assert _apres(6) - depart == pytest.approx(2 * (_apres(3) - depart))


def test_a_real_improvement_restarts_local_exploitation_after_stagnation():
    """Un bassin qui paie doit être affiné, même après un long réchauffage."""
    t = float(Config.STARR_DE_T_MIN)
    for streak in range(1, 11):
        t = _T(t, streak=streak)
    apres_stagnation = t
    apres_gain = _T(apres_stagnation, gain=GAIN_ORDINAIRE)
    assert apres_gain < apres_stagnation
    assert apres_gain <= float(Config.STARR_DE_IMPROVEMENT_T_MAX)
    assert apres_gain >= float(Config.STARR_DE_T_MIN)


def test_a_frequent_improver_still_cools_down():
    """La contrepartie : tant que ça progresse vraiment, on doit exploiter.

    Une amélioration une génération sur deux doit faire baisser la température,
    sinon le solveur ne se resserre jamais sur le bassin qui paie.
    """
    t = float(Config.STARR_DE_T0)
    for nit in range(1, 201):
        improved = nit % 2 == 0
        t = _T(
            t,
            gain=GAIN_ORDINAIRE if improved else 0.0,
            streak=0 if improved else 1,
        )
    assert t == pytest.approx(float(Config.STARR_DE_T_MIN), abs=1e-9)


def test_a_stalled_run_heats_up_within_a_few_dozen_generations():
    """Rejeu de la boucle : progrès jusqu'à la génération 300, puis plus rien.

    Avant correction, une amélioration toutes les 30 générations suffisait à
    interdire tout réchauffage sur 600 générations — T figée à T_MIN.
    """
    temperature = float(Config.STARR_DE_T0)
    streak = 0
    temperatures = []
    for nit in range(1, 601):
        improved = nit <= 300 and nit % 30 == 0
        streak = 0 if improved else streak + 1
        temperature = next_temperature(
            temperature,
            gain=GAIN_ORDINAIRE if improved else 0.0,
            stagnation_streak=streak,
            stop_requested=False,
        )
        temperatures.append(temperature)

    # Le plateau commence à la génération 300 ; 60 générations plus tard la
    # température doit être remontée au-dessus de sa valeur refroidie.
    assert temperatures[359] > temperatures[299]
    assert temperatures[-1] == pytest.approx(float(Config.STARR_DE_T_MAX))


def test_a_stop_request_freezes_reheating_for_good():
    """L'exigence explicite : arrêter ne doit JAMAIS relancer l'exploration."""
    t = float(Config.STARR_DE_T_MAX)
    for k in range(1, 51):
        suivant = _T(t, streak=k, stop=True)
        assert suivant <= t + 1e-12      # ne remonte jamais
        t = suivant
    assert t == pytest.approx(float(Config.STARR_DE_T_MIN), abs=1e-9)


# ── Acceptation entre bassins (basin hopping) ───────────────────────────────


def test_an_improvement_is_always_accepted():
    # Même avec le pire tirage possible et une température nulle.
    assert accept_new_anchor(5.0, 5.5, 0.0, 0.999999) is True


def test_a_hot_anchor_may_drift_downhill():
    """Sans cette dérive, les perturbations restent clouées au même optimum."""
    assert accept_new_anchor(5.0, 4.5, 1.0, 0.2) is True


def test_a_cold_anchor_never_drifts_downhill():
    assert accept_new_anchor(5.0, 4.5, 0.05, 0.2) is False
    assert accept_new_anchor(5.0, 4.999, 0.0, 0.0) is False


def test_acceptance_probability_grows_with_temperature():
    tirage = 0.5
    froid = accept_new_anchor(5.0, 4.7, 0.1, tirage)
    chaud = accept_new_anchor(5.0, 4.7, 1.0, tirage)
    assert chaud and not froid


def test_a_bigger_degradation_is_less_often_accepted():
    petite = accept_new_anchor(5.0, 4.9, 0.5, 0.5)
    grosse = accept_new_anchor(5.0, 2.0, 0.5, 0.5)
    assert petite and not grosse


def test_comparing_a_point_to_itself_always_accepts():
    """Le piège qui a rendu le basin hopping inopérant, isolé.

    La boucle proposait l'INCUMBENT comme nouvelle ancre, alors que l'ancre
    valait déjà son score : Metropolis comparait un point à lui-même, exp(0)=1,
    donc acceptation systématique à TOUTE température. L'ancre recollait au
    meilleur individu à chaque tour, toutes les perturbations repartaient du même
    portefeuille, et les mêmes tickers restaient du début à la fin du run.

    La fonction n'est pas en cause — ce test fixe son comportement pour que le
    piège reste visible : le candidat doit être un point DIFFÉRENT.
    """
    for temperature in (0.05, 0.3, 1.0):
        for tirage in (0.0, 0.5, 0.999999):
            assert accept_new_anchor(5.0, 5.0, temperature, tirage) is True


def test_a_distinct_candidate_restores_the_cold_refusal():
    """Avec un vrai candidat, la règle retrouve son sens : froid = on ne bouge
    que pour mieux, chaud = on accepte de descendre pour changer de bassin."""
    assert accept_new_anchor(5.0, 4.6, 0.05, 0.5) is False
    assert accept_new_anchor(5.0, 4.6, 1.0, 0.3) is True


# ── Ce qui COMPTE comme une amélioration ────────────────────────────────────
# Le DE est élitiste : son meilleur individu grappille des miettes numériques
# presque à chaque génération. Avec un seuil purement absolu (1e-6) sur un score
# de l'ordre de 3, chacune de ces miettes refroidissait la température ET
# réarmait la fenêtre de stagnation — le réchauffage ne pouvait jamais se
# déclencher, et la température restait collée à son plancher. Le seuil est donc
# proportionnel au score.


def test_a_numerical_crumb_is_not_an_improvement():
    """1e-6 sur un score de 3 : c'est du bruit, pas un progrès."""
    assert is_real_improvement(-3.000001, -3.0) is False


def test_a_meaningful_gain_is_an_improvement():
    assert is_real_improvement(-3.05, -3.0) is True


def test_the_threshold_scales_with_the_score():
    """Le même gain absolu compte sur un petit score, pas sur un gros."""
    gain = 0.005
    assert is_real_improvement(-(0.1 + gain), -0.1) is True
    assert is_real_improvement(-(100.0 + gain), -100.0) is False


def test_the_first_generation_always_improves():
    """La référence vaut +inf tant qu'aucune génération n'a été évaluée."""
    assert is_real_improvement(-3.0, float("inf")) is True


def test_a_degradation_is_never_an_improvement():
    assert is_real_improvement(-2.9, -3.0) is False


def test_a_near_zero_score_still_uses_the_absolute_floor():
    """Sans plancher absolu, tout gain deviendrait significatif près de 0."""
    assert is_real_improvement(-1e-9, 0.0) is False


def test_crumbs_no_longer_pin_the_temperature_to_its_floor():
    """Régression observée : courbe froide de bout en bout, T figée à T_MIN.

    On rejoue la boucle du solveur — seuil d'amélioration, ancienneté de la
    stagnation, loi de température — sur un paysage qui ne rend plus que des
    miettes de 1e-6 après un vrai gain initial. Avant correction, chaque miette
    refroidissait ET réarmait la fenêtre : la température ne remontait jamais.
    Elle doit maintenant décoller dès la deuxième génération.
    """
    temperature = float(Config.STARR_DE_T0)
    reference = float("inf")
    streak = 0
    energie = -3.0
    temperatures = []

    for _nit in range(1, 221):
        energie -= 1e-6  # une miette, génération après génération
        improved = is_real_improvement(energie, reference)
        gain = relative_gain(energie, reference) if improved else 0.0
        if improved:
            reference = energie
            streak = 0
        else:
            streak += 1
        temperature = next_temperature(
            temperature,
            gain=gain,
            stagnation_streak=streak,
            stop_requested=False,
        )
        temperatures.append(temperature)

    assert temperatures[-1] == pytest.approx(float(Config.STARR_DE_T_MAX)), (
        "la température n'est jamais remontée malgré une stagnation réelle"
    )
    # Le départ est désormais froid et la montée volontairement lente, mais elle
    # commence immédiatement : aucune fenêtre de carence ne bloque le mouvement.
    assert temperatures[1] > float(Config.STARR_DE_T0)


# ── Signature de support : l'identité DISCRÈTE d'un portefeuille ────────────


def test_the_signature_lists_the_open_lines_only():
    poids = np.array([0.20, 0.0, 0.005, 0.30, 0.0])
    assert sorted(support_signature(poids, 0.01)) == [0, 3]


def test_two_weightings_of_the_same_lines_share_a_signature():
    """C'est ce qui rend la mémoire utile — et un cache de SCORE faux."""
    a = np.array([0.5, 0.5, 0.0])
    b = np.array([0.9, 0.1, 0.0])
    assert support_signature(a, 0.01) == support_signature(b, 0.01)


def test_the_signature_is_hashable_for_a_tabu_list():
    tabou = {support_signature(np.array([0.4, 0.0, 0.6]), 0.01)}
    assert support_signature(np.array([0.3, 0.0, 0.7]), 0.01) in tabou


# ── Balayage force : chaque titre ouvre son propre bassin ──────────────────


def test_forced_floor_probes_try_every_instrument_at_ten_percent():
    anchor = np.array([0.50, 0.30, 0.20, 0.0])
    probes = build_forced_floor_probes(anchor, range(4), 0.10)

    assert probes.shape == (4, 4)
    assert np.allclose(probes.sum(axis=0), 1.0)
    # Les trois lignes deja au-dessus de 10 % restent des ancres identiques.
    assert np.allclose(probes[:, :3], anchor[:, None])
    # La ligne absente est reellement ouverte a 10 %, sans changer les
    # proportions relatives 5:3:2 du reste du portefeuille.
    assert probes[3, 3] == pytest.approx(0.10)
    assert probes[0, 3] / probes[1, 3] == pytest.approx(5 / 3)
    assert probes[1, 3] / probes[2, 3] == pytest.approx(3 / 2)


def test_forced_floor_probe_can_cover_the_whole_universe_in_batches():
    anchor = np.array([0.7, 0.3, 0.0, 0.0, 0.0])
    batches = [
        build_forced_floor_probes(anchor, [0, 1], 0.10),
        build_forced_floor_probes(anchor, [2, 3], 0.10),
        build_forced_floor_probes(anchor, [4], 0.10),
    ]
    tested = sum(batch.shape[1] for batch in batches)
    assert tested == len(anchor)
    assert batches[1][2, 0] == pytest.approx(0.10)
    assert batches[1][3, 1] == pytest.approx(0.10)
    assert batches[2][4, 0] == pytest.approx(0.10)


def test_probe_elites_reserve_room_for_actions_and_etfs():
    # Sans stratification, les quatre meilleurs scores seraient tous des ETF.
    energies = np.array([1.0, 2.0, 3.0, 4.0, 10.0, 11.0, np.inf])
    is_etf = np.array([True, True, True, True, False, False, False])
    selected = select_stratified_probe_elites(energies, is_etf, count=4)

    assert len(selected) == 4
    assert int(is_etf[selected].sum()) == 2
    assert int((~is_etf[selected]).sum()) == 2
    assert set(selected) == {0, 1, 4, 5}


def test_probe_elites_fill_unused_class_quota_by_score():
    energies = np.array([4.0, 1.0, 3.0, 2.0])
    selected = select_stratified_probe_elites(
        energies, np.ones(4, dtype=bool), count=3
    )
    assert selected.tolist() == [1, 3, 2]


def test_forced_floor_uses_the_small_brokers_maximum_when_ten_percent_is_impossible():
    targets = effective_forced_floor_targets(
        0.10,
        # Premier titre seulement T212, deuxieme seulement BD, troisieme les deux.
        [[True, False], [False, True], [True, True]],
        [0.029, 0.971],
    )
    assert targets == pytest.approx([0.029, 0.10, 0.10])


# ── Amplitude du réchauffage : ce que la température COMMANDE vraiment ──────
# Exigence : « quand T se rapproche de 0, on fait des changements tout petits,
# et quand T=1 alors tout le portefeuille est aléatoire ».
#
# Défaut observé : la température montait au plafond sans que RIEN ne bouge.
# Mesuré sur les constantes de production, à T=1 la secousse valait 6 lignes
# échangées sur ~40 (une borne FIXE, indépendante du portefeuille), 129
# individus sur 515, et jamais l'incumbent — que `best1bin` prend justement
# comme base de tous ses mutants. Le DE reconvergeait aussitôt sur le même
# optimum : température brûlante, portefeuille immobile.


def test_a_cold_reheat_moves_a_single_line():
    """T→0 : le plus petit changement qui existe, une ligne."""
    assert reheat_amplitude(0.0, 40) == 1


def test_a_maximal_reheat_redraws_the_whole_support():
    """T=1 : tout le portefeuille est remis en jeu, pas une borne fixe."""
    assert reheat_amplitude(1.0, 40) == 40
    assert reheat_amplitude(1.0, 7) == 7


def test_the_amplitude_is_relative_to_the_portfolio_not_a_constant():
    """Le même T doit secouer plus fort un portefeuille plus large."""
    assert reheat_amplitude(0.5, 100) > reheat_amplitude(0.5, 10)


def test_the_amplitude_grows_with_the_temperature():
    valeurs = [reheat_amplitude(t / 10, 40) for t in range(11)]
    assert valeurs == sorted(valeurs)
    assert valeurs[0] < valeurs[-1]


def test_a_maximal_reheat_produces_an_unrecognisable_portfolio():
    """À T=1, aucune ligne d'origine ne survit : le portefeuille est neuf."""
    x = np.zeros(200)
    x[:40] = 0.04
    avant = set(np.flatnonzero(x > 0).tolist())
    chaud = kick_portfolio(x, np.random.default_rng(0),
                           n_drop=reheat_amplitude(1.0, len(avant)),
                           n_add=reheat_amplitude(1.0, len(avant)))
    apres = set(np.flatnonzero(chaud > 0).tolist())
    assert not (avant & apres), "des lignes d'origine ont survécu à T=1"
    assert len(apres) == len(avant)


def test_dense_de_anchor_is_projected_to_the_portfolio_actually_deployed():
    """Le cas réel absent des anciens tests : le DE rend son vecteur dense.

    Seules quatre lignes sont effectivement retenues. Le kick doit donc partir
    de ces quatre lignes, pas considérer les 200 coordonnées positives comme
    200 positions détenues.
    """
    raw = np.linspace(1.0, 0.01, 200)
    deployed = np.zeros(200)
    deployed[[2, 7, 31, 150]] = [0.4, 0.3, 0.2, 0.1]

    sparse = project_preferences_to_deployed_support(raw, deployed)

    assert set(np.flatnonzero(sparse > 0.0)) == {2, 7, 31, 150}
    assert sparse[2] == pytest.approx(raw[2])
    assert sparse[150] == pytest.approx(raw[150])


def test_hot_kick_changes_every_effective_line_even_from_a_dense_de_anchor():
    raw = np.linspace(1.0, 0.01, 200)
    deployed = np.zeros(200)
    deployed[[2, 7, 31, 150]] = [0.4, 0.3, 0.2, 0.1]
    sparse = project_preferences_to_deployed_support(raw, deployed)
    before = set(np.flatnonzero(deployed > 0.0))

    kicked = kick_portfolio(
        sparse,
        np.random.default_rng(12),
        n_drop=len(before),
        n_add=len(before),
    )
    after = set(np.flatnonzero(kicked > 0.0))

    assert not (before & after)
    assert len(after) == len(before)


def test_a_cold_reheat_barely_touches_the_portfolio():
    x = np.zeros(200)
    x[:40] = 0.04
    avant = set(np.flatnonzero(x > 0).tolist())
    froid = kick_portfolio(x, np.random.default_rng(0),
                           n_drop=reheat_amplitude(0.05, len(avant)),
                           n_add=reheat_amplitude(0.05, len(avant)))
    apres = set(np.flatnonzero(froid > 0).tolist())
    assert len(avant & apres) >= len(avant) - 3


# ── Combien on RETIRE et combien on AJOUTE : deux tirages indépendants ──────
# Régression signalée : « ça peut ajouter ou enlever seulement 1 seule action,
# je veux que ça puisse changer complètement le portefeuille — si besoin ça
# enlève 10 et ajoute 15 autres. »
#
# `_reheat` passait la MÊME valeur à n_drop et n_add. La cardinalité du
# portefeuille était donc un invariant absolu du kick : un portefeuille à 11
# lignes restait à 11 lignes pour toujours, quelle que soit la température.


def test_the_two_sides_of_a_kick_are_drawn_independently():
    """Sans cela, le nombre de lignes ne peut JAMAIS changer."""
    rng = np.random.default_rng(0)
    tirages = [sample_kick_sizes(rng, 12) for _ in range(200)]
    assert any(d != a for d, a in tirages), "n_drop et n_add toujours égaux"
    assert any(a > d for d, a in tirages), "le portefeuille ne peut jamais grossir"
    assert any(d > a for d, a in tirages), "le portefeuille ne peut jamais maigrir"


def test_a_kick_always_changes_something():
    rng = np.random.default_rng(1)
    for _ in range(200):
        n_drop, n_add = sample_kick_sizes(rng, 5)
        assert (n_drop, n_add) != (0, 0)


def test_kick_sizes_stay_within_the_ceiling():
    rng = np.random.default_rng(2)
    for _ in range(200):
        n_drop, n_add = sample_kick_sizes(rng, 7)
        assert 0 <= n_drop <= 7 and 0 <= n_add <= 7


def test_a_kick_can_change_the_number_of_lines():
    """Le test qui compte : la cardinalité doit pouvoir bouger."""
    x = np.zeros(100)
    x[:20] = 0.05
    rng = np.random.default_rng(3)
    cardinalites = set()
    for _ in range(60):
        n_drop, n_add = sample_kick_sizes(rng, 15)
        variante = kick_portfolio(x, rng, n_drop=n_drop, n_add=n_add)
        cardinalites.add(int(np.count_nonzero(variante > 0)))
    assert len(cardinalites) > 1, "toutes les variantes ont le même nombre de lignes"
    assert max(cardinalites) > 20, "le portefeuille ne grossit jamais"
    assert min(cardinalites) < 20, "le portefeuille ne maigrit jamais"


def test_a_hot_kick_can_replace_ten_lines_with_fifteen_others():
    """L'exemple exact demandé : -10 / +15 doit être atteignable."""
    x = np.zeros(100)
    x[:20] = 0.05
    avant = set(np.flatnonzero(x > 0).tolist())
    variante = kick_portfolio(x, np.random.default_rng(4), n_drop=10, n_add=15)
    apres = set(np.flatnonzero(variante > 0).tolist())
    assert len(avant - apres) == 10        # 10 sorties
    assert len(apres - avant) == 15        # 15 entrées
    assert len(apres) == 25                # la cardinalité a bien changé


def test_multiscale_kicks_visit_every_scale_and_change_cardinality():
    rng = np.random.default_rng(44)
    draws = [sample_multiscale_kick_sizes(rng, 20, 30) for _ in range(2000)]
    assert {mode for mode, _drop, _add in draws} == {
        "local", "medium", "large", "global"
    }
    assert any(drop == 4 and add >= 5 for _mode, drop, add in draws)
    assert any(add > drop for _mode, drop, add in draws)
    assert any(drop > add for _mode, drop, add in draws)


def test_guided_repair_prefers_a_strong_uncorrelated_candidate():
    x = np.array([1.0, 0.0, 0.0, 0.0])
    scores = np.array([0.5, 1.0, 0.9, 0.1])
    corr = np.eye(4)
    corr[0, 1] = corr[1, 0] = 0.95
    corr[0, 2] = corr[2, 0] = 0.05
    rebuilt = guided_kick_portfolio(
        x,
        np.random.default_rng(3),
        n_drop=0,
        n_add=1,
        standalone_scores=scores,
        correlation=corr,
        guidance_weight=0.55,
    )
    assert rebuilt[2] > 0.0
    assert rebuilt[1] == 0.0


def test_guided_repair_ignores_inaccessible_candidates():
    x = np.array([1.0, 0.0, 0.0])
    rebuilt = guided_kick_portfolio(
        x,
        np.random.default_rng(17),
        n_drop=0,
        n_add=1,
        standalone_scores=np.array([0.1, 100.0, 0.2]),
        correlation=np.eye(3),
        guidance_weight=1.0,
        eligible_mask=np.array([True, False, True]),
    )
    assert rebuilt[1] == 0.0
    assert rebuilt[2] > 0.0


def test_guided_repair_uses_correlation_to_the_weighted_portfolio():
    """Un ETF/action peu corrélé au portefeuille global peut battre un candidat
    moins corrélé à la ligne la plus lourde prise isolément."""
    x = np.array([0.10, 0.90, 0.0, 0.0])
    scores = np.ones(4)
    corr = np.eye(4)
    # Candidat 2 : corrélation faible avec chaque ligne, mais positive partout.
    corr[2, 0] = corr[0, 2] = 0.15
    corr[2, 1] = corr[1, 2] = 0.15
    # Candidat 3 : corrélation un peu plus forte avec la petite ligne, mais
    # négative avec la ligne dominante : corrélation portefeuille globale nulle.
    corr[3, 0] = corr[0, 3] = 0.25
    corr[3, 1] = corr[1, 3] = -1.0
    rebuilt = guided_kick_portfolio(
        x,
        np.random.default_rng(11),
        n_drop=0,
        n_add=1,
        standalone_scores=scores,
        correlation=corr,
        guidance_weight=0.0,
    )
    assert rebuilt[3] > 0.0
    assert rebuilt[2] == 0.0


def test_guided_repair_can_disable_noise_for_singleton_correlation_probe():
    x = np.array([0.70, 0.30, 0.0, 0.0])
    scores = np.ones(4)
    corr = np.eye(4)
    corr[2, 0] = corr[0, 2] = 0.10
    corr[2, 1] = corr[1, 2] = 0.10
    corr[3, 0] = corr[0, 3] = 0.45
    corr[3, 1] = corr[1, 3] = 0.45
    rebuilt = guided_kick_portfolio(
        x,
        np.random.default_rng(99),
        n_drop=0,
        n_add=1,
        standalone_scores=scores,
        correlation=corr,
        guidance_weight=0.0,
        selection_noise=0.0,
    )
    assert rebuilt[2] > 0.0
    assert rebuilt[3] == 0.0


def test_geography_child_finances_a_new_country_inside_the_same_sector():
    # A et B sont de la finance française ; C est de la finance allemande ; D
    # est une technologie allemande. Le mouvement doit choisir C et réduire A/B.
    x = np.array([0.60, 0.40, 0.0, 0.0])
    sectors = np.array([
        [1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [0.0, 1.0]
    ])
    countries = np.array([
        [1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]
    ])
    child = geography_guided_child(
        x,
        np.random.default_rng(7),
        sector_matrix=sectors,
        country_matrix=countries,
        standalone_scores=np.ones(4),
        correlation=np.eye(4),
        temperature=0.5,
    )
    assert child[2] > 0.0
    assert child[3] == 0.0
    assert child[0] < x[0] or child[1] < x[1]


def test_diverse_archive_replaces_clones_but_keeps_distant_supports():
    first = np.array([0.5, 0.5, 0.0, 0.0, 0.0])
    clone = np.array([0.7, 0.3, 0.0, 0.0, 0.0])
    distant = np.array([0.0, 0.0, 0.5, 0.5, 0.0])
    archive = [(2.0, first)]
    archive = update_diverse_support_archive(
        archive, clone, 1.5, min_position=0.0, max_size=4, min_distance=0.3
    )
    archive = update_diverse_support_archive(
        archive, distant, 1.8, min_position=0.0, max_size=4, min_distance=0.3
    )
    assert len(archive) == 2
    assert archive[0][0] == pytest.approx(1.5)
    assert support_jaccard_distance(archive[0][1], archive[1][1]) == pytest.approx(1.0)


# ── Combien de lignes un kick peut OUVRIR ───────────────────────────────────
# Le plafond valait le SEUIL DU MALUS (23 lignes sur un cas réel) alors que le
# déploiement en tolère jusqu'à la CAPACITÉ ÉCONOMIQUE (100). Le kick ne pouvait
# donc jamais ouvrir plus de lignes que le portefeuille n'en garde : aucune
# compétition entre candidats, et le tri fait par le tirage plutôt que par
# l'objectif.


def test_a_kick_may_open_more_lines_than_the_portfolio_will_keep():
    """Le mécanisme existe et se règle par le facteur.

    Il est laissé à 1,0 par défaut : mesuré sur un banc de 300 titres, élargir
    le kick fait TOMBER le score de 15 % (8,65 -> 7,39) en produisant des
    portefeuilles dilués que le malus ne corrige pas — ils restent sous son
    seuil. L'écart ne se résorbe pas en quadruplant le budget de générations.
    """
    assert kick_line_budget(23, 100, factor=2.5) > 23


def test_the_economic_capacity_is_never_exceeded():
    """Sous le plancher de 1 %, une ligne de plus n'est pas achetable."""
    assert kick_line_budget(23, 30) <= 30
    # Broker minuscule : 2 lignes finançables, pas de kick absurde à 5.
    assert kick_line_budget(2, 2) == 2


def test_the_budget_grows_with_the_threshold():
    assert kick_line_budget(40, 1000) > kick_line_budget(20, 1000)


def test_at_least_one_line_is_always_openable():
    assert kick_line_budget(0, 0) == 1


def test_the_factor_is_configurable():
    assert kick_line_budget(20, 1000, factor=1.0) == 20
    assert kick_line_budget(20, 1000, factor=3.0) == 60


# ── Quelle PART de la population la température remanie ─────────────────────


def test_a_cold_reheat_replaces_almost_nobody():
    assert reheat_quota(0.05, 515) < 40


def test_a_reheat_never_replaces_the_entire_population():
    """Une secousse n'est pas une DESTRUCTION.

    Tout remplacer ne laisse au DE qu'une génération de croisement avant que la
    population soit jetée : il ne converge jamais, et un portefeuille tiré au
    hasard ne bat jamais un optimum affiné. Mesuré sur 400 générations, passer
    de 100 % à 70 % fait monter le score de 8,65 à 9,39, les améliorations de
    6 à 15 et les supports distincts de 4 à 12.
    """
    assert reheat_quota(1.0, 515) < 515


def test_the_preserved_share_follows_the_configured_cap():
    assert reheat_quota(1.0, 1000, max_share=0.70) == 700
    assert reheat_quota(1.0, 1000, max_share=0.25) == 250


def test_the_cap_is_neutral_at_its_upper_bound():
    """Un plafond de 100 % restitue exactement l'ancien comportement."""
    assert reheat_quota(1.0, 515, max_share=1.0) == 515


def test_below_the_cap_the_temperature_still_commands():
    """Non-régression : sous le plafond, rien ne change."""
    assert reheat_quota(0.10, 1000, max_share=0.70) == 100
    assert reheat_quota(0.50, 1000, max_share=0.70) == 500


def test_the_incumbent_now_always_survives():
    """L'index 0 est le dernier servi : un plafond < 100 % le protège seul.

    Aucun cas particulier n'est nécessaire — les cibles sont les PIRES d'abord.
    """
    energies = np.array([-5.0, 1.0, 3.0, 0.0, 2.0])
    ordre = list(np.argsort(energies)[::-1])
    assert ordre[0] == 2               # le pire d'abord
    assert ordre[-1] == 0              # l'incumbent en dernier
    for temperature in (0.05, 0.5, 1.0):
        assert 0 not in ordre[: reheat_quota(temperature, len(energies))]


# ── UNE SEULE loi gouverne la température ───────────────────────────────────
# Une « détente » ramenait la température à T0 dès qu'une refonte totale avait eu
# lieu, sans qu'aucun progrès ne l'ait justifié. Mesuré sur un run réel : une
# refonte complète toutes les 18 générations interrompait la dynamique naturelle
# du recuit — le solveur ne redescendait jamais dans le bassin qu'il venait
# d'ouvrir.


def test_nothing_resets_the_temperature_without_a_real_gain():
    """À stagnation continue, la température monte et ne redescend JAMAIS d'elle-
    même : seul un progrès la fait baisser."""
    t = float(Config.STARR_DE_T_MIN)
    precedente = t
    for streak in range(1, 400):
        t = _T(t, streak=streak)
        assert t >= precedente - 1e-12, "la température a baissé sans aucun gain"
        precedente = t
    assert t == pytest.approx(float(Config.STARR_DE_T_MAX))


def test_only_an_improvement_brings_the_temperature_down():
    chaud = float(Config.STARR_DE_T_MAX)
    assert _T(chaud, streak=50) == pytest.approx(chaud)      # plafonnée, pas rabaissée
    assert _T(chaud, gain=0.20) < chaud                      # seul le gain fait baisser


# ── Injection dans la population : les invariants de scipy ──────────────────


def test_injected_individuals_stay_inside_the_bounds():
    """`_ensure_constraint` ne s'applique qu'aux trials, jamais à la population."""
    x = np.zeros(30)
    x[:10] = 0.9
    for variante in build_kick_variants(
        x, np.random.default_rng(3), count=8, min_lines=2, max_lines=8
    ):
        borne = np.clip(variante, 0.0, 1.0)
        assert np.array_equal(variante, borne)


def test_the_sentinel_is_never_injectable():
    """Une énergie infinie rendrait `convergence` infinie et `converged()` faux."""
    energies = np.array([1.0, np.inf, INVALID_OBJECTIVE_ENERGY, -2.0])
    utilisables = np.isfinite(energies) & (energies < INVALID_OBJECTIVE_ENERGY)
    assert utilisables.tolist() == [True, False, False, True]


def test_the_worst_members_are_targeted_and_index_zero_is_spared():
    """L'index 0 est le meilleur : `best1bin` mute autour de lui."""
    energies = np.array([-5.0, 1.0, 3.0, 0.0, 2.0])
    ordre = [i for i in np.argsort(energies)[::-1] if i != 0]
    assert ordre[0] == 2                 # le pire d'abord
    assert 0 not in ordre                # jamais l'incumbent


# ── Screening initial (conservé de l'ancienne seed froide) ──────────────────


def _prefer_first_asset(X):
    return -np.asarray(X, dtype=float)[0, :]


def test_the_initial_screening_still_returns_sorted_elites():
    elites = sample_elite_seeds(
        12, np.random.default_rng(0), _prefer_first_asset,
        batch_size=64, max_batches=5, n_elites=10,
    )
    energies = [float(_prefer_first_asset(np.asarray(x)[:, None])[0]) for x in elites]
    assert len(elites) == 10
    assert energies == sorted(energies)


# ── Bout en bout : une seule seed, bornée en mode programmatique ────────────


def test_the_anchor_actually_leaves_the_incumbent_on_a_plateau(monkeypatch):
    """Sur un plateau, l'exploration doit VRAIMENT changer de point de départ.

    Régression signalée : « les mêmes tickers du début à la fin ». L'ancre étant
    systématiquement recollée à l'incumbent, toutes les variantes repartaient du
    même portefeuille et l'on revisitait sans fin les mêmes supports. Le compteur
    `anchor_drifts` reste à zéro tant que ce défaut est là.
    """
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 5000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 40)
    monkeypatch.setattr(Config, "STARR_DE_MAX_REHEATS", 30)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 5)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 4)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 2)

    rng = np.random.default_rng(5)
    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rets = pd.DataFrame(
        rng.normal(0.0006, 0.02, (jours, 12)), columns=[f"T{i}" for i in range(12)]
    )

    _poids, _score, diagnostics = optimize_portfolio_de(
        list(rets.columns), rets, [[True]] * 12, ["IBKR"], n_sim=400,
        benchmark_returns=rng.normal(0.0004, 0.01, jours),
        return_diagnostics=True,
    )

    annealing = diagnostics["termination"]["annealing"]
    assert annealing["reheats"] > 0, "aucun réchauffage : le test ne prouve rien"
    assert annealing["anchor_drifts"] > 0, (
        "l'ancre n'a jamais quitté l'incumbent : les perturbations repartent "
        "toutes du même portefeuille"
    )


def test_a_hot_epoch_probes_the_whole_universe_at_the_forced_floor(monkeypatch):
    from app.services.finance.buffett import optimizer

    tickers = [f"T{i}" for i in range(8)]
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 5000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_T0", 1.0)
    monkeypatch.setattr(Config, "STARR_LNS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_T_MAX", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 4)
    monkeypatch.setattr(Config, "STARR_DE_MAX_REHEATS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MIN_IMPROVEMENT", 1e9)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 12)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 1)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 2)
    monkeypatch.setattr(Config, "STARR_DE_FORCED_PROBE_BATCH_SIZE", 3)
    monkeypatch.setattr(Config, "STARR_DE_FORCED_PROBE_ELITES", 4)
    monkeypatch.setattr(Config, "STARR_DE_FUNNEL_CONSTRAINED_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_FUNNEL_FREE_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_FUNNEL_FREE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set())
    monkeypatch.setattr(
        optimizer,
        "load_asset_classes",
        lambda: {ticker: "actions" for ticker in tickers},
    )

    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rng = np.random.default_rng(91)
    returns = pd.DataFrame(
        rng.normal(0.0004, 0.01, (jours, len(tickers))), columns=tickers
    )
    forced_temperatures: list[float] = []

    def _progress(_seed, _iteration, _convergence, _best=None, **kwargs):
        if kwargs.get("forced_labels"):
            forced_temperatures.append(float(kwargs["temperature"]))

    _weights, _score, diagnostics = optimizer.optimize_portfolio_de(
        tickers,
        returns,
        [[True]] * len(tickers),
        ["IBKR"],
        n_sim=100,
        benchmark_returns=rng.normal(0.0003, 0.009, jours),
        progress_cb=_progress,
        return_diagnostics=True,
    )

    annealing = diagnostics["termination"]["annealing"]
    assert annealing["exploration_epochs"] >= 1
    assert annealing["forced_probes_tested"] >= len(tickers)
    assert annealing["forced_probes_injected"] >= 1
    assert annealing["forced_searches_completed"] == annealing["forced_probes_injected"]
    assert annealing["forced_floor"] == pytest.approx(0.10)
    assert annealing["probe_floors"] == pytest.approx([0.01, 0.03, 0.05, 0.10])
    assert annealing["funnel_constrained_generations"] == 1
    assert annealing["funnel_free_generations"] == 2
    assert forced_temperatures
    assert forced_temperatures == pytest.approx(
        [float(Config.STARR_DE_T_MAX)] * len(forced_temperatures)
    )


def test_lns_replaces_forced_funnels_and_reports_multiscale_moves(monkeypatch):
    from app.services.finance.buffett import optimizer

    tickers = [f"T{i}" for i in range(8)]
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 5000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_LNS_ENABLED", True)
    monkeypatch.setattr(Config, "STARR_DE_T0", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_T_MAX", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 4)
    monkeypatch.setattr(Config, "STARR_DE_MAX_REHEATS", 2)
    monkeypatch.setattr(Config, "STARR_DE_MIN_IMPROVEMENT", 1e9)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 12)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 1)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 2)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set())
    monkeypatch.setattr(
        optimizer,
        "load_asset_classes",
        lambda: {ticker: "actions" for ticker in tickers},
    )

    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rng = np.random.default_rng(92)
    returns = pd.DataFrame(
        rng.normal(0.0004, 0.01, (jours, len(tickers))), columns=tickers
    )
    _weights, _score, diagnostics = optimizer.optimize_portfolio_de(
        tickers,
        returns,
        [[True]] * len(tickers),
        ["IBKR"],
        n_sim=100,
        benchmark_returns=rng.normal(0.0003, 0.009, jours),
        return_diagnostics=True,
    )

    annealing = diagnostics["termination"]["annealing"]
    lns = annealing["large_neighborhood_search"]
    assert lns["enabled"] is True
    assert sum(lns["moves"].values()) > 0
    assert annealing["forced_searches_completed"] == 0
    assert annealing["forced_probes_tested"] == 0


def test_lns_keeps_injecting_when_defensive_repair_would_collapse_supports(monkeypatch):
    from app.services.finance.buffett import lookthrough, optimizer

    tickers = [f"T{i}" for i in range(12)]
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 5000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.30)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 0.25)
    monkeypatch.setattr(Config, "MAX_REGION_PCT", 0.50)
    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_LNS_ENABLED", True)
    monkeypatch.setattr(Config, "STARR_DE_T0", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_T_MAX", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 4)
    monkeypatch.setattr(Config, "STARR_DE_MAX_REHEATS", 2)
    monkeypatch.setattr(Config, "STARR_DE_MIN_IMPROVEMENT", 1e9)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 3)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 4)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set())
    monkeypatch.setattr(
        optimizer,
        "load_asset_classes",
        lambda: {ticker: "actions" for ticker in tickers},
    )
    monkeypatch.setattr(
        lookthrough,
        "load_lookthrough",
        lambda: (
            {ticker: float(index < 4) for index, ticker in enumerate(tickers)},
            {ticker: {"France": 1.0} for ticker in tickers},
        ),
    )

    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rng = np.random.default_rng(93)
    returns = pd.DataFrame(
        rng.normal(0.0004, 0.01, (jours, len(tickers))), columns=tickers
    )
    _weights, _score, diagnostics = optimizer.optimize_portfolio_de(
        tickers,
        returns,
        [[True]] * len(tickers),
        ["IBKR"],
        n_sim=100,
        benchmark_returns=rng.normal(0.0003, 0.009, jours),
        return_diagnostics=True,
    )

    evolution = diagnostics["termination"]["annealing"]["evolutionary_generation"]
    assert evolution["generations"] >= 1
    assert evolution["injected"] > 0


def test_infeasible_previous_champion_is_repaired_before_de(monkeypatch):
    """Un ancien portefeuille invalide ne doit pas devenir une fausse sentinelle."""
    from app.services.finance.buffett import optimizer

    tickers = [f"T{i}" for i in range(6)]
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 5000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.30)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 4)
    monkeypatch.setattr(Config, "STARR_DE_MAX_REHEATS", 2)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 12)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 1)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 2)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set())
    monkeypatch.setattr(
        optimizer,
        "load_asset_classes",
        lambda: {ticker: "actions" for ticker in tickers},
    )

    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rng = np.random.default_rng(94)
    returns = pd.DataFrame(
        rng.normal(0.0004, 0.01, (jours, len(tickers))), columns=tickers
    )
    _weights, _score, diagnostics = optimizer.optimize_portfolio_de(
        tickers,
        returns,
        [[True]] * len(tickers),
        ["IBKR"],
        n_sim=100,
        benchmark_returns=rng.normal(0.0003, 0.009, jours),
        current_weights={"T0": 1.0},
        defensive_exposures_by_ticker={ticker: float(index > 0) for index, ticker in enumerate(tickers)},
        return_diagnostics=True,
    )

    champion = diagnostics["previous_run_champion"]
    assert champion["accepted_as_initial_incumbent"] is True
    assert champion["feasible_under_current_constraints"] is False
    assert champion["repaired_before_optimization"] is True
    assert champion["repaired_score"] is not None
    assert diagnostics["benchmark_relative"]["search_objective_score"] < INVALID_OBJECTIVE_ENERGY


def test_unreachable_defensive_floor_is_clamped_to_executable_maximum(monkeypatch):
    """Un plancher supérieur aux plafonds reste actif, mais devient faisable."""
    from app.services.finance.buffett import lookthrough, optimizer

    tickers = [f"T{i}" for i in range(5)]
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 5000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.30)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_POSITION_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 0.25)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT_OVERRIDES", {})
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_MAX_REHEATS", 1)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 8)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 1)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 2)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set())
    monkeypatch.setattr(
        optimizer,
        "load_asset_classes",
        lambda: {ticker: "actions" for ticker in tickers},
    )
    monkeypatch.setattr(
        lookthrough,
        "load_lookthrough",
        lambda: (
            {ticker: 1.0 for ticker in tickers},
            {ticker: {"France": 1.0} for ticker in tickers},
        ),
    )

    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rng = np.random.default_rng(95)
    returns = pd.DataFrame(
        rng.normal(0.0004, 0.01, (jours, len(tickers))), columns=tickers
    )
    _weights, _score, diagnostics = optimizer.optimize_portfolio_de(
        tickers,
        returns,
        [[True]] * len(tickers),
        ["IBKR"],
        n_sim=100,
        benchmark_returns=rng.normal(0.0003, 0.009, jours),
        sector_by_ticker={ticker: "Healthcare" for ticker in tickers},
        return_diagnostics=True,
    )

    universe = diagnostics["asset_universe"]
    assert universe["defensive_floor_enabled"] is True
    assert universe["defensive_floor_requested_pct"] == pytest.approx(0.30)
    assert universe["defensive_floor_relaxed_for_feasibility"] is True
    assert universe["maximum_achievable_defensive_pct"] == pytest.approx(0.25)
    assert universe["defensive_floor_effective_pct"] < 0.30
    assert np.isfinite(_score)


def test_a_single_continuous_seed_runs_and_reports_a_temperature(monkeypatch):
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 25)
    monkeypatch.setattr(Config, "STARR_DE_MAX_REHEATS", 2)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 5)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 4)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 2)

    rng = np.random.default_rng(5)
    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rets = pd.DataFrame(
        rng.normal(0.0006, 0.02, (jours, 6)), columns=[f"T{i}" for i in range(6)]
    )
    vus: list[tuple] = []

    def _cb(seed_num, iteration, convergence, best=None, *, seed_score=None,
            temperature=None):
        vus.append((seed_num, iteration, temperature))

    poids, score = optimize_portfolio_de(
        list(rets.columns), rets, [[True]] * 6, ["IBKR"], n_sim=400,
        benchmark_returns=rng.normal(0.0004, 0.01, jours),
        progress_cb=_cb,
    )

    assert np.isfinite(score)
    assert vus, "aucune génération rapportée"
    # UNE seule seed : le numéro ne bouge jamais.
    assert {s for s, _i, _t in vus} == {1}
    # Les générations sont strictement croissantes — invariant du graphe côté front.
    iterations = [i for _s, i, _t in vus]
    assert iterations == sorted(iterations)
    assert len(set(iterations)) == len(iterations)
    # La température est bien transmise et reste dans ses bornes.
    temperatures = [t for _s, _i, t in vus if t is not None]
    assert temperatures
    assert all(
        float(Config.STARR_DE_T_MIN) - 1e-9 <= t <= float(Config.STARR_DE_T_MAX) + 1e-9
        for t in temperatures
    )


def test_a_programmatic_run_stops_on_the_requested_hot_plateau(monkeypatch):
    """Sans bouton d'arrêt possible, le mode programmatique reste borné."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 40)
    monkeypatch.setattr(Config, "STARR_DE_HOT_CONVERGENCE_GENERATIONS", 3)
    monkeypatch.setattr(Config, "STARR_DE_MIN_IMPROVEMENT", 1e9)
    monkeypatch.setattr(Config, "STARR_DE_FORCED_FLOOR", 0.0)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 12)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 4)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 3)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 2)

    rng = np.random.default_rng(11)
    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    # Rendements plats : après la première mesure, le solveur reste à T=1 sans
    # amélioration et doit donc conclure au troisième point chaud consécutif.
    rets = pd.DataFrame(
        rng.normal(0.0005, 0.02, (jours, 3)), columns=["A", "B", "C"]
    )
    poids, score, diagnostics = optimize_portfolio_de(
        ["A", "B", "C"], rets, [[True]] * 3, ["IBKR"], n_sim=300,
        benchmark_returns=rng.normal(0.0004, 0.01, jours),
        continuous_until_stopped=False,
        return_diagnostics=True,
    )
    assert np.isfinite(score)
    assert np.isfinite(np.asarray(poids, dtype=float)).all()
    termination = diagnostics["termination"]
    assert termination["detail"] == "convergence_plateau_chaud"
    assert termination["hot_plateau_streak"] == 3
    assert termination["generations"] == 4


def test_interactive_run_restarts_an_independent_seed_before_stop(monkeypatch):
    """Un plateau chaud polit le support puis change réellement de seed."""
    from app.services.finance.buffett.optimizer import optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 3)
    monkeypatch.setattr(Config, "STARR_DE_HOT_CONVERGENCE_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_T0", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_T_MIN", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_T_MAX", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_MIN_IMPROVEMENT", 1e9)
    monkeypatch.setattr(Config, "STARR_DE_FORCED_FLOOR", 0.0)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 10)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 12)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 3)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 1)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 2)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(Config, "STARR_EVOLUTION_PARENT_COUNT", 1)
    monkeypatch.setattr(Config, "STARR_EVOLUTION_CHILDREN_PER_PARENT", 2)
    monkeypatch.setattr(Config, "STARR_EVOLUTION_GEOGRAPHY_CHILDREN", 0)
    monkeypatch.setattr(Config, "STARR_EVOLUTION_GLOBAL_LOCAL_CHILDREN", 1)
    monkeypatch.setattr(Config, "STARR_EVOLUTION_RANDOM_CANDIDATES", 1)

    latest = {"seed": 0, "iteration": 0, "reports": 0}
    seen_seeds: set[int] = set()

    def _progress(seed_num, iteration, _convergence, _best=None, **_kwargs):
        latest["seed"] = int(seed_num)
        latest["iteration"] = int(iteration)
        latest["reports"] += 1
        seen_seeds.add(int(seed_num))

    rng = np.random.default_rng(41)
    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    returns = pd.DataFrame(
        rng.normal(0.0005, 0.02, (jours, 3)), columns=["A", "B", "C"]
    )
    _weights, _score, diagnostics = optimize_portfolio_de(
        list(returns.columns),
        returns,
        [[True]] * 3,
        ["IBKR"],
        n_sim=100,
        benchmark_returns=rng.normal(0.0004, 0.01, jours),
        progress_cb=_progress,
        should_stop=lambda: (
            (latest["seed"] >= 2 and latest["iteration"] >= 1)
            or latest["reports"] >= 12
        ),
        continuous_until_stopped=True,
        return_diagnostics=True,
    )

    termination = diagnostics["termination"]
    assert termination["reason"] == "user_stop"
    assert termination["detail"] == "convergence_apres_arret"
    assert seen_seeds >= {1, 2}
    assert termination["generations"] > 3
    assert termination["independent_seeds_completed"] >= 1
    assert termination["current_seed_number"] >= 2
    assert termination["persistent_until_stopped"] is True


def test_independent_seed_falls_back_to_feasible_global_champion(monkeypatch):
    """Un redémarrage ne doit pas échouer si le hasard ne tire aucun seed faisable."""
    from app.services.finance.buffett import optimizer

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 3)
    monkeypatch.setattr(Config, "STARR_DE_HOT_CONVERGENCE_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_T0", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_T_MIN", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_T_MAX", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_MIN_IMPROVEMENT", 1e9)
    monkeypatch.setattr(Config, "STARR_DE_FORCED_FLOOR", 0.0)
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 10)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 12)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 1)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 2)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 1)
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: set())
    search_calls = {"count": 0}

    def _no_random_seed(*_args, **_kwargs):
        search_calls["count"] += 1
        raise optimizer.PositiveSeedNotFound("test: aucun seed aléatoire faisable")

    monkeypatch.setattr(optimizer, "find_positive_random_seed", _no_random_seed)

    latest = {"seed": 0, "iteration": 0}

    def _progress(seed_num, iteration, _convergence, _best=None, **_kwargs):
        latest["seed"] = int(seed_num)
        latest["iteration"] = int(iteration)

    rng = np.random.default_rng(42)
    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    returns = pd.DataFrame(
        rng.normal(0.0005, 0.02, (jours, 3)), columns=["A", "B", "C"]
    )
    _weights, _score, diagnostics = optimizer.optimize_portfolio_de(
        list(returns.columns),
        returns,
        [[True]] * 3,
        ["IBKR"],
        n_sim=100,
        benchmark_returns=rng.normal(0.0004, 0.01, jours),
        current_weights={"A": 1.0},
        progress_cb=_progress,
        should_stop=lambda: latest["seed"] >= 3 and latest["iteration"] >= 1,
        continuous_until_stopped=True,
        return_diagnostics=True,
    )

    termination = diagnostics["termination"]
    assert termination["independent_seeds_completed"] >= 2
    assert termination["current_seed_number"] >= 3
    assert search_calls["count"] == 1
    assert termination["reason"] == "user_stop"
    assert np.isfinite(_score)


def test_a_stop_request_always_terminates_even_without_convergence(monkeypatch):
    """Une demande d'arrêt doit TOUJOURS aboutir.

    `solver.converged()` mesure la dispersion des énergies de toute la
    population, pas la progression du score : il pouvait rester faux pendant des
    milliers de générations alors que le meilleur point était figé, donnant
    l'impression d'un run bloqué. On force ici ce cas — tolérance de convergence
    inatteignable — et on exige quand même une terminaison.
    """
    from scipy.optimize._differentialevolution import DifferentialEvolutionSolver

    from app.services.finance.buffett import optimizer

    optimize_portfolio_de = optimizer.optimize_portfolio_de

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 1000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_CARD_BETA", 0.0)
    monkeypatch.setattr(Config, "STARR_STRESS_WEIGHT", 0.0)
    monkeypatch.setattr(Config, "TRANSACTION_COSTS_ENABLED", False)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 1)
    # Garde-fou LARGE devant la fenêtre de stagnation : si le test se termine,
    # c'est par la nouvelle porte de sortie, pas parce qu'il a tapé le plafond.
    monkeypatch.setattr(Config, "STARR_DE_MAX_GENERATIONS", 400)
    monkeypatch.setattr(Config, "STARR_DE_HOT_CONVERGENCE_GENERATIONS", 5)
    monkeypatch.setattr(Config, "STARR_DE_TOL", 1e-300)  # converged() jamais vrai
    monkeypatch.setattr(
        DifferentialEvolutionSolver,
        "converged",
        lambda _self: False,
    )
    monkeypatch.setattr(Config, "STARR_DE_POPSIZE", 12)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_BATCH_SIZE", 16)
    monkeypatch.setattr(Config, "STARR_DE_POSITIVE_INIT_MAX_BATCHES", 4)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_BATCHES", 2)
    monkeypatch.setattr(Config, "STARR_DE_ELITE_COUNT", 3)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 2)

    rng = np.random.default_rng(3)
    jours = int(Config.STARR_MIN_HISTORY_DAYS)
    rets = pd.DataFrame(
        rng.normal(0.0005, 0.02, (jours, 4)), columns=["A", "B", "C", "D"]
    )

    poids, score, diagnostics = optimize_portfolio_de(
        ["A", "B", "C", "D"], rets, [[True]] * 4, ["IBKR"], n_sim=300,
        benchmark_returns=rng.normal(0.0004, 0.01, jours),
        should_stop=lambda: True,          # arrêt demandé dès la 1re génération
        continuous_until_stopped=True,     # mode des runs réels
        return_diagnostics=True,
    )

    assert np.isfinite(score)
    termination = diagnostics["termination"]
    # `reason` dit qui a arrêté, `detail` comment la boucle a conclu.
    assert termination["reason"] == "user_stop"
    assert termination["detail"] == "convergence_apres_arret"
    # La sortie n'a pas attendu le garde-fou des 400 générations.
    assert termination["generations"] < 400
    assert termination["hot_plateau_streak"] == 5
    # La validation demandée reste entièrement à température maximale.
    assert termination["annealing"]["temperature_final"] == pytest.approx(
        float(Config.STARR_DE_T_MAX)
    )
