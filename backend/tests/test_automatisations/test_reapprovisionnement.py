"""Tests TDD pour le réapprovisionnement auto skincare (#209)."""
import datetime as dt
import pytest
from tests.conftest import mem_session  # noqa: F401
from sqlmodel import select

from app.models.scheduler import Notification
from app.models.skincare import SkincareProduct
from app.services.automatisations.reapprovisionnement import (
    days_of_stock_remaining,
    check_skincare_reorder,
    run_skincare_reorder_check,
)


# ─── Fonctions pures ─────────────────────────────────────────────────────────

class TestDaysOfStockRemaining:
    def test_no_stock_qte_returns_none(self):
        p = SkincareProduct(nom="SPF", stock_qte=None, frequence_type="quotidien")
        assert days_of_stock_remaining(p) is None

    def test_quotidien_once_per_day(self):
        p = SkincareProduct(nom="SPF", stock_qte=30.0, unite="ml",
                            frequence_type="quotidien")
        # consommation estimée : 1 application/jour = 1 unité fictive
        # sans consommation_par_application, on suppose 1 unité
        days = days_of_stock_remaining(p, consommation_par_application=2.0)
        # 30 / 2 applications/jour = 15 jours
        assert days == 15

    def test_n_par_semaine(self):
        p = SkincareProduct(nom="Retinoide", stock_qte=14.0,
                            frequence_type="n_par_semaine", frequence_n=2)
        days = days_of_stock_remaining(p, consommation_par_application=1.0)
        # 14 / (2/7 par jour) = 49 jours
        assert days == pytest.approx(49, abs=1)

    def test_zero_stock_returns_zero(self):
        p = SkincareProduct(nom="Creme", stock_qte=0.0, frequence_type="quotidien")
        assert days_of_stock_remaining(p) == 0


class TestCheckSkincareReorder:
    def test_expired_product_flagged(self, mem_session):
        yesterday = dt.date.today() - dt.timedelta(days=1)
        p = SkincareProduct(nom="Vieux sérum", date_peremption=yesterday, actif=True)
        mem_session.add(p)
        mem_session.commit()
        results = check_skincare_reorder(mem_session, today=dt.date.today())
        noms = [r["nom"] for r in results]
        assert "Vieux sérum" in noms

    def test_zero_stock_flagged(self, mem_session):
        p = SkincareProduct(nom="SPF vide", stock_qte=0.0, actif=True)
        mem_session.add(p)
        mem_session.commit()
        results = check_skincare_reorder(mem_session)
        noms = [r["nom"] for r in results]
        assert "SPF vide" in noms

    def test_ok_product_not_flagged(self, mem_session):
        tomorrow = dt.date.today() + dt.timedelta(days=60)
        p = SkincareProduct(nom="Bon produit", stock_qte=100.0, date_peremption=tomorrow, actif=True)
        mem_session.add(p)
        mem_session.commit()
        results = check_skincare_reorder(mem_session)
        noms = [r["nom"] for r in results]
        assert "Bon produit" not in noms

    def test_inactive_product_ignored(self, mem_session):
        p = SkincareProduct(nom="Inactif", stock_qte=0.0, actif=False)
        mem_session.add(p)
        mem_session.commit()
        results = check_skincare_reorder(mem_session)
        noms = [r["nom"] for r in results]
        assert "Inactif" not in noms


class TestRunSkincareReorderCheck:
    def test_creates_notification_when_needed(self, mem_session):
        p = SkincareProduct(nom="SPF vide", stock_qte=0.0, actif=True)
        mem_session.add(p)
        mem_session.commit()
        run_skincare_reorder_check(mem_session)
        notifs = list(mem_session.exec(select(Notification)).all())
        assert any("SPF vide" in n.message or "SPF vide" in n.titre for n in notifs)

    def test_no_notification_when_nothing_to_reorder(self, mem_session):
        run_skincare_reorder_check(mem_session)
        notifs = list(mem_session.exec(select(Notification)).all())
        assert notifs == []
