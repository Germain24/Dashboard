"""Détection ETF/fonds — critère durci unique, partagé par runner.py et scoring.py.

Un titre n'est classé ETF/fonds que s'il réunit DEUX conditions :
1. aucune donnée financière exploitable (compte de résultat ET bilan vides) ;
2. son NOM contient un mot-clé de fonds (UCITS, iShares, Amundi…).

But : ne plus se fier au seul ``quoteType`` de yfinance, qui renvoie "ETF" à tort
sur des cotations secondaires / CDR (ex. BA.TO=Boeing, LVMH.TO, *.F allemands).
Ces actions mal cotées se voyaient attribuer Score=200, polluaient l'allocation et
contournaient le dédoublonnage (les ETF en sont exemptés).
"""

from __future__ import annotations

import re

# Mots du NOM qui identifient un vrai fonds/ETF (UCITS, iShares, Amundi…).
FUND_NAME_KW = (
    "ETF", "UCITS", "ISHARES", "AMUNDI", "INVESCO", "LYXOR", "XTRACKERS",
    "VANGUARD", "SPDR", "INDEX SOLUTIONS",
)

# Mots ENTIERS uniquement : "ETF" doit être un mot, pas une sous-chaîne — sinon
# "nETFlix", "nETFonds", "rockETFuel" matchent à tort. \b borne les mots.
_FUND_RE = re.compile(r"\b(?:" + "|".join(FUND_NAME_KW) + r")\b")


def looks_like_fund(*names: str) -> bool:
    """Vrai si l'un des noms contient un mot-clé de fonds (mot entier)."""
    return any(_FUND_RE.search(n) is not None for n in names if n)


def is_empty_financials(data: dict) -> bool:
    """Vrai si yfinance n'a renvoyé aucune donnée financière exploitable."""
    if not data:
        return True
    inc, bal = data.get("income"), data.get("balance")
    inc_empty = inc is None or getattr(inc, "empty", True)
    bal_empty = bal is None or getattr(bal, "empty", True)
    return inc_empty and bal_empty


def is_etf(data: dict) -> bool:
    """Vrai ssi (financials vides) ET (nom de fonds). Voir docstring du module."""
    if not is_empty_financials(data):
        return False
    info = data.get("info", {}) or {}
    ln = (info.get("longName") or "").upper()
    sn = (info.get("shortName") or "").upper()
    return looks_like_fund(ln, sn)
