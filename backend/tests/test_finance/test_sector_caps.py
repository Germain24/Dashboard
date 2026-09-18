"""Plafonds sectoriels différenciés (poche or bornée sous le plafond commun)."""

import numpy as np
import pytest


def test_gold_labels_all_collapse_to_the_same_compartment():
    """« Métaux précieux » et « Or physique » ne doivent pas ouvrir deux poches.

    Deux libellés distincts donneraient deux compartiments plafonnés séparément,
    soit le double d'or accepté.
    """
    from app.services.finance.buffett.sector_constraints import SectorCaps

    caps = SectorCaps(0.25, {"Or": 0.10})

    for label in ("Or", "or", "Métaux précieux", "metaux precieux", "Or physique",
                  "gold", "Gold", "PRECIOUS METALS"):
        assert caps.for_label(label) == pytest.approx(0.10), label
    assert caps.for_label("Technologie") == pytest.approx(0.25)
    assert caps.for_label(None) == pytest.approx(0.25)


def test_sector_caps_from_config_reads_config_at_call_time(monkeypatch):
    """Plusieurs tests monkeypatchent MAX_SECTOR_PCT : la lecture doit être tardive."""
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.sector_constraints import SectorCaps

    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 1.0)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT_OVERRIDES", {})
    assert SectorCaps.from_config().for_label("Or") == pytest.approx(1.0)

    monkeypatch.setattr(Config, "MAX_SECTOR_PCT", 0.25)
    monkeypatch.setattr(Config, "MAX_SECTOR_PCT_OVERRIDES", {"Or": 0.10})
    assert SectorCaps.from_config().for_label("Or") == pytest.approx(0.10)


def test_float_cap_still_accepted_everywhere():
    """Rétro-compatibilité : l'ancien appel avec un float ne change pas."""
    from app.services.finance.buffett.sector_constraints import as_sector_caps

    caps = as_sector_caps(0.25)
    assert caps.is_uniform()
    assert caps.for_label("Or") == pytest.approx(0.25)


def test_gold_variants_are_canonicalised_before_reaching_the_cap():
    """Le regroupement se fait sur le libellé résolu en amont, pas sur le brut.

    C'est `_usable_category` qui garantit qu'un ETF « Métaux précieux » et un ETF
    « Or physique » tombent dans le MÊME compartiment : sans cela, chacun aurait
    droit à sa propre poche de 10 %.
    """
    from app.services.finance.buffett.sector_constraints import _usable_category

    for label in ("Or", "Métaux précieux", "Or physique", "gold", "Precious Metals"):
        assert _usable_category(label) == "Or", label
    assert _usable_category("Technologie") == "Technologie"


def test_gold_is_capped_below_the_common_sector_limit():
    from app.services.finance.buffett.optimizer import cap_sector_weights_cube
    from app.services.finance.buffett.sector_constraints import SectorCaps

    # 3 tickers : deux lignes or (déjà canonisées en amont), une techno.
    cube = np.array([[[0.20]], [[0.10]], [[0.30]]], dtype=float)
    labels = ["Or", "Or", "Technologie"]

    capped = cap_sector_weights_cube(cube, labels, SectorCaps(0.25, {"Or": 0.10}))

    gold = float(capped[0].sum() + capped[1].sum())
    assert gold == pytest.approx(0.10, abs=1e-9)
    # La techno reste sous le plafond commun, inchangée.
    assert float(capped[2].sum()) == pytest.approx(0.25, abs=1e-9)


def test_uniform_float_cap_matches_previous_behaviour():
    from app.services.finance.buffett.optimizer import cap_sector_weights_cube

    cube = np.array([[[0.40]], [[0.10]]], dtype=float)
    labels = ["Or", "Technologie"]

    capped = cap_sector_weights_cube(cube, labels, 0.25)

    assert float(capped[0].sum()) == pytest.approx(0.25, abs=1e-9)
    assert float(capped[1].sum()) == pytest.approx(0.10, abs=1e-9)


def test_matrix_path_requires_sector_names_when_caps_differ():
    """Sans les noms de colonnes, la surcharge or serait silencieusement ignorée."""
    from app.services.finance.buffett.optimizer import cap_sector_weights_cube
    from app.services.finance.buffett.sector_constraints import SectorCaps

    cube = np.array([[[0.30]], [[0.30]]], dtype=float)
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=float)

    with pytest.raises(ValueError, match="sector_names"):
        cap_sector_weights_cube(
            cube, ["Or", "Technologie"], SectorCaps(0.25, {"Or": 0.10}),
            matrix,
        )


def test_matrix_path_applies_the_gold_override():
    from app.services.finance.buffett.optimizer import cap_sector_weights_cube
    from app.services.finance.buffett.sector_constraints import SectorCaps

    # Ticker 0 = 100 % or ; ticker 1 = ETF mixte 50/50 or-techno.
    cube = np.array([[[0.12]], [[0.20]]], dtype=float)
    matrix = np.array([[1.0, 0.0], [0.5, 0.5]], dtype=float)

    capped = cap_sector_weights_cube(
        cube, ["Or", "Mixte"], SectorCaps(0.25, {"Or": 0.10}),
        matrix, ["Or", "Technologie"],
    )

    exposure_gold = float(matrix[:, 0] @ capped.sum(axis=1).ravel())
    assert exposure_gold <= 0.10 + 1e-9


def test_redeployment_never_pushes_gold_back_over_its_own_cap():
    """Le cash libéré doit repartir ailleurs, pas regonfler la poche or."""
    from app.services.finance.buffett.optimizer import redeploy_uninvested_cube
    from app.services.finance.buffett.sector_constraints import SectorCaps

    cube = np.array([[[0.50]], [[0.30]]], dtype=float)
    labels = ["Or", "Technologie"]

    capped = redeploy_uninvested_cube(
        cube,
        np.array([True, False]),
        0.50,
        labels,
        SectorCaps(0.60, {"Or": 0.10}),
        [1.0],
        iterations=3,
    )

    assert float(capped[0].sum()) <= 0.10 + 1e-9


def test_geographic_label_never_becomes_a_sector_compartment():
    """« USA » / « Monde » sont des pays, pas des secteurs.

    Ils restent des catégories VALIDES pour l'éligibilité (un ETF Monde doit
    rester investissable) mais ne doivent ouvrir aucun compartiment sectoriel :
    sinon ils consomment un plafond de secteur et apparaissent dans la
    contribution au risque sectoriel sous un nom de pays.
    """
    from app.services.finance.buffett.sector_constraints import (
        _usable_category,
        constrained_sector_labels,
        is_geographic_label,
    )

    for label in ("USA", "Monde", "Zone euro", "Japon", "Allemagne", "Emergents"):
        assert is_geographic_label(label), label
        # Éligibilité préservée : le ticker n'est PAS écarté de l'univers.
        assert _usable_category(label) is not None, label
    assert not is_geographic_label("Or")
    assert not is_geographic_label("Technologie")

    labels = constrained_sector_labels(
        ["WORLD", "GLDM", "NVDA"],
        is_etf=[True, True, False],
        fallback_sectors={"WORLD": "Monde", "GLDM": "Or", "NVDA": "Technologie"},
    )
    assert labels == [None, "Or", "Technologie"]


def test_sector_matrix_ignores_a_geographic_fallback():
    """Sans composition sectorielle connue, un ETF pays ne crée pas de pseudo-secteur."""
    from app.services.finance.buffett.sector_lookthrough import sector_matrix

    matrix, names = sector_matrix(
        ["WORLD", "NVDA"],
        {"NVDA": {"Technologie": 1.0}},
        ["Monde", "Technologie"],
    )

    assert names == ["Technologie"]
    assert matrix[0].sum() == 0.0      # l'ETF monde n'est rattaché à aucun secteur
    assert matrix[1][0] == 1.0
