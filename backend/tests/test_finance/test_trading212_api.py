"""Client API Trading 212 : conversions, dédoublonnage, pagination, snapshots.

Aucun appel réseau : les charges utiles reproduisent fidèlement les réponses de
l'API v0 (relevées sur le compte réel), les fonctions testées étant pures.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.finance import trading212_api as api

# Ordre exécuté tel que renvoyé par /api/v0/equity/history/orders.
_ORDER = {
    "order": {
        "id": 54903239349, "ticker": "SGLNl_EQ", "status": "FILLED",
        "filledValue": 100.03, "side": "BUY", "currency": "EUR",
        "createdAt": "2026-07-29T21:28:51.000Z",
        "instrument": {"ticker": "SGLNl_EQ", "isin": "IE00B4ND3602",
                       "currency": "GBX"},
    },
    "fill": {
        "id": 54915406142, "quantity": 1.45954774, "price": 5871.0,
        "filledAt": "2026-07-30T07:00:32.000Z",
        "walletImpact": {
            "currency": "EUR", "netValue": 100.03, "fxRate": 85.79299941,
            "taxes": [{"name": "CURRENCY_CONVERSION_FEE", "quantity": -0.15,
                       "currency": "EUR"}],
        },
    },
}

_SYMBOLS = {"SGLNl_EQ": "SGLN.L", "BAH_US_EQ": "BAH"}


def test_order_to_transaction_isole_les_frais_du_prix():
    """`filledValue` inclut les frais pour un achat : le prix unitaire brut
    doit les exclure, sinon ils seraient comptés deux fois (frais + prix)."""
    tx = api.order_to_transaction(_ORDER, _SYMBOLS)

    assert tx["type"] == "achat"
    assert tx["ticker"] == "SGLN.L"          # symbole Yahoo, pas le code interne
    assert tx["frais"] == 0.15
    # (100.03 - 0.15) / 1.45954774 -> cohérent avec 5871 GBX / 85.79 (fxRate)
    assert tx["prix_unitaire"] == pytest.approx(68.4321, abs=1e-3)
    assert tx["quantite"] == pytest.approx(1.45954774)
    assert tx["note"] == "T212 EOF54915406142"


def test_order_to_transaction_date_est_l_execution_pas_la_creation():
    """Les transactions déjà en base sont datées de l'exécution."""
    assert api.order_to_transaction(_ORDER, _SYMBOLS)["date"] == dt.datetime(
        2026, 7, 30, 7, 0, 32
    )


def test_order_non_execute_est_ignore():
    assert api.order_to_transaction({"order": {"side": "BUY"}}, {}) is None
    assert api.order_to_transaction(
        {"order": {"side": "BUY"}, "fill": {"id": 1, "quantity": 0}}, {}
    ) is None


def test_vente_ajoute_les_frais_avant_de_deriver_le_prix():
    """Pour une vente, `filledValue` est net de frais : le brut les réintègre."""
    item = {
        "order": dict(_ORDER["order"], side="SELL", filledValue=100.0),
        "fill": dict(_ORDER["fill"], quantity=2.0),
    }
    tx = api.order_to_transaction(item, _SYMBOLS)

    assert tx["type"] == "vente"
    assert tx["prix_unitaire"] == pytest.approx((100.0 + 0.15) / 2.0)


def test_cash_to_transaction_couvre_depot_retrait_interet():
    depot = api.cash_to_transaction({
        "type": "DEPOSIT", "amount": 100.0, "currency": "EUR",
        "reference": "abc", "dateTime": "2026-07-29T14:16:05.283Z",
    })
    assert (depot["type"], depot["ticker"], depot["prix_unitaire"]) == (
        "depot", "CASH", 100.0)
    assert depot["note"] == "T212 abc"

    interet = api.cash_to_transaction({
        "type": "INTEREST_ON_FREE_CASH", "amount": 0.03, "currency": "EUR",
        "reference": "def", "dateTime": "2026-07-07T01:08:00.389Z",
    })
    assert interet["type"] == "interet"
    assert interet["montant_brut"] == 0.03

    assert api.cash_to_transaction({"type": "INCONNU"}) is None


def test_dividende_converti_en_euros_et_date_en_utc():
    """`paidOn` arrive avec un décalage horaire ; la base stocke de l'UTC naïf."""
    tx = api.dividend_to_transaction({
        "ticker": "BAH_US_EQ", "reference": "xyz", "quantity": 2.06,
        "amount": 0.91, "amountInEuro": 0.91,
        "paidOn": "2026-06-26T18:01:25.000+03:00",
    }, _SYMBOLS)

    assert tx["ticker"] == "BAH"
    assert tx["date"] == dt.datetime(2026, 6, 26, 15, 1, 25)
    assert tx["prix_unitaire"] == 0.91


def test_signature_dividende_ignore_le_montant():
    """Les dividendes des anciens CSV portent le BRUT fiscal, l'API le NET :
    inclure le montant dans la signature les dupliquerait tous."""
    date = dt.datetime(2026, 6, 26, 15, 1, 25)
    brut = {"type": "dividende", "date": date, "prix_unitaire": 1.22}
    net = {"type": "dividende", "date": date, "prix_unitaire": 0.91}

    assert api._signature(brut) == api._signature(net)

    # Les autres types gardent le montant : deux intérêts du même horodatage
    # mais de montants différents sont deux mouvements distincts.
    a = {"type": "interet", "date": date, "prix_unitaire": 0.03}
    b = {"type": "interet", "date": date, "prix_unitaire": 0.05}
    assert api._signature(a) != api._signature(b)


@pytest.mark.parametrize("nxt, attendu", [
    ("?limit=50&cursor=abc", "/api/v0/history/transactions?limit=50&cursor=abc"),
    ("limit=50&cursor=abc", "/api/v0/history/transactions?limit=50&cursor=abc"),
    ("/api/v0/equity/history/orders?cursor=z", "/api/v0/equity/history/orders?cursor=z"),
])
def test_next_page_target_accepte_les_trois_formes(nxt, attendu):
    """Trading 212 renvoie tantôt un chemin absolu, tantôt une query string
    (avec ou sans `?`) — les trois doivent mener à une URL appelable."""
    assert api._next_page_target("/api/v0/history/transactions", nxt) == attendu


def test_yahoo_symbol_par_place():
    sched = {1: "Euronext Paris", 2: "NASDAQ", 3: "London Stock Exchange"}
    assert api.yahoo_symbol({"shortName": "SU", "workingScheduleId": 1}, sched) == "SU.PA"
    assert api.yahoo_symbol({"shortName": "AAPL", "workingScheduleId": 2}, sched) == "AAPL"
    assert api.yahoo_symbol({"shortName": "SGLN", "workingScheduleId": 3}, sched) == "SGLN.L"
    # Place inconnue -> aucun symbole inventé.
    assert api.yahoo_symbol({"shortName": "X", "workingScheduleId": 99}, sched) is None
    assert api.yahoo_symbol({"shortName": "", "workingScheduleId": 1}, sched) is None


def test_snapshot_un_seul_point_par_jour(tmp_path, monkeypatch):
    """Deux rafraîchissements le même jour ne laissent qu'un point : la courbe
    du patrimoine ne doit pas compter deux fois la même journée."""
    monkeypatch.setattr(api, "history_path", lambda: tmp_path / "hist.jsonl")
    jour = dt.date(2026, 8, 6)

    api.record_snapshot({"total": 1000.0, "invested": 900.0, "ppl": 100.0,
                         "free": 0.0}, today=jour)
    api.record_snapshot({"total": 1010.0, "invested": 900.0, "ppl": 110.0,
                         "free": 0.0}, today=jour)

    points = api.load_history()
    assert len(points) == 1
    assert points[0]["total"] == 1010.0        # le dernier du jour l'emporte


def test_load_history_trie_et_ignore_les_lignes_illisibles(tmp_path, monkeypatch):
    path = tmp_path / "hist.jsonl"
    path.write_text(
        '{"date": "2026-08-06", "total": 2}\n'
        "pas du json\n"
        '{"date": "2026-08-01", "total": 1}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "history_path", lambda: path)

    assert [r["date"] for r in api.load_history()] == ["2026-08-01", "2026-08-06"]


def test_is_configured_exige_les_deux_moities(monkeypatch):
    """Une clé sans secret ne s'authentifie pas : l'API v0 attend le couple."""
    monkeypatch.setattr(api.settings, "trading212_key_id", "id")
    monkeypatch.setattr(api.settings, "trading212_secret", "")
    assert api.is_configured() is False

    monkeypatch.setattr(api.settings, "trading212_secret", "secret")
    assert api.is_configured() is True
