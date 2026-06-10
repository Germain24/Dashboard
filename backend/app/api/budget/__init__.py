"""Routes Budget — package par module (#507). URLs inchangées.

Le module historique `routes_budget.py` a été découpé en sous-routeurs
cohérents : transactions, categories (+ règles + enveloppes), analytics.
Tous sont montés sous le même préfixe `/budget`.
"""
from fastapi import APIRouter

from . import analytics, categories, transactions

router = APIRouter(tags=["budget"])
router.include_router(transactions.router)
router.include_router(categories.router)
router.include_router(analytics.router)
