"""Primitives communes aux métriques de performance et de risque.

Les snapshots Finance sont des valorisations de fin de journée.  Ils peuvent
être irréguliers et, historiquement, quelques journées ne contiennent qu'un
sous-compte.  Ce module transforme ces données en une série exploitable sans
modifier l'historique persisté : une valorisation partielle qui s'effondre puis
revient immédiatement est traitée comme une donnée manquante. Le rendement est
alors réparti sur tout l'intervalle réel jusqu'au prochain point fiable.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# Une chute de valeur suivie d'un retour rapide caractérise les snapshots où un
# broker manque (cas réel : 27 k€ -> 861 € -> 28 k€). Le capital peut déjà avoir
# été réconcilié/carry-forward en amont ; la récupération encadrée protège contre
# l'effacement d'une baisse de marché durable.
_PARTIAL_VALUE_RATIO = 0.70
_RECOVERY_RATIO = 0.80
_MAX_RECOVERY_DAYS = 7
_MAX_RECOVERY_POINTS = 3
# Sans point futur, on ne masque qu'un effondrement extrême (< 25 %) avec un
# capital pratiquement inchangé. Ce seuil volontairement strict couvre un
# dernier snapshot mono-compte sans prendre une baisse de marché ordinaire pour
# une donnée manquante.
_MANIFEST_PARTIAL_TAIL_RATIO = 0.25
_TAIL_CAPITAL_RATIO_MIN = 0.80
_TAIL_CAPITAL_RATIO_MAX = 1.25

# Au-delà de 15 % en une journée au niveau du portefeuille, la chaîne de flux
# n'est pas assez fiable pour publier un TWR. La métrique reste alors absente au
# lieu d'afficher un nombre trompeur. Les métriques de risque ont une garde plus
# large (50 %) et neutralisent seulement les observations manifestement cassées.
MAX_RELIABLE_DAILY_RETURN = 0.15
MAX_RISK_DAILY_RETURN = 0.50


@dataclass(frozen=True)
class MetricSnapshot:
    date: dt.date
    valeur: float
    investit: float | None


@dataclass(frozen=True)
class ReturnObservation:
    """Rendement total entre deux snapshots et équivalent journalier."""

    date: dt.date
    days: int
    factor: float
    daily_return: float
    valid: bool = True


def _as_date(value: Any, index: int) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if value is not None:
        try:
            return dt.date.fromisoformat(str(value)[:10])
        except ValueError:
            pass
    # Compatibilité avec les rares appels historiques sans date : chaque point
    # reste une observation quotidienne, comme avant.
    return dt.date(1970, 1, 1) + dt.timedelta(days=index)


def _coerce_snapshot(item: Any, index: int) -> MetricSnapshot | None:
    if isinstance(item, MetricSnapshot):
        return item
    if isinstance(item, dict):
        date = item.get("date")
        valeur = item.get("valeur")
        investit = item.get("investit")
    elif isinstance(item, (tuple, list)) and len(item) >= 3:
        date, valeur, investit = item[:3]
    else:
        date = getattr(item, "date", None)
        valeur = getattr(item, "valeur", None)
        investit = getattr(item, "investit", None)

    try:
        valeur_float = float(valeur)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(valeur_float) or valeur_float <= 0:
        return None

    investit_float: float | None
    try:
        investit_float = float(investit) if investit is not None else None
    except (TypeError, ValueError):
        investit_float = None
    if investit_float is not None and (
        not math.isfinite(investit_float) or investit_float < 0
    ):
        investit_float = None

    return MetricSnapshot(_as_date(date, index), valeur_float, investit_float)


def _looks_partial(current: MetricSnapshot, reference: MetricSnapshot) -> bool:
    # La réconciliation des apports porte déjà le dernier capital fiable sur
    # les jours incomplets. La valeur seule doit donc pouvoir déclencher la
    # détection ; le retour rapide à >= 80 % protège ensuite contre une vraie
    # baisse durable.
    return current.valeur < reference.valeur * _PARTIAL_VALUE_RATIO


def _has_recovered(candidate: MetricSnapshot, reference: MetricSnapshot) -> bool:
    if candidate.valeur < reference.valeur * _RECOVERY_RATIO:
        return False
    if candidate.investit is None or reference.investit is None:
        return True
    return candidate.investit >= reference.investit * _RECOVERY_RATIO


def _looks_manifestly_partial_tail(
    current: MetricSnapshot,
    reference: MetricSnapshot,
) -> bool:
    days = (current.date - reference.date).days
    if not 0 < days <= _MAX_RECOVERY_DAYS:
        return False
    if current.valeur >= reference.valeur * _MANIFEST_PARTIAL_TAIL_RATIO:
        return False
    if (
        current.investit is None
        or reference.investit is None
        or reference.investit <= 0
    ):
        return False
    capital_ratio = current.investit / reference.investit
    return _TAIL_CAPITAL_RATIO_MIN <= capital_ratio <= _TAIL_CAPITAL_RATIO_MAX


def _drop_incomplete_prefix(snapshots: list[MetricSnapshot]) -> list[MetricSnapshot]:
    """Écarte un premier snapshot manifestement partiel, faute de valeur à porter."""
    while len(snapshots) >= 2:
        first, second = snapshots[0], snapshots[1]
        if (second.date - first.date).days > _MAX_RECOVERY_DAYS:
            break
        if not _looks_partial(first, second):
            break
        # Un simple apport peut faire doubler valeur et capital sans rendre le
        # premier point invalide. On exige aussi une couverture valeur/capital
        # sensiblement plus faible sur le premier snapshot.
        if first.investit and second.investit:
            first_ratio = first.valeur / first.investit
            second_ratio = second.valeur / second.investit
            if first_ratio >= second_ratio * _RECOVERY_RATIO:
                break
            # Capital inchangé : on ne supprime le premier point que si la
            # couverture est manifestement partielle, pas après un simple gain.
            if (
                first.investit == second.investit
                and first.valeur >= second.valeur * 0.30
            ):
                break
        snapshots = snapshots[1:]
    return snapshots


def _ordered_metric_snapshots(items: Iterable[Any]) -> list[MetricSnapshot]:
    coerced = [
        snapshot
        for index, item in enumerate(items)
        if (snapshot := _coerce_snapshot(item, index)) is not None
    ]
    by_date = {snapshot.date: snapshot for snapshot in coerced}
    return [by_date[date] for date in sorted(by_date)]


def _repair_transient_gaps(
    snapshots: list[MetricSnapshot],
) -> list[MetricSnapshot]:
    if len(snapshots) < 2:
        return snapshots

    cleaned: list[MetricSnapshot] = []
    index = 0
    while index < len(snapshots):
        current = snapshots[index]
        if cleaned and _looks_partial(current, cleaned[-1]):
            reference = cleaned[-1]
            if (
                index == len(snapshots) - 1
                and _looks_manifestly_partial_tail(current, reference)
            ):
                index += 1
                continue
            recovery_index: int | None = None
            stop = min(len(snapshots), index + _MAX_RECOVERY_POINTS + 1)
            for candidate_index in range(index + 1, stop):
                candidate = snapshots[candidate_index]
                if (candidate.date - current.date).days > _MAX_RECOVERY_DAYS:
                    break
                if _has_recovered(candidate, reference):
                    recovery_index = candidate_index
                    break
            if recovery_index is not None:
                index = recovery_index
                continue
        cleaned.append(current)
        index += 1
    return cleaned


def prepare_metric_snapshots(items: Iterable[Any]) -> list[MetricSnapshot]:
    """Nettoie et trie une série sans jamais écrire dans la base.

    Les doublons de date gardent la dernière valeur. Une courte séquence
    partielle encadrée par deux valorisations complètes est écartée de la série
    métrique. Elle reste intacte en base et l'intervalle entre points fiables est
    conservé pour l'annualisation date-aware.
    """
    snapshots = _drop_incomplete_prefix(_ordered_metric_snapshots(items))
    return _repair_transient_gaps(snapshots)


def return_observations(
    snapshots: Iterable[Any],
    *,
    prepared: bool = False,
) -> list[ReturnObservation]:
    """Rendements ajustés des flux, normalisés selon les jours écoulés.

    ``factor`` utilise la convention historique de flux en fin de période :
    ``(valeur_fin - flux_net) / valeur_début``. L'équivalent quotidien répartit
    géométriquement ce facteur sur la durée réelle ; un intervalle de 25 jours
    n'est donc plus pris pour une seule séance dans volatilité/Sharpe/Sortino.
    """
    series = list(snapshots) if prepared else prepare_metric_snapshots(snapshots)
    observations: list[ReturnObservation] = []
    for previous, current in zip(series, series[1:], strict=False):
        days = (current.date - previous.date).days
        if days <= 0:
            continue
        if previous.investit is not None and current.investit is not None:
            cashflow = current.investit - previous.investit
            factor = (current.valeur - cashflow) / previous.valeur
        else:
            factor = current.valeur / previous.valeur
        valid = math.isfinite(factor) and factor > 0
        if valid:
            daily_return = math.exp(math.log(factor) / days) - 1.0
        else:
            # Un facteur négatif ne peut pas appartenir à un indice de richesse.
            # Il sera neutralisé côté risque et rendra le TWR indisponible.
            factor = 1.0
            daily_return = 0.0
        observations.append(
            ReturnObservation(current.date, days, factor, daily_return, valid)
        )
    return observations


def daily_returns_for_risk(observations: Iterable[ReturnObservation]) -> list[float]:
    """Développe les intervalles en rendements calendaires date-aware."""
    daily: list[float] = []
    for observation in observations:
        value = observation.daily_return
        if not observation.valid or abs(value) > MAX_RISK_DAILY_RETURN:
            value = 0.0
        daily.extend([value] * observation.days)
    return daily


def adjusted_wealth_index(observations: Iterable[ReturnObservation]) -> list[float]:
    """Indice base 1 neutralisant apports, retraits et snapshots cassés."""
    index = [1.0]
    for observation in observations:
        factor = observation.factor
        if (
            not observation.valid
            or abs(observation.daily_return) > MAX_RISK_DAILY_RETURN
        ):
            factor = 1.0
        index.append(index[-1] * factor)
    return index


def annualized_capital_return(
    valeur: float,
    investit: float,
    start_date: dt.date,
    end_date: dt.date,
) -> float | None:
    """Annualise le rendement valeur/capital selon la durée calendaire exacte."""
    days = (end_date - start_date).days
    if days <= 0 or valeur <= 0 or investit <= 0:
        return None
    factor = valeur / investit
    if factor <= 0 or not math.isfinite(factor):
        return None
    return round((factor ** (365.25 / days) - 1.0) * 100.0, 2)


def _xirr(cashflows: Iterable[tuple[dt.date, float]]) -> float | None:
    """Résout le TRI annualisé de flux datés, sans dépendance numérique externe."""
    by_date: dict[dt.date, float] = {}
    for date, amount in cashflows:
        if math.isfinite(amount):
            by_date[date] = by_date.get(date, 0.0) + amount
    dated = sorted((date, amount) for date, amount in by_date.items() if amount)
    if len(dated) < 2:
        return None
    amounts = [amount for _, amount in dated]
    if not any(amount < 0 for amount in amounts) or not any(
        amount > 0 for amount in amounts
    ):
        return None

    origin = dated[0][0]

    def npv(rate: float) -> float:
        base = 1.0 + rate
        return sum(
            amount / (base ** ((date - origin).days / 365.25))
            for date, amount in dated
        )

    low = -0.999999
    high = 1.0
    low_value = npv(low)
    high_value = npv(high)
    while low_value * high_value > 0 and high < 1_000_000:
        high = high * 2.0 + 1.0
        high_value = npv(high)
    if (
        not math.isfinite(low_value)
        or not math.isfinite(high_value)
        or low_value * high_value > 0
    ):
        return None

    for _ in range(160):
        middle = (low + high) / 2.0
        middle_value = npv(middle)
        if abs(middle_value) < 1e-9:
            return middle
        if low_value * middle_value <= 0:
            high = middle
            high_value = middle_value
        else:
            low = middle
            low_value = middle_value
    return (low + high) / 2.0


def money_weighted_annual_return(
    snapshots: Iterable[Any],
    *,
    prepared: bool = False,
) -> float | None:
    """TRI annualisé tenant compte du montant et de la date des apports.

    La valeur du premier snapshot est le capital d'ouverture de la période.
    Chaque variation ultérieure de ``investit`` est un flux externe daté, puis
    la valeur finale liquide virtuellement le portefeuille. Contrairement au
    simple multiple valeur/capital, deux apports identiques mais effectués à des
    dates différentes ne produisent donc pas le même rendement annualisé.
    """
    series = list(snapshots) if prepared else prepare_metric_snapshots(snapshots)
    if len(series) < 2:
        return None

    cashflows: list[tuple[dt.date, float]] = [
        (series[0].date, -series[0].valeur)
    ]
    for previous, current in zip(series, series[1:], strict=False):
        if previous.investit is None or current.investit is None:
            return None
        net_contribution = current.investit - previous.investit
        if abs(net_contribution) >= 0.005:
            cashflows.append((current.date, -net_contribution))
    cashflows.append((series[-1].date, series[-1].valeur))

    rate = _xirr(cashflows)
    if rate is None or not math.isfinite(rate):
        return None
    return round(rate * 100.0, 2)
