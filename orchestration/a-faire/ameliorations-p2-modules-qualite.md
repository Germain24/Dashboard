# Mission Control — Améliorations P2 : enrichir les modules, qualité & DX (à faire)

> Extrait de `orchestration/en-cours/improvements.md` le 2026-07-04 : §5
> (enrichir les modules « automatisation de vie ») et §6 (qualité & DX) n'ont
> pas encore commencé — seule une puce de §5.4 (garde-robe) est déjà livrée
> (notée ci-dessous). Déplacés ici (P2, pas encore attaqué) pour ne pas les
> mélanger avec §1/§2/§4 (livrés, dans `orchestration/finis/`) et §3 (encore
> mixte, resté dans `orchestration/en-cours/improvements.md`).
>
> Contraintes non négociables (héritées du contexte d'origine) : pas d'IA
> conversationnelle ni d'aides vocales dans le dashboard ; l'arborescence est
> synchronisée avec graphify (l'utilisateur gère la sync) ; les données réelles
> (Desjardins, nutrition, Buffett, garde-robe) restent la source de vérité —
> les mock data ne servent qu'aux intégrations pas encore branchées.

Légende : [S] petit · [M] moyen · [L] gros — (\*) confort · (\*\*) valeur réelle · (\*\*\*) structurant

---

## 5. Modules « automatisation de vie » — enrichir l'existant (P2)

> Tous les modules demandés existent déjà avec de vraies données. Les mock data ne
> sont introduites **que** pour les intégrations non branchées, sous forme de
> fixtures de test + adaptateurs prêts à recevoir le vrai flux.

### 5.1 Dashboard quantitatif & Finance
- [M](\*\*\*) Métriques quantitatives calculées sur le ledger réel : Sharpe, Sortino,
  volatilité annualisée, max drawdown, exposition par secteur (le TWR et le HHI
  existent déjà dans `services/finance/`).
- [M](\*\*) Adaptateur d'ingestion **OpenBB** : interface `MarketDataProvider` avec
  implémentation yfinance actuelle + implémentation OpenBB derrière un flag ;
  fixtures mock pour les tests uniquement.
- [S](\*) Volumes quotidiens et mini-sparklines sur les positions du portefeuille.

### 5.2 Performance & Physiologie
- [S](\*\*) Le tracker macros dérive déjà ses cibles de l'optimiseur nutrition
  (profil réel ~57 kg) — vérifier que la liste d'épicerie consomme bien
  `calculate_daily_targets` (dette connue : cibles encore codées en dur).
- [M](\*\*) Ingestion d'exports **Strava/GPX/TCX** : parseur + table `SeanceImportee`,
  fixtures d'exemple calibrées (57 kg) pour les tests ; l'UI entraînement existante
  affiche les séances importées à côté du mésocycle.
- [S](\*) Corrélations simples score/sommeil/nutrition sur la page `/score` existante.

### 5.3 Knowledge & Library
- [M](\*\*) Enrichir `livres/` : statuts (en cours/terminé/pile à lire), progression,
  notes de lecture ; support séries/mangas (tomes) à côté des essais.
- [S](\*) Si la base est vide au premier lancement : seed d'exemple optionnel
  (Housel, Lynch, une série manga) clairement marqué « exemple », jamais mélangé
  aux vraies entrées.

### 5.4 Logistique & Planification
- [S](\*\*) Voyage : la carte Leaflet vient d'être livrée — checklist par voyage et
  budget par étape comme prochains incréments.
- [M](\*\*) Garde-robe : conseils d'achat combinatoires + enrichissement BonneGueule
  livrés (plans dans `orchestration/finis/`). ← FINIS ✓ (2026-07-01)
  Module garde-robe complet, plus rien en attente.
- [S](\*) Objectifs long-terme : jalons datés + lien vers les modules concernés
  (un objectif « épargne X $ » pointe vers patrimoine).

## 6. Qualité & DX (P2)

6.1 [S](\*\*) CI : passer le lint d'advisory à bloquant, règle par règle (la dette est
    déjà suivie séparément).
6.2 [S](\*\*) Étendre les snapshots visuels Playwright aux états animés stabilisés
    (attendre la fin des transitions avant capture).
6.3 [S](\*) `gen:types` vérifié en CI (diff vide entre OpenAPI et `lib/types.ts`).
6.4 [S](\*) Un `docs/CONTRIBUTING.md` court : conventions commits, TDD, workflow
    AMELIORATIONS, sync graphify.
