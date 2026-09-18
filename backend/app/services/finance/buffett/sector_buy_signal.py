"""Signal Achat fondé sur les quantiles sectoriels de valorisation.

Deux axes par titre — valeur et qualité — comparés aux quantiles de SON secteur.
La métrique de chaque axe dépend du profil du secteur (cf. ``sector_valuation``) :
P/FFO pour l'immobilier, PER normalisé pour les cycliques, PEG ajusté du dividende
pour les valeurs matures, P/B ÷ ROE pour la finance, PER/PEG partout ailleurs.

Règle d'or : le quantile d'un secteur est calculé sur la MÊME métrique que le
filtre de ce secteur. Le pool global reste, lui, toujours en PER/PEG, et sert de
repli aux secteurs trop petits — lesquels retombent donc aussi sur le profil
standard, sans quoi on comparerait un P/FFO à une médiane de PER.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .breakdown import _canon_sector
from .sector_valuation import STANDARD, profile_for_sector

BUY_SIGNAL_MODEL_VERSION = 5
DEFAULT_PERCENTILE = 0.50
DEFAULT_MIN_SECTOR_SIZE = 20
DEFAULT_MIN_METRIC_COVERAGE = 0.60


def _positive(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _is_etf(row: Any, etf_tickers: set[str]) -> bool:
    ticker = str(getattr(row, "ticker", "") or "").strip().upper()
    sector = str(getattr(row, "secteur", "") or "")
    # Le score 200 est aussi utilisé par les achats forcés : il ne constitue
    # donc pas une preuve qu'un instrument est un ETF.
    return ticker in etf_tickers or "ETF" in sector.upper()


def _effective_peg(row: Any) -> float | None:
    """PEG comparable, après le garde-fou de croissance déjà utilisé au calcul."""
    growth_pct = _positive(getattr(row, "croissance", None))
    if growth_pct is not None and growth_pct > 50.0:
        return None
    return _positive(getattr(row, "peg", None))


def _row_valuation(row: Any) -> dict:
    """Métriques du titre, avec repli sur ``per``/``peg`` pour les anciens runs.

    Les lignes enregistrées avant l'introduction des profils n'ont pas de bloc
    ``secteurs_extra["valuation"]`` : elles restent scorées comme auparavant.
    """
    extra = getattr(row, "secteurs_extra", None) or {}
    values = dict(extra.get("valuation") or {}) if isinstance(extra, dict) else {}
    values["per"] = _positive(getattr(row, "per", None))
    values["peg"] = _effective_peg(row)
    return values


def _quantile(values: list[float], percentile: float) -> float | None:
    """Quantile continu, sans dépendance NumPy.

    Le cas 0.50 délègue à ``statistics.median`` pour ne pas décaler d'un epsilon
    les seuils historiques (nombre pair d'éléments : moyenne des deux centraux).
    """
    if not values:
        return None
    ratio = min(max(float(percentile), 0.0), 1.0)
    if abs(ratio - 0.5) <= 1e-12:
        return float(statistics.median(values))
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = ratio * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[int(position)])
    weight = position - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def apply_sector_percentile_buy_signal(
    rows: Iterable[Any],
    *,
    etf_tickers: set[str] | None = None,
    percentile: float = DEFAULT_PERCENTILE,
    min_sector_size: int = DEFAULT_MIN_SECTOR_SIZE,
    profiles_enabled: bool | None = None,
    profile_overrides: dict | None = None,
    min_metric_coverage: float | None = None,
) -> dict:
    """Met à jour ``achat`` sans toucher au score MOAT."""
    from .config import Config

    if profiles_enabled is None:
        profiles_enabled = bool(
            getattr(Config, "SECTOR_VALUATION_PROFILES_ENABLED", False)
        )
    if profile_overrides is None:
        profile_overrides = dict(
            getattr(Config, "SECTOR_VALUATION_PROFILE_OVERRIDES", None) or {}
        )
    if min_metric_coverage is None:
        min_metric_coverage = float(
            getattr(Config, "SECTOR_VALUATION_MIN_COVERAGE", DEFAULT_MIN_METRIC_COVERAGE)
        )

    missing_quality_percentile = float(
        getattr(Config, "BUY_SIGNAL_MISSING_QUALITY_PERCENTILE", 0.0) or 0.0
    )

    items = list(rows)
    etfs = {str(t).strip().upper() for t in (etf_tickers or set())}

    # ── Passe 1 : métriques par titre, groupées par secteur ──────────────
    values_by_sector: dict[str, list[dict]] = defaultdict(list)
    global_per: list[float] = []
    global_peg: list[float] = []
    for row in items:
        if _is_etf(row, etfs):
            continue
        sector = _canon_sector(str(getattr(row, "secteur", "") or ""))
        values = _row_valuation(row)
        values_by_sector[sector].append(values)
        if values.get("per") is not None:
            global_per.append(float(values["per"]))
        if values.get("peg") is not None:
            global_peg.append(float(values["peg"]))

    global_per_max = _quantile(global_per, percentile)
    global_peg_max = _quantile(global_peg, percentile)

    # ── Passe 2 : profil retenu et seuils, secteur par secteur ───────────
    thresholds: dict[str, dict] = {}
    profiles: dict[str, Any] = {}
    for sector in sorted(values_by_sector):
        rows_values = values_by_sector[sector]
        candidate = profile_for_sector(
            sector, enabled=profiles_enabled, overrides=profile_overrides
        )
        value_values = [
            v for v in (item.get(candidate.value_axis.key) for item in rows_values)
            if _positive(v) is not None
        ]
        quality_values = [
            v for v in (item.get(candidate.quality_axis.key) for item in rows_values)
            if _positive(v) is not None
        ]
        enough = (
            len(value_values) >= min_sector_size
            and len(quality_values) >= min_sector_size
        )
        covered = sum(
            1
            for item in rows_values
            if _positive(item.get(candidate.value_axis.key)) is not None
            and _positive(item.get(candidate.quality_axis.key)) is not None
        )
        coverage = covered / len(rows_values) if rows_values else 0.0
        fallback = None
        profile = candidate
        standard_value_values = [
            v for v in (item.get("per") for item in rows_values)
            if _positive(v) is not None
        ]
        standard_quality_values = [
            v for v in (item.get("peg") for item in rows_values)
            if _positive(v) is not None
        ]
        standard_enough = (
            len(standard_value_values) >= min_sector_size
            and len(standard_quality_values) >= min_sector_size
        )
        if sector == "Inconnu":
            # « Inconnu » agrège des entreprises de métiers sans rapport entre
            # eux : son quantile interne n'a aucune signification économique.
            # On conserve les effectifs pour le diagnostic, mais les seuils et
            # métriques de décision proviennent toujours du repli global PER/PEG.
            profile = STANDARD
            fallback = "unknown_global"
            enough = False
        elif candidate is not STANDARD and not enough:
            # L'échantillon spécialisé est réellement trop petit pour produire
            # des quantiles stables : tout le secteur revient alors au standard.
            profile = STANDARD
            fallback = "standard"
            value_values = standard_value_values
            quality_values = standard_quality_values
            enough = standard_enough
        elif candidate is not STANDARD and coverage < 1.0:
            # Il y a assez d'observations pour conserver le profil spécialisé.
            # Les titres individuellement incomplets seront jugés en PER/PEG
            # lors de la passe 3 au lieu de dégrader tout le secteur.
            fallback = "per_title_standard"
        profiles[sector] = profile
        thresholds[sector] = {
            "per_max": _quantile([float(v) for v in value_values], percentile)
            if enough
            else global_per_max,
            "peg_max": _quantile([float(v) for v in quality_values], percentile)
            if enough
            else global_peg_max,
            # Seuil SÉVÈRE du repli « valorisation seule » (axe qualité absent).
            # Calculé sur les mêmes titres, à un percentile plus bas : sans PEG,
            # il faut être nettement moins cher pour compenser une croissance
            # non vérifiée. None => repli désactivé pour ce secteur.
            "per_max_strict": (
                _quantile([float(v) for v in value_values], missing_quality_percentile)
                if enough and missing_quality_percentile > 0
                else None
            ),
            "source": "sector" if enough else "global",
            "n_per": len(value_values),
            "n_peg": len(quality_values),
            "profile": profile.name,
            "profile_fallback": fallback,
            "coverage": round(coverage, 4),
            "value_metric": profile.value_axis.key,
            "quality_metric": profile.quality_axis.key,
            "value_metric_label": profile.value_axis.label,
            "quality_metric_label": profile.quality_axis.label,
            "fallback_per_max": (
                _quantile([float(v) for v in standard_value_values], percentile)
                if standard_enough
                else global_per_max
            ),
            "fallback_peg_max": (
                _quantile([float(v) for v in standard_quality_values], percentile)
                if standard_enough
                else global_peg_max
            ),
            "fallback_per_max_strict": (
                _quantile(
                    [float(v) for v in standard_value_values],
                    missing_quality_percentile,
                )
                if standard_enough and missing_quality_percentile > 0
                else None
            ),
            "fallback_source": "sector" if standard_enough else "global",
        }
        if not enough:
            # Seuils globaux = PER/PEG : le secteur doit être jugé sur les mêmes
            # métriques, sans quoi on comparerait un P/FFO à une médiane de PER.
            profiles[sector] = STANDARD
            thresholds[sector]["profile"] = STANDARD.name
            thresholds[sector]["profile_fallback"] = fallback or "standard"
            thresholds[sector]["value_metric"] = STANDARD.value_axis.key
            thresholds[sector]["quality_metric"] = STANDARD.quality_axis.key
            thresholds[sector]["value_metric_label"] = STANDARD.value_axis.label
            thresholds[sector]["quality_metric_label"] = STANDARD.quality_axis.label

    # ── Passe 3 : décision par titre ─────────────────────────────────────
    accepted = 0
    missing_quality_total = 0
    missing_quality_accepted = 0
    missing_quality_excluded = 0
    accepted_value_only = 0
    for row in items:
        extra = dict(getattr(row, "secteurs_extra", None) or {})
        if _is_etf(row, etfs):
            row.achat = True
            extra["buy_signal"] = {
                "model_version": BUY_SIGNAL_MODEL_VERSION,
                "reason": "etf",
            }
            row.secteurs_extra = extra
            accepted += 1
            continue

        sector = _canon_sector(str(getattr(row, "secteur", "") or ""))
        limits = thresholds.get(sector) or {
            "per_max": global_per_max,
            "peg_max": global_peg_max,
            "source": "global",
            "n_per": 0,
            "n_peg": 0,
            "profile": STANDARD.name,
            "profile_fallback": None,
            "coverage": 0.0,
            "value_metric": STANDARD.value_axis.key,
            "quality_metric": STANDARD.quality_axis.key,
            "value_metric_label": STANDARD.value_axis.label,
            "quality_metric_label": STANDARD.quality_axis.label,
        }
        profile = profiles.get(sector, STANDARD)
        values = _row_valuation(row)
        value = _positive(values.get(limits["value_metric"]))
        quality = _positive(values.get(limits["quality_metric"]))
        per_title_profile_fallback = False
        decision_per_max = limits.get("per_max")
        decision_peg_max = limits.get("peg_max")
        decision_per_max_strict = limits.get("per_max_strict")
        decision_value_metric = limits["value_metric"]
        decision_quality_metric = limits["quality_metric"]
        decision_value_label = limits["value_metric_label"]
        decision_quality_label = limits["quality_metric_label"]
        if profile is not STANDARD and (value is None or quality is None):
            # Repli PAR TITRE : un REIT sans FFO, par exemple, reste comparable
            # à ses pairs en PER/PEG sans faire perdre le P/FFO à tout le secteur.
            per_title_profile_fallback = True
            value = _positive(values.get("per"))
            quality = _positive(values.get("peg"))
            decision_per_max = limits.get("fallback_per_max")
            decision_peg_max = limits.get("fallback_peg_max")
            decision_per_max_strict = limits.get("fallback_per_max_strict")
            decision_value_metric = STANDARD.value_axis.key
            decision_quality_metric = STANDARD.quality_axis.key
            decision_value_label = STANDARD.value_axis.label
            decision_quality_label = STANDARD.quality_axis.label
        fallback_used = False
        if quality is None:
            missing_quality_total += 1
        accepted_row = bool(
            value is not None
            and quality is not None
            and decision_per_max is not None
            and decision_peg_max is not None
            and value <= float(decision_per_max)
            and quality <= float(decision_peg_max)
        )
        if not accepted_row and quality is None and value is not None:
            # Repli « valorisation seule » : l'axe qualité manque, on juge sur le
            # seul axe valorisation mais à un seuil nettement plus sévère. Sans
            # lui, un PEG absent rejetait sans appel — soit 76 % des actions, et
            # très inégalement selon la place de cotation.
            strict = decision_per_max_strict
            if strict is not None and value <= float(strict):
                accepted_row = True
                fallback_used = True
        row.achat = accepted_row
        if accepted_row:
            accepted += 1
            if fallback_used:
                accepted_value_only += 1
        if quality is None:
            if accepted_row:
                missing_quality_accepted += 1
            else:
                missing_quality_excluded += 1
        extra["buy_signal"] = {
            "model_version": BUY_SIGNAL_MODEL_VERSION,
            "sector": sector,
            # Valeurs brutes conservées pour l'affichage, même hors profil standard.
            "per": values.get("per"),
            "peg": values.get("peg"),
            "value": value,
            "quality": quality,
            **limits,
            "per_max": decision_per_max,
            "peg_max": decision_peg_max,
            "per_max_strict": decision_per_max_strict,
            "value_metric": decision_value_metric,
            "quality_metric": decision_quality_metric,
            "value_metric_label": decision_value_label,
            "quality_metric_label": decision_quality_label,
            "per_title_profile_fallback": per_title_profile_fallback,
            "reason": (
                "accepted_value_only"
                if fallback_used
                else "accepted"
                if accepted_row
                else "missing_peg"
                if quality is None and decision_quality_metric == "peg"
                else "missing_quality_metric"
                if quality is None
                else "missing_per"
                if value is None and decision_value_metric == "per"
                else "missing_value_metric"
                if value is None
                else "above_sector_median"
            ),
        }
        row.secteurs_extra = extra

    return {
        "model_version": BUY_SIGNAL_MODEL_VERSION,
        "method": "sector_percentile",
        "percentile": float(percentile),
        "min_sector_size": int(min_sector_size),
        "profiles_enabled": bool(profiles_enabled),
        "min_metric_coverage": float(min_metric_coverage),
        "global": {
            "per_max": global_per_max,
            "peg_max": global_peg_max,
            "n_per": len(global_per),
            "n_peg": len(global_peg),
        },
        "sectors": thresholds,
        "accepted": accepted,
        # Nom conservé pour la compatibilité, mais il compte en réalité tout axe
        # QUALITÉ inexploitable : donnée absente, valeur <= 0, ou croissance
        # jugée non fiable (> GROWTH_EXTREME). Mesuré sur l'univers réel, la
        # quasi-totalité relève du premier cas.
        # Ancienne clé conservée pour les clients historiques, mais elle compte
        # désormais réellement les EXCLUS et non tous les titres incomplets.
        "excluded_missing_peg": missing_quality_excluded,
        "missing_quality_total": missing_quality_total,
        "missing_quality_accepted": missing_quality_accepted,
        "missing_quality_excluded": missing_quality_excluded,
        "missing_quality_percentile": missing_quality_percentile,
        "accepted_value_only": accepted_value_only,
        "n_instruments": len(items),
    }
