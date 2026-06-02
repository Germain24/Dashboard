"""Routes Finance — agrégateur de sous-routeurs.

Le module historique `routes_finance.py` (609 lignes) a été découpé en
sous-routeurs cohérents : portfolio, risk, transactions, buffett, rebalancing.
Tous sont montés sous le même préfixe `/finance` : les URLs sont inchangées.
"""

from fastapi import APIRouter

from . import buffett, portfolio, rebalancing, risk, transactions

router = APIRouter(tags=["finance"])
router.include_router(portfolio.router)
router.include_router(risk.router)
router.include_router(transactions.router)
router.include_router(buffett.router)
router.include_router(rebalancing.router)
