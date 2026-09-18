"""Sous-routeur Finance : analyses Buffett (runs, progression, export, optimisation)."""
from __future__ import annotations

import io
import logging
import threading
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from app.api.schemas_finance import (
    BuffettEquityLookthroughOut,
    BuffettLiveStateOut,
    BuffettProgressOut,
    BuffettRunDetailOut,
    BuffettRunOut,
    BuffettScenarioSelectIn,
)
from app.core.db import get_session
from app.core.rate_limit import rate_limit
from app.models.finance import BuffettRun, BuffettRunResult, BuffettRunStatus

logger = logging.getLogger(__name__)
router = APIRouter()

_HTTP_JOB_GUARD = threading.Lock()
_HTTP_JOBS: set[str] = set()


def _top_score_results(session: Session, run_id: int) -> list[BuffettRunResult]:
    from app.services.finance.buffett.reporting import top_company_results

    return top_company_results(session, run_id)


def _stored_portfolio_score(run: BuffettRun) -> tuple[int, float | None]:
    """Compatibilité de test/API pour le sélecteur partagé des champions."""
    from app.services.finance.buffett.champion import stored_portfolio_score

    return stored_portfolio_score(run)


def _start_dedicated_job(name: str, target, *args) -> bool:
    """Lance un long job hors du pool AnyIO utilisé par les requêtes HTTP.

    Les enrichissements ETF peuvent attendre des centaines de réponses
    officielles. Les exécuter comme ``BackgroundTask`` Starlette occupait le
    même pool que les endpoints synchrones et provoquait les ``socket hang up``
    observés lors d'un rechargement de page.
    """
    with _HTTP_JOB_GUARD:
        if name in _HTTP_JOBS:
            return False
        _HTTP_JOBS.add(name)

    def run() -> None:
        try:
            target(*args)
        finally:
            with _HTTP_JOB_GUARD:
                _HTTP_JOBS.discard(name)

    threading.Thread(
        target=run,
        name=f"mission-control-{name}",
        daemon=True,
    ).start()
    return True

# Rate limit partagé des analyses Buffett coûteuses (#193) : 5 lancements/min/IP.
_analysis_rl = rate_limit(max_calls=5, window_s=60, name="finance_analysis")


@router.get("/buffett/runs", response_model=list[BuffettRunOut])
def buffett_runs(limit: int = 12, session: Session = Depends(get_session)):
    stmt = (select(BuffettRun)
            .order_by(BuffettRun.run_date.desc())
            .limit(limit))
    return list(session.exec(stmt).all())


@router.get("/buffett/latest", response_model=Optional[BuffettRunOut])
def buffett_latest(session: Session = Depends(get_session)):
    stmt = (select(BuffettRun)
            .where(BuffettRun.statut == BuffettRunStatus.TERMINE.value)
            .order_by(BuffettRun.run_date.desc()))
    return session.exec(stmt).first()


@router.get("/buffett/progress", response_model=BuffettProgressOut)
def buffett_progress(session: Session = Depends(get_session)):
    from app.services.finance.scheduler_stub import is_analysis_running
    active = is_analysis_running()

    # Si aucune analyse ne tourne reellement dans ce process, un run encore
    # "en_cours" en base est en fait interrompu (programme ferme) -> on le marque
    # immediatement resumable pour debloquer le bouton "Reprendre". Le scoring
    # des tickers a 100% NE VEUT PAS DIRE que la pipeline est terminee : l'
    # optimisation DE (seeds illimites, peut durer des heures) vient juste
    # apres et peut avoir ete tuee en vol (crash, redemarrage --reload) sans
    # avoir produit de portefeuille. Seul finalize_run() (appele apres la
    # pipeline COMPLETE) a le droit de marquer "termine" -- ne jamais le faire
    # ici, sous peine de masquer un DE jamais termine sans aucune erreur
    # visible (et de reclasser a tort un run deja "interrompu").
    if not active:
        stuck = session.exec(
            select(BuffettRun).where(BuffettRun.statut == BuffettRunStatus.EN_COURS.value)  # type: ignore[attr-defined]
        ).all()
        changed = False
        for sr in stuck:
            sr.statut = BuffettRunStatus.INTERROMPU.value
            sr.erreur = "Process interrompu (relancez pour reprendre)"
            session.add(sr)
            changed = True
        if changed:
            session.commit()

    run = session.exec(
        select(BuffettRun)
        .where(BuffettRun.statut.in_([
            BuffettRunStatus.EN_COURS.value,
            BuffettRunStatus.INTERROMPU.value,
        ]))  # type: ignore[attr-defined]
        .order_by(BuffettRun.created_at.desc())
    ).first()
    if run:
        from app.services.finance.buffett.progress_state import snapshot as progress_snapshot
        from app.services.finance.buffett.rate_limiter import active_paused_until
        progress = progress_snapshot()
        # L'état mémoire transporte aussi run_id/n_done/n_total pour SSE.
        # Une fusion explicite évite les mots-clés dupliqués et garde la base
        # comme source autoritaire pour l'endpoint REST.
        progress.update(
            run_id=run.id,
            statut=run.statut,
            active=active,
            progress_pct=run.progress_pct or 0.0,
            n_done=run.n_tickers_analyzed,
            n_total=run.n_tickers_total,
            paused_until=active_paused_until() if active else None,
        )
        return BuffettProgressOut(**progress)
    return BuffettProgressOut(run_id=None, statut="idle", active=False, progress_pct=0.0)


@router.get("/portfolio/progress")
def portfolio_progress(history_after: int | None = Query(default=None, ge=0)):
    """Progression de l'optimisation de portefeuille (Differential Evolution).

    Alimente la barre de chargement du bouton « Créer le portefeuille optimal ».
    ``convergence`` (0→1) vient du callback DE et croît à mesure que la population
    converge ; ``progress_pct`` en dérive (0–100). Quand ``history_after`` est
    fourni, renvoie aussi chaque génération créée après cette itération globale,
    avec le score propre à sa seed et le meilleur score global.
    """
    from app.services.finance.buffett import optimization_progress as opt_prog
    snap = opt_prog.snapshot(history_after=history_after)
    snap["progress_pct"] = round(snap.get("convergence", 0.0) * 100, 1)
    return snap


@router.get("/buffett/live-state", response_model=BuffettLiveStateOut)
async def buffett_live_state(
    response: Response,
    history_after: int | None = Query(default=0, ge=0),
):
    """État atomique et non mis en cache utilisé lors d'un F5 du dashboard.

    L'historique des runs est volontairement exclu : une lecture lente de la
    timeline ne doit jamais masquer un calcul actif. Cet endpoint ne déclenche
    aucun téléchargement ni calcul financier.
    """
    from app.services.finance.buffett import optimization_progress as opt_prog
    from app.services.finance.buffett.progress_state import snapshot as progress_snapshot
    from app.services.finance.buffett.rate_limiter import active_paused_until
    from app.services.finance.scheduler_stub import is_analysis_running

    optimization = opt_prog.snapshot(history_after=history_after)
    optimization["progress_pct"] = round(
        float(optimization.get("convergence", 0.0)) * 100,
        1,
    )

    # Chemin critique pendant un long calcul : ne pas passer par une dépendance
    # Session synchrone ni par le pool AnyIO. Quand un navigateur abandonne une
    # requête proxy, un appel synchrone continue sinon à occuper son worker ; une
    # succession de timeouts finit par remplir tout le pool et bloque également
    # health, notifications et SSE. Les deux états live sont déjà thread-safe et
    # donnent tout ce dont le dashboard a besoin pendant une run.
    running = is_analysis_running()
    memory_progress = progress_snapshot()
    memory_active = bool(memory_progress.get("active"))
    if running and memory_active:
        memory_progress.update(
            statut="en_cours",
            active=True,
            paused_until=active_paused_until(),
        )
        analysis = BuffettProgressOut(**memory_progress)
    elif running and bool(optimization.get("active")):
        # Optimisation manuelle d'un run déjà terminé : aucun scoring actif.
        # Éviter la base reste important car le calcul numérique peut maintenir
        # une forte pression sur les workers du process.
        analysis = BuffettProgressOut(
            run_id=None,
            statut="idle",
            active=False,
            progress_pct=0.0,
        )
    else:
        # Hors calcul, conserver la logique historique (dont la détection d'un
        # run interrompu), mais l'exécuter explicitement hors de l'event loop.
        def read_persisted_progress() -> BuffettProgressOut:
            from app.core.db import engine

            with Session(engine) as session:
                return buffett_progress(session)

        analysis = await run_in_threadpool(read_persisted_progress)

    response.headers["Cache-Control"] = "no-store, max-age=0"
    return BuffettLiveStateOut(
        analysis=analysis,
        optimization=optimization,
    )


@router.post("/buffett/optimization/stop")
def optimization_stop():
    """Demande l'arrêt de l'optimisation DE en cours (run automatique OU bouton
    manuel « Créer le portefeuille optimal » -- un seul DE actif à la fois,
    cf. is_analysis_running()). Pris en compte à la fin de la GÉNÉRATION en
    cours (jamais au milieu d'une) : effectif en ~1 génération, le meilleur
    portefeuille trouvé jusque-là est conservé."""
    from app.services.finance.buffett import optimization_progress as opt_prog
    from app.services.finance.buffett import progress_state
    accepted = opt_prog.request_stop() or progress_state.request_stop()
    return {
        "accepted": accepted,
        "message": (
            "Arrêt demandé — le meilleur portefeuille sera conservé."
            if accepted else "Aucune optimisation active."
        ),
    }


@router.get("/buffett/runs/{run_id}", response_model=BuffettRunDetailOut)
def buffett_run_detail(run_id: int, session: Session = Depends(get_session)):
    run = session.get(BuffettRun, run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} introuvable")
    top = _top_score_results(session, run_id)
    alloc = list(session.exec(
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run_id)
        .where(BuffettRunResult.allocation_pct.isnot(None))
        .order_by(BuffettRunResult.allocation_pct.desc())
    ).all())
    optimization = (run.params_json or {}).get("optimization")
    buy_signal = (run.params_json or {}).get("buy_signal")
    return BuffettRunDetailOut(
        run=run,
        top_results=top,
        allocation_cible=alloc,
        optimization=optimization,
        buy_signal=buy_signal,
    )


@router.get(
    "/buffett/runs/{run_id}/equity-lookthrough",
    response_model=BuffettEquityLookthroughOut,
)
def buffett_run_equity_lookthrough(
    run_id: int,
    refresh: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    """Remplace visuellement les ETF d'une allocation terminée par leurs actions."""
    from app.core.timeutil import utcnow
    from app.services.finance.buffett.equity_lookthrough import (
        build_equity_lookthrough,
        fetch_etf_holdings,
    )

    run = session.get(BuffettRun, run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} introuvable")
    if run.statut != BuffettRunStatus.TERMINE.value:
        raise HTTPException(409, "La décomposition est disponible uniquement pour une run terminée")

    params = dict(run.params_json or {})
    cached = params.get("equity_lookthrough_v3")
    if cached and not refresh:
        return cached

    allocation = list(
        session.exec(
            select(BuffettRunResult)
            .where(BuffettRunResult.run_id == run_id)
            .where(BuffettRunResult.allocation_pct.isnot(None))
            .order_by(BuffettRunResult.allocation_pct.desc())
        ).all()
    )
    allocation = [row for row in allocation if (row.allocation_pct or 0) > 0]
    if not allocation:
        raise HTTPException(409, "Cette run terminée ne contient aucune allocation cible")

    etf_tickers = [
        row.ticker
        for row in allocation
        if (row.secteur or "").strip().upper() == "ETF"
    ]
    result = build_equity_lookthrough(allocation, fetch_etf_holdings(etf_tickers))
    result.update(run_id=run_id, generated_at=utcnow().isoformat())
    params["equity_lookthrough_v3"] = result
    run.params_json = params
    run.updated_at = utcnow()
    session.add(run)
    session.commit()
    return result


@router.put("/buffett/runs/{run_id}/active-scenario")
def select_buffett_scenario(
    run_id: int,
    payload: BuffettScenarioSelectIn,
    session: Session = Depends(get_session),
):
    """Sélectionne une cible persistée sans créer d'ordre ni de transaction."""
    from app.services.finance.buffett.reporting import update_allocations

    run = session.get(BuffettRun, run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} introuvable")
    params = dict(run.params_json or {})
    optimization = dict(params.get("optimization") or {})
    scenarios = dict(optimization.get("world_scenarios") or {})
    selected = scenarios.get(payload.scenario)
    if not isinstance(selected, dict) or not selected.get("allocation"):
        raise HTTPException(409, f"Scénario {payload.scenario} indisponible pour cette run")
    update_allocations(session, run_id, list(selected["allocation"]))
    scenarios["active"] = payload.scenario
    optimization["world_scenarios"] = scenarios
    params["optimization"] = optimization
    params.pop("equity_lookthrough_v2", None)
    params.pop("equity_lookthrough_v3", None)
    run.params_json = params
    session.add(run)
    session.commit()
    return {"run_id": run_id, "active_scenario": payload.scenario}


@router.delete("/buffett/runs/{run_id}", status_code=204)
def buffett_run_delete(run_id: int, session: Session = Depends(get_session)):
    """Supprime un run Buffett (et ses résultats) — ex. analyse bloquée."""
    from app.services.finance.buffett.reporting import delete_run
    if not delete_run(session, run_id):
        raise HTTPException(404, f"Run {run_id} introuvable")


@router.get("/buffett/runs/{run_id}/export")
def buffett_run_export(run_id: int, session: Session = Depends(get_session)):
    """Exporte les resultats d'un run Buffett en Excel."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    run = session.get(BuffettRun, run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} introuvable")

    results = list(session.exec(
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run_id)
        .order_by(BuffettRunResult.chance_moat.desc())
    ).all())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resultats MOAT"

    ws.append([f"Analyse Buffett - Run #{run_id} - {run.run_date}"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([
        f"Statut : {run.statut}",
        f"Tickers analyses : {run.n_tickers_analyzed or 0}/{run.n_tickers_total or 0}",
        f"Duree : {run.duree_sec or 0:.0f}s",
    ])
    ws.append([])

    headers = ["Ticker", "Nom", "Secteur", "Pays", "Score MOAT", "Alloc. cible (%)", "Broker cible", "Achat"]
    header_row = 4
    ws.append(headers)
    header_fill = PatternFill("solid", fgColor="1E3A5F")
    header_font = Font(bold=True, color="FFFFFF")
    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    green_fill = PatternFill("solid", fgColor="D6F5D6")
    blue_fill = PatternFill("solid", fgColor="D6E8F5")
    for r in results:
        score_val = r.chance_moat
        row = [
            r.ticker,
            r.nom or "",
            r.secteur or "",
            r.pays or "",
            round(score_val, 2) if score_val is not None else None,
            round(r.allocation_pct, 2) if r.allocation_pct is not None else None,
            r.broker_cible or "",
            "oui" if r.achat else "",
        ]
        ws.append(row)
        if (r.secteur or "").strip().upper() == "ETF":
            fill = blue_fill  # ETF
        elif score_val and score_val >= 80:
            fill = green_fill  # Eligible
        else:
            fill = None
        if fill:
            for col_idx in range(1, len(headers) + 1):
                ws.cell(row=ws.max_row, column=col_idx).fill = fill

    col_widths = [12, 32, 20, 18, 12, 16, 16, 7]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    alloc_list = [r for r in results if r.allocation_pct]
    if alloc_list:
        ws2 = wb.create_sheet("Allocation cible")
        ws2.append(["Ticker", "Nom", "Broker cible", "Alloc. cible (%)"])
        for cell in ws2[1]:
            cell.fill = header_fill
            cell.font = header_font
        for r in sorted(alloc_list, key=lambda x: -(x.allocation_pct or 0)):
            ws2.append([r.ticker, r.nom or "", r.broker_cible or "",
                        round(r.allocation_pct, 2) if r.allocation_pct else None])
        for i, w in enumerate([12, 32, 16, 16], 1):
            ws2.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"buffett_run_{run_id}_{run.run_date}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/buffett/runs/{run_id}/export.csv")
def buffett_run_export_csv(run_id: int, session: Session = Depends(get_session)):
    """Exporte les résultats d'un run Buffett en CSV (sans dépendance)."""
    import csv
    import io as _io

    run = session.get(BuffettRun, run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} introuvable")

    results = list(session.exec(
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run_id)
        .order_by(BuffettRunResult.chance_moat.desc())
    ).all())

    buf = _io.StringIO()
    writer = csv.writer(buf, delimiter=';')
    writer.writerow([
        "Ticker", "Nom", "Secteur", "Pays", "Score MOAT", "Achat",
        "Allocation cible (%)", "Broker cible", "PER", "Prix",
    ])
    for r in results:
        writer.writerow([
            r.ticker, r.nom or "", r.secteur or "", r.pays or "",
            round(r.chance_moat, 2) if r.chance_moat is not None else "",
            "oui" if r.achat else "",
            round(r.allocation_pct, 2) if r.allocation_pct is not None else "",
            r.broker_cible or "",
            round(r.per, 2) if r.per else "",
            round(r.prix, 2) if r.prix else "",
        ])
    buf.seek(0)
    filename = f"buffett_run_{run_id}_{run.run_date}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/buffett/breakdown/{ticker}")
def buffett_breakdown(ticker: str, force: bool = False):
    """Détail du score Buffett d'un titre par critère (marge, ROE, dette…)."""
    from app.services.finance.buffett.runner import analyze_single_ticker
    from app.services.finance.buffett.scoring_pure import score_breakdown

    result = analyze_single_ticker(ticker.upper().strip(), force=force)
    if result is None:
        raise HTTPException(404, f"Analyse impossible pour {ticker} (données absentes/invalides).")
    score, metrics = result
    ratios = metrics.get("ratios_recents") or {}
    return {
        "ticker": ticker.upper(),
        "score": score,
        "secteur": metrics.get("Secteur"),
        "couverture_pct": metrics.get("score_coverage_pct"),
        "criteres": score_breakdown(
            ratios,
            str(metrics.get("Secteur") or ""),
            str(metrics.get("Industrie") or ""),
        ),
    }


@router.get("/backtest")
def backtest_allocation(periode: str = "2y", session: Session = Depends(get_session)):
    """Backtest buy-and-hold de l'allocation cible du dernier run Buffett terminé.

    Renvoie {dates, equity (base 100), rendement_pct, n_points, tickers}.
    """
    run = session.exec(
        select(BuffettRun)
        .where(BuffettRun.statut == BuffettRunStatus.TERMINE.value)
        .order_by(BuffettRun.run_date.desc())
    ).first()
    if not run:
        raise HTTPException(404, "Aucun run Buffett terminé")

    rows = list(session.exec(
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run.id)
        .where(BuffettRunResult.allocation_pct.isnot(None))  # type: ignore[attr-defined]
    ).all())
    weights = {r.ticker: float(r.allocation_pct or 0) for r in rows if (r.allocation_pct or 0) > 0}
    if not weights:
        return {"dates": [], "equity": [], "rendement_pct": 0.0, "n_points": 0, "tickers": []}

    from app.services.finance.backtest import simulate_allocation
    dates: list[str] = []
    prices: dict[str, list[float]] = {}
    try:
        from app.services.finance.buffett.allocation import close_prices_from_download
        from app.services.finance.yf_session import download_with_timeout, yf_session
        t_list = list(weights.keys())
        raw = download_with_timeout(
            tickers=t_list, period=periode, interval="1d", progress=False,
            group_by="ticker", session=yf_session(),
        )
        if not raw.empty:
            cd = close_prices_from_download(raw, t_list)
            cd = cd.dropna(how="all").ffill().dropna()
            dates = [d.strftime("%Y-%m-%d") for d in cd.index]
            prices = {t: [float(x) for x in cd[t].tolist()] for t in cd.columns}
    except Exception as exc:
        logger.warning("Backtest download: %s", exc)

    sim = simulate_allocation(prices, weights)
    dates = dates[: sim["n_points"]]
    return {
        "dates": dates,
        "equity": sim["equity"],
        "rendement_pct": sim["rendement_pct"],
        "n_points": sim["n_points"],
        "tickers": list(prices.keys()),
    }


@router.get("/backtest/walk-forward")
def backtest_walk_forward(
    periode: str = "5y",
    cost_bps: float = 10.0,
    session: Session = Depends(get_session),
):
    """Backtest trimestriel des allocations réellement connues à chaque date.

    Contrairement au backtest buy-and-hold de la cible actuelle, aucune allocation
    future n'est appliquée au passé. Avec un seul run historique, la période testable
    commence donc à ce run — limitation honnête plutôt qu'une fuite temporelle.
    """
    runs = list(session.exec(
        select(BuffettRun)
        .where(BuffettRun.statut == BuffettRunStatus.TERMINE.value)
        .order_by(BuffettRun.run_date.asc())
    ).all())
    allocations = []
    scenario_allocations: dict[str, list[dict]] = {
        "free": [], "world_25": [], "world_40": [], "world_55": [],
    }
    all_tickers: set[str] = set()
    for run in runs:
        rows = list(session.exec(
            select(BuffettRunResult)
            .where(BuffettRunResult.run_id == run.id)
            .where(BuffettRunResult.allocation_pct.isnot(None))  # type: ignore[attr-defined]
        ).all())
        weights = {
            row.ticker: float(row.allocation_pct or 0.0)
            for row in rows if float(row.allocation_pct or 0.0) > 0
        }
        if weights:
            allocations.append({"date": run.run_date.isoformat(), "weights": weights})
            all_tickers.update(weights)
        scenarios = ((run.params_json or {}).get("optimization") or {}).get(
            "world_scenarios"
        ) or {}
        for scenario_key in scenario_allocations:
            scenario = scenarios.get(scenario_key)
            if not isinstance(scenario, dict):
                continue
            scenario_weights: dict[str, float] = {}
            for item in scenario.get("allocation") or []:
                ticker = str(item.get("AnalysisTicker") or item.get("Ticker") or "").strip()
                weight = float(item.get("Poids total (%)") or 0.0)
                if ticker and weight > 0:
                    scenario_weights[ticker] = scenario_weights.get(ticker, 0.0) + weight
            if scenario_weights:
                scenario_allocations[scenario_key].append({
                    "date": run.run_date.isoformat(), "weights": scenario_weights,
                })
                all_tickers.update(scenario_weights)
    if not allocations:
        return {
            "mode": "walk_forward", "dates": [], "equity": [], "n_points": 0,
            "rendement_pct": 0.0, "n_runs": 0, "tickers": [],
        }
    # Benchmark investissable commun à l'application. Son ajout n'influence pas
    # l'univers optimisé ; il sert uniquement à la comparaison hors échantillon.
    all_tickers.add("CW8.PA")

    dates: list[str] = []
    prices: dict[str, list[float]] = {}
    try:
        from app.services.finance.buffett.allocation import close_prices_from_download
        from app.services.finance.yf_session import download_with_timeout, yf_session

        ticker_list = sorted(all_tickers)
        raw = download_with_timeout(
            tickers=ticker_list,
            period=periode,
            interval="1d",
            progress=False,
            group_by="ticker",
            session=yf_session(),
        )
        if raw is not None and not raw.empty:
            close = close_prices_from_download(raw, ticker_list).dropna(how="all").ffill()
            dates = [value.strftime("%Y-%m-%d") for value in close.index]
            prices = {
                ticker: [float(value) for value in close[ticker].to_numpy()]
                for ticker in close.columns
            }
    except Exception as exc:
        logger.warning("Backtest walk-forward download: %s", exc)

    from app.services.finance.backtest import simulate_walk_forward

    result = simulate_walk_forward(
        dates, prices, allocations, rebalance_days=80, cost_bps=cost_bps
    )
    equal_allocations = [
        {"date": item["date"], "weights": {ticker: 1.0 for ticker in item["weights"]}}
        for item in allocations
    ]
    equal_result = simulate_walk_forward(
        dates, prices, equal_allocations, rebalance_days=80, cost_bps=cost_bps
    )
    benchmark_allocations = [
        {"date": item["date"], "weights": {"CW8.PA": 1.0}}
        for item in allocations
    ]
    benchmark_result = simulate_walk_forward(
        dates, prices, benchmark_allocations, rebalance_days=80, cost_bps=cost_bps
    )
    scenario_results = {
        key: simulate_walk_forward(
            dates, prices, values, rebalance_days=80, cost_bps=cost_bps
        )
        for key, values in scenario_allocations.items()
        if values
    }

    def _summary(values: dict) -> dict:
        return {
            key: values.get(key, 0.0)
            for key in (
                "rendement_pct", "cagr_pct", "max_drawdown_pct", "cvar_5_pct",
                "turnover", "costs_pct", "n_points",
                "volatility_pct", "semi_deviation_pct", "omega",
            )
        }

    return {
        "mode": "walk_forward",
        **result,
        "n_runs": len(allocations),
        "tickers": sorted(prices),
        "cost_bps": cost_bps,
        "comparisons": {
            "optimized": _summary(result),
            "equal_weight": _summary(equal_result),
            "CW8.PA": _summary(benchmark_result),
            **{key: _summary(value) for key, value in scenario_results.items()},
        },
        "scenario_series": {
            key: {"dates": value.get("dates", []), "equity": value.get("equity", [])}
            for key, value in scenario_results.items()
        },
    }


# --- Bouton 1 : Analyser tous les tickers ---

@router.post("/buffett/run", status_code=202, dependencies=[Depends(_analysis_rl)])
def buffett_run_start(
    background_tasks: BackgroundTasks,
    csv_path: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Lance ou REPREND l'analyse de tous les tickers de tickers.csv.

    Si une analyse tourne deja dans ce process, l'appel est ignore. Sinon le job
    reprend automatiquement le dernier run interrompu (sans refaire les tickers
    deja analyses, sauvegardes un a un) ou en cree un nouveau.
    """
    from app.services.finance.scheduler_stub import is_analysis_running, job_monthly_buffett
    if is_analysis_running():
        return {"message": "Analyse deja en cours", "status": "running"}
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.ticker_universe import (
        TickerCatalogError,
        read_ticker_catalog,
    )
    requested_csv = csv_path or str(Config.TICKERS_CSV)
    resumable = session.exec(
        select(BuffettRun)
        .where(BuffettRun.statut.in_([
            BuffettRunStatus.EN_COURS.value,
            BuffettRunStatus.INTERROMPU.value,
        ]))  # type: ignore[attr-defined]
        .order_by(BuffettRun.run_date.desc(), BuffettRun.id.desc())  # type: ignore[attr-defined]
    ).first()
    validation_path = requested_csv
    if resumable:
        from app.services.finance.buffett.universe_snapshot import snapshot_path

        validation_path = snapshot_path(resumable.params_json, requested_csv)
    try:
        read_ticker_catalog(validation_path, require_canonical=True)
    except TickerCatalogError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_ticker_catalog",
                "message": str(exc),
                **exc.diagnostics.as_dict(),
            },
        ) from exc
    if not _start_dedicated_job("buffett-exclusive", job_monthly_buffett, csv_path):
        return {"message": "Analyse deja en cours", "status": "running"}
    return {"message": "Analyse demarree (reprise si un run etait interrompu)", "status": "accepted"}


# --- Bouton 2 : Analyser un ticker precis ---

@router.post("/buffett/analyze-ticker", status_code=200, dependencies=[Depends(_analysis_rl)])
async def buffett_analyze_ticker(ticker: str, force: bool = False):
    """Analyse un seul ticker et retourne score + metrics immediatement."""
    from app.services.finance.buffett.runner import analyze_single_ticker
    result = analyze_single_ticker(ticker.upper().strip(), force=force)
    if result is None:
        raise HTTPException(
            404,
            f"Impossible d'analyser {ticker} : donnees absentes, trop fraiches, ou ticker invalide.",
        )
    score, metrics = result
    return {"ticker": ticker.upper(), "score": score, "metrics": metrics}


# --- Bouton 3 : Creer le portefeuille optimal (Differential Evolution) ---

def _run_portfolio_creation(
    run_id: int,
    min_score_val: float,
    include_etfs: bool = True,
) -> None:
    """Corps du job d'arriere-plan lance par ``portfolio_create``.

    Extrait au niveau module (plutot que ferme dans ``portfolio_create``) pour
    pouvoir etre appele/teste directement, et surtout pour pouvoir acquerir
    ``_ANALYSIS_LOCK`` en garde reelle : le pre-check HTTP ``is_analysis_running()``
    dans ``portfolio_create`` est fait UNE FOIS avant de planifier ce job en
    BackgroundTask -- un double-clic ou un chevauchement avec le run automatique
    ``job_monthly_buffett`` peut donc passer ce pre-check puis s'executer en
    parallele d'un autre job, mutant Config.BUDGET_BROKERS / optimization_progress
    / ToutBroker.xlsx depuis deux threads a la fois. Le verrou ici est la seule
    garde fiable contre cette course.
    """
    from app.services.finance.scheduler_stub import _ANALYSIS_LOCK
    if not _ANALYSIS_LOCK.acquire(blocking=False):
        logger.info("[portfolio_create] Analyse deja en cours dans ce process -> job ignore")
        return
    try:
        import pandas as pd
        from sqlmodel import Session as S
        from sqlmodel import select as sel

        from app.core.db import engine
        from app.services.finance.buffett import optimization_progress as opt_prog
        from app.services.finance.buffett.allocation import (
            average_turnover_eur_from_download,
            close_prices_from_download,
            discretize_allocation,
            latest_prices_eur,
        )
        from app.services.finance.buffett.broker_availability import (
            current_target_weights,
            load_broker_table,
            load_etf_tickers,
            merge_broker_columns,
        )
        from app.services.finance.buffett.config import Config
        from app.services.finance.buffett.dedup import deduplicate_tickers
        from app.services.finance.buffett.optimizer import (
            meets_optimization_score_threshold,
            optimize_portfolio_de,
            prepare_optimization,
        )
        from app.services.finance.buffett.reporting import (
            fundamental_mismatch_tickers,
            persist_optimization_outcome,
        )
        from app.services.finance.buffett.transaction_costs import (
            estimate_rebalance_costs_by_broker,
            ttf_tickers_from_dataframe,
        )

        opt_prog.start(run_id=run_id, message="Préparation des candidats…")
        Config.load_params()
        from app.services.finance.buffett.broker_budgets import apply_live_broker_budgets
        apply_live_broker_budgets()  # budgets = soldes réels des comptes
        logger.info(
            "[portfolio_create] Paramètres allocation : seuil_global=%.2f%%, "
            "seuil_T212_pie=%.2f%%, budgets=%s",
            float(Config.MIN_ALLOCATION_THRESHOLD) * 100.0,
            float(Config.STARR_MIN_T212_PIE_PCT) * 100.0,
            dict(Config.BUDGET_BROKERS),
        )
        with S(engine) as sess:
            # Tous les candidats: score >= seuil OU ETF (score=200) OU Achat=True
            all_rows = list(sess.exec(
                sel(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
            ).all())

            requested_mode = "actions_and_etfs" if include_etfs else "actions_only"
            from app.services.finance.buffett.champion import (
                select_best_stored_target,
            )

            # Le workbook est une sortie de compatibilité, pas la source de
            # vérité du champion : le sélecteur partagé examine les allocations
            # réellement persistées et privilégie le meilleur score exécutable.
            selected_target = select_best_stored_target(
                sess,
                current_run_id=run_id,
                requested_mode=requested_mode,
            )
            previous_target_weights = selected_target["weights"]
            previous_target_source = selected_target["source"]
            previous_target_run_id = selected_target["run_id"]
            previous_target_mode = selected_target["mode"]
            previous_target_score_rank = selected_target["score_rank"]
            previous_target_historical_score = selected_target["historical_score"]

        broker_table = load_broker_table()
        etf_tickers = load_etf_tickers(broker_table)

        def is_etf_result(row: BuffettRunResult) -> bool:
            return (
                row.ticker.upper() in etf_tickers
                or str(row.secteur or "").strip().upper() == "ETF"
            )

        row_metrics = {
            row.ticker: (
                float(row.chance_moat or 0.0),
                {
                    **dict((row.secteurs_extra or {}).get("scores") or {}),
                    "ISIN": ((row.secteurs_extra or {}).get("entity") or {}).get("isin"),
                    "FundamentalsSymbol": ((row.secteurs_extra or {}).get("entity") or {}).get("fundamentals_symbol"),
                    "Secteur": row.secteur,
                },
            )
            for row in all_rows
        }
        mismatch_tickers = fundamental_mismatch_tickers(row_metrics)
        candidates = {
            r.ticker: r for r in all_rows
            if include_etfs or not is_etf_result(r)
            if meets_optimization_score_threshold(
                r.ticker,
                r.chance_moat or 0,
                min_score_val,
                Config.FORCED_BUY_TICKERS,
                is_etf=is_etf_result(r),
                quality_score=((r.secteurs_extra or {}).get("scores") or {}).get("buffett_quality_score"),
                confidence_pct=((r.secteurs_extra or {}).get("scores") or {}).get("confidence_pct"),
                comparable_to_standard=bool(((r.secteurs_extra or {}).get("scores") or {}).get("comparable_to_standard", True)),
                model_complete=bool(((r.secteurs_extra or {}).get("scores") or {}).get("model_complete", True)),
                fundamental_mismatch=r.ticker.upper() in mismatch_tickers,
                min_confidence_pct=Config.SCORE_MIN_CONFIDENCE_PCT,
            )
        }
        excluded_etf_count = (
            sum(is_etf_result(row) for row in all_rows) if not include_etfs else 0
        )
        if excluded_etf_count:
            logger.info(
                "[portfolio_create] Mode actions uniquement : %s ETF ignorés.",
                excluded_etf_count,
            )
        if candidates:
            import pandas as pd
            preliminary = pd.DataFrame([{
                "Ticker Yahoo Finance": ticker,
                "Nom": row.nom or "",
                "Secteur": row.secteur or "",
                "Volume": row.volume or 0,
            } for ticker, row in candidates.items()])
            preliminary = merge_broker_columns(preliminary)
            canonical = set(
                deduplicate_tickers(
                    pd.DataFrame(columns=list(candidates)),
                    preliminary,
                ).columns
            )
            candidates = {
                ticker: row for ticker, row in candidates.items()
                if ticker in canonical
            }
        if not candidates:
            logger.warning("[portfolio_create] Aucun candidat eligible.")
            opt_prog.finish(
                message="Aucun candidat éligible avec les critères demandés.",
                status="error",
                termination_reason="no_eligible_candidates",
            )
            return

        logger.info(f"[portfolio_create] {len(candidates)} candidats (depuis le run en DB)...")

        # On NE re-télécharge PAS chaque candidat en live : sous rate-limit
        # yfinance, ces appels échouaient tous -> 0 ticker valide -> DE sur liste
        # vide -> Sharpe -inf. On réutilise les scores/indicateurs déjà calculés
        # par le run (en DB). Le seul appel réseau restant est le download groupé
        # des cours pour la matrice de covariance (impersoné via yf_session).
        from app.services.finance.buffett.liquidity import passes_portfolio_liquidity
        forced = [t.upper() for t in Config.FORCED_BUY_TICKERS]
        verified: dict[str, tuple[float, dict]] = {}
        n_illiquid = 0
        for ticker, r in candidates.items():
            score = float(r.chance_moat or 0)
            is_etf = is_etf_result(r)
            is_forced = ticker.upper() in forced
            # ``candidates`` a déjà appliqué Quality V3, confiance et modèle.
            # Ne pas réinterpréter ici le classement shrinké comme un score de
            # qualité, sinon les meilleures sociétés à preuve partielle sortent.
            eligible = True
            # Filtre de liquidité (sauf forcés) : volume échangé €/jour >= seuil.
            # r.volume est en euros depuis le passage de la colonne Volume en €
            # (runs anterieurs : nb d'actions brut, pas de migration -- spec).
            # Le volume échangé sur UNE place n'est pas une mesure fiable de
            # liquidité d'un ETF : teneurs de marché et création/rachat donnent
            # accès à la liquidité du panier sous-jacent. Garder le seuil pour
            # les actions ; le volume ETF reste utilisé pour classer les fonds.
            if not passes_portfolio_liquidity(
                r.volume,
                is_etf=is_etf,
                is_forced=is_forced,
            ):
                if eligible and r.achat:
                    n_illiquid += 1
                continue
            if eligible and r.achat:
                verified[ticker] = (score, {
                    "Nom": r.nom or "", "Secteur": r.secteur or "",
                    "Pays": r.pays or "Inconnu",
                    "Volume": r.volume or 0, "Achat": True,
                    **dict((r.secteurs_extra or {}).get("scores") or {}),
                })

        from app.services.finance.buffett.leverage_filter import is_leveraged_product
        verified = {
            ticker: value
            for ticker, value in verified.items()
            if not (
                ticker.upper() not in forced
                and (
                    ticker.upper() in etf_tickers
                    or "ETF" in str(value[1].get("Secteur", "")).upper()
                )
                and is_leveraged_product(value[1].get("Nom", ""))
            )
        }

        if not include_etfs:
            replication_diagnostics = {
                "total": len(etf_tickers),
                "known_before": 0,
                "unknown_before": 0,
                "resolved_now": 0,
                "unknown_after": 0,
                "statuses": {},
                "skipped": True,
                "reason": "include_etfs=false",
            }
            isin_diagnostics = {"skipped": True, "reason": "include_etfs=false"}
            logger.info(
                "[portfolio_create] Réplications ETF ignorées (mode actions uniquement) : "
                "%d ETF du catalogue non utilisés.",
                len(etf_tickers),
            )
        else:
            try:
                from collections import Counter

                from app.services.finance.buffett.etf_index_registry import resolve_index_registry

                known = resolve_index_registry(etf_tickers, broker_table=broker_table)
                statuses = Counter(
                    str(value.get("replication") or "unknown") for value in known.values()
                )
                replication_diagnostics = {
                    "total": len(etf_tickers),
                    "known_before": len(etf_tickers) - statuses.get("unknown", 0),
                    "unknown_before": statuses.get("unknown", 0),
                    "resolved_now": 0,
                    "unknown_after": statuses.get("unknown", 0),
                    "statuses": dict(statuses),
                    "deferred_until_after_correlation": True,
                }
                isin_diagnostics = {"deferred": True}
                logger.info(
                    "[portfolio_create] Réplications ETF : %s",
                    replication_diagnostics,
                )
            except Exception as exc:
                replication_diagnostics = {
                    "total": len(etf_tickers),
                    "known_before": 0,
                    "unknown_before": len(etf_tickers),
                    "resolved_now": 0,
                    "unknown_after": len(etf_tickers),
                    "statuses": {},
                    "error": str(exc),
                }
                isin_diagnostics = {"error": str(exc)}
                logger.warning(
                    "[portfolio_create] Identification des réplications ETF incomplète: %s",
                    exc,
                )

        logger.info(f"[portfolio_create] {len(verified)} tickers valides "
                    f"({n_illiquid} écartés <{Config.MIN_VOLUME_EUR:,.0f} €/j) -> optimisation DE...")
        from app.services.finance.buffett.sector_constraints import resolve_risk_categories

        risk_categories, classification_diagnostics = resolve_risk_categories(
            {
                ticker: value[1].get("Secteur", "")
                for ticker, value in verified.items()
            },
            broker_table=broker_table,
        )
        classification_diagnostics["replication_enrichment"] = replication_diagnostics
        classification_diagnostics["isin_enrichment"] = isin_diagnostics
        verified = {
            ticker: value
            for ticker, value in verified.items()
            if ticker.upper() in risk_categories
        }
        if classification_diagnostics["excluded"]:
            logger.info(
                "[portfolio_create] Classification risque: %s titres écartés avant cours",
                classification_diagnostics["excluded"],
            )
        if not verified:
            logger.warning("[portfolio_create] Aucun ticker valide -> optimisation annulee.")
            opt_prog.finish(
                message="Aucun titre ne satisfait les critères de liquidité et de classification.",
                status="error",
                termination_reason="no_valid_candidates",
            )
            return

        # Le benchmark doit etre telecharge meme s'il n'est pas eligible : c'est
        # la reference du score, pas un candidat a l'allocation force (meme
        # logique que runner.py -- ce chemin est le SECOND call site independant
        # vers optimize_portfolio_de, celui du bouton manuel "Creer le
        # portefeuille optimal" ; avant ce correctif il ne passait pas du tout
        # benchmark_returns et levait donc systematiquement une ValueError).
        bench_ticker = str(Config.STARR_BENCHMARK_TICKER).strip().upper()
        t_list = list(verified.keys())
        if bench_ticker and bench_ticker not in {t.upper() for t in t_list}:
            t_list.append(bench_ticker)
        ticker_col = "Ticker Yahoo Finance"
        try:
            opt_prog.set_phase("preparation", "Téléchargement des cours…")
            from app.services.finance.yf_session import download_prices_bulk_with_retry
            raw = download_prices_bulk_with_retry(
                t_list, period="5y", interval="1d", progress=False, group_by="ticker",
                use_cache=True,
                on_progress=lambda done, tot: opt_prog.set_phase(
                    "preparation", f"Téléchargement des cours… {done}/{tot} titres"),
            )
            if raw.empty:
                opt_prog.finish(
                    message="Cours indisponibles : aucun portefeuille n'a été calculé.",
                    status="error",
                    termination_reason="prices_unavailable",
                )
                return
            etf_turnover = average_turnover_eur_from_download(raw, list(etf_tickers))
            for ticker, turnover in etf_turnover.items():
                if ticker in verified:
                    verified[ticker][1]["Volume"] = turnover
                    verified[ticker][1]["VolumeDevise"] = "EUR"
            from app.services.finance.buffett.allocation import drop_short_history
            cd = close_prices_from_download(raw, t_list)
            cd, too_young = drop_short_history(cd, int(Config.STARR_MIN_HISTORY_DAYS))
            if too_young:
                logger.info(f"[portfolio_create] Historique < {Config.STARR_MIN_HISTORY_DAYS} "
                            f"jours : {len(too_young)} titres écartés")
            cd = cd.ffill()
            rets = cd.pct_change().dropna().clip(-0.5, 0.5)
            if len(rets):
                logger.info(f"[portfolio_create] Fenêtre commune de rendements : {len(rets)} jours "
                            f"({rets.index[0].date()} -> {rets.index[-1].date()})")

            # Extraction du benchmark AVANT dedup/selection : ces etapes peuvent
            # l'ecarter (jumeau d'indice, plafond de 50 ETF/broker) alors qu'il
            # doit rester la reference du score (meme raisonnement que runner.py).
            from app.services.finance.buffett.dedup import returns_in_base_currency
            bench_rets = None
            bench_col = next((c for c in rets.columns if str(c).upper() == bench_ticker), None)
            if bench_col is not None:
                bench_rets = returns_in_base_currency(
                    rets[[bench_col]], "EUR", strict=True
                )[bench_col]
                logger.info(f"[portfolio_create] Benchmark {bench_ticker} : {len(bench_rets)} jours")
                if bench_ticker not in {t.upper() for t in verified}:
                    # Ajoute uniquement pour extraire son rendement (pas eligible,
                    # cf. plus haut) : ne doit pas rester un candidat a
                    # l'allocation, sinon prepare_optimization lui accorderait un
                    # acces broker par defaut (ticker absent de df_m -> True) et
                    # le DE pourrait l'acheter reellement.
                    rets = rets.drop(columns=[bench_col])
            else:
                logger.warning(f"[portfolio_create] ATTENTION : benchmark {bench_ticker} absent des cours")

            df_m = pd.DataFrame([{
                ticker_col: t,
                "Nom": verified[t][1].get("Nom", ""),
                "Secteur": verified[t][1].get("Secteur", ""),
                "Risk Category": risk_categories.get(t.upper(), ""),
                "Volume": verified[t][1].get("Volume", 0),
                "Chance MOAT": verified[t][0],
                "Achat": True,
            } for t in t_list if t in rets.columns])

            # Disponibilite par broker depuis ToutBroker.xlsx (sinon tout dispo)
            df_m = merge_broker_columns(
                df_m,
                ticker_col,
                broker_table=broker_table,
            )
            opt_prog.set_phase("preparation", "Déduplication (cross-listings)…")
            rets = deduplicate_tickers(rets, df_m, ticker_col)
            # returns_in_base_currency deja importe plus haut (extraction du
            # benchmark) : cet appel-ci convertit tout `rets`, pas seulement sa
            # colonne.
            rets = returns_in_base_currency(rets, "EUR", strict=True)
            from app.services.finance.buffett.equity_lookthrough import (
                _is_non_equity_etf,
                economic_exposure_from_payload,
                index_risk_lookthrough,
                index_sector_country_lookthrough,
            )

            economic_minimum_coverage = float(
                Config.ETF_ECONOMIC_COMPOSITION_MIN_COVERAGE
            )
            economic_compositions: dict[str, dict] = {}
            composition_quality: dict[str, dict] = {}
            rejected_by_broker: dict[str, set[str]] = {}
            etf_exclusions: set[str] = set()
            row_by_ticker = {
                str(row.get(ticker_col) or "").strip().upper(): row
                for _, row in df_m.iterrows()
            }
            constituent_metadata = {
                str(ticker).strip().upper(): {
                    "country": values[1].get("Pays", ""),
                    "sector": values[1].get("Secteur", ""),
                }
                for ticker, values in verified.items()
                if str(ticker).strip().upper() not in etf_tickers
            }
            rets_pool, df_pool = rets, df_m
            correlation_promotions: list[dict] = []
            round_index = 0
            replacement_search_truncated = False
            unverified_after_search_limit: set[str] = set()

            def report_etf_composition(
                batch: int, stage: str, done: int, total: int, item: str,
            ) -> None:
                nonlocal round_index
                round_index = batch
                label = {
                    "fonds": "fonds émetteurs",
                    "indices": "indices officiels",
                    "assemblage": "assemblage des expositions",
                }.get(stage, stage)
                current = str(item or "").strip()
                opt_prog.set_phase(
                    "preparation",
                    f"Compositions ETF — lot {max(batch, 1)} · "
                    f"{label} {done}/{total}"
                    + (f" · {current}" if current else ""),
                    done=done,
                    total=total,
                    current_item=current,
                )

            def report_etf_batch(batch: int, pending: list[str], diagnostics: dict) -> None:
                nonlocal round_index
                round_index = batch
                if pending:
                    broker_quota = " · ".join(
                        f"{broker} lot {values.get('selected', 0)} "
                        f"(cible {Config.ETF_MAX_CANDIDATES_PER_BROKER})"
                        for broker, values in (
                            diagnostics.get("brokers") or {}
                        ).items()
                    )
                    opt_prog.set_phase(
                        "preparation",
                        f"Compositions ETF — lot {batch} · "
                        f"{len(pending)} à vérifier"
                        + (f" · {broker_quota}" if broker_quota else ""),
                    )

            from app.services.finance.buffett.etf_composition_batches import (
                select_verified_etfs_per_broker,
            )

            batch_result = select_verified_etfs_per_broker(
                rets_pool,
                df_pool,
                ticker_col,
                etf_tickers=etf_tickers,
                metadata_by_ticker=row_by_ticker,
                constituent_metadata=constituent_metadata,
                returns_are_base_currency=True,
                should_stop=lambda: bool(opt_prog.snapshot().get("stop_requested")),
                on_batch=report_etf_batch,
                on_progress=report_etf_composition,
                on_error=lambda exc: logger.warning(
                    "Compositions économiques ETF indisponibles: %s", exc
                ),
            )
            if batch_result.stopped:
                opt_prog.finish(
                    message="Arrêté par l’utilisateur pendant la vérification des compositions ETF.",
                    status="stopped",
                    termination_reason="user_stop",
                )
                return
            rets, df_m = batch_result.returns, batch_result.frame
            etf_selection_diagnostics = batch_result.selection_diagnostics
            economic_compositions = batch_result.compositions
            composition_quality = batch_result.quality_by_ticker
            etf_exclusions = batch_result.exclusions
            rejected_by_broker = batch_result.rejected_by_broker
            attempted_upfront = batch_result.attempted
            initial_broker_candidates = batch_result.initial_broker_candidates
            round_index = batch_result.batches
            if not previous_target_weights:
                previous_target_weights = current_target_weights(df_m, ticker_col)
                previous_target_source = "workbook_fallback"
            logger.info(
                "[portfolio_create] Champion précédent : source=%s run_id=%s mode=%s "
                "poids=%s",
                previous_target_source,
                previous_target_run_id,
                previous_target_mode,
                round(sum(previous_target_weights.values()), 6),
            )
            previous_weights = previous_target_weights
            ttf_tickers = ttf_tickers_from_dataframe(df_m, ticker_col)
            t_opt = list(rets.columns)
            retained_champion = {
                str(ticker).strip().upper(): float(weight or 0.0)
                for ticker, weight in previous_weights.items()
                if str(ticker).strip().upper() in {str(value).strip().upper() for value in t_opt}
            }
            logger.info(
                "[portfolio_create] Champion dans univers courant : %d/%d titres, "
                "poids retenu=%.4f",
                len(retained_champion),
                len(previous_weights),
                sum(retained_champion.values()),
            )
            opt_prog.set_phase(
                "preparation",
                f"Champion précédent : {len(retained_champion)}/{len(previous_weights)} "
                f"titres conservés ({sum(retained_champion.values()):.1%})…",
            )
            if len(t_opt) < 2:
                logger.warning(
                    f"[portfolio_create] {len(t_opt)} ticker(s) avec historique de cours "
                    "exploitable -> optimisation impossible (besoin d'au moins 2)."
                )
                opt_prog.finish(
                    message="Pas assez de titres avec un historique exploitable.",
                    status="error",
                    termination_reason="insufficient_history",
                )
                return
            mat_access, active_b = prepare_optimization(t_opt, df_m)
            economic_action_exposures: dict[str, dict[str, float]] = {
                ticker.upper(): {ticker.upper(): 1.0}
                for ticker in t_opt
                if ticker.upper() not in etf_tickers
            }
            economic_unknown_exposures: dict[str, float] = {}
            sector_country_exposures = index_sector_country_lookthrough(
                economic_compositions,
                constituent_metadata,
            )
            country_exposures: dict[str, dict[str, float]] = {}
            sector_exposures: dict[str, dict[str, float]] = {}
            defensive_exposures: dict[str, float] = {}
            etf_countries, etf_sectors, etf_defensive = index_risk_lookthrough(
                economic_compositions,
                constituent_metadata,
            )
            country_exposures.update(etf_countries)
            sector_exposures.update(etf_sectors)
            defensive_exposures.update(etf_defensive)
            for ticker in t_opt:
                key = ticker.upper()
                if key in etf_tickers:
                    continue
                values = verified.get(ticker, verified.get(key, (0, {})))[1]
                country = str(values.get("Pays") or "Inconnu")
                sector = str(values.get("Secteur") or "Inconnu")
                country_exposures[key] = {country: 1.0}
                sector_exposures[key] = {sector: 1.0}
                sector_country_exposures[key] = {sector: {country: 1.0}}
            coverage_by_ticker: dict[str, float] = {}
            for ticker in t_opt:
                key = ticker.upper()
                if key not in etf_tickers:
                    continue
                metadata = row_by_ticker.get(key, {})
                if _is_non_equity_etf(metadata):
                    continue
                exposure, coverage, _, source_is_economic = economic_exposure_from_payload(
                    economic_compositions.get(key, []),
                    minimum_coverage=0.0,
                )
                if not source_is_economic:
                    exposure, coverage = {}, 0.0
                economic_action_exposures[key] = exposure
                economic_unknown_exposures[key] = max(0.0, 1.0 - coverage)
                coverage_by_ticker[key] = coverage
            sector_by_ticker = {
                ticker.upper(): risk_categories[ticker.upper()]
                for ticker in t_opt
                if ticker.upper() in risk_categories
            }
            total_cap = sum(Config.BUDGET_BROKERS.values())
            prices = latest_prices_eur(cd, t_opt)
            from app.services.finance.buffett.execution import prepare_execution_quotes

            execution_routes, execution_prices = prepare_execution_quotes(
                t_opt, active_b, mat_access, df_m, prices,
            )
            from app.services.finance.buffett.broker_positions import (
                current_broker_weights as load_current_broker_weights,
            )
            with S(engine) as position_session:
                broker_holdings = load_current_broker_weights(
                    position_session,
                    prices_eur=prices,
                    total_capital_eur=total_cap,
                    active_brokers=active_b,
                )
            opt_prog.set_phase("optimisation", f"Optimisation Differential Evolution ({len(t_opt)} titres)…")

            def _executable_weights(continuous_weights):
                """Version réellement achetable du portefeuille, pour la scorer.

                Rend une matrice de poids reconstruite depuis une discrétisation
                en actions entières / pies. La réserve de frais est estimée
                directement depuis la cible et les positions courantes afin que
                le score exécutable et l'allocation finale parlent du même
                portefeuille réellement achetable.
                """
                from app.services.finance.buffett.allocation import (
                    alloc_to_weight_matrix,
                )

                fee_reserve = estimate_rebalance_costs_by_broker(
                    t_opt,
                    continuous_weights,
                    active_b,
                    total_cap,
                    current_broker_holdings=broker_holdings,
                    is_etf_tickers=etf_tickers,
                    ttf_tickers=ttf_tickers,
                    execution_routes=execution_routes,
                )
                trial = discretize_allocation(
                    t_opt,
                    continuous_weights,
                    active_b,
                    prices,
                    total_cap,
                    sector_by_ticker=sector_by_ticker,
                    sector_exposures_by_ticker=sector_exposures,
                    execution_routes=execution_routes,
                    execution_prices=execution_prices,
                    fee_reserve_eur_by_broker=fee_reserve,
                )
                return alloc_to_weight_matrix(trial, t_opt, active_b, total_cap)

            def _on_new_best(w_matrix) -> None:
                """Réserve le callback pour la progression, sans muter la cible.

                Une amélioration continue peut devenir moins bonne après
                discrétisation en actions entières/pies. La cible DB est donc
                remplacée uniquement après le score exécutable final.
                """
                return None

            weights, sharpe, diagnostics = optimize_portfolio_de(
                t_opt, rets, mat_access, active_b,
                progress_cb=opt_prog.update_de,
                initialization_cb=opt_prog.update_initialization,
                discretize_cb=_executable_weights,
                on_new_best=_on_new_best,
                preparation_cb=lambda msg: opt_prog.set_phase("optimisation", msg),
                should_stop=lambda: opt_prog.snapshot()["stop_requested"],
                continuous_until_stopped=True,
                current_weights=previous_weights,
                current_broker_holdings=broker_holdings,
                sector_by_ticker=sector_by_ticker,
                sector_exposures_by_ticker=sector_exposures,
                defensive_exposures_by_ticker=defensive_exposures,
                country_exposures=country_exposures,
                economic_action_exposures=economic_action_exposures,
                economic_unknown_exposures=economic_unknown_exposures,
                sector_country_exposures_by_ticker=sector_country_exposures,
                ttf_tickers=ttf_tickers,
                benchmark_returns=bench_rets,
                quality_scores_by_ticker={
                    ticker.upper(): float(verified[ticker][1].get("buffett_quality_score") or 0.0)
                    for ticker in t_opt
                    if ticker in verified and ticker.upper() not in etf_tickers
                },
                return_diagnostics=True,
            )
            diagnostics["etf_selection"] = etf_selection_diagnostics
            diagnostics["portfolio_universe"] = {
                "include_etfs": include_etfs,
                "mode": "actions_only" if not include_etfs else "actions_and_etfs",
                "etf_candidates_excluded": excluded_etf_count,
                "previous_target_source": previous_target_source,
                "previous_target_run_id": previous_target_run_id,
                "previous_target_mode": previous_target_mode,
                "previous_target_historical_score": previous_target_historical_score,
                "previous_target_score_kind": (
                    "executable"
                    if previous_target_score_rank == 2
                    else "continuous"
                    if previous_target_score_rank == 1
                    else "unavailable"
                ),
                "previous_target_mode_comparable": previous_target_mode == (
                    "actions_and_etfs" if include_etfs else "actions_only"
                ),
            }
            diagnostics["economic_composition_filter"] = {
                "quality_reference_coverage": economic_minimum_coverage,
                "descriptive_only": False,
                "excluded_for_economic_coverage": len(etf_exclusions),
                "coverage_by_ticker": coverage_by_ticker,
                "replaced_tickers": sorted(etf_exclusions),
                "quality_by_ticker": composition_quality,
                "correlation_promotions": correlation_promotions,
                "replacement_search": {
                    "rounds": round_index,
                    "batches": round_index,
                    "batch_buffer_per_broker": int(
                        Config.ETF_COMPOSITION_BATCH_BUFFER_PER_BROKER
                    ),
                    "attempted_count": len(attempted_upfront),
                    "rejected_count": len(etf_exclusions),
                    "max_network_workers": int(Config.ETF_ENRICHMENT_MAX_WORKERS),
                    "max_rounds": None,
                    "truncated": replacement_search_truncated,
                    "unverified_count": len(unverified_after_search_limit),
                    "unverified_tickers": sorted(unverified_after_search_limit),
                },
                "broker_verification": {
                    broker: {
                        "target": int(Config.ETF_MAX_CANDIDATES_PER_BROKER),
                        "catalog_candidates": int(
                            initial_broker_candidates.get(
                                broker, values.get("candidates_before", 0)
                            )
                        ),
                        "verified": int(values.get("selected", 0)),
                        "shortage": max(
                            int(Config.ETF_MAX_CANDIDATES_PER_BROKER)
                            - int(values.get("selected", 0)),
                            0,
                        ),
                        "rejected": len(rejected_by_broker.get(broker, set())),
                        "rejected_tickers": sorted(rejected_by_broker.get(broker, set())),
                        "shortfall_reason": (
                            "eligible_catalog_exhausted"
                            if int(values.get("selected", 0))
                            < int(Config.ETF_MAX_CANDIDATES_PER_BROKER)
                            else ""
                        ),
                    }
                    for broker, values in (
                        etf_selection_diagnostics.get("brokers") or {}
                    ).items()
                },
            }
            diagnostics["classification_filter"] = classification_diagnostics

            opt_prog.set_phase("finalisation", "Calcul de l'allocation…")
            # Actions entieres (hors Trading212) / pies (Trading212), a partir des prix
            execution_fee_reserve = estimate_rebalance_costs_by_broker(
                t_opt,
                weights,
                active_b,
                total_cap,
                current_broker_holdings=broker_holdings,
                is_etf_tickers=etf_tickers,
                ttf_tickers=ttf_tickers,
                execution_routes=execution_routes,
            )
            alloc = discretize_allocation(
                t_opt,
                weights,
                active_b,
                prices,
                total_cap,
                sector_by_ticker=sector_by_ticker,
                sector_exposures_by_ticker=sector_exposures,
                execution_routes=execution_routes,
                execution_prices=execution_prices,
                fee_reserve_eur_by_broker=execution_fee_reserve,
            )
            diagnostics.setdefault("transaction_costs", {})[
                "allocation_fee_reserve_eur_by_broker"
            ] = {
                broker: float(value)
                for broker, value in execution_fee_reserve.items()
            }
            diagnostics["transaction_costs"][
                "allocation_reserve_matches_executable_score"
            ] = True
            if isinstance(diagnostics.get("executed_portfolio"), dict):
                diagnostics["executed_portfolio"][
                    "fee_reserve_eur_by_broker"
                ] = {
                    broker: float(value)
                    for broker, value in execution_fee_reserve.items()
                }
            from app.services.finance.buffett.allocation import (
                allocation_sector_diagnostics,
            )
            post_sector = allocation_sector_diagnostics(
                alloc,
                total_cap=total_cap,
                sector_by_ticker=sector_by_ticker,
                sector_exposures_by_ticker=sector_exposures,
            )
            diagnostics["sector_constraints"]["post_discretization"] = post_sector
            diagnostics["sector_constraints"]["compliant"] = post_sector["compliant"]
            from app.services.finance.buffett.champion import allocation_replacement_decision

            replacement = allocation_replacement_decision(
                diagnostics, min_improvement=Config.STARR_DE_MIN_IMPROVEMENT,
            )
            diagnostics["allocation_replacement"] = replacement
            replace_allocation = replacement["accepted"]
            new_executed_score = replacement["new_executed_score"]
            previous_executed_score = replacement["previous_executed_score"]
            replacement_reason = replacement["reason"]
            with S(engine) as sess:
                alloc, _persisted_diagnostics = persist_optimization_outcome(
                    sess, run_id, alloc, diagnostics,
                )
            logger.info(
                "[portfolio_create] Allocation %s : nouveau=%.5f précédent=%s (%s)",
                "remplacée" if replace_allocation else "conservée",
                float(new_executed_score) if new_executed_score is not None else float("nan"),
                previous_executed_score,
                replacement_reason,
            )
            # Le fichier broker est lui aussi une cible active : ne pas y
            # écrire un candidat refusé par la comparaison exécutable.
            if replace_allocation:
                try:
                    from app.services.finance.buffett.broker_availability import (
                        update_broker_file_weights,
                    )
                    n_w = update_broker_file_weights(alloc)
                    logger.info(f"[portfolio_create] {n_w} poids ecrits dans ToutBroker.xlsx")
                except Exception as e:
                    logger.error(f"[portfolio_create] Ecriture Poids: {e}")
            n_alloc = len({a["Ticker"] for a in alloc})
            logger.info(f"[portfolio_create] Sharpe={sharpe:.3f}, {n_alloc} tickers alloues.")
            stopped = (diagnostics.get("termination") or {}).get("reason") == "user_stop"
            opt_prog.finish(
                message=(
                    "Arrêté par l’utilisateur — meilleur portefeuille conservé."
                    if stopped else (
                        f"Portefeuille créé : {n_alloc} titres alloués."
                        if replace_allocation else f"Champion conservé : {n_alloc} titres alloués."
                    )
                ),
                status="stopped" if stopped else "completed",
                termination_reason=(diagnostics.get("termination") or {}).get("reason"),
            )
        except Exception as e:
            logger.error(f"[portfolio_create] Erreur optimisation: {e}")
            opt_prog.finish(
                message=f"Erreur optimisation : {e}",
                status="error",
                termination_reason="error",
            )
    except Exception as exc:
        from app.services.finance.buffett import optimization_progress as opt_prog

        logger.exception("[portfolio_create] Erreur de préparation du portefeuille")
        opt_prog.finish(
            message=f"Erreur de préparation : {exc}",
            status="error",
            termination_reason="error",
        )
    finally:
        _ANALYSIS_LOCK.release()


@router.post("/portfolio/create", status_code=202, dependencies=[Depends(_analysis_rl)])
def portfolio_create(
    background_tasks: BackgroundTasks,
    min_score: float = 80.0,
    include_etfs: bool = True,
    session: Session = Depends(get_session),
):
    """Filtre les eligibles, re-verifie les scores, optimise avec DE.

    ``include_etfs=false`` conserve le même objectif et les mêmes contraintes,
    mais retire les ETF de l'univers avant la préparation des cours.
    """
    from app.services.finance.scheduler_stub import is_analysis_running
    if is_analysis_running():
        raise HTTPException(409, "Une analyse ou optimisation est deja en cours.")

    latest_run = _latest_optimizable_run(session)
    if latest_run is None:
        raise HTTPException(404, "Aucun run Buffett termine. Lancer d'abord l'analyse complete.")

    if not _start_dedicated_job(
        "buffett-exclusive",
        _run_portfolio_creation,
        latest_run.id,
        min_score,
        include_etfs,
    ):
        raise HTTPException(409, "Une optimisation est deja en cours.")
    return {
        "message": (
            f"Creation portefeuille lancee (run #{latest_run.id}, seuil={min_score}, "
            f"ETF={'oui' if include_etfs else 'non'})"
        ),
        "status": "accepted",
        "run_id": latest_run.id,
    }


def _latest_optimizable_run(session: Session) -> BuffettRun | None:
    """Dernier run dont le scoring est complet, même si son optimisation a échoué.

    Une erreur postérieure au scoring (comme une incompatibilité pandas pendant
    la présélection ETF) marque le run ``erreur`` mais ses résultats restent
    complets et réutilisables. Le bouton de création doit reprendre ce run au
    lieu de retomber silencieusement sur un ancien portefeuille terminé.
    """
    return session.exec(
        select(BuffettRun)
        .where(BuffettRun.statut.in_([  # type: ignore[attr-defined]
            BuffettRunStatus.TERMINE.value,
            BuffettRunStatus.ERREUR.value,
        ]))
        .where(BuffettRun.n_tickers_total > 0)  # type: ignore[operator]
        .where(BuffettRun.n_tickers_analyzed >= BuffettRun.n_tickers_total)  # type: ignore[operator]
        .order_by(BuffettRun.run_date.desc(), BuffettRun.id.desc())  # type: ignore[attr-defined]
    ).first()
