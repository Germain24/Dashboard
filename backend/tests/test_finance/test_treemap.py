"""Treemap hiérarchique secteurs/pays/devises (nodes id/parent/label/valeur)."""

from app.services.finance.risk import get_treemap_data

POSITIONS = [
    {"ticker": "AAPL", "valeur_actuelle": 600.0, "devise": "USD"},
    {"ticker": "MSFT", "valeur_actuelle": 300.0, "devise": "USD"},
    {"ticker": "OR.PA", "valeur_actuelle": 100.0, "devise": "EUR"},
]


def test_empty_returns_no_nodes():
    assert get_treemap_data([]) == []


def test_zero_value_positions_excluded():
    assert get_treemap_data([{"ticker": "X", "valeur_actuelle": 0}]) == []


def test_nodes_have_schema_shape():
    """Chaque node doit avoir id/parent/label/valeur (contrat TreemapNodeOut)."""
    nodes = get_treemap_data(POSITIONS, group_by="devise")
    assert nodes  # non vide
    for n in nodes:
        assert set(n) == {"id", "parent", "label", "valeur"}


def test_group_by_devise_builds_roots_and_children():
    nodes = get_treemap_data(POSITIONS, group_by="devise")
    roots = [n for n in nodes if n["parent"] == ""]
    # 2 devises : USD (900) et EUR (100)
    assert {r["label"] for r in roots} == {"USD", "EUR"}
    usd = next(r for r in roots if r["label"] == "USD")
    assert usd["valeur"] == 900.0
    # racines triées par valeur décroissante
    assert roots[0]["label"] == "USD"
    # enfants (tickers) rattachés à leur racine devise
    children = [n for n in nodes if n["parent"] == usd["id"]]
    assert {c["label"] for c in children} == {"AAPL", "MSFT"}


def test_group_by_secteur_uses_label_mapping():
    nodes = get_treemap_data(
        POSITIONS,
        group_by="secteur",
        label_by_ticker={"AAPL": "Tech", "MSFT": "Tech", "OR.PA": "Conso"},
    )
    roots = [n for n in nodes if n["parent"] == ""]
    assert {r["label"] for r in roots} == {"Tech", "Conso"}
    tech = next(r for r in roots if r["label"] == "Tech")
    assert tech["valeur"] == 900.0


def test_missing_label_is_inconnu():
    nodes = get_treemap_data(POSITIONS, group_by="secteur", label_by_ticker={})
    roots = [n for n in nodes if n["parent"] == ""]
    assert roots[0]["label"] == "Inconnu"
