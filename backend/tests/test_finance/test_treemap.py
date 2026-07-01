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


# ── Look-through ETF (frac_by_ticker) ───────────────────────────────────────

def test_frac_by_ticker_splits_etf_across_countries():
    """Un ETF connu du look-through est réparti sur plusieurs pays plutôt
    qu'attribué en bloc à son pays de cotation."""
    positions = [{"ticker": "CW8.PA", "valeur_actuelle": 1000.0, "devise": "EUR"}]
    nodes = get_treemap_data(
        positions,
        group_by="pays",
        label_by_ticker={"CW8.PA": "France"},
        frac_by_ticker={"CW8.PA": {"United States": 0.7, "France": 0.3}},
    )
    roots = {n["label"]: n["valeur"] for n in nodes if n["parent"] == ""}
    assert roots == {"United States": 700.0, "France": 300.0}
    # deux enfants CW8.PA (un par pays), rattachés chacun à leur racine
    children = [n for n in nodes if n["parent"] != ""]
    assert len(children) == 2
    assert {c["label"] for c in children} == {"CW8.PA"}
    assert {c["id"] for c in children} == {"United States/CW8.PA", "France/CW8.PA"}


def test_frac_by_ticker_falls_back_to_label_when_ticker_unknown():
    """Une action non couverte par le look-through garde l'attribution simple."""
    positions = [{"ticker": "AAPL", "valeur_actuelle": 500.0, "devise": "USD"}]
    nodes = get_treemap_data(
        positions,
        group_by="pays",
        label_by_ticker={"AAPL": "United States"},
        frac_by_ticker={"CW8.PA": {"United States": 0.7, "France": 0.3}},
    )
    roots = [n for n in nodes if n["parent"] == ""]
    assert roots == [{"id": "United States", "parent": "", "label": "United States", "valeur": 500.0}]


def test_frac_by_ticker_mixes_with_plain_positions():
    positions = [
        {"ticker": "CW8.PA", "valeur_actuelle": 1000.0, "devise": "EUR"},
        {"ticker": "AAPL", "valeur_actuelle": 500.0, "devise": "USD"},
    ]
    nodes = get_treemap_data(
        positions,
        group_by="pays",
        label_by_ticker={"CW8.PA": "France", "AAPL": "United States"},
        frac_by_ticker={"CW8.PA": {"United States": 0.7, "France": 0.3}},
    )
    roots = {n["label"]: n["valeur"] for n in nodes if n["parent"] == ""}
    # 700 (CW8.PA) + 500 (AAPL) = 1200 aux États-Unis, 300 en France
    assert roots == {"United States": 1200.0, "France": 300.0}
