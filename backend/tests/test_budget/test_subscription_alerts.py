"""Alertes sur abonnements détectés : hausses de prix & doublons (#260).

Étend la détection existante (#116 `detect_recurring` / #266 `recurring_vs_oneoff`)
avec le volet « alerte » : un abonnement dont le prix monte, ou payé deux fois.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from app.services.budget.analytics import (
    detect_duplicate_subscriptions,
    detect_price_increases,
    detect_recurring,
    subscription_alerts,
)


def _txd(montant, marchand, date):
    return SimpleNamespace(montant=montant, marchand=marchand, date=date, category_id=None)


def _monthly(marchand, montants, *, start=(2026, 1), day=5):
    """Une série de prélèvements mensuels (un par mois consécutif) pour `marchand`."""
    out = []
    y, m = start
    for montant in montants:
        out.append(_txd(-montant, marchand, dt.date(y, m, day)))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


# ── Hausses ──────────────────────────────────────────────────────────────────

def test_hausse_detectee_sur_augmentation_franche():
    txs = _monthly("NETFLIX.COM", [15.99, 15.99, 15.99, 18.99])
    (h,) = detect_price_increases(txs)
    assert h["marchand"] == "NETFLIX.COM"
    assert h["montant_precedent"] == 15.99
    assert h["montant_actuel"] == 18.99
    assert h["delta"] == 3.0
    assert h["delta_pct"] == 18.8
    assert h["date"] == "2026-04-05"


def test_pas_de_hausse_sous_le_plancher_absolu():
    # 2 centimes d'écart (arrondi/taux de change) : jamais une alerte.
    assert detect_price_increases(_monthly("SPOTIFY", [12.99, 12.99, 12.99, 13.01])) == []


def test_pas_de_hausse_sous_le_plancher_relatif():
    # +1,50 $ en absolu (> plancher abs.) mais +1,5 % seulement : pas d'alerte.
    assert detect_price_increases(_monthly("ASSURANCE", [99.0, 99.0, 99.0, 100.5])) == []


def test_baisse_de_prix_ignoree():
    assert detect_price_increases(_monthly("NETFLIX", [18.99, 18.99, 18.99, 15.99])) == []


def test_hausse_detectee_meme_quand_le_montant_devient_instable():
    """Une grosse hausse sort l'abonnement de `detect_recurring` (montant instable) —
    l'alerte doit quand même être émise, c'est le cas le plus utile."""
    txs = _monthly("GYM PLUS", [15.99, 15.99, 15.99, 24.99])
    assert detect_recurring(txs) == []          # filtre de stabilité : abonnement perdu
    (h,) = detect_price_increases(txs)          # ... mais la hausse reste signalée
    assert h["montant_actuel"] == 24.99


def test_hausse_ignore_les_marchands_non_mensuels():
    # Achats hebdomadaires : pas un abonnement, aucune alerte de hausse.
    txs = [_txd(-40.0, "IGA", dt.date(2026, 1, d)) for d in (1, 8, 15)]
    txs.append(_txd(-80.0, "IGA", dt.date(2026, 1, 22)))
    assert detect_price_increases(txs) == []


def test_hausse_hors_fenetre_de_comparaison_ignoree():
    """Un prix relevé il y a plus de 13 mois ne sert pas de référence : seul
    l'historique récent compte."""
    vieux = _monthly("CLOUD", [5.0, 5.0, 5.0], start=(2024, 1))
    recent = _monthly("CLOUD", [12.0, 12.0, 12.0, 12.0], start=(2026, 1))
    assert detect_price_increases(vieux + recent) == []


# ── Doublons ─────────────────────────────────────────────────────────────────

def test_doublon_meme_service_sous_deux_libelles():
    txs = _monthly("NETFLIX.COM", [17.99] * 4) + _monthly("NETFLIX 866-579-7172", [17.99] * 4)
    (d,) = detect_duplicate_subscriptions(txs)
    assert d["type"] == "meme_service"
    assert d["service"] == "NETFLIX"
    assert sorted(d["marchands"]) == ["NETFLIX 866-579-7172", "NETFLIX.COM"]
    assert d["montant_redondant"] == 17.99


def test_pas_de_doublon_quand_les_periodes_ne_se_chevauchent_pas():
    """Libellé bancaire renommé en cours de route : c'est le MÊME abonnement qui
    continue, pas deux abonnements — aucun mois ne porte les deux prélèvements."""
    txs = _monthly("NETFLIX", [17.99] * 3, start=(2026, 1))
    txs += _monthly("NETFLIX.COM", [17.99] * 3, start=(2026, 4))
    assert detect_duplicate_subscriptions(txs) == []


def test_pas_de_doublon_sur_des_montants_differents():
    # Deux services distincts de la même marque (17,99 vs 4,99) : pas un doublon.
    txs = _monthly("DISNEY PLUS", [17.99] * 4) + _monthly("DISNEY MOBILE", [4.99] * 4)
    assert detect_duplicate_subscriptions(txs) == []


def test_pas_de_doublon_via_une_passerelle_de_paiement():
    # PAYPAL *X et PAYPAL *Y partagent le 1er token sans être le même service.
    txs = _monthly("PAYPAL *NETFLIX", [17.99] * 4) + _monthly("PAYPAL *SPOTIFY", [17.99] * 4)
    assert detect_duplicate_subscriptions(txs) == []


def test_doublon_double_prelevement_dans_le_mois():
    txs = _monthly("SPOTIFY", [16.0] * 5)
    txs.append(_txd(-16.0, "SPOTIFY", dt.date(2026, 3, 6)))  # prélevé 2× en mars
    (d,) = detect_duplicate_subscriptions(txs)
    assert d["type"] == "double_prelevement"
    assert d["marchands"] == ["SPOTIFY"]
    assert d["mois"] == "2026-03"
    assert d["montant_redondant"] == 16.0


def test_pas_de_double_prelevement_sur_un_montant_different():
    # Cotisation annuelle en plus de la mensualité : montants trop éloignés.
    txs = _monthly("GYM", [40.0] * 5)
    txs.append(_txd(-120.0, "GYM", dt.date(2026, 3, 20)))
    assert detect_duplicate_subscriptions(txs) == []


# ── Agrégat ──────────────────────────────────────────────────────────────────

def test_subscription_alerts_agrege_les_deux_familles():
    txs = _monthly("NETFLIX.COM", [15.99, 15.99, 15.99, 18.99])
    txs += _monthly("SPOTIFY", [16.0] * 5)
    txs.append(_txd(-16.0, "SPOTIFY", dt.date(2026, 3, 6)))
    out = subscription_alerts(txs)
    assert [h["marchand"] for h in out["hausses"]] == ["NETFLIX.COM"]
    assert [d["type"] for d in out["doublons"]] == ["double_prelevement"]
    assert out["nb_alertes"] == 2
    assert out["surcout_mensuel"] == 19.0  # 3,00 de hausse + 16,00 prélevé en double


def test_subscription_alerts_sans_donnees():
    out = subscription_alerts([])
    assert out == {"hausses": [], "doublons": [], "nb_alertes": 0, "surcout_mensuel": 0.0}
