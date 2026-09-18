"""Report + escalade de priorité de la dette micronutritionnelle (spec §3).

Basé sur la consommation RÉELLE de la fenêtre précédente. Un micro sous-consommé
voit sa cible relevée (borné) et sa priorité escaladée ; escaladée assez de
fenêtres, elle force l'optimiseur à le couvrir malgré le coût (contrepoids du
ratio pur). Un surplus remet la série à 0 sans créditer (report conservateur :
on ne « banque » pas un excès, surtout hydrosoluble).
"""
from __future__ import annotations

from app.services.sante.coverage import MICRO_KEYS

ESCALATION = 1.6          # facteur multiplicatif de priorité par fenêtre de dette
MAX_MULT = 8.0            # plafond de priorité (évite de tout sacrifier à un micro)
REPORT_FRACTION = 0.5    # report borné à 50 % de la cible de la fenêtre passée


def carryover(
    prev_targets: dict[str, float],
    prev_consumed: dict[str, float],
    prev_series: dict[str, int] | None,
) -> tuple[dict[str, float], dict[str, float], dict[str, int]]:
    prev_series = prev_series or {}
    target_add: dict[str, float] = {}
    weight_mult: dict[str, float] = {}
    new_series: dict[str, int] = {}
    for m in MICRO_KEYS:
        tgt = prev_targets.get(m)
        if not tgt or float(tgt) <= 0:
            continue
        tgt = float(tgt)
        got = float(prev_consumed.get(m, 0.0) or 0.0)
        gap = tgt - got
        if gap > 0:                                   # déficit
            streak = int(prev_series.get(m, 0)) + 1
            new_series[m] = streak
            target_add[m] = min(gap, tgt * REPORT_FRACTION)
            weight_mult[m] = min(ESCALATION ** streak, MAX_MULT)
        else:                                         # atteint ou surplus
            new_series[m] = 0
    return target_add, weight_mult, new_series
