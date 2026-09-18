"use client";

/** Vue détail d'un run Buffett : allocation cible, backtest, exports (extrait de BuffettTab, #532). */

import { AlertTriangle } from "lucide-react";
import type { BuffettRunDetail } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { fmt, StatusBadge, type OptProgress } from "./buffett-ui";
import { DeStarrChart } from "./DeStarrChart";
import { BacktestChart } from "./BacktestChart";
import { brokerShort, investedEur } from "./BuffettAllocationCells";
import { BuffettAllocationSection } from "./BuffettAllocationSection";
import { useBuffettRunDetailActions } from "./BuffettRunDetailActions";

export function BuffettRunDetailView({
  selected,
  onBack,
  onError,
  onReload,
  optProgress = null,
}: {
  selected: BuffettRunDetail;
  onBack: () => void;
  onError: (msg: string) => void;
  onReload: () => Promise<void>;
  /** Progression DE live (SSE via le parent) : affiche le graphe STARR ici
   *  aussi — avant, il n'existait que sur la vue liste de l'onglet, donc il
   *  « disparaissait » dès qu'on ouvrait le détail du run (#bug rapporté). */
  optProgress?: OptProgress | null;
}) {
  const {
    backtest,
    backtesting,
    lookthrough,
    showLookthrough,
    loadingLookthrough,
    lookthroughError,
    selectingScenario,
    runBacktest,
    runWalkForward,
    selectAllocationView,
    selectScenario,
    exportRun,
  } = useBuffettRunDetailActions({ selected, onError, onReload });

  // S'il existe une allocation cible : on affiche le portefeuille complet à
  // acheter (toutes les lignes allouées, pas seulement le top 50 par score),
  // trié par poids décroissant. Sinon : top scores Buffett conservateurs.
  const allocated = [...selected.allocation_cible]
    .filter((r) => (r.allocation_pct ?? 0) > 0)
    .sort((a, b) => investedEur(b) - investedEur(a)); // tri par montant investi décroissant
  const hasAlloc = allocated.length > 0;
  const v3TopResults = selected.top_results.filter(
    (result) => result.score_model_version === 3,
  );
  // Pendant une reprise ciblée, l'API peut momentanément renvoyer un mélange
  // d'anciens scores sans détail et de résultats V3. Ne jamais présenter les
  // anciennes valeurs comme une « Qualité » V3 avec huit colonnes vides.
  const displayRows = hasAlloc
    ? allocated
    : v3TopResults.length > 0
      ? v3TopResults
      : selected.top_results;
  const totalInvested = allocated.reduce((s, r) => s + investedEur(r), 0);
  const totalPct = allocated.reduce((s, r) => s + (r.allocation_pct ?? 0), 0);
  const missingIndexAlerts = Object.entries(
    selected.optimization?.economic_composition_filter?.quality_by_ticker ?? {},
  )
    .filter(([, quality]) => {
      const status = (quality.index_status ?? "").toLowerCase();
      const complete = status === "complete" || status === "complete_cached";
      return (
        !quality.eligible &&
        !complete &&
        (Boolean(status) ||
          quality.reason === "synthetic_index_unresolved" ||
          quality.reason === "synthetic_index_constituents_required" ||
          quality.reason === "unofficial_or_collateral_composition")
      );
    })
    .sort(([left], [right]) => left.localeCompare(right));

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← Retour
        </Button>
        <h2 className="text-base font-semibold">Run du {selected.run.run_date}</h2>
        <StatusBadge s={selected.run.statut} />
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void runBacktest();
            }}
            loading={backtesting}
          >
            📈 Backtest 2 ans
          </Button>
          <Button
            variant="outline"
            size="sm"
            title="Backtest hors échantillon sur 5 ans : applique seulement les allocations déjà connues à chaque date, avec rééquilibrage trimestriel et frais de 0,10 %."
            aria-label="Lancer le walk-forward historique sans utiliser d’informations futures"
            onClick={() => {
              void runWalkForward();
            }}
            loading={backtesting}
          >
            🧭 Walk-forward
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void exportRun("xlsx");
            }}
          >
            📊 Excel
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void exportRun("csv");
            }}
          >
            📄 CSV
          </Button>
        </div>
      </div>
      {missingIndexAlerts.length > 0 && (
        <div className="rounded-xl border border-amber-500/60 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-100">
          <div className="flex items-center gap-2 font-semibold">
            <span aria-hidden="true">⚠️</span>
            <span>Indices à compléter ({missingIndexAlerts.length})</span>
          </div>
          <p className="mt-1 text-xs opacity-85">
            Ces ETF restent dans le catalogue, mais sont exclus de l’optimisation tant que leur
            indice économique officiel n’est pas identifié et vérifié. Chaque absence est désormais
            affichée explicitement, y compris lorsqu’aucun nom d’indice n’a été trouvé.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {missingIndexAlerts.map(([ticker, quality]) => (
              <span
                key={`missing-index-${ticker}`}
                className="rounded-full border border-amber-500/50 px-2 py-1 text-xs"
              >
                {ticker} · {quality.index || quality.index_id || "indice inconnu"}
                {quality.provider ? ` · ${quality.provider}` : ""}
                {quality.index_status ? ` · ${quality.index_status}` : ` · ${quality.reason}`}
              </span>
            ))}
          </div>
        </div>
      )}
      {selected.optimization?.world_scenarios && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold">Scénarios MSCI World</span>
            {(["free", "world_25", "world_40", "world_55"] as const).map((key) => {
              const scenario = selected.optimization?.world_scenarios?.[key];
              if (!scenario) return null;
              const active = selected.optimization?.world_scenarios?.active === key;
              return (
                <Button
                  key={key}
                  size="sm"
                  variant={active ? "default" : "outline"}
                  loading={selectingScenario === key}
                  onClick={() => {
                    void selectScenario(key);
                  }}
                >
                  {key === "free"
                    ? "Libre"
                    : `World ≥ ${Math.round(scenario.minimum_world_weight * 100)} %`}
                  {` · ${scenario.score >= 0 ? "+" : ""}${scenario.score.toFixed(2)}`}
                </Button>
              );
            })}
            {selected.optimization.world_scenarios.unavailable_reason && (
              <span className="text-xs text-[var(--muted-foreground)]">
                {selected.optimization.world_scenarios.unavailable_reason}
              </span>
            )}
          </div>
          <p className="mt-2 text-xs text-[var(--muted-foreground)]">
            Libre reste la cible par défaut. Changer de scénario modifie seulement la cible
            enregistrée, sans créer d’ordre.
          </p>
        </div>
      )}
      {selected.run.statut === "en_cours" && (
        <p className="text-xs rounded-[var(--radius)] bg-[var(--info-muted)] text-[var(--info-foreground)] px-3 py-2">
          Optimisation en cours — la meilleure allocation affichée reste provisoire et s’actualise
          automatiquement.
        </p>
      )}
      {selected.run.statut === "en_cours" &&
        optProgress?.run_id === selected.run.id &&
        optProgress.best_score != null &&
        optProgress.best_score < 0 && (
          <p className="flex items-start gap-2 rounded-[var(--radius)] border border-[var(--destructive)]/40 bg-[var(--destructive)]/10 px-3 py-2 text-xs text-[var(--destructive)]">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
              Meilleure solution provisoire&nbsp;: score contre CW8 {fmt(optProgress.best_score, 4)}
              . Elle reste moins bonne que le benchmark et ne constitue pas encore une cible
              validée.
            </span>
          </p>
        )}
      {optProgress?.active && optProgress.run_id === selected.run.id && (
        <DeStarrChart optProgress={optProgress} />
      )}
      {backtest && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm flex items-center gap-3 flex-wrap">
          <span className="text-[var(--muted-foreground)]">
            {backtest.mode === "walk_forward"
              ? `Walk-forward trimestriel (${backtest.n_runs ?? 0} runs, frais 10 pb) :`
              : "Backtest buy-and-hold (2 ans) de l'allocation cible :"}
          </span>
          {backtest.n_points > 0 ? (
            <span
              className={`font-mono font-semibold ${backtest.rendement_pct >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}
            >
              {backtest.rendement_pct >= 0 ? "+" : ""}
              {backtest.rendement_pct.toFixed(2)} %
            </span>
          ) : (
            <span className="text-[var(--muted-foreground)]">données indisponibles</span>
          )}
          {backtest.mode === "walk_forward" && backtest.n_points > 0 && (
            <>
              <span className="text-xs text-[var(--muted-foreground)]">
                CAGR {fmt(backtest.cagr_pct)} % · drawdown {fmt(backtest.max_drawdown_pct)} % · CVaR
                5 % {fmt(backtest.cvar_5_pct)} % · semi-déviation {fmt(backtest.semi_deviation_pct)}{" "}
                % · volatilité {fmt(backtest.volatility_pct)} % · Omega{" "}
                {fmt(backtest.omega ?? undefined, 2)} · turnover{" "}
                {fmt((backtest.turnover ?? 0) * 100)} %
              </span>
              {backtest.comparisons && (
                <span className="basis-full text-xs text-[var(--muted-foreground)]">
                  Comparaison CAGR : optimisé {fmt(backtest.comparisons.optimized?.cagr_pct)} % ·
                  équipondéré {fmt(backtest.comparisons.equal_weight?.cagr_pct)} % · CW8{" "}
                  {fmt(backtest.comparisons["CW8.PA"]?.cagr_pct)} %
                </span>
              )}
              {backtest.comparisons?.free && (
                <span className="basis-full text-xs text-[var(--muted-foreground)]">
                  Scénarios prospectifs — Libre {fmt(backtest.comparisons.free.cagr_pct)} % · World
                  25 {fmt(backtest.comparisons.world_25?.cagr_pct)} % · World 40{" "}
                  {fmt(backtest.comparisons.world_40?.cagr_pct)} % · World 55{" "}
                  {fmt(backtest.comparisons.world_55?.cagr_pct)} % CAGR
                </span>
              )}
            </>
          )}
        </div>
      )}
      {backtest && backtest.n_points > 0 && backtest.equity.length > 1 && (
        <BacktestChart
          equity={backtest.equity}
          dates={backtest.dates}
          label={
            backtest.mode === "walk_forward"
              ? "Équité walk-forward (base 100)"
              : "Équité du portefeuille sur 2 ans (base 100)"
          }
        />
      )}
      {selected.run.resume && (
        <p className="text-sm text-[var(--muted-foreground)]">{selected.run.resume}</p>
      )}
      {selected.buy_signal && (
        <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold">Seuils d&apos;achat sectoriels</h3>
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              Quantile {(selected.buy_signal.percentile * 100).toFixed(0)} % · les deux critères
              doivent être inférieurs ou égaux au seuil de leur secteur · qualité absente : repli
              valeur stricte possible
            </p>
          </div>
          <div className="grid gap-2 text-xs sm:grid-cols-4">
            <div>
              <span className="text-[var(--muted-foreground)]">Retenus</span>
              <br />
              <strong>
                {selected.buy_signal.accepted} / {selected.buy_signal.n_instruments}
              </strong>
            </div>
            <div>
              <span className="text-[var(--muted-foreground)]">Qualité absente</span>
              <br />
              <strong>
                {selected.buy_signal.missing_quality_total ??
                  selected.buy_signal.excluded_missing_peg}
              </strong>
            </div>
            <div>
              <span className="text-[var(--muted-foreground)]">
                Sans qualité : retenus / exclus
              </span>
              <br />
              <strong>
                {selected.buy_signal.missing_quality_accepted ?? 0} /{" "}
                {selected.buy_signal.missing_quality_excluded ??
                  selected.buy_signal.excluded_missing_peg}
              </strong>
            </div>
            <div>
              <span className="text-[var(--muted-foreground)]">Repli global</span>
              <br />
              <strong>
                PER ≤ {fmt(selected.buy_signal.global.per_max ?? undefined)} · PEG ≤{" "}
                {fmt(selected.buy_signal.global.peg_max ?? undefined)}
              </strong>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            {Object.entries(selected.buy_signal.sectors)
              .sort(([left], [right]) => left.localeCompare(right, "fr"))
              .map(([sector, threshold]) => (
                <span
                  key={sector}
                  className="rounded-full border border-[var(--border)] px-2.5 py-1"
                >
                  {/* Le libellé suit la métrique du secteur : afficher « PER »
                      devant un P/FFO donnerait une information fausse. */}
                  {sector} · {threshold.value_metric_label ?? "PER"} ≤{" "}
                  {fmt(threshold.per_max ?? undefined)} · {threshold.quality_metric_label ?? "PEG"}{" "}
                  ≤ {fmt(threshold.peg_max ?? undefined)}
                  {threshold.source === "global" ? " · repli global" : ""}
                  {threshold.profile_fallback === "per_title_standard"
                    ? " · données spécialisées partielles, repli PER/PEG titre par titre"
                    : threshold.profile_fallback
                      ? " · échantillon spécialisé trop petit, repli PER/PEG"
                      : ""}
                </span>
              ))}
          </div>
        </div>
      )}
      {selected.optimization && (
        <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
          <h3 className="text-sm font-semibold mb-2">Comparaison reproductible des stratégies</h3>
          <div className="grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <span className="text-[var(--muted-foreground)]">Portefeuille réel</span>
              <br />
              <strong>{fmt(selected.optimization.benchmarks.optimized, 4)}</strong>
            </div>
            <div>
              <span className="text-[var(--muted-foreground)]">
                Équipondéré ({selected.optimization.benchmarks.equal_weight_max_lines_per_broker}{" "}
                lignes/broker)
              </span>
              <br />
              <strong>{fmt(selected.optimization.benchmarks.equal_weight, 4)}</strong>
            </div>
            <div>
              <span className="text-[var(--muted-foreground)]">
                Meilleur candidat simple (top{" "}
                {selected.optimization.benchmarks.best_single_candidates_tested})
              </span>
              <br />
              <strong>
                {selected.optimization.benchmarks.best_single_ticker ?? "—"} ·{" "}
                {fmt(selected.optimization.benchmarks.best_single, 4)}
              </strong>
            </div>
            <div>
              <span className="text-[var(--muted-foreground)]">Reproductibilité</span>
              <br />
              <strong>
                seed {selected.optimization.seed} · {selected.optimization.termination.seeds_run}{" "}
                seed(s)
              </strong>
            </div>
          </div>
          <p className="mt-2 text-xs text-[var(--muted-foreground)]">
            Score calculé en {selected.optimization.base_currency ?? "EUR"}, après budgets et
            disponibilités broker · la température monte dès la première génération sans
            amélioration, et de plus en plus vite tant que ça dure (
            {selected.optimization.termination.stagnation_streak} génération(s) sans progrès à
            l&apos;arrivée) ; arrêt global uniquement sur demande.
          </p>
          {selected.optimization.benchmark_relative?.validation_objective_score != null && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-1 font-semibold">Validation hors entraînement</h4>
              <p className="text-[var(--muted-foreground)]">
                Objectif recherche{" "}
                <strong className="text-[var(--foreground)]">
                  {fmt(selected.optimization.benchmark_relative.search_objective_score, 4)}
                </strong>
                {" · objectif validation "}
                <strong className="text-[var(--foreground)]">
                  {fmt(selected.optimization.benchmark_relative.validation_objective_score, 4)}
                </strong>
                {" · écart "}
                <strong className="text-[var(--foreground)]">
                  {fmt(selected.optimization.benchmark_relative.validation_gap, 4)}
                </strong>
                {` · ${selected.optimization.benchmark_relative.stability ?? "—"}`}
                {` · ${selected.optimization.benchmark_relative.elite_count ?? 0} élites testées`}
              </p>
              {selected.optimization.benchmark_relative.stability === "instable" && (
                <p className="mt-2 flex items-start gap-2 text-[var(--destructive)]">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  Écart supérieur à 3 points : le portefeuille final ne doit pas être interprété
                  à partir du seul score affiché pendant la recherche.
                </p>
              )}
            </div>
          )}
          {selected.optimization.best_action_candidate && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-1 font-semibold">Comparaison sans contrainte d&apos;actions</h4>
              {selected.optimization.best_action_candidate.found ? (
                <p className="text-[var(--muted-foreground)]">
                  Meilleur candidat contenant une action :{" "}
                  <strong className="text-[var(--foreground)]">
                    {fmt(selected.optimization.best_action_candidate.score, 4)}
                  </strong>
                  {" · écart avec le meilleur libre "}
                  <strong className="text-[var(--foreground)]">
                    {fmt(selected.optimization.best_action_candidate.score_gap_to_unrestricted, 4)}
                  </strong>
                  {" · "}
                  {((selected.optimization.best_action_candidate.action_weight ?? 0) * 100).toFixed(
                    1,
                  )}{" "}
                  % en actions
                  {" · "}
                  {selected.optimization.best_action_candidate.action_count ?? 0} ligne(s)
                  {selected.optimization.best_action_candidate.action_tickers?.length
                    ? ` · ${selected.optimization.best_action_candidate.action_tickers
                        .slice(0, 12)
                        .join(", ")}`
                    : ""}
                </p>
              ) : (
                <p className="text-[var(--muted-foreground)]">
                  Aucun portefeuille admissible contenant une action n&apos;a été découvert.
                </p>
              )}
            </div>
          )}
          {selected.optimization.regimes && (
            <div className="border-t border-[var(--border)] pt-3">
              <h4 className="text-xs font-semibold mb-2">Régimes historiques et stress</h4>
              <div className="flex flex-wrap gap-2">
                {selected.optimization.regimes.windows.map((window) => (
                  <span
                    key={window.label}
                    className="rounded-full bg-[var(--muted)] px-2.5 py-1 text-xs"
                  >
                    {window.label} · {window.observations} j · {(window.weight * 100).toFixed(0)} %
                  </span>
                ))}
              </div>
              {selected.optimization.regimes.search_sample && (
                <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                  Recherche stratifiée sur {selected.optimization.regimes.search_sample.n_sim} scénarios :{" "}
                  {Object.entries(selected.optimization.regimes.search_sample.counts)
                    .map(([label, count]) => `${label} ${count}`)
                    .join(" · ")}
                </p>
              )}
            </div>
          )}
          {selected.optimization.etf_selection?.enabled && (
            <div className="border-t border-[var(--border)] pt-3">
              <h4 className="text-xs font-semibold mb-2">
                Présélection ETF · {selected.optimization.etf_selection.n_etf_before} →{" "}
                {selected.optimization.etf_selection.n_etf_after} dans l&apos;union
              </h4>
              <div className="grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(selected.optimization.etf_selection.brokers).map(
                  ([broker, info]) => (
                    <div key={broker} className="rounded-lg bg-[var(--muted)] px-3 py-2">
                      <strong>{brokerShort(broker)}</strong>
                      <br />
                      <span className="text-[var(--muted-foreground)]">
                        {info.candidates_before} candidats → {info.selected} retenus
                      </span>
                    </div>
                  ),
                )}
              </div>
            </div>
          )}
          {(selected.optimization.estimation || selected.optimization.turnover) && (
            <div className="grid gap-2 border-t border-[var(--border)] pt-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
              {selected.optimization.estimation && (
                <>
                  <div>
                    <span className="text-[var(--muted-foreground)]">Signal rendement propre</span>
                    <br />
                    <strong>
                      {(selected.optimization.estimation.mean_signal_weight * 100).toFixed(0)} %
                    </strong>
                  </div>
                  <div>
                    <span className="text-[var(--muted-foreground)]">Shrinkage corrélations</span>
                    <br />
                    <strong>
                      {(selected.optimization.estimation.correlation_shrinkage * 100).toFixed(0)} %
                    </strong>
                  </div>
                </>
              )}
              {selected.optimization.turnover && (
                <>
                  <div>
                    <span className="text-[var(--muted-foreground)]">Turnover estimé</span>
                    <br />
                    <strong>
                      {(selected.optimization.turnover.estimated_one_way * 100).toFixed(1)} %
                    </strong>
                  </div>
                  <div>
                    <span className="text-[var(--muted-foreground)]">Bande sans intervention</span>
                    <br />
                    <strong>
                      {(selected.optimization.turnover.rebalance_band * 100).toFixed(1)} %
                    </strong>
                  </div>
                </>
              )}
            </div>
          )}
          {selected.optimization.sector_constraints && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Diversification sectorielle</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(
                  selected.optimization.sector_constraints.post_discretization?.exposures ??
                    selected.optimization.sector_constraints.exposures,
                )
                  .sort(([, left], [, right]) => right - left)
                  .map(([sector, exposure]) => (
                    <span
                      key={sector}
                      className="rounded-full border border-[var(--border)] px-2 py-1"
                    >
                      {sector} · {(exposure * 100).toFixed(1)} %
                    </span>
                  ))}
                <span className="rounded-full border border-[var(--border)] px-2 py-1 text-[var(--muted-foreground)]">
                  plafond{" "}
                  {(selected.optimization.sector_constraints.max_sector_pct * 100).toFixed(0)} %
                  {" · "}
                  cash{" "}
                  {(
                    (selected.optimization.sector_constraints.post_discretization?.cash_weight ??
                      selected.optimization.sector_constraints.cash_weight) * 100
                  ).toFixed(1)}{" "}
                  %
                </span>
              </div>
              {selected.optimization.sector_constraints.downside_risk && (
                <div className="mt-2">
                  <p className="mb-1 text-[var(--muted-foreground)]">
                    Contribution au risque baissier · budget souple par défaut{" "}
                    {(
                      selected.optimization.sector_constraints.downside_risk.max_risk_share * 100
                    ).toFixed(0)}{" "}
                    % · technologie 10 %
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(selected.optimization.sector_constraints.downside_risk.sectors)
                      .sort(([, left], [, right]) => right.risk_share - left.risk_share)
                      // Les compartiments à 0 % noyaient la liste sous une
                      // quinzaine d'étiquettes sans information.
                      .filter(([, risk]) => risk.risk_share > 0.0005)
                      .map(([sector, risk]) => (
                        <span
                          key={`risk-${sector}`}
                          className={`rounded-full border px-2 py-1 ${
                            risk.risk_budget_excess > 0
                              ? "border-amber-500/60 text-amber-600 dark:text-amber-400"
                              : "border-[var(--border)]"
                          }`}
                        >
                          {sector} · {(risk.risk_share * 100).toFixed(1)} % du risque
                          {risk.risk_budget != null
                            ? ` · budget ${(risk.risk_budget * 100).toFixed(0)} %`
                            : ""}
                        </span>
                      ))}
                    {(selected.optimization.sector_constraints.country_diversification
                      ?.disabled_sectors_by_risk?.length ?? 0) > 0 && (
                      <span className="rounded-full border border-amber-500/60 px-2 py-1 text-amber-600 dark:text-amber-400">
                        bonus géographique suspendu uniquement pour{" "}
                        {selected.optimization.sector_constraints.country_diversification?.disabled_sectors_by_risk?.join(
                          ", ",
                        )}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          {selected.optimization.score_breakdown &&
            Object.keys(selected.optimization.score_breakdown.terms).length > 0 && (
              <div className="border-t border-[var(--border)] pt-3 text-xs">
                <h4 className="mb-2 font-semibold">Ce qui pèse sur le score</h4>
                <p className="mb-2 text-[var(--muted-foreground)]">
                  Pénalités du portefeuille retenu, en points d&apos;objectif · total{" "}
                  {selected.optimization.score_breakdown.total_penalty.toFixed(2)}
                  {" · dominant : "}
                  {selected.optimization.score_breakdown.dominant_term.replace(/_/g, " ")}
                </p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(selected.optimization.score_breakdown.terms)
                    .filter(([, points]) => Math.abs(points) > 0.005)
                    .sort(([, left], [, right]) => Math.abs(right) - Math.abs(left))
                    .map(([term, points]) => (
                      <span
                        key={`score-${term}`}
                        className={`rounded-full border px-2 py-1 ${
                          points > 0
                            ? "border-[var(--border)]"
                            : "border-emerald-500/60 text-emerald-600 dark:text-emerald-400"
                        }`}
                      >
                        {term.replace(/_/g, " ")} · {points > 0 ? "−" : "+"}
                        {Math.abs(points).toFixed(2)} pt
                      </span>
                    ))}
                  {Object.entries(selected.optimization.score_breakdown.terms).every(
                    ([, points]) => Math.abs(points) <= 0.005,
                  ) && (
                    <span className="rounded-full border border-[var(--border)] px-2 py-1 text-[var(--muted-foreground)]">
                      aucune contrainte pénalisante
                    </span>
                  )}
                </div>
              </div>
            )}
          {selected.optimization.country_constraints && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Diversification géographique</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(selected.optimization.country_constraints.exposures)
                  .sort(([, left], [, right]) => right - left)
                  .filter(([, exposure]) => exposure > 0.0005)
                  .map(([country, exposure]) => (
                    <span
                      key={country}
                      className="rounded-full border border-[var(--border)] px-2 py-1"
                    >
                      {country} · {(exposure * 100).toFixed(1)} %
                    </span>
                  ))}
                {selected.optimization.country_constraints.hard_cap_enabled &&
                selected.optimization.country_constraints.max_country_pct != null ? (
                  <span className="rounded-full border border-[var(--border)] px-2 py-1 text-[var(--muted-foreground)]">
                    plafond{" "}
                    {(selected.optimization.country_constraints.max_country_pct * 100).toFixed(0)} %
                  </span>
                ) : (
                  <span className="rounded-full border border-[var(--border)] px-2 py-1 text-[var(--muted-foreground)]">
                    aucun plafond dur · risque pénalisé
                  </span>
                )}
              </div>
              {selected.optimization.country_constraints.downside_risk && (
                <div className="mt-2">
                  <p className="mb-1 text-[var(--muted-foreground)]">
                    Contribution au risque baissier · seuil{" "}
                    {(
                      selected.optimization.country_constraints.downside_risk.max_risk_share * 100
                    ).toFixed(0)}{" "}
                    %
                    {/* Coefficient nul : on contraint sur le poids (fait
                        vérifiable) et on se contente de MESURER le risque
                        (estimé, pro-cyclique). Le dire évite de croire à une
                        contrainte qui ne s'applique pas. */}
                    {selected.optimization.country_constraints.downside_risk.penalty_coefficient ===
                    0
                      ? " · indicateur, sans effet sur l’allocation"
                      : " · budget souple"}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(
                      selected.optimization.country_constraints.downside_risk.countries,
                    )
                      .sort(([, left], [, right]) => right.risk_share - left.risk_share)
                      // Un pays à 0 % de risque n'apprend rien et noie la liste.
                      .filter(([, risk]) => risk.risk_share > 0.0005)
                      .map(([country, risk]) => (
                        <span
                          key={`country-risk-${country}`}
                          className={`rounded-full border px-2 py-1 ${
                            risk.risk_budget_excess > 0
                              ? "border-amber-500/60 text-amber-600 dark:text-amber-400"
                              : "border-[var(--border)]"
                          }`}
                        >
                          {country} · {(risk.risk_share * 100).toFixed(1)} % du risque
                        </span>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {selected.optimization.region_constraints && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Diversification régionale</h4>
              {selected.optimization.region_constraints.hard_cap_enabled &&
                selected.optimization.region_constraints.max_region_pct != null && (
                  <p className="mb-2 text-[var(--muted-foreground)]">
                    Plafond dur d&apos;exposition{" "}
                    {(selected.optimization.region_constraints.max_region_pct * 100).toFixed(0)} %
                    par région
                  </p>
                )}
              <div className="flex flex-wrap gap-2">
                {Object.entries(selected.optimization.region_constraints.downside_risk.regions)
                  .sort(([, left], [, right]) => right.risk_share - left.risk_share)
                  .filter(([, risk]) => risk.weight > 0.0005)
                  .map(([region, risk]) => (
                    <span
                      key={region}
                      className={`rounded-full border px-2 py-1 ${risk.risk_budget_excess > 0 ? "border-amber-500/60 text-amber-600 dark:text-amber-400" : "border-[var(--border)]"}`}
                    >
                      {region} · {(risk.weight * 100).toFixed(1)} % ·{" "}
                      {(risk.risk_share * 100).toFixed(1)} % du risque
                    </span>
                  ))}
                <span className="rounded-full border border-[var(--border)] px-2 py-1 text-[var(--muted-foreground)]">
                  budget souple{" "}
                  {(
                    selected.optimization.region_constraints.downside_risk.max_risk_share * 100
                  ).toFixed(0)}{" "}
                  % du risque
                </span>
              </div>
            </div>
          )}
          {selected.optimization.economic_action_concentration && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Concentration par action économique</h4>
              <p className="text-[var(--muted-foreground)]">
                Couverture{" "}
                {(
                  selected.optimization.economic_action_concentration.coverage_weight * 100
                ).toFixed(1)}{" "}
                % · HHI {selected.optimization.economic_action_concentration.hhi.toFixed(4)} ·{" "}
                {selected.optimization.economic_action_concentration.effective_actions.toFixed(1)}{" "}
                actions effectives · information descriptive
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(selected.optimization.economic_action_concentration.actions)
                  .slice(0, 10)
                  .map(([ticker, weight]) => (
                    <span
                      key={ticker}
                      className={`rounded-full border px-2 py-1 ${weight > selected.optimization!.economic_action_concentration!.threshold ? "border-amber-500/60 text-amber-600 dark:text-amber-400" : "border-[var(--border)]"}`}
                    >
                      {ticker} · {(weight * 100).toFixed(2)} %
                    </span>
                  ))}
              </div>
            </div>
          )}
          {selected.optimization.direct_action_policy?.enabled && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-1 font-semibold">Exploration des actions directes V3</h4>
              <p className="text-[var(--muted-foreground)]">
                {selected.optimization.direct_action_policy.eligible_action_candidates} actions conservées dans l’univers
                {" · portefeuille libre retenu : "}{selected.optimization.direct_action_policy.actual_lines} actions / {fmt(selected.optimization.direct_action_policy.actual_weight * 100)} % du capital
                {" · aucune poche minimale imposée"}
                {" · bonus qualité "}{fmt(selected.optimization.direct_action_policy.quality_bonus_points, 3)} pt
              </p>
            </div>
          )}
          {selected.optimization.classification_filter?.score_calibration && (
            <details className="border-t border-[var(--border)] pt-3 text-xs">
              <summary className="cursor-pointer font-semibold">Calibration statistique Quality V3</summary>
              {(() => {
                const calibration = selected.optimization.classification_filter.score_calibration;
                const rows = [["Tout l’univers", calibration.global] as const, ...Object.entries(calibration.by_business_model)];
                return (
                  <div className="mt-2 overflow-x-auto">
                    <table className="min-w-full text-right">
                      <thead><tr><th className="pr-3 text-left">Modèle</th><th className="pr-3">N</th><th className="pr-3">P50</th><th className="pr-3">P90</th><th className="pr-3">≥85</th><th>≥90</th></tr></thead>
                      <tbody>{rows.map(([name, values]) => (
                        <tr key={name} className="border-t border-[var(--border)]">
                          <td className="py-1 pr-3 text-left">{name}</td><td className="pr-3">{values.count}</td>
                          <td className="pr-3">{values.percentiles?.p50 == null ? "—" : fmt(values.percentiles.p50)}</td>
                          <td className="pr-3">{values.percentiles?.p90 == null ? "—" : fmt(values.percentiles.p90)}</td>
                          <td className="pr-3">{values.thresholds_pct?.gte_85 == null ? "—" : `${fmt(values.thresholds_pct.gte_85)} %`}</td>
                          <td>{values.thresholds_pct?.gte_90 == null ? "—" : `${fmt(values.thresholds_pct.gte_90)} %`}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                );
              })()}
            </details>
          )}
          {selected.optimization.economic_composition_filter && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Contrôle des compositions ETF</h4>
              <p className="text-[var(--muted-foreground)]">
                Source économique officielle requise · couverture minimale{" "}
                {(
                  selected.optimization.economic_composition_filter.quality_reference_coverage * 100
                ).toFixed(0)}{" "}
                % · ETF exclus/remplacés{" "}
                {selected.optimization.economic_composition_filter.excluded_for_economic_coverage}
              </p>
              {selected.optimization.economic_composition_filter.broker_verification && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(
                    selected.optimization.economic_composition_filter.broker_verification,
                  ).map(([broker, verification]) => (
                    <span
                      key={`broker-composition-${broker}`}
                      className={`rounded-full border px-2 py-1 ${
                        verification.shortage > 0
                          ? "border-amber-500/60 text-amber-600 dark:text-amber-400"
                          : "border-[var(--border)]"
                      }`}
                    >
                      {broker} · {verification.verified}/{verification.target} validés
                      {verification.shortage > 0
                        ? ` · pénurie ${verification.shortage} (catalogue admissible épuisé)`
                        : ""}
                    </span>
                  ))}
                </div>
              )}
              {selected.optimization.economic_composition_filter.replacement_search?.truncated && (
                <details className="mt-2 rounded-lg border border-amber-500/50 p-2">
                  <summary className="cursor-pointer font-medium text-amber-600 dark:text-amber-400">
                    Recherche bornée après{" "}
                    {selected.optimization.economic_composition_filter.replacement_search.rounds}{" "}
                    tours ·{" "}
                    {
                      selected.optimization.economic_composition_filter.replacement_search
                        .unverified_count
                    }{" "}
                    ETF non vérifiés exclus
                  </summary>
                  <p className="mt-2 break-words text-[var(--muted-foreground)]">
                    {selected.optimization.economic_composition_filter.replacement_search.unverified_tickers.join(
                      ", ",
                    )}
                  </p>
                </details>
              )}
              {selected.optimization.economic_composition_filter.index_resolution && (
                <div className="mt-2 rounded-lg border border-[var(--border)] p-2">
                  <p>
                    ETF contrôlés{" "}
                    <strong>
                      {
                        selected.optimization.economic_composition_filter.index_resolution
                          .checked_etfs
                      }
                    </strong>
                    {" · "}compositions officielles exploitables{" "}
                    <strong>
                      {
                        selected.optimization.economic_composition_filter.index_resolution
                          .official_compositions
                      }
                    </strong>
                    {" · "}proxies de trackers physiques{" "}
                    <strong>
                      {selected.optimization.economic_composition_filter.index_resolution
                        .physical_tracker_proxies ?? 0}
                    </strong>
                    {" · "}ETF non validés (exclus){" "}
                    <strong>
                      {
                        selected.optimization.economic_composition_filter.index_resolution
                          .unresolved_count
                      }
                    </strong>
                  </p>
                  {Object.keys(
                    selected.optimization.economic_composition_filter.index_resolution
                      .unresolved_reason_counts ?? {},
                  ).length > 0 && (
                    <>
                      <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                        Motifs d’exclusion des{" "}
                        {
                          selected.optimization.economic_composition_filter.index_resolution
                            .unresolved_count
                        }{" "}
                        ETF non validés :
                      </p>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {Object.entries(
                          selected.optimization.economic_composition_filter.index_resolution
                            .unresolved_reason_counts ?? {},
                        )
                          .sort(([, left], [, right]) => right - left)
                          .map(([reason, count]) => (
                            <span
                              key={`index-reason-${reason}`}
                              className="rounded-full border border-[var(--destructive)]/40 px-2 py-1"
                            >
                              {reason} · {count}
                            </span>
                          ))}
                      </div>
                    </>
                  )}
                  <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                    Statuts d’indice (sur les{" "}
                    {
                      selected.optimization.economic_composition_filter.index_resolution
                        .checked_etfs
                    }{" "}
                    ETF contrôlés, éligibles inclus) :
                  </p>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {Object.entries(
                      selected.optimization.economic_composition_filter.index_resolution
                        .status_counts,
                    )
                      .sort(([, left], [, right]) => right - left)
                      .map(([status, count]) => (
                        <span
                          key={`index-status-${status}`}
                          className="rounded-full border border-amber-500/50 px-2 py-1"
                        >
                          {status} · {count}
                        </span>
                      ))}
                  </div>
                  {selected.optimization.economic_composition_filter.index_resolution.unresolved
                    .length > 0 && (
                    <details className="mt-2">
                      <summary className="cursor-pointer font-medium">
                        Afficher les indices/ETF non validés
                      </summary>
                      <div className="mt-2 max-h-80 space-y-1 overflow-auto">
                        {selected.optimization.economic_composition_filter.index_resolution.unresolved.map(
                          (item) => (
                            <div
                              key={`unresolved-index-${item.ticker}`}
                              className="rounded border border-[var(--border)] px-2 py-1"
                            >
                              <strong>{item.ticker}</strong>
                              {` · ${item.replication} · ${item.index || "indice non identifié"}`}
                              {` · ${item.provider} · ${item.status || item.reason}`}
                              {item.error ? ` · ${item.error}` : ""}
                              {item.pipeline_errors.map((error) => (
                                <span
                                  key={`${item.ticker}-${error.stage}`}
                                  className="text-[var(--destructive)]"
                                >
                                  {` · ${error.stage}: ${error.message}`}
                                </span>
                              ))}
                              {item.source_url && (
                                <>
                                  {" · "}
                                  <a
                                    href={item.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="underline"
                                  >
                                    source officielle
                                  </a>
                                </>
                              )}
                            </div>
                          ),
                        )}
                      </div>
                    </details>
                  )}
                </div>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(selected.optimization.economic_composition_filter.quality_by_ticker)
                  .sort(([, left], [, right]) => Number(left.eligible) - Number(right.eligible))
                  .slice(0, 20)
                  .map(([ticker, quality]) => (
                    <span
                      key={`composition-${ticker}`}
                      className={`rounded-full border px-2 py-1 ${
                        quality.eligible
                          ? "border-[var(--border)]"
                          : "border-amber-500/60 text-amber-600 dark:text-amber-400"
                      }`}
                    >
                      {ticker} · {quality.provider || quality.source || "source inconnue"}
                      {` · ${(quality.coverage * 100).toFixed(0)} %`}
                      {!quality.eligible ? ` · ${quality.index_status || quality.reason}` : ""}
                      {!quality.eligible && quality.index_error ? ` · ${quality.index_error}` : ""}
                    </span>
                  ))}
              </div>
            </div>
          )}
          {selected.optimization.classification_filter?.replication_enrichment && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Identification des réplications ETF</h4>
              {selected.optimization.classification_filter.replication_enrichment.error ? (
                <p className="text-[var(--destructive)]">
                  Enrichissement incomplet&nbsp;:{" "}
                  {selected.optimization.classification_filter.replication_enrichment.error}
                </p>
              ) : (
                <>
                  <p className="text-[var(--muted-foreground)]">
                    Catalogue{" "}
                    {selected.optimization.classification_filter.replication_enrichment.total} ETF ·
                    connus avant cette optimisation{" "}
                    {
                      selected.optimization.classification_filter.replication_enrichment
                        .known_before
                    }{" "}
                    · résolus maintenant{" "}
                    {
                      selected.optimization.classification_filter.replication_enrichment
                        .resolved_now
                    }{" "}
                    · encore inconnus{" "}
                    {
                      selected.optimization.classification_filter.replication_enrichment
                        .unknown_after
                    }
                  </p>
                  {selected.optimization.classification_filter.replication_enrichment
                    .broker_priority && (
                    <p className="mt-1 text-[var(--muted-foreground)]">
                      Priorité brokers actifs · inconnus achetables{" "}
                      {
                        selected.optimization.classification_filter.replication_enrichment
                          .broker_priority.available_unknown
                      }{" "}
                      · résolus maintenant{" "}
                      {
                        selected.optimization.classification_filter.replication_enrichment
                          .broker_priority.available_resolved_now
                      }
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(
                      selected.optimization.classification_filter.replication_enrichment.statuses,
                    )
                      .sort(([, left], [, right]) => right - left)
                      .map(([status, count]) => (
                        <span
                          key={status}
                          className="rounded-full border border-[var(--border)] px-2 py-1 text-[var(--muted-foreground)]"
                        >
                          {status} · {count}
                        </span>
                      ))}
                  </div>
                </>
              )}
            </div>
          )}
          {selected.optimization.unknown_equity_composition && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Composition actions inconnue</h4>
              <p className="text-[var(--muted-foreground)]">
                {(selected.optimization.unknown_equity_composition.actual_weight * 100).toFixed(2)}{" "}
                % du portefeuille · information descriptive, sans effet sur l&apos;optimisation
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(selected.optimization.unknown_equity_composition.by_ticker)
                  .sort(
                    ([, left], [, right]) => right.unknown_contribution - left.unknown_contribution,
                  )
                  .slice(0, 10)
                  .map(([ticker, values]) => (
                    <span
                      key={ticker}
                      className="rounded-full border border-[var(--border)] px-2 py-1"
                    >
                      {ticker} · {(values.unknown_contribution * 100).toFixed(2)} % Autres
                      {` (${(values.unknown_fraction * 100).toFixed(0)} % non documenté)`}
                    </span>
                  ))}
              </div>
            </div>
          )}
          {selected.optimization.transaction_costs?.enabled && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="mb-2 font-semibold">Frais intégrés à l’optimisation</h4>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <span className="text-[var(--muted-foreground)]">Prochain rebalancement</span>
                  <br />
                  <strong>
                    {(
                      selected.optimization.transaction_costs.next_rebalance_cost_eur ??
                      selected.optimization.transaction_costs.trade_cost_eur
                    ).toFixed(2)}{" "}
                    €
                  </strong>
                </div>
                <div>
                  <span className="text-[var(--muted-foreground)]">Coût première année</span>
                  <br />
                  <strong>
                    {(
                      selected.optimization.transaction_costs.first_year_cost_eur ??
                      selected.optimization.transaction_costs.annualized_cost_eur
                    ).toFixed(2)}{" "}
                    €
                  </strong>
                </div>
                <div>
                  <span className="text-[var(--muted-foreground)]">Impact première année</span>
                  <br />
                  <strong>
                    {(
                      (selected.optimization.transaction_costs.first_year_cost_pct ??
                        selected.optimization.transaction_costs.annualized_cost_pct) * 100
                    ).toFixed(2)}{" "}
                    %
                  </strong>
                </div>
                <div>
                  <span className="text-[var(--muted-foreground)]">Garde étrangère annuelle</span>
                  <br />
                  <strong>
                    {selected.optimization.transaction_costs.annual_custody_eur.toFixed(2)} €
                  </strong>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-[var(--muted-foreground)]">
                {selected.optimization.transaction_costs.brokers.map((info) => (
                  <span
                    key={info.broker}
                    className="rounded-full border border-[var(--border)] px-2 py-1"
                  >
                    {brokerShort(info.broker)} · ordre {info.trade_cost_eur.toFixed(2)} €
                    {info.annual_custody_eur > 0
                      ? ` · garde ${info.annual_custody_eur.toFixed(2)} €`
                      : ""}
                  </span>
                ))}
              </div>
            </div>
          )}
      {selected.optimization.regimes?.correlation_stability?.available && (
            <div className="border-t border-[var(--border)] pt-3 text-xs">
              <h4 className="font-semibold mb-1">Stabilité des corrélations</h4>
              <p className="text-[var(--muted-foreground)]">
                {selected.optimization.regimes.correlation_stability.unstable_pairs ?? 0} paires
                instables ·{" "}
                {selected.optimization.regimes.correlation_stability.major_shift_pairs ?? 0}{" "}
                changements majeurs
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(selected.optimization.regimes.correlation_stability.top_pairs ?? [])
                  .slice(0, 5)
                  .map((pair) => (
                    <span
                      key={`${pair.ticker_a}-${pair.ticker_b}`}
                      className="rounded-full border border-[var(--border)] px-2 py-1"
                    >
                      {pair.ticker_a}/{pair.ticker_b} · Δ {pair.max_delta.toFixed(2)}
                    </span>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}
      <BuffettAllocationSection
        allocated={allocated}
        displayRows={displayRows}
        hasAlloc={hasAlloc}
        totalInvested={totalInvested}
        totalPct={totalPct}
        runStatus={selected.run.statut}
        showLookthrough={showLookthrough}
        loadingLookthrough={loadingLookthrough}
        lookthroughError={lookthroughError}
        lookthrough={lookthrough}
        onSelectAllocationView={selectAllocationView}
      />
    </div>
  );
}
