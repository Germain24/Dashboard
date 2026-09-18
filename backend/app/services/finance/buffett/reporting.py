"""Persistance des résultats Buffett en DB (BuffettRun + BuffettRunResult)."""

from __future__ import annotations

import datetime as dt
from copy import deepcopy
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, delete, select

from app.core.realtime import publish
from app.core.timeutil import utcnow
from app.models.finance import BuffettRun, BuffettRunResult, BuffettRunStatus

from .config import Config


def fundamental_mismatch_tickers(results: dict[str, tuple[float, dict]]) -> set[str]:
    """Détecte une divergence fondamentale entre cotations d'une même société."""
    grouped: dict[str, list[tuple[str, dict]]] = {}
    for ticker, (_, metrics) in results.items():
        if str(metrics.get("InstrumentType") or metrics.get("Secteur") or "").upper() == "ETF":
            continue
        key = str(
            metrics.get("ISIN")
            or metrics.get("FundamentalsSymbol")
            or metrics.get("company_id")
            or ""
        ).strip().upper()
        if key:
            grouped.setdefault(key, []).append((ticker, metrics))
    mismatches: set[str] = set()
    for rows in grouped.values():
        if len(rows) < 2:
            continue
        fingerprints = {
            (
                int(metrics.get("score_model_version") or metrics.get("model_version") or 0),
                round(float(metrics.get("buffett_quality_score") or 0.0), 2),
                round(float(metrics.get("durability_score") or 0.0), 2),
                round(float(metrics.get("dilution_discipline_score") or 0.0), 2),
            )
            for _, metrics in rows
        }
        if len(fingerprints) > 1:
            mismatches.update(ticker.upper() for ticker, _ in rows)
    return mismatches


def score_calibration(results: dict[str, tuple[float, dict]]) -> dict[str, Any]:
    """Distribution de Quality V3 globale et par business model (actions seules)."""
    import numpy as np

    groups: dict[str, list[float]] = {"ALL": []}
    for _, (_, metrics) in results.items():
        if str(metrics.get("InstrumentType") or metrics.get("Secteur") or "").upper() == "ETF":
            continue
        value = metrics.get("buffett_quality_score")
        try:
            quality = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(quality):
            continue
        model = str(metrics.get("business_model") or metrics.get("score_business_model") or "unknown_model")
        groups["ALL"].append(quality)
        groups.setdefault(model, []).append(quality)

    def summarize(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0}
        array = np.asarray(values, dtype=float)
        return {
            "count": int(array.size),
            "percentiles": {
                f"p{percentile}": round(float(np.percentile(array, percentile)), 2)
                for percentile in (50, 75, 90, 95, 99)
            },
            "thresholds_pct": {
                f"gte_{threshold}": round(float(np.mean(array >= threshold) * 100.0), 2)
                for threshold in (80, 85, 90, 95)
            },
        }

    return {
        "score": "buffett_quality_v3",
        "global": summarize(groups.pop("ALL")),
        "by_business_model": {
            name: summarize(values) for name, values in sorted(groups.items())
        },
    }


def top_company_results(
    session: Session, run_id: int, limit: int = 50
) -> list[BuffettRunResult]:
    """Classe les sociétés, pas leurs lignes de cotation.

    ``company_id`` (normalement l'ISIN) est prioritaire. Les anciens résultats
    sans identité utilisent prudemment le nom normalisé. Les listings restent
    attachés au représentant dans ``secteurs_extra['entity']['listings']``.
    """
    from .dedup import normalize

    model_version = func.json_extract(
        BuffettRunResult.secteurs_extra, "$.scores.model_version"
    )
    base = select(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
    candidates = list(session.exec(
        base.where(model_version == 3)
        .order_by(BuffettRunResult.chance_moat.desc())
        .limit(max(limit * 20, 1000))
    ).all())
    if not candidates:
        candidates = list(session.exec(
            base.order_by(BuffettRunResult.chance_moat.desc())
            .limit(max(limit * 4, 200))
        ).all())

    grouped: dict[str, list[BuffettRunResult]] = {}
    order: list[str] = []
    for row in candidates:
        entity = dict((row.secteurs_extra or {}).get("entity") or {})
        company_id = str(entity.get("company_id") or "").strip().upper()
        normalized_name = normalize(str(row.nom or ""))
        key = company_id or (f"NAME:{normalized_name}" if normalized_name else f"TICKER:{row.ticker}")
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)

    representatives: list[BuffettRunResult] = []
    for key in order:
        listings = grouped[key]
        first_entity = dict((listings[0].secteurs_extra or {}).get("entity") or {})
        fundamental = str(first_entity.get("fundamentals_symbol") or "").upper()
        representative = min(
            listings,
            key=lambda row: (
                row.ticker.upper() != fundamental if fundamental else True,
                str(row.secteur or "").strip().casefold() in {"", "inconnu", "unknown"},
                -(float(row.volume or 0.0)),
                row.ticker,
            ),
        )
        quality_values = {
            round(float(value), 2)
            for row in listings
            if (value := ((row.secteurs_extra or {}).get("scores") or {}).get(
                "buffett_quality_score"
            )) is not None
        }
        extra = dict(representative.secteurs_extra or {})
        entity = dict(extra.get("entity") or {})
        entity.update({
            "company_id": entity.get("company_id") or key,
            "listings": sorted({row.ticker for row in listings}),
            "fundamental_mismatch": len(quality_values) > 1,
        })
        if len(quality_values) > 1:
            entity["flag"] = "FUNDAMENTAL_MISMATCH"
        extra["entity"] = entity
        representative.secteurs_extra = extra
        representatives.append(representative)
        if len(representatives) >= limit:
            break
    return representatives


def _publish_run(run_id: int, reason: str, **data: Any) -> None:
    publish(
        "finance.run.changed",
        data={"run_id": run_id, "reason": reason, **data},
        invalidate=[["finance", "buffett"]],
    )


def get_latest_results_by_ticker(
    session: Session, tickers: Iterable[str]
) -> dict[str, BuffettRunResult]:
    """Retourne le dernier résultat d'un run terminé pour chaque ticker.

    Les runs interrompus ou en cours sont ignorés. Les lignes historiques sans
    ``run_id`` restent disponibles en repli pour les tickers qui n'ont encore
    aucun résultat rattaché à un run terminé.
    """
    normalized = sorted({ticker.upper().strip() for ticker in tickers if ticker.strip()})
    if not normalized:
        return {}

    completed_rows = session.exec(
        select(BuffettRunResult)
        .join(BuffettRun, BuffettRun.id == BuffettRunResult.run_id)
        .where(BuffettRunResult.ticker.in_(normalized))  # type: ignore[attr-defined]
        .where(BuffettRun.statut == BuffettRunStatus.TERMINE.value)
        .order_by(BuffettRun.run_date.desc(), BuffettRun.id.desc())
    ).all()
    latest: dict[str, BuffettRunResult] = {}
    for row in completed_rows:
        latest.setdefault(row.ticker, row)

    missing = [ticker for ticker in normalized if ticker not in latest]
    if missing:
        legacy_rows = session.exec(
            select(BuffettRunResult)
            .where(BuffettRunResult.run_id.is_(None))  # type: ignore[union-attr]
            .where(BuffettRunResult.ticker.in_(missing))  # type: ignore[attr-defined]
            .order_by(BuffettRunResult.updated_at.desc(), BuffettRunResult.id.desc())
        ).all()
        for row in legacy_rows:
            latest.setdefault(row.ticker, row)

    return latest


def get_latest_result_for_ticker(
    session: Session, ticker: str
) -> BuffettRunResult | None:
    """Version unitaire de :func:`get_latest_results_by_ticker`."""
    normalized = ticker.upper().strip()
    return get_latest_results_by_ticker(session, [normalized]).get(normalized)


def delete_run(session: Session, run_id: int) -> bool:
    """Supprime un run Buffett et tous ses résultats. False si introuvable.

    Sert à retirer une analyse bloquée/interrompue (#) depuis l'UI.

    On efface les enfants via un **seul** DELETE en masse (et non ligne par ligne
    via l'ORM) : un run peut avoir des dizaines de milliers de résultats, et la
    boucle ORM tenait le verrou d'écriture SQLite trop longtemps → "database is
    locked" quand un autre run écrivait en parallèle. Le DELETE enfants passe
    AVANT le parent pour respecter la FK (ON en prod)."""
    run = session.get(BuffettRun, run_id)
    if run is None:
        return False
    session.exec(delete(BuffettRunResult).where(BuffettRunResult.run_id == run_id))
    session.delete(run)
    session.commit()
    _publish_run(run_id, "deleted")
    return True


def create_run(session: Session, n_total: int, params: dict) -> BuffettRun:
    """Crée un run en statut actif."""
    run = BuffettRun(
        run_date=dt.date.today(),
        statut=BuffettRunStatus.EN_COURS.value,
        n_tickers_total=n_total,
        n_tickers_analyzed=0,
        progress_pct=0.0,
        params_json=params,
        updated_at=utcnow(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    _publish_run(run.id, "created", statut=run.statut)
    return run


def archive_legacy_run(session: Session, run_id: int) -> bool:
    """Marque une analyse héritée comme non comparable, sans supprimer ses résultats."""
    run = session.get(BuffettRun, run_id)
    if run is None:
        return False
    if run.statut in {
        BuffettRunStatus.EN_COURS.value,
        BuffettRunStatus.INTERROMPU.value,
    }:
        raise RuntimeError(f"le run #{run_id} n'est pas terminé")
    params = dict(run.params_json or {})
    if params.get("archived_legacy"):
        return False
    params.update({"archived_legacy": True, "comparable": False})
    run.params_json = params
    legacy_note = "Analyse héritée non comparable"
    run.resume = f"{legacy_note} · {run.resume}" if run.resume else legacy_note
    run.updated_at = utcnow()
    session.add(run)
    session.commit()
    return True


def update_run_progress(session: Session, run_id: int, n_done: int, n_total: int) -> None:
    """Met à jour la progression et le total réellement analysable d'un run.

    Le run est créé avant le filtrage des titres indisponibles chez tous les
    brokers. ``n_total`` est donc la source de vérité après ce filtrage.
    """
    run = session.get(BuffettRun, run_id)
    if run:
        run.n_tickers_total = n_total
        run.n_tickers_analyzed = n_done
        run.progress_pct = round(n_done / n_total * 100, 1) if n_total else 0
        run.updated_at = utcnow()
        if run.statut != BuffettRunStatus.TERMINE.value:
            run.statut = BuffettRunStatus.EN_COURS.value  # un run qui progresse est bien actif
        session.add(run)
        session.commit()
        _publish_run(
            run_id,
            "progress",
            statut=run.statut,
            n_done=n_done,
            n_total=n_total,
            progress_pct=run.progress_pct,
        )


def update_run_optimization_diagnostics(
    session: Session, run_id: int, diagnostics: dict[str, Any]
) -> None:
    """Persiste les paramètres reproductibles et benchmarks de l'optimisation."""
    run = session.get(BuffettRun, run_id)
    if run is None:
        return
    params = dict(run.params_json or {})
    params["optimization"] = diagnostics
    run.params_json = params
    benchmarks = diagnostics.get("benchmarks") or {}
    optimized = benchmarks.get("optimized")
    equal_weight = benchmarks.get("equal_weight")
    best_ticker = benchmarks.get("best_single_ticker")
    best_single = benchmarks.get("best_single")
    if optimized is not None and equal_weight is not None:
        # Le score n'est plus un ratio sans unité mais un ÉCART au benchmark, en
        # points de rendement annuel : un « 2,05 » d'un ancien run et un « +3,22 »
        # d'un nouveau ne sont pas comparables, d'où l'étiquette explicite.
        bench_ticker = (diagnostics.get("benchmark_relative") or {}).get(
            "ticker", Config.STARR_BENCHMARK_TICKER
        )
        run.resume = (
            f"score vs {bench_ticker} {float(optimized):+.2f} pts "
            f"· équipondéré {float(equal_weight):+.2f}"
            + (
                f" · meilleur candidat simple {best_ticker} {float(best_single):+.2f}"
                if best_ticker and best_single is not None
                else ""
            )
        )
    run.updated_at = utcnow()
    session.add(run)
    session.commit()


def persist_optimization_outcome(
    session: Session,
    run_id: int,
    alloc: list[dict],
    diagnostics: dict[str, Any],
) -> tuple[list[dict], dict[str, Any]]:
    """Persiste ensemble la cible retenue et les diagnostics qui la décrivent.

    En cas de refus, les scores/mode du candidat ne doivent pas écraser ceux du
    portefeuille conservé. Si ce dernier vient d'un autre run, son allocation
    est recopiée sur le run demandé avec ses diagnostics d'origine.
    """
    replacement = diagnostics.get("allocation_replacement") or {}
    if replacement.get("accepted") is not False:
        update_allocations(session, run_id, alloc, reset=True)
        update_run_optimization_diagnostics(session, run_id, diagnostics)
        return alloc, diagnostics

    source_id = (diagnostics.get("portfolio_universe") or {}).get(
        "previous_target_run_id"
    ) or run_id
    source = session.get(BuffettRun, int(source_id))
    retained = deepcopy((source.params_json or {}).get("optimization") or {}) if source else {}
    source_rows = list(session.exec(
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == source_id)
        .where(BuffettRunResult.allocation_pct > 0)
    ).all())
    if not source_rows:
        # ``current_target_weights`` peut fournir un champion issu du fichier
        # broker, sans run DB correspondant. Dans ce cas, un candidat refusé
        # par la comparaison historique ne dispose d'aucune allocation
        # persistée à recopier. Ne pas faire échouer toute la run : conserver
        # la seule allocation concrète produite par cette optimisation permet
        # notamment à l'interface d'afficher le portefeuille trouvé au lieu de
        # retomber silencieusement sur le Top 50 des scores.
        if source_id == run_id and alloc:
            fallback_diagnostics = deepcopy(diagnostics)
            fallback_diagnostics.setdefault("allocation_replacement", {})[
                "fallback_persisted_candidate"
            ] = True
            update_allocations(session, run_id, alloc, reset=True)
            update_run_optimization_diagnostics(
                session, run_id, fallback_diagnostics
            )
            return alloc, fallback_diagnostics
        raise ValueError(
            "Aucune allocation admissible à conserver : " + str(replacement.get("reason") or "")
        )
    retained_alloc: list[dict] = []
    for row in source_rows:
        items = (row.secteurs_extra or {}).get("allocations") or []
        if items:
            retained_alloc.extend({
                "Ticker": item.get("ticker") or row.ticker,
                "AnalysisTicker": row.ticker,
                "Broker": item.get("broker"),
                "Poids total (%)": item.get("pct"),
                **{key: item.get(key) for key in ("shares", "eur", "prix", "type", "pie_pct")},
            } for item in items)
        else:
            retained_alloc.append({
                "Ticker": row.ticker,
                "Broker": row.broker_cible,
                "Poids total (%)": row.allocation_pct,
            })
        if source_id != run_id:
            target = session.exec(
                select(BuffettRunResult)
                .where(BuffettRunResult.run_id == run_id)
                .where(BuffettRunResult.ticker == row.ticker)
            ).first()
            if target is None:
                # Un ancien champion peut contenir un titre absent du nouveau
                # scoring. Conserver son identité et ses données historiques.
                values = row.model_dump(exclude={"id", "run_id"})
                session.add(BuffettRunResult(run_id=run_id, **values))
    # Une seule tentative est conservée : éviter une chaîne récursive de runs.
    retained.pop("last_optimization_attempt", None)
    retained["last_optimization_attempt"] = deepcopy(diagnostics)
    retained["retained_allocation_source_run_id"] = int(source_id)
    if source_id != run_id:
        session.flush()
        update_allocations(session, run_id, retained_alloc, reset=True)
    update_run_optimization_diagnostics(session, run_id, retained)
    return retained_alloc, retained


def update_run_buy_signal_diagnostics(
    session: Session, run_id: int, diagnostics: dict[str, Any]
) -> None:
    run = session.get(BuffettRun, run_id)
    if run is None:
        return
    params = dict(run.params_json or {})
    params["buy_signal"] = diagnostics
    run.params_json = params
    run.updated_at = utcnow()
    session.add(run)
    session.commit()


def finalize_run(
    session: Session, run_id: int, statut: str, duree_sec: float, erreur: str | None = None
) -> None:
    """Clôture un run (completed ou error)."""
    run = session.get(BuffettRun, run_id)
    if run:
        run.statut = statut
        run.duree_sec = duree_sec
        run.progress_pct = 100.0 if statut == BuffettRunStatus.TERMINE.value else run.progress_pct
        run.erreur = erreur
        run.updated_at = utcnow()
        session.add(run)
        session.commit()
        _publish_run(run_id, "finished", statut=statut, erreur=erreur)


def get_done_tickers(session: Session, run_id: int) -> set[str]:
    """Tickers deja persistes pour ce run (reprise apres fermeture du programme)."""
    rows = session.exec(
        select(BuffettRunResult.ticker).where(BuffettRunResult.run_id == run_id)
    ).all()
    return {t for t in rows}


def upsert_result(
    session: Session,
    run_id: int,
    ticker: str,
    score: float,
    metrics: dict,
    *,
    commit: bool = True,
) -> None:
    """Upsert un BuffettRunResult (1 ticker scoré pour ce run).

    Race condition safe : on attrape IntegrityError (note 13 du PLAN).
    """
    from sqlalchemy.exc import IntegrityError

    existing = session.exec(
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run_id)
        .where(BuffettRunResult.ticker == ticker)
    ).first()
    growth = metrics.get("CAGR")
    peg = metrics.get("PEG")
    values: dict[str, Any] = {
        "run_id": run_id,
        "nom": metrics.get("Nom"),
        "pays": metrics.get("Pays") or "Inconnu",
        "secteur": metrics.get("Secteur") or "Inconnu",
        "prix": float(metrics.get("Prix") or 0),
        "eps": float(metrics.get("EPS") or 0),
        "per": float(metrics.get("PER") or 0),
        "croissance": float(growth * 100) if growth else None,
        "peg": float(peg) if peg is not None else None,
        "volume": float(metrics.get("Volume") or 0),
        "chance_moat": (
            None
            if str(metrics.get("InstrumentType") or metrics.get("Secteur") or "").upper() == "ETF"
            else round(score, 2)
        ),
        "achat": bool(metrics.get("Achat", False)),
        "updated_at": utcnow(),
    }
    # FUSION, jamais remplacement : `secteurs_extra` porte aussi allocations,
    # buy_signal et valuation, qu'une reprise de run ne doit pas écraser.
    extra = dict(getattr(existing, "secteurs_extra", None) or {}) if existing else {}
    score_v2 = metrics.get("score_v3") or metrics.get("score_v2")
    if isinstance(score_v2, dict):
        extra["scores"] = {
            **score_v2,
            "buffett_rules_score": metrics.get("buffett_rules_score"),
        }
    identity_key = str(metrics.get("ISIN") or "").strip().upper()
    fundamentals_symbol = str(metrics.get("FundamentalsSymbol") or ticker).strip().upper()
    if identity_key or fundamentals_symbol:
        extra["entity"] = {
            "company_id": identity_key or fundamentals_symbol,
            "isin": identity_key or None,
            "fundamentals_symbol": fundamentals_symbol,
            "quote_symbol": str(metrics.get("QuoteSymbol") or ticker).strip().upper(),
        }
    valuation = metrics.get("valuation")
    if valuation:
        extra["valuation"] = valuation
    encours = metrics.get("Encours", metrics.get("AUM"))
    try:
        encours_value = float(encours)
    except (TypeError, ValueError):
        encours_value = 0.0
    if encours_value > 0:
        fund = dict(extra.get("fund") or {})
        fund["aum"] = encours_value
        extra["fund"] = fund
    if extra:
        values["secteurs_extra"] = extra
    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
        session.add(existing)
    else:
        obj = BuffettRunResult(ticker=ticker, **values)
        session.add(obj)
    if commit:
        try:
            session.commit()
        except IntegrityError:
            session.rollback()


def upsert_results_batch(
    session: Session, run_id: int, items: Iterable[tuple[str, float, dict]]
) -> None:
    """Persiste un lot avec un seul commit SQLite."""
    from sqlalchemy.exc import IntegrityError

    batch = list(items)
    for ticker, score, metrics in batch:
        upsert_result(session, run_id, ticker, score, metrics, commit=False)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Repli unitaire uniquement pour isoler une éventuelle course rare.
        for ticker, score, metrics in batch:
            upsert_result(session, run_id, ticker, score, metrics)


def update_allocations(
    session: Session, run_id: int, alloc: list[dict], reset: bool = True
) -> None:
    """Persiste l'allocation cible (multi-broker) sur les BuffettRunResult.

    ``alloc`` : liste de dicts produits par ``allocation.discretize_allocation`` :
      {Ticker, Broker, shares (int|None), eur, prix, type ('pie'|'shares'),
       'Poids total (%)'}

    Agrège par ticker : ``allocation_pct`` = somme des poids (%), ``broker_cible`` =
    broker(s), et stocke le détail par broker (nombre d'actions entières, montant €,
    prix, type) dans ``secteurs_extra['allocations']`` — sans migration de schéma.
    """
    by_ticker: dict[str, list[dict]] = {}
    for a in alloc:
        analysis_ticker = str(a.get("AnalysisTicker") or a["Ticker"])
        by_ticker.setdefault(analysis_ticker, []).append(a)

    # Les réponses Yahoo en cache peuvent ne contenir que le ticker. Le
    # catalogue local possède alors le nom officiel déjà vérifié : il est la
    # source de repli stable pour les allocations nouvelles et historiques.
    catalog_names: dict[str, str] = {}
    try:
        from .broker_availability import load_broker_table

        catalog = load_broker_table()
        ticker_col = next(
            (c for c in catalog.columns if str(c).strip() == "Ticker Yahoo Finance"),
            None,
        )
        name_col = next(
            (c for c in catalog.columns if str(c).strip().casefold() in {"nom", "name"}),
            None,
        )
        if ticker_col is not None and name_col is not None:
            catalog_names = {
                str(ticker).strip().upper(): str(name).strip()
                for ticker, name in zip(catalog[ticker_col], catalog[name_col], strict=True)
                if str(ticker).strip() and str(name).strip().casefold() not in {"", "nan", "none"}
            }
    except Exception:
        catalog_names = {}

    if reset and run_id is not None:
        rows = session.exec(
            select(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
        ).all()
        for r in rows:
            r.allocation_pct = None
            r.broker_cible = None
            extra = dict(r.secteurs_extra or {})
            if "allocations" in extra:
                extra.pop("allocations", None)
                r.secteurs_extra = extra or None
                session.add(r)

    for ticker, items in by_ticker.items():
        row = session.exec(
            select(BuffettRunResult)
            .where(BuffettRunResult.run_id == run_id)
            .where(BuffettRunResult.ticker == ticker)
        ).first()
        if not row:
            continue
        catalog_name = catalog_names.get(ticker.upper())
        if catalog_name and (not row.nom or row.nom.strip().upper() == ticker.upper()):
            row.nom = catalog_name
        total_pct = sum(float(it.get("Poids total (%)") or 0) for it in items)
        brokers = sorted({str(it.get("Broker")) for it in items})
        details = [{
            "broker": it.get("Broker"),
            "ticker": it.get("Ticker"),
            "shares": it.get("shares"),
            "eur": it.get("eur"),
            "prix": it.get("prix"),
            "type": it.get("type"),
            "pie_pct": it.get("pie_pct"),   # T212 : % entier du pie (somme 100 dans le broker)
            "pct": it.get("Poids total (%)"),
        } for it in items]
        row.allocation_pct = round(total_pct, 4)
        row.broker_cible = ", ".join(brokers)
        extra = dict(row.secteurs_extra or {})
        extra["allocations"] = details
        row.secteurs_extra = extra
        session.add(row)
    session.commit()
    _publish_run(run_id, "allocation", progressive=not reset)
